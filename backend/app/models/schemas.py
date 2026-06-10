"""Pydantic 数据模型 - 请求/响应 Schema"""

from typing import Optional

from pydantic import BaseModel


class ApiResponse(BaseModel):
    """统一 API 响应格式"""

    code: int = 0
    message: str = "success"
    data: Optional[dict] = None


class ConvertData(BaseModel):
    """转换成功响应数据"""

    token: str
    original_name: str
    download_url: str
    file_size: int


class HealthData(BaseModel):
    """健康检查响应数据"""

    service: str
    version: str
    libreoffice_available: bool
    libreoffice_path: Optional[str]
    max_upload_size_mb: int
