"""API 主路由 - 聚合所有子路由"""

from fastapi import APIRouter

from .health import router as health_router
from .convert import router as convert_router
from .download import router as download_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(convert_router)
api_router.include_router(download_router)
