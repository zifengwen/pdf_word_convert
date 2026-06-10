# PDF2Word Converter

免费在线文档格式转换工具，支持 **Word ↔ PDF** 双向转换，保持原始排版（表格、图片、页眉页脚）。

## 功能特性

- ✅ Word (.docx/.doc) → PDF 转换
- ✅ PDF → Word (.docx) 转换
- ✅ 保持复杂格式：表格、图片、页眉页脚
- ✅ 拖拽上传 + 点击选择文件
- ✅ 上传进度实时显示
- ✅ 转换完成自动下载
- ✅ 文件自动过期清理（默认 60 分钟）
- ✅ RESTful API，支持接入微信小程序

## 环境要求

| 依赖 | 说明 |
|------|------|
| Python 3.7+ | 后端运行环境 |
| LibreOffice 7.0+ | 文档转换引擎（**必须安装**） |

### 安装 LibreOffice

- **Windows**: [LibreOffice 下载](https://www.libreoffice.org/download/)
- **macOS**: `brew install --cask libreoffice`
- **Linux**: `sudo apt-get install libreoffice` 或 `sudo yum install libreoffice`

## 快速启动

### 方式一：Ubuntu 一键部署（推荐 · 生产环境）

```bash
# 克隆项目后执行
chmod +x deploy.sh
sudo bash deploy.sh

# 带域名 + Nginx 的一键部署
sudo DOMAIN=pdf.example.com SETUP_NGINX=true bash deploy.sh
```

部署完成后服务自动运行在后台，访问 `http://<服务器IP>:8000`。

### 方式二：Ubuntu 命令行启动

```bash
chmod +x start.sh
bash start.sh
```

### 方式三：Docker 部署

```bash
docker-compose up -d
```

### 方式四：Windows 一键启动

双击运行 `start.bat`

### 访问

- 前端页面：http://localhost:8000
- API 文档（Swagger）：http://localhost:8000/docs
- 健康检查：http://localhost:8000/api/health

## Ubuntu 部署详解

### 一键部署 (`deploy.sh`)

脚本将自动完成以下步骤：

1. 安装系统依赖（Python3、LibreOffice）
2. 创建 Python 虚拟环境并安装依赖
3. 配置 systemd 服务（开机自启、崩溃重启）
4. 配置防火墙规则
5. 可选：配置 Nginx 反向代理 + SSL 证书

```bash
# 完整部署
sudo bash deploy.sh

# 仅安装系统依赖
sudo bash deploy.sh --install-deps

# 仅配置 systemd 服务
sudo bash deploy.sh --setup-systemd

# 仅配置 Nginx
sudo DOMAIN=pdf.example.com bash deploy.sh --setup-nginx
```

### systemd 服务管理

```bash
sudo systemctl status pdf2word     # 查看状态
sudo systemctl restart pdf2word    # 重启服务
sudo systemctl stop pdf2word       # 停止服务
sudo journalctl -u pdf2word -f     # 查看实时日志
```

### Nginx 反向代理（推荐）

1. 将 `nginx.conf` 中的 `${DOMAIN}` 替换为你的域名，`${APP_PORT}` 替换为后端端口
2. 将配置文件复制到 Nginx 配置目录
3. 申请 SSL 证书（Let's Encrypt）:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

4. 重载 Nginx:

```bash
sudo nginx -t && sudo nginx -s reload
```

然后直接启动服务即可通过 `http://<公网IP>:8000` 访问。

## API 文档

### 统一响应格式

```json
{
    "code": 0,        // 0=成功, 400x=客户端错误, 500x=服务端错误
    "message": "success",
    "data": { ... }
}
```

### 错误码

| code | HTTP | 说明 |
|------|------|------|
| 0 | 200 | 成功 |
| 4001 | 400 | 不支持的文件格式 |
| 4002 | 400 | 未提供文件/文件为空 |
| 4003 | 400 | 文件超过大小限制 |
| 5001 | 500 | 转换失败 |
| 5002 | 500 | 服务器内部错误 |
| 5003 | 503 | LibreOffice 不可用 |
| 4041 | 404/410 | 下载链接已过期 |

### 端点

#### `POST /api/convert/{direction}`

上传文件并转换格式。

**路径参数：**
- `direction`: `word-to-pdf` 或 `pdf-to-word`

**请求体：** `multipart/form-data`
- `file`: 上传的文件

**成功响应：**
```json
{
    "code": 0,
    "message": "success",
    "data": {
        "token": "uuid-string",
        "original_name": "document.docx",
        "download_url": "http://localhost:8000/api/download/uuid-string",
        "file_size": 12345
    }
}
```

#### `GET /api/download/{token}`

下载转换后的文件。返回二进制文件流。

#### `GET /api/health`

服务健康检查。

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "service": "PDF2Word Converter",
        "version": "1.0.0",
        "libreoffice_available": true,
        "libreoffice_path": "/usr/bin/soffice",
        "max_upload_size_mb": 50
    }
}
```

## 微信小程序接入指南

### 调用示例

```javascript
// 1. 选择文件
wx.chooseMessageFile({
    count: 1,
    type: 'file',
    extension: ['docx', 'doc', 'pdf'],
    success(res) {
        const file = res.tempFiles[0];
        uploadAndConvert(file.path);
    }
});

