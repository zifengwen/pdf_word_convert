"""应用配置 - 所有配置从环境变量或 .env 文件读取"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 从 backend/.env 加载（相对于 config.py 的路径，确保无论从哪个目录启动都能正确加载）
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


class Settings:
    """应用全局配置"""

    # --- 服务配置 ---
    APP_TITLE: str = "PDF2Word Converter"
    APP_VERSION: str = "1.0.0"
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))

    # --- 公网访问配置 ---
    # 是否允许所有跨域来源（设为 true 时忽略 CORS_ORIGINS 列表）
    ALLOW_ALL_ORIGINS: bool = os.getenv("ALLOW_ALL_ORIGINS", "false").lower() in ("true", "1", "yes")
    # 公网访问地址（用于文档展示，如 https://pdf.example.com）
    PUBLIC_URL: str = os.getenv("PUBLIC_URL", "")

    # --- 文件上传限制 ---
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
    MAX_UPLOAD_SIZE_BYTES: int = MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # --- 允许的文件格式 ---
    ALLOWED_WORD_EXTENSIONS: tuple = (".docx", ".doc")
    ALLOWED_PDF_EXTENSIONS: tuple = (".pdf",)

    # --- 转换配置 ---
    CONVERSION_TIMEOUT_SECONDS: int = int(os.getenv("CONVERSION_TIMEOUT_SECONDS", "120"))

    # --- 文件生命周期 ---
    FILE_EXPIRY_MINUTES: int = int(os.getenv("FILE_EXPIRY_MINUTES", "60"))
    CLEANUP_INTERVAL_MINUTES: int = int(os.getenv("CLEANUP_INTERVAL_MINUTES", "10"))

    # --- LibreOffice 路径 ---
    LIBREOFFICE_PATH: str = os.getenv("LIBREOFFICE_PATH", "soffice")

    # --- 存储路径 ---
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads"))
    CONVERTED_DIR: str = os.getenv("CONVERTED_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "converted"))

    # --- CORS ---
    # 生产环境务必配置为具体的域名列表，如 "https://example.com,https://www.example.com"
    # 若 ALLOW_ALL_ORIGINS=true，则允许所有来源（不推荐生产环境使用）
    @property
    def CORS_ORIGINS(self) -> list:
        if self.ALLOW_ALL_ORIGINS:
            return ["*"]
        origins = os.getenv(
            "CORS_ORIGINS",
            "http://localhost:8000,http://127.0.0.1:8000"
        ).split(",")
        return [o.strip() for o in origins if o.strip()]

    # --- 安全配置 ---
    # 是否启用 Swagger /docs 文档（生产环境建议关闭）
    ENABLE_DOCS: bool = os.getenv("ENABLE_DOCS", "false").lower() in ("true", "1", "yes")

    # 频率限制：每个 IP 在每个时间窗口内允许的最大请求数
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "30"))
    RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

    # 上传频率限制（比普通 API 更严格）
    UPLOAD_RATE_LIMIT_REQUESTS: int = int(os.getenv("UPLOAD_RATE_LIMIT_REQUESTS", "10"))
    UPLOAD_RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("UPLOAD_RATE_LIMIT_WINDOW_SECONDS", "60"))

    # 下载频率限制
    DOWNLOAD_RATE_LIMIT_REQUESTS: int = int(os.getenv("DOWNLOAD_RATE_LIMIT_REQUESTS", "20"))
    DOWNLOAD_RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("DOWNLOAD_RATE_LIMIT_WINDOW_SECONDS", "60"))


settings = Settings()
