# ============================================================================
# PDF2Word Converter - Docker 镜像
# ============================================================================
#
# 构建: docker build -t pdf2word:latest .
# 运行: docker run -d -p 8000:8000 --name pdf2word pdf2word:latest
#
# ============================================================================

FROM python:3.10-slim

LABEL maintainer="PDF2Word Converter"
LABEL description="PDF 和 Word 相互转换服务"

# 设置时区（可选，避免 LibreOffice 时区警告）
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# --- 安装系统依赖和 LibreOffice ---
# libreoffice-writer 用于文档格式转换
# libreoffice-impress 支持 PPT 相关的兼容性
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer \
    libreoffice-impress \
    fontconfig \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# --- 创建工作目录 ---
WORKDIR /app

# --- 安装 Python 依赖 ---
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# --- 复制应用代码 ---
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

# --- 创建上传和转换目录 ---
RUN mkdir -p /app/backend/uploads /app/backend/converted

# --- 暴露端口 ---
EXPOSE 8000

# --- 健康检查 ---
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

# --- 启动命令 ---
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
