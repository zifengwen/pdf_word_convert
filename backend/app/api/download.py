"""下载 API - GET /api/download/{token}"""

import os

from fastapi import APIRouter
from fastapi.responses import FileResponse

from ..services.file_manager import file_manager

router = APIRouter(tags=["download"])


@router.get("/download/{token}")
async def download_file(token: str):
    """
    下载转换后的文件。

    - **token**: 转换完成后返回的下载 token
    """
    # --- 1. 查找转换结果 ---
    info = file_manager.get_info(token)
    if info is None:
        return {"code": 4041, "message": "下载链接已过期或不存在，请重新上传转换", "data": None}

    converted_path = info.get("converted_path")
    if not converted_path or not os.path.exists(converted_path):
        return {"code": 4041, "message": "文件已被清理，请重新上传转换", "data": None}

    # --- 2. 确定原始文件名和输出格式 ---
    original_name = info.get("original_name", "document")
    direction = info.get("direction", "word-to-pdf")

    # 构建下载文件名
    base_name, _ = os.path.splitext(original_name)
    if direction == "word-to-pdf":
        download_name = f"{base_name}.pdf"
        media_type = "application/pdf"
    else:
        download_name = f"{base_name}.docx"
        media_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    # --- 3. 返回文件（FastAPI 自动处理 Content-Disposition 和中文文件名编码）---
    return FileResponse(
        path=converted_path,
        media_type=media_type,
        filename=download_name,
    )
