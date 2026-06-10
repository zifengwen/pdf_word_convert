/**
 * 主应用逻辑 - 状态机、事件绑定、UI 切换
 */

(function () {
    'use strict';

    // ---------- 状态定义 ----------
    const STATES = {
        IDLE: 'idle',
        FILE_SELECTED: 'file-selected',
        UPLOADING: 'uploading',
        CONVERTING: 'converting',
        COMPLETED: 'completed',
        ERROR: 'error',
    };

    // ---------- 当前状态 ----------
    let currentState = STATES.IDLE;
    let currentFile = null;
    let currentDirection = 'word-to-pdf';
    let downloadInfo = null;

    // ---------- DOM 元素 ----------
    const $ = (id) => document.getElementById(id);

    const dropZone = $('dropZone');
    const dropZoneText = $('dropZoneText');
    const dropZoneHint = $('dropZoneHint');
    const fileInput = $('fileInput');
    const fileInfo = $('fileInfo');
    const fileName = $('fileName');
    const fileSize = $('fileSize');
    const btnRemove = $('btnRemove');
    const convertBtnArea = $('convertBtnArea');
    const btnStartConvert = $('btnStartConvert');
    const progressArea = $('progressArea');
    const progressFill = $('progressFill');
    const progressText = $('progressText');
    const statusArea = $('statusArea');
    const statusText = $('statusText');
    const resultArea = $('resultArea');
    const resultDetail = $('resultDetail');
    const btnDownload = $('btnDownload');
    const btnDownloadText = $('btnDownloadText');
    const btnNewConvert = $('btnNewConvert');
    const errorArea = $('errorArea');
    const errorMessage = $('errorMessage');
    const btnRetry = $('btnRetry');

    // 左侧栏
    const sideWordToPdf = $('sideWordToPdf');
    const sidePdfToWord = $('sidePdfToWord');

    // ---------- 状态切换 ----------
    function setState(state, data) {
        currentState = state;

        // 隐藏所有动态区域
        [dropZone, fileInfo, convertBtnArea, progressArea, statusArea, resultArea, errorArea].forEach(
            (el) => (el.style.display = 'none')
        );

        switch (state) {
            case STATES.IDLE:
                fileInput.value = '';
                currentFile = null;
                downloadInfo = null;
                dropZone.style.display = '';
                updateDropZoneHint();
                enableSidebar(true);
                break;

            case STATES.FILE_SELECTED:
                fileInfo.style.display = '';
                convertBtnArea.style.display = '';
                dropZone.style.display = '';
                enableSidebar(true);
                break;

            case STATES.UPLOADING:
                progressArea.style.display = '';
                progressFill.style.width = '0%';
                progressText.textContent = '上传中... 0%';
                enableSidebar(false);
                break;

            case STATES.CONVERTING:
                statusArea.style.display = '';
                statusText.textContent =
                    currentDirection === 'word-to-pdf'
                        ? '正在转换为 PDF...'
                        : '正在转换为 Word...';
                enableSidebar(false);
                break;

            case STATES.COMPLETED:
                resultArea.style.display = '';
                if (data) {
                    resultDetail.textContent = data.detail || '';
                    btnDownloadText.textContent = data.btnText || '下载文件';
                }
                enableSidebar(false);
                break;

            case STATES.ERROR:
                errorArea.style.display = '';
                if (data && data.message) {
                    errorMessage.textContent = data.message;
                }
                enableSidebar(true);
                break;
        }
    }

    function enableSidebar(enabled) {
        sideWordToPdf.style.pointerEvents = enabled ? '' : 'none';
        sidePdfToWord.style.pointerEvents = enabled ? '' : 'none';
        sideWordToPdf.style.opacity = enabled ? '' : '0.5';
        sidePdfToWord.style.opacity = enabled ? '' : '0.5';
    }

    function updateDropZoneHint() {
        const formats =
            currentDirection === 'word-to-pdf'
                ? '.docx / .doc'
                : '.pdf';
        dropZoneText.textContent = '拖拽文件到此处';
        dropZoneHint.textContent = `或点击选择 — 支持 ${formats} 文件，最大 50MB`;
    }

    // ---------- 模式切换 ----------
    function switchDirection(direction) {
        if (currentState === STATES.UPLOADING || currentState === STATES.CONVERTING) {
            return;
        }

        currentDirection = direction;

        if (direction === 'word-to-pdf') {
            sideWordToPdf.classList.add('sidebar__item--active');
            sidePdfToWord.classList.remove('sidebar__item--active');
            fileInput.accept = '.docx,.doc';
        } else {
            sidePdfToWord.classList.add('sidebar__item--active');
            sideWordToPdf.classList.remove('sidebar__item--active');
            fileInput.accept = '.pdf';
        }

        updateDropZoneHint();
        // 清除已选文件
        if (currentState === STATES.FILE_SELECTED || currentState === STATES.ERROR) {
            setState(STATES.IDLE);
        }
    }

    sideWordToPdf.addEventListener('click', () => switchDirection('word-to-pdf'));
    sidePdfToWord.addEventListener('click', () => switchDirection('pdf-to-word'));

    // ---------- 文件选择 ----------
    function handleFileSelected(file) {
        // 客户端校验扩展名
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        const allowedExts =
            currentDirection === 'word-to-pdf' ? ['.docx', '.doc'] : ['.pdf'];

        if (!allowedExts.includes(ext)) {
            setState(STATES.ERROR, {
                message: `不支持的文件格式: ${ext}。请选择 ${allowedExts.join(' / ')} 文件`,
            });
            return;
        }

        // 客户端校验大小
        const maxBytes = 50 * 1024 * 1024; // 50MB
        if (file.size > maxBytes) {
            setState(STATES.ERROR, {
                message: `文件过大: ${formatFileSize(file.size)}，最大允许 50MB`,
            });
            return;
        }

        currentFile = file;
        fileName.textContent = file.name;
        fileSize.textContent = formatFileSize(file.size);
        setState(STATES.FILE_SELECTED);
    }

    // 初始化拖拽上传区
    initDropZone(dropZone, fileInput, handleFileSelected);

    // 文件选择
    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) handleFileSelected(file);
    });

    // 移除文件
    btnRemove.addEventListener('click', (e) => {
        e.stopPropagation();
        setState(STATES.IDLE);
    });

    // ---------- 开始转换 ----------
    function startConvert() {
        if (!currentFile) return;

        setState(STATES.UPLOADING);

        apiConvert(
            currentDirection,
            currentFile,
            // 进度回调
            (percent) => {
                if (currentState === STATES.UPLOADING) {
                    progressFill.style.width = percent + '%';
                    progressText.textContent = `上传中... ${percent}%`;

                    if (percent >= 100) {
                        setState(STATES.CONVERTING);
                    }
                }
            }
        )
            .then((data) => {
                downloadInfo = {
                    url: data.data.download_url,
                    filename:
                        currentDirection === 'word-to-pdf'
                            ? currentFile.name.replace(/\.(docx|doc)$/i, '.pdf')
                            : currentFile.name.replace(/\.pdf$/i, '.docx'),
                };

                const targetFormat =
                    currentDirection === 'word-to-pdf' ? 'PDF' : 'Word';

                setState(STATES.COMPLETED, {
                    detail: `${currentFile.name} → ${downloadInfo.filename}`,
                    btnText: `下载 ${targetFormat} 文件`,
                });
            })
            .catch((err) => {
                setState(STATES.ERROR, {
                    message: err.message || '转换失败，请重试',
                });
            });
    }

    // "开始转换" 按钮
    btnStartConvert.addEventListener('click', startConvert);

    // 在 FILE_SELECTED 状态下点击 drop-zone 也触发转换（重新选文件）
    dropZone.addEventListener('click', (e) => {
        if (currentState === STATES.FILE_SELECTED) {
            // 已经有文件了，点击 drop-zone 是重新选择文件，不自动转换
            // 用户需要点"开始转换"按钮
            return;
        }
    });

    // ---------- 下载 ----------
    btnDownload.addEventListener('click', () => {
        if (downloadInfo) {
            apiDownload(downloadInfo.url, downloadInfo.filename);
        }
    });

    // ---------- 重新转换 ----------
    btnNewConvert.addEventListener('click', () => {
        setState(STATES.IDLE);
    });

    // ---------- 重试 ----------
    btnRetry.addEventListener('click', () => {
        if (currentFile) {
            setState(STATES.FILE_SELECTED);
        } else {
            setState(STATES.IDLE);
        }
    });

    // ---------- 初始化 ----------
    updateDropZoneHint();
    console.log('PDF2Word Converter 已就绪');
})();
