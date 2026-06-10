/**
 * 上传交互模块 - 拖拽上传、文件选择、进度追踪
 */

/**
 * 初始化拖拽上传区
 * @param {HTMLElement} dropZone - 拖拽区域元素
 * @param {HTMLInputElement} fileInput - 隐藏的文件输入
 * @param {function} onFileSelected - 文件选中回调 (file: File)
 * @param {string} acceptExtensions - 接受的文件扩展名
 */
function initDropZone(dropZone, fileInput, onFileSelected) {
    // 点击选择文件
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    // 文件选择变更
    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            onFileSelected(file);
        }
    });

    // 阻止默认行为（允许拖放）
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach((eventName) => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
        });
    });

    // 拖入
    ['dragenter', 'dragover'].forEach((eventName) => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.add('drop-zone--drag-over');
        });
    });

    // 拖出
    ['dragleave', 'drop'].forEach((eventName) => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.remove('drop-zone--drag-over');
        });
    });

    // 放下文件
    dropZone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            onFileSelected(files[0]);
        }
    });
}

/**
 * 格式化文件大小
 * @param {number} bytes
 * @returns {string}
 */
function formatFileSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * 获取文件类型图标文字
 * @param {string} filename
 * @returns {string}
 */
function getFileType(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    if (ext === 'pdf') return 'PDF';
    if (ext === 'docx' || ext === 'doc') return 'Word';
    return ext.toUpperCase();
}
