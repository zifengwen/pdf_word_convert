#!/bin/bash
# ============================================================================
# PDF2Word Converter - Ubuntu/Linux 一键启动脚本
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  PDF2Word Converter - 启动中..."
echo "========================================"

# --- 检查 Python3 ---
if ! command -v python3 &>/dev/null; then
    echo "[错误] 未找到 python3，请先安装 Python 3.8+"
    echo "  sudo apt update && sudo apt install python3 python3-venv -y"
    exit 1
fi

echo "[检测] Python3: $(python3 --version)"

# --- 检查 LibreOffice ---
if ! command -v soffice &>/dev/null; then
    echo "[警告] 未检测到 LibreOffice，转换功能将不可用"
    echo "  安装: sudo apt install libreoffice -y"
else
    echo "[检测] LibreOffice: $(soffice --version 2>/dev/null || echo '已安装')"
fi

# --- 创建虚拟环境 ---
if [ ! -d "venv" ]; then
    echo "[1/3] 创建虚拟环境..."
    python3 -m venv venv
fi

# --- 激活虚拟环境 ---
source venv/bin/activate

# --- 安装依赖 ---
echo "[2/3] 安装依赖..."
pip install -r backend/requirements.txt -q

# --- 启动服务 ---
echo "[3/3] 启动服务..."
echo ""
echo "  前端页面: http://localhost:8000"
echo "  API 文档: http://localhost:8000/docs"
echo "  健康检查: http://localhost:8000/api/health"
echo ""
echo "  按 Ctrl+C 停止服务"
echo "========================================"

uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
