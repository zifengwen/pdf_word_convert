/**
 * API 封装层 - fetch 封装、错误处理
 */

const API_BASE = '/api';

/**
 * 上传文件并转换
 * @param {string} direction - 'word-to-pdf' 或 'pdf-to-word'
 * @param {File} file - 要上传的文件
 * @param {function} onProgress - 进度回调 (percent: number)
 * @returns {Promise<object>} 解析后的响应数据
 */
function apiConvert(direction, file, onProgress) {
    return new Promise((resolve, reject) => {
        const formData = new FormData();
        formData.append('file', file);

        const xhr = new XMLHttpRequest();

        // 上传进度
        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable && onProgress) {
                const percent = Math.round((e.loaded / e.total) * 100);
                onProgress(percent);
            }
        });

        // 完成
        xhr.addEventListener('loadend', () => {
            if (xhr.status === 0) {
                reject({ code: -1, message: '网络连接失败，请检查网络' });
                return;
            }

            let data;
            try {
                data = JSON.parse(xhr.responseText);
            } catch (e) {
                reject({
                    code: -1,
                    message: `服务器响应异常 (HTTP ${xhr.status})`,
                });
                return;
            }

            if (data.code === 0) {
                resolve(data);
            } else {
                reject({
                    code: data.code,
                    message: data.message || '未知错误',
                });
            }
        });

        // 网络错误
        xhr.addEventListener('error', () => {
            reject({ code: -1, message: '网络连接失败，请检查网络' });
        });

        // 超时
        xhr.addEventListener('timeout', () => {
            reject({ code: -1, message: '请求超时，请重试' });
        });

        xhr.open('POST', `${API_BASE}/convert/${direction}`);
        xhr.timeout = 300000; // 5 分钟超时（含转换时间）
        xhr.send(formData);
    });
}

/**
 * 触发文件下载
 * 使用隐藏 iframe 方式，比 <a> 标签更可靠，不会受浏览器安全策略影响
 * @param {string} downloadUrl - 完整下载 URL
 * @param {string} filename - 下载文件名（备用，实际文件名由服务端 Content-Disposition 决定）
 */
function apiDownload(downloadUrl, filename) {
    // 方式1：创建隐藏 iframe 触发下载（最可靠）
    var iframe = document.createElement('iframe');
    iframe.style.display = 'none';
    iframe.style.width = '0px';
    iframe.style.height = '0px';
    iframe.style.border = 'none';
    iframe.src = downloadUrl;
    document.body.appendChild(iframe);

    // 下载完成后清理 iframe
    setTimeout(function () {
        if (iframe.parentNode) {
            iframe.parentNode.removeChild(iframe);
        }
    }, 10000);
}
