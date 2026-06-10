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

### 方式一：一键启动（Windows）

双击运行 `start.bat`

### 方式二：命令行启动

```bash
# 1. 创建虚拟环境
python -m venv venv

# 2. 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 3. 安装依赖
pip install -r backend/requirements.txt

# 4. 启动服务
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 访问

- 前端页面：http://localhost:8000
- API 文档（Swagger）：http://localhost:8000/docs
- 健康检查：http://localhost:8000/api/health

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
| CORS_ORIGINS | * | 允许的跨域来源 |

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
├── .gitignore
├── README.md
└── start.bat                    # 一键启动
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
