@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   PDF2Word Converter - 启动中...
echo ========================================

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

:: 创建虚拟环境（如果不存在）
if not exist "venv\" (
    echo [1/3] 创建虚拟环境...
    python -m venv venv
)

:: 激活虚拟环境
call venv\Scripts\activate.bat

:: 安装依赖
echo [2/3] 安装依赖...
pip install -r backend\requirements.txt -q

:: 启动服务
echo [3/3] 启动服务...
echo.
echo   前端页面: http://localhost:8000
echo   API 文档: http://localhost:8000/docs
echo   健康检查: http://localhost:8000/api/health
echo.
echo   按 Ctrl+C 停止服务
echo ========================================

uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

pause
