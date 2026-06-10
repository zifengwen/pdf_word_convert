"""FastAPI 应用入口 - 应用工厂、CORS、安全中间件、限流、静态文件挂载、异常处理"""

import asyncio
import logging
import os
import sys
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from .config import settings

# 确保 services 模块可导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- 日志 ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("pdf2word")


# ============================================================================
# 内存频率限制器
# ============================================================================

class InMemoryRateLimiter:
    """基于滑动窗口的内存频率限制器，线程安全"""

    def __init__(self):
        self._store: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """检查 key 是否在限流窗口内超出限制"""
        now = time.monotonic()
        async with self._lock:
            window_start = now - window_seconds
            # 清理过期记录
            self._store[key] = [t for t in self._store[key] if t > window_start]
            if len(self._store[key]) >= max_requests:
                return False
            self._store[key].append(now)

            # 定期清理过期 key（超过 10000 个 key 时触发）
            if len(self._store) > 10000:
                stale_keys = [
                    k for k, v in self._store.items()
                    if not v or v[-1] <= window_start
                ]
                for k in stale_keys:
                    del self._store[k]
            return True


_rate_limiter = InMemoryRateLimiter()


# ============================================================================
# 客户端 IP 获取
# ============================================================================

def _get_client_ip(request: Request) -> str:
    """
    获取客户端真实 IP。
    优先从 X-Forwarded-For / X-Real-IP 头获取（支持反向代理部署）。
    """
    # X-Forwarded-For 格式: client, proxy1, proxy2
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # 取第一个（最原始的客户端 IP）
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    # 直连模式：从 connection scope 获取
    client = request.client
    if client:
        return client.host

    return "unknown"


# ============================================================================
# 中间件函数（在 app 创建后注册）
# ============================================================================

async def rate_limit_middleware(request: Request, call_next):
    """
    基于 IP 的频率限制中间件。
    上传和下载端点有独立的限流配置。
    """
    path = request.url.path
    client_ip = _get_client_ip(request)

    # 为上传端点使用更严格的限流
    if path.startswith("/api/convert/"):
        max_req = settings.UPLOAD_RATE_LIMIT_REQUESTS
        window = settings.UPLOAD_RATE_LIMIT_WINDOW_SECONDS
        key = f"upload:{client_ip}"
    elif path.startswith("/api/download/"):
        max_req = settings.DOWNLOAD_RATE_LIMIT_REQUESTS
        window = settings.DOWNLOAD_RATE_LIMIT_WINDOW_SECONDS
        key = f"download:{client_ip}"
    else:
        max_req = settings.RATE_LIMIT_REQUESTS
        window = settings.RATE_LIMIT_WINDOW_SECONDS
        key = f"global:{client_ip}"

    allowed = await _rate_limiter.is_allowed(key, max_req, window)
    if not allowed:
        logger.warning("Rate limit exceeded: ip=%s, path=%s", client_ip, path)
        return JSONResponse(
            status_code=429,
            content={
                "code": 4291,
                "message": "请求过于频繁，请稍后重试",
                "data": None,
            },
        )

    response = await call_next(request)
    return response


async def security_headers_middleware(request: Request, call_next):
    """添加常见的安全响应头"""
    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), interest-cohort=()"
    )
    # 仅对 HTML 响应添加 CSP
    content_type = response.headers.get("content-type", "")
    if "text/html" in content_type:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        )

    return response


# ============================================================================
# 应用工厂
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化，关闭时清理"""
    # 启动时
    from .services.file_manager import file_manager
    file_manager.start_cleanup()
    logger.info(
        "PDF2Word Converter v%s started — max upload: %sMB, rate limit: %s req/%ss",
        settings.APP_VERSION,
        settings.MAX_UPLOAD_SIZE_MB,
        settings.RATE_LIMIT_REQUESTS,
        settings.RATE_LIMIT_WINDOW_SECONDS,
    )
    yield
    # 关闭时
    file_manager.stop_cleanup()
    logger.info("PDF2Word Converter stopped")


# 根据配置决定是否启用 /docs 和 /redoc
app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_DOCS else None,
)

# 注册安全中间件（后添加的先执行 → 安全头最外层 → 再限流 → 再到路由）
app.middleware("http")(security_headers_middleware)
app.middleware("http")(rate_limit_middleware)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# --- 注册 API 路由 ---
from .api.router import api_router

app.include_router(api_router, prefix="/api")


# --- 请求验证异常处理器 ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求参数校验失败，返回统一 JSON 错误格式"""
    messages = []
    for error in exc.errors():
        loc = " -> ".join(str(l) for l in error["loc"])
        messages.append(f"{loc}: {error['msg']}")
    logger.warning(
        "Validation error from %s: %s",
        _get_client_ip(request),
        "; ".join(messages) if messages else "请求参数错误",
    )
    return JSONResponse(
        status_code=400,
        content={
            "code": 4002,
            "message": "; ".join(messages) if messages else "请求参数错误",
            "data": None,
        },
    )


# --- 全局异常处理器（脱敏：不暴露内部异常信息）---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理，记录详细日志但不向客户端暴露内部信息"""
    logger.exception(
        "Unhandled exception from %s %s: %s",
        _get_client_ip(request),
        request.url.path,
        exc,
    )
    return JSONResponse(
        status_code=500,
        content={
            "code": 5002,
            "message": "服务器内部错误，请稍后重试",
            "data": None,
        },
    )


# --- 挂载前端静态文件（放在最后，确保 /api/* 优先匹配）---
FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "frontend",
)
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
