"""
DOCX 后处理：
1. 含文字的形状 wp:extent cx +30000 EMU（防字符裁切）
2. 含文字的形状移除填充色（防背景遮挡文字）
"""

import os, shutil, tempfile, zipfile
from xml.etree import ElementTree as ET

DELTA = 40000


def fix_docx(docx_path: str) -> str:
    namespaces = [
        ("w",   "http://schemas.openxmlformats.org/wordprocessingml/2006/main"),
        ("wp",  "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"),
        ("a",   "http://schemas.openxmlformats.org/drawingml/2006/main"),
        ("v",   "urn:schemas-microsoft-com:vml"),
        ("mc",  "http://schemas.openxmlformats.org/markup-compatibility/2006"),
        ("o",   "urn:schemas-microsoft-com:office:office"),
        ("r",   "http://schemas.openxmlformats.org/officeDocument/2006/relationships"),
        ("w10", "urn:schemas-microsoft-com:office:word"),
        ("wps", "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"),
        ("wpg", "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup"),
        ("pic", "http://schemas.openxmlformats.org/drawingml/2006/picture"),
        ("wp14","http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"),
        ("w14", "http://schemas.microsoft.com/office/word/2010/wordml"),
        ("w15", "http://schemas.microsoft.com/office/word/2012/wordml"),
    ]
    for p, u in namespaces:
        ET.register_namespace(p, u)

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".docx")
    os.close(tmp_fd)

    try:
        with zipfile.ZipFile(docx_path, "r") as zin:
            with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    data = zin.read(item.filename)
                    if item.filename == "word/document.xml":
                        data = _process(data)
                    zout.writestr(item, data)
        shutil.move(tmp_path, docx_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
    return docx_path


def _process(data: bytes) -> bytes:
    root = ET.fromstring(data)

    WP_ANCHOR = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}anchor"
    WP_EXTENT = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}extent"
    W_T       = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
    WPS_SPPR  = "{http://schemas.microsoft.com/office/word/2010/wordprocessingShape}spPr"
    A_SOLID   = "{http://schemas.openxmlformats.org/drawingml/2006/main}solidFill"
    A_NOFILL  = "{http://schemas.openxmlformats.org/drawingml/2006/main}noFill"
    V_SHAPE   = "{urn:schemas-microsoft-com:vml}shape"

    fill_tags = {
        "{http://schemas.openxmlformats.org/drawingml/2006/main}solidFill",
        "{http://schemas.openxmlformats.org/drawingml/2006/main}gradFill",
        "{http://schemas.openxmlformats.org/drawingml/2006/main}pattFill",
    }

    for anchor in root.iter(WP_ANCHOR):
        # 判断是否含文字
        has_text = False
        for t in anchor.iter(W_T):
            if t.text and t.text.strip():
                has_text = True
                break

        if has_text:
            # --- 1. wp:extent cx 加宽、cy 加高 ---
            ext = anchor.find(WP_EXTENT)
            if ext is not None:
                cx = ext.get("cx", "")
                cy = ext.get("cy", "")
                if cx:
                    try:
                        ext.set("cx", str(int(cx) + DELTA))
                    except ValueError:
                        pass
                if cy:
                    try:
                        ext.set("cy", str(int(int(cy) * 1.10)))
                    except ValueError:
                        pass

            # --- 2. behindDoc 改为 0（文字在文档层上方）---
            if anchor.get("behindDoc") == "1":
                anchor.set("behindDoc", "0")

            # --- 3. 移除 VML 填充色 ---
            for shape in anchor.iter(V_SHAPE):
                if shape.get("fillcolor"):
                    del shape.attrib["fillcolor"]

            # --- 4. DML solidFill → noFill ---
            for spPr in anchor.iter(WPS_SPPR):
                has_fill = False
                for child in list(spPr):
                    if child.tag in fill_tags:
                        spPr.remove(child)
                        has_fill = True
                if has_fill:
                    existing = spPr.find(A_NOFILL)
                    if existing is None:
                        spPr.append(ET.Element(A_NOFILL))
        else:
            # --- 背景板：z-order 置底 ---
            anchor.set("relativeHeight", "0")
            anchor.set("behindDoc", "1")

    # --- 5. 删除所有 mc:Fallback 元素（VML 备选路径）---
    MC_ALTERNATE = "{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent"
    MC_FALLBACK  = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"
    for ac in root.iter(MC_ALTERNATE):
        for fb in ac.findall(MC_FALLBACK):
            ac.remove(fb)

    # --- 6. 全局：移除所有 VML fill 和 stroke 子元素 ---
    V_FILL   = "{urn:schemas-microsoft-com:vml}fill"
    V_STROKE = "{urn:schemas-microsoft-com:vml}stroke"
    for parent in list(root.iter()):
        for child in list(parent):
            if child.tag in (V_FILL, V_STROKE):
                parent.remove(child)

    # --- 7. w:pict 中的背景 v:shape → style 加 z-index:-1 置于底层 ---
    W_PICT = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pict"
    for pict in root.iter(W_PICT):
        for shape in pict.iter(V_SHAPE):
            fc = shape.get("fillcolor", "")
            if not fc:
                continue
            has_text = False
            for t in shape.iter(W_T):
                if t.text and t.text.strip():
                    has_text = True
                    break
            if has_text:
                continue
            style = shape.get("style", "")
            if "z-index" not in style:
                shape.set("style", style + ";z-index:-1")

    return (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        + ET.tostring(root, encoding="UTF-8")
    )
