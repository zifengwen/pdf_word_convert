"""转换 API - POST /api/convert/{direction}"""

import logging
from fastapi import APIRouter, File, Request, UploadFile

from ..config import settings
from ..models.schemas import ConvertData
from ..services.converter import (
    ConversionError,
    ConversionTimeoutError,
    EncryptedPDFError,
    LibreOfficeNotFoundError,
    converter,
)
from ..services.file_manager import file_manager
from ..utils.validators import (
    validate_file_extension,
    validate_file_magic,
    validate_file_size,
)

logger = logging.getLogger("pdf2word")
router = APIRouter(tags=["convert"])

# 读取文件头用于魔数校验的字节数
_MAGIC_READ_SIZE = 8192


@router.post("/convert/{direction}")
async def convert_file(
    request: Request,
    direction: str,
    file: UploadFile = File(None),
):
    """
    上传文件并转换格式。

    - **direction**: `word-to-pdf` 将 Word 转为 PDF；`pdf-to-word` 将 PDF 转为 Word
    - **file**: 上传的文件（multipart/form-data, field name: "file"）
    """
    # --- 1. 校验转换方向 ---
    if direction not in ("word-to-pdf", "pdf-to-word"):
        return {
            "code": 4001,
            "message": f"不支持的转换方向: {direction}。支持: word-to-pdf, pdf-to-word",
            "data": None,
        }

    # --- 2. 校验文件存在 ---
    if file is None or file.filename is None:
        return {
            "code": 4002,
            "message": "请选择要上传的文件",
            "data": None,
        }

    # --- 3. 校验文件扩展名（快速检查，无 I/O）---
    is_valid, error_code, error_msg = validate_file_extension(
        file.filename, direction
    )
    if not is_valid:
        return {"code": error_code, "message": error_msg, "data": None}

    # --- 4. 预检 Content-Length（提前拦截超大文件，避免完整读取）---
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            content_length_bytes = int(content_length)
            if content_length_bytes > settings.MAX_UPLOAD_SIZE_BYTES:
                max_mb = settings.MAX_UPLOAD_SIZE_MB
                actual_mb = round(content_length_bytes / (1024 * 1024), 1)
                logger.warning(
                    "Rejected oversized upload: %sMB > %sMB (Content-Length)",
                    actual_mb, max_mb,
                )
                return {
                    "code": 4003,
                    "message": f"文件过大: {actual_mb}MB，最大允许 {max_mb}MB",
                    "data": None,
                }
        except (ValueError, TypeError):
            pass  # Content-Length 不合法则跳过预检，后续读文件时会校验实际大小

    # --- 5. 分步读取: 先读文件头做魔数校验，再读完整内容 ---
    # 第一步：读取文件头部用于魔数校验
    header_bytes = await file.read(_MAGIC_READ_SIZE)
    if not header_bytes:
        return {"code": 4002, "message": "文件为空", "data": None}

    # 魔数校验（防止伪造扩展名）
    is_valid, error_code, error_msg = validate_file_magic(header_bytes, direction)
    if not is_valid:
        logger.warning(
            "Magic number validation failed: filename=%s, direction=%s",
            file.filename, direction,
        )
        return {"code": error_code, "message": error_msg, "data": None}

    # 第二步：读取剩余文件内容
    remaining_bytes = await file.read()
    file_data = header_bytes + remaining_bytes

    # --- 6. 校验实际文件大小 ---
    is_valid, error_code, error_msg = validate_file_size(len(file_data))
    if not is_valid:
        return {"code": error_code, "message": error_msg, "data": None}

    # --- 7. 保存上传文件 ---
    upload_info = file_manager.save_upload(file_data, file.filename)
    token = upload_info["token"]

    # --- 8. 执行转换 ---
    try:
        converted_path = await converter.convert(upload_info["saved_path"], direction)
    except LibreOfficeNotFoundError:
        return {
            "code": 5003,
            "message": (
                "LibreOffice 不可用。请确保已安装 LibreOffice。\n"
                "下载地址: https://www.libreoffice.org/download/"
            ),
            "data": None,
        }
    except EncryptedPDFError as e:
        return {
            "code": 4004,
            "message": str(e),
            "data": None,
        }
    except ConversionTimeoutError:
        return {
            "code": 5001,
            "message": "转换超时，请尝试较小的文件",
            "data": None,
        }
    except ConversionError as e:
        logger.error("Conversion error: %s", e)
        return {
            "code": 5001,
            "message": str(e),
            "data": None,
        }
    except Exception:
        logger.exception("Unexpected error during conversion")
        return {
            "code": 5002,
            "message": "服务器内部错误，请稍后重试",
            "data": None,
        }

    # --- 9. 注册转换结果 ---
    file_manager.register_conversion(token, converted_path, direction)

    # --- 10. 构建下载 URL ---
    download_url = str(request.url_for("download_file", token=token))

    return {
        "code": 0,
        "message": "success",
        "data": {
            "token": token,
            "original_name": file.filename,
            "download_url": download_url,
            "file_size": len(file_data),
        },
    }
