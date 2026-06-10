#!/bin/bash
# ============================================================================
# PDF2Word Converter - Ubuntu 一键部署脚本
# ============================================================================
#
# 用法:
#   chmod +x deploy.sh
#   sudo bash deploy.sh
#
# 或分步执行:
#   sudo bash deploy.sh --install-deps     # 仅安装系统依赖
#   sudo bash deploy.sh --setup-app        # 仅配置应用
#   sudo bash deploy.sh --setup-nginx      # 仅配置 Nginx
#   sudo bash deploy.sh --all              # 全部执行（默认）
#
# ============================================================================

set -e

# --- 颜色输出 ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
step()  { echo -e "\n${BLUE}════════════════════════════════════════${NC}"; echo -e "${BLUE}  $1${NC}"; echo -e "${BLUE}════════════════════════════════════════${NC}\n"; }

# --- 默认配置 ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${APP_DIR:-$SCRIPT_DIR}"                    # 应用安装目录
APP_USER="${APP_USER:-$USER}"                         # 运行用户
APP_PORT="${APP_PORT:-8000}"                          # 应用端口
DOMAIN="${DOMAIN:-}"                                  # 域名（配置 Nginx 时需要）
SETUP_NGINX="${SETUP_NGINX:-false}"                   # 是否配置 Nginx
ENABLE_UFW="${ENABLE_UFW:-true}"                      # 是否配置防火墙

# --- 检查 root 权限 ---
check_root() {
    if [ "$EUID" -ne 0 ]; then
        error "请使用 sudo 运行此脚本:\n  sudo bash deploy.sh"
    fi
}

# --- 检测系统 ---
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        OS_VERSION=$VERSION_ID
    else
        error "无法检测操作系统版本"
    fi

    case "$OS" in
        ubuntu|debian)
            info "检测到系统: $OS $OS_VERSION"
            ;;
        *)
            warn "未经测试的系统: $OS。脚本可能无法正常工作。"
            read -p "是否继续? [y/N] " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 0
            fi
            ;;
    esac
}

# ============================================================================
# 1. 安装系统依赖
# ============================================================================
install_deps() {
    step "1/4 安装系统依赖"

    info "更新软件包列表..."
    apt update

    info "安装 Python3 和 venv..."
    apt install -y python3 python3-venv python3-pip

    info "安装 LibreOffice（文档转换引擎）..."
    apt install -y libreoffice-writer

    info "安装其他工具..."
    apt install -y curl wget

    # 检测 LibreOffice 是否安装成功
    if command -v soffice &>/dev/null; then
        info "LibreOffice 安装成功: $(soffice --version 2>/dev/null || echo 'ok')"
    else
        warn "LibreOffice 安装后未检测到 soffice 命令，请检查"
    fi

    info "系统依赖安装完成"
}

# ============================================================================
# 2. 配置应用
# ============================================================================
setup_app() {
    step "2/4 配置应用"

    # 创建应用目录（如果和脚本目录不同）
    if [ "$APP_DIR" != "$SCRIPT_DIR" ]; then
        info "复制项目到 $APP_DIR..."
        mkdir -p "$APP_DIR"
        cp -r "$SCRIPT_DIR"/* "$APP_DIR"/
        chown -R "$APP_USER:$APP_USER" "$APP_DIR"
    fi

    cd "$APP_DIR"

    # 创建虚拟环境
    if [ ! -d "venv" ]; then
        info "创建 Python 虚拟环境..."
        sudo -u "$APP_USER" python3 -m venv venv
    else
        info "虚拟环境已存在，跳过"
    fi

    # 安装 Python 依赖
    info "安装 Python 依赖..."
    sudo -u "$APP_USER" venv/bin/pip install -r backend/requirements.txt -q

    # 创建必要的目录
    info "创建上传和转换输出目录..."
    mkdir -p backend/uploads backend/converted
    chown -R "$APP_USER:$APP_USER" backend/uploads backend/converted

    # 配置 .env 文件
    if [ ! -f "backend/.env" ]; then
        warn "backend/.env 文件不存在，将使用默认配置"
    else
        info "backend/.env 配置文件已就绪"
        # 确保公网访问配置
        if [ -n "$DOMAIN" ]; then
            info "配置 CORS 域名: $DOMAIN"
            sed -i "s/^ALLOW_ALL_ORIGINS=.*/ALLOW_ALL_ORIGINS=false/" backend/.env
            sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=https://${DOMAIN}|" backend/.env
        fi
    fi

    info "应用配置完成"
}

# ============================================================================
# 3. 配置 systemd 服务
# ============================================================================
setup_systemd() {
    step "3/4 配置 systemd 后台服务"

    local service_file="$APP_DIR/pdf2word.service"
    local target_service="/etc/systemd/system/pdf2word.service"

    if [ ! -f "$service_file" ]; then
        error "未找到 pdf2word.service 模板文件"
    fi

    # 替换占位符并安装服务文件
    info "安装 systemd 服务..."
    sed -e "s|\${APP_DIR}|$APP_DIR|g" \
        -e "s|\${APP_USER}|$APP_USER|g" \
        "$service_file" > "$target_service"

    # 重载 systemd 配置
    systemctl daemon-reload

    # 启用开机自启并立即启动
    info "启用并启动服务..."
    systemctl enable pdf2word.service
    systemctl start pdf2word.service

    # 检查服务状态
    sleep 2
    if systemctl is-active --quiet pdf2word.service; then
        info "服务已成功启动"
    else
        warn "服务可能未正常启动，请检查: sudo systemctl status pdf2word"
        systemctl status pdf2word.service --no-pager || true
    fi

    info "systemd 服务配置完成"
}

