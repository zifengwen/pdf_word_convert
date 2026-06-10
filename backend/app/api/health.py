"""健康检查端点"""

from fastapi import APIRouter

from ..config import settings
from ..services.converter import converter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """返回服务健康状态，包含 LibreOffice 可用性"""
    return {
        "code": 0,
        "message": "success",
        "data": {
            "service": settings.APP_TITLE,
            "version": settings.APP_VERSION,
            "libreoffice_available": converter.is_available(),
            "libreoffice_path": converter.libreoffice_path,
            "max_upload_size_mb": settings.MAX_UPLOAD_SIZE_MB,
        },
    }