// 2. 上传并转换
function uploadAndConvert(filePath) {
    wx.showLoading({ title: '转换中...' });

    wx.uploadFile({
        url: 'https://your-server.com/api/convert/word-to-pdf',
        filePath: filePath,
        name: 'file',
        success(res) {
            const data = JSON.parse(res.data);
            if (data.code === 0) {
                downloadFile(data.data.download_url);
            } else {
                wx.showToast({ title: data.message, icon: 'none' });
            }
        },
        fail() {
            wx.showToast({ title: '网络错误', icon: 'none' });
        },
        complete() {
            wx.hideLoading();
        }
    });
}

// 3. 下载结果文件
function downloadFile(url) {
    wx.downloadFile({
        url: url,
        success(res) {
            // 预览 PDF
            if (url.endsWith('.pdf')) {
                wx.openDocument({
                    filePath: res.tempFilePath,
                    fileType: 'pdf'
                });
            } else {
                // 保存或分享 docx 文件
                wx.shareFileMessage({
                    filePath: res.tempFilePath,
                });
            }
        }
    });
}
```

### 注意事项

1. 服务器域名需要在微信小程序后台配置为 **request 合法域名** 和 **uploadFile 合法域名**
2. 建议在 API 响应中返回的 `download_url` 使用 HTTPS 协议
3. 微信小程序 `wx.uploadFile` 单文件默认限制为 10MB
4. 下载的临时文件需要及时处理，小程序存储空间有限

## 配置说明

通过环境变量或 `.env` 文件配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| APP_HOST | 0.0.0.0 | 监听地址 |
| APP_PORT | 8000 | 监听端口 |
| MAX_UPLOAD_SIZE_MB | 50 | 最大上传文件大小 (MB) |
| CONVERSION_TIMEOUT_SECONDS | 120 | 转换超时时间 (秒) |
| FILE_EXPIRY_MINUTES | 60 | 转换文件有效期 (分钟) |
| CLEANUP_INTERVAL_MINUTES | 10 | 过期文件清理间隔 (分钟) |
| LIBREOFFICE_PATH | soffice | LibreOffice 可执行文件路径 |
| **ALLOW_ALL_ORIGINS** | **false** | **是否允许所有跨域来源（公网无域名时临时开启）** |
| **PUBLIC_URL** | **(空)** | **公网访问地址，如 https://pdf.example.com** |
| CORS_ORIGINS | localhost:8000,... | 允许的跨域来源列表（逗号分隔，ALLOW_ALL_ORIGINS=true 时忽略） |
| ENABLE_DOCS | false | 是否启用 /docs API 文档（生产环境建议关闭） |
| RATE_LIMIT_REQUESTS | 30 | 全局频率限制（每 IP 每窗口请求数） |
| RATE_LIMIT_WINDOW_SECONDS | 60 | 全局频率限制时间窗口 (秒) |
| UPLOAD_RATE_LIMIT_REQUESTS | 10 | 上传端点频率限制 |
| UPLOAD_RATE_LIMIT_WINDOW_SECONDS | 60 | 上传端点频率限制窗口 (秒) |
| DOWNLOAD_RATE_LIMIT_REQUESTS | 20 | 下载端点频率限制 |
| DOWNLOAD_RATE_LIMIT_WINDOW_SECONDS | 60 | 下载端点频率限制窗口 (秒) |

## 项目结构

```
pdf2word/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # 应用配置
│   │   ├── api/                 # API 路由
│   │   │   ├── router.py        # 路由聚合
│   │   │   ├── convert.py       # 文件转换接口
│   │   │   ├── download.py      # 文件下载接口
│   │   │   └── health.py        # 健康检查接口
│   │   ├── services/            # 业务逻辑
│   │   │   ├── converter.py     # LibreOffice 转换引擎
│   │   │   └── file_manager.py  # 文件生命周期管理
│   │   ├── models/              # 数据模型
│   │   │   └── schemas.py
│   │   └── utils/               # 工具函数
│   │       └── validators.py
│   ├── uploads/                 # 临时上传目录
│   ├── converted/               # 转换结果目录
│   └── requirements.txt
├── frontend/
│   ├── index.html               # 单页应用
│   ├── css/style.css            # 样式
│   └── js/                      # 前端逻辑
│       ├── app.js               # 状态机
│       ├── upload.js            # 拖拽上传
│       └── api.js               # API 封装
├── Dockerfile                   # Docker 镜像构建
├── docker-compose.yml           # Docker Compose 编排
├── nginx.conf                   # Nginx 反向代理配置模板
├── .dockerignore                # Docker 构建忽略
├── .gitignore
├── README.md
└── start.bat                    # 一键启动 (Windows)
```

## 技术栈

- **后端**: Python + FastAPI
- **前端**: 原生 HTML/CSS/JS（无框架）
- **转换引擎**: LibreOffice headless
- **部署**: Uvicorn ASGI Server

## 已知限制

- 扫描版 PDF（图片）转换为 Word 时无法提取文字（需 OCR，未来版本可集成 Tesseract）
- 超大文件（>200页）转换可能较慢
- LibreOffice 不支持并发转换（已通过锁机制串行化处理）

## License

MIT