# ============================================================================
# 4. 配置 Nginx 反向代理（可选）
# ============================================================================
setup_nginx() {
    step "4/4 配置 Nginx 反向代理"

    if [ "$SETUP_NGINX" != "true" ]; then
        info "跳过 Nginx 配置（设置 SETUP_NGINX=true 以启用）"
        return
    fi

    if [ -z "$DOMAIN" ]; then
        warn "未设置 DOMAIN 变量，跳过 Nginx 配置"
        warn "示例: sudo DOMAIN=pdf.example.com bash deploy.sh --setup-nginx"
        return
    fi

    # 安装 Nginx
    if ! command -v nginx &>/dev/null; then
        info "安装 Nginx..."
        apt install -y nginx
    else
        info "Nginx 已安装: $(nginx -v 2>&1)"
    fi

    # 复制并配置 Nginx 配置
    local nginx_src="$APP_DIR/nginx.conf"
    local nginx_dst="/etc/nginx/sites-available/pdf2word"

    if [ -f "$nginx_src" ]; then
        info "配置 Nginx 站点..."

        # 替换占位符
        sed -e "s|\${DOMAIN}|$DOMAIN|g" \
            -e "s|\${APP_PORT}|$APP_PORT|g" \
            "$nginx_src" > "$nginx_dst"

        # 启用站点
        ln -sf "$nginx_dst" /etc/nginx/sites-enabled/
        rm -f /etc/nginx/sites-enabled/default

        # 测试配置
        if nginx -t; then
            systemctl reload nginx
            info "Nginx 配置已生效"
        else
            warn "Nginx 配置测试失败，请手动检查"
        fi
    else
        warn "未找到 nginx.conf 模板文件，跳过"
    fi

    # 配置 SSL（如果域名可解析）
    if command -v certbot &>/dev/null; then
        info "检测到 certbot，尝试申请 SSL 证书..."
        if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email "admin@${DOMAIN}" --redirect; then
            info "SSL 证书申请成功"
        else
            warn "SSL 证书申请失败，请手动执行: sudo certbot --nginx -d $DOMAIN"
        fi
    else
        info "安装 certbot..."
        apt install -y certbot python3-certbot-nginx
        info "手动申请证书: sudo certbot --nginx -d $DOMAIN"
    fi

    info "Nginx 配置完成"
}

# ============================================================================
# 5. 配置防火墙
# ============================================================================
setup_firewall() {
    if [ "$ENABLE_UFW" != "true" ]; then
        return
    fi

    if ! command -v ufw &>/dev/null; then
        info "安装 ufw 防火墙..."
        apt install -y ufw
    fi

    info "配置防火墙规则..."
    ufw allow ssh
    ufw allow "${APP_PORT}/tcp" comment "PDF2Word Converter"

    if [ "$SETUP_NGINX" = "true" ]; then
        ufw allow 80/tcp comment "HTTP"
        ufw allow 443/tcp comment "HTTPS"
    fi

    ufw --force enable
    ufw status verbose

    info "防火墙配置完成"
}

# ============================================================================
# 完成输出
# ============================================================================
print_summary() {
    local ip
    ip=$(curl -s ifconfig.me 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')

    echo ""
    echo "========================================"
    echo "  部署完成！"
    echo "========================================"
    echo ""
    echo "  服务管理命令:"
    echo "    sudo systemctl status pdf2word    # 查看状态"
    echo "    sudo systemctl restart pdf2word   # 重启服务"
    echo "    sudo systemctl stop pdf2word      # 停止服务"
    echo "    sudo journalctl -u pdf2word -f    # 查看日志"
    echo ""
    echo "  访问地址:"
    echo "    本地:    http://localhost:${APP_PORT}"
    echo "    内网:    http://${ip}:${APP_PORT}"

    if [ -n "$DOMAIN" ] && [ "$SETUP_NGINX" = "true" ]; then
        echo "    公网:    https://${DOMAIN}"
    fi

    echo ""
    echo "  健康检查:"
    echo "    curl http://localhost:${APP_PORT}/api/health"
    echo ""
}

# ============================================================================
# 主入口
# ============================================================================
main() {
    check_root
    detect_os

    case "${1:-}" in
        --install-deps)
            install_deps
            ;;
        --setup-app)
            setup_app
            ;;
        --setup-nginx)
            setup_nginx
            ;;
        --setup-systemd)
            setup_systemd
            ;;
        --firewall)
            setup_firewall
            ;;
        --all|"")
            install_deps
            setup_app
            setup_systemd
            setup_firewall
            setup_nginx
            print_summary
            ;;
        *)
            echo "用法: sudo bash deploy.sh [选项]"
            echo ""
            echo "选项:"
            echo "  --all             全部执行（默认）"
            echo "  --install-deps    仅安装系统依赖"
            echo "  --setup-app       仅配置应用"
            echo "  --setup-systemd   仅配置 systemd 服务"
            echo "  --setup-nginx     仅配置 Nginx 反向代理"
            echo "  --firewall        仅配置防火墙"
            echo ""
            echo "环境变量:"
            echo "  APP_DIR           应用安装目录（默认: 脚本所在目录）"
            echo "  APP_USER          运行用户（默认: 当前用户）"
            echo "  APP_PORT          应用端口（默认: 8000）"
            echo "  DOMAIN            域名（配置 Nginx 时需要）"
            echo "  SETUP_NGINX       是否配置 Nginx（默认: false）"
            echo "  ENABLE_UFW        是否配置防火墙（默认: true）"
            echo ""
            echo "示例:"
            echo "  sudo DOMAIN=pdf.example.com SETUP_NGINX=true bash deploy.sh"
            exit 1
            ;;
    esac
}

main "$@"
