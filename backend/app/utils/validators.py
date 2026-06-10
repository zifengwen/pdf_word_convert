"""文件验证工具 - 扩展名校验、魔数校验、文件大小校验"""

import os
from ..config import settings

# ---------- 文件魔数（Magic Bytes）----------
# PDF：以 %PDF- 开头（规范要求在文件前 1024 字节内）
PDF_MAGIC = b"%PDF-"
# DOCX / OOXML：ZIP 格式，以 PK\x03\x04 开头
DOCX_MAGIC = b"PK\x03\x04"
# DOC（旧格式）：OLE2 Compound Document
DOC_MAGIC = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"


def validate_file_extension(filename: str, direction: str) -> tuple:
    """
    验证文件扩展名是否合法。
    返回 (is_valid, error_code, error_message)
    """
    if not filename:
        return False, 4002, "未提供文件"

    _, ext = os.path.splitext(filename)
    ext = ext.lower()

    if direction == "word-to-pdf":
        if ext not in settings.ALLOWED_WORD_EXTENSIONS:
            return (
                False,
                4001,
                f"不支持的文件格式: {ext}。请上传 Word 文档（{', '.join(settings.ALLOWED_WORD_EXTENSIONS)}）",
            )
    elif direction == "pdf-to-word":
        if ext not in settings.ALLOWED_PDF_EXTENSIONS:
            return (
                False,
                4001,
                f"不支持的文件格式: {ext}。请上传 PDF 文件（{', '.join(settings.ALLOWED_PDF_EXTENSIONS)}）",
            )
    else:
        return False, 4001, f"不支持的转换方向: {direction}"

    return True, 0, "ok"


def validate_file_magic(file_data: bytes, direction: str) -> tuple:
    """
    通过文件头魔数（Magic Bytes）校验文件真实类型，防止伪造扩展名。
    返回 (is_valid, error_code, error_message)
    """
    if not file_data or len(file_data) < 4:
        return False, 4001, "文件内容为空或损坏"

    if direction == "word-to-pdf":
        # DOCX: PK\x03\x04（ZIP 格式头）
        # DOC:  \xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1（OLE2 复合文档格式头）
        is_docx = file_data[:4] == DOCX_MAGIC
        is_doc = len(file_data) >= 8 and file_data[:8] == DOC_MAGIC
        if not is_docx and not is_doc:
            return (
                False,
                4001,
                "文件内容不是有效的 Word 文档（DOCX/DOC），请检查文件是否损坏",
            )
    elif direction == "pdf-to-word":
        # PDF 格式头必须在文件前 1024 字节内出现
        search_area = file_data[:1024]
        if PDF_MAGIC not in search_area:
            return (
                False,
                4001,
                "文件内容不是有效的 PDF 文档，请检查文件是否损坏",
            )
    else:
        return False, 4001, f"不支持的转换方向: {direction}"

    return True, 0, "ok"


def validate_file_size(file_size: int) -> tuple:
    """
    验证文件大小是否在限制内。
    返回 (is_valid, error_code, error_message)
    """
    if file_size is None or file_size == 0:
        return False, 4002, "文件为空"

    if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
        max_mb = settings.MAX_UPLOAD_SIZE_MB
        actual_mb = round(file_size / (1024 * 1024), 1)
        return (
            False,
            4003,
            f"文件过大: {actual_mb}MB，最大允许 {max_mb}MB",
        )

    return True, 0, "ok"


def get_file_size_display(size_bytes: int) -> str:
    """将字节数转换为可读的文件大小字符串"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
