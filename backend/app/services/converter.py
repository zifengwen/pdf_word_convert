"""LibreOffice 转换引擎 - 子进程调用、锁、超时处理、加密 PDF 预处理"""

import asyncio
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Optional

import fitz  # PyMuPDF — 用于检测/解密 PDF

from ..config import settings

logger = logging.getLogger("pdf2word")


class LibreOfficeConverter:
    """封装 LibreOffice headless 转换逻辑"""

    def __init__(self):
        self._libreoffice_path: Optional[str] = None
        self._available: Optional[bool] = None
        self._lock = asyncio.Lock()
        self._detect_binary()

    # ---------- 二进制检测 ----------

    def _detect_binary(self):
        """自动探测 LibreOffice 路径（不启动子进程验证，避免卡死）"""
        paths_to_try = []

        # 1. 配置中指定的路径
        if settings.LIBREOFFICE_PATH and settings.LIBREOFFICE_PATH != "soffice":
            paths_to_try.append(settings.LIBREOFFICE_PATH)

        # 2. PATH 中的 soffice / libreoffice
        for name in ("soffice", "libreoffice"):
            found = shutil.which(name)
            if found:
                paths_to_try.append(found)

        # 3. Windows 常见安装路径
        if sys.platform == "win32":
            for base in (
                r"C:\Program Files\LibreOffice\program\soffice.exe",
                r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
            ):
                if os.path.exists(base):
                    paths_to_try.append(base)

        # 4. Linux/macOS 常见路径
        for path in (
            "/usr/bin/soffice",
            "/usr/bin/libreoffice",
            "/usr/local/bin/soffice",
            "/usr/local/bin/libreoffice",
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        ):
            if os.path.exists(path):
                paths_to_try.append(path)

        # 直接使用第一个找到的可执行文件（不再运行 --version 避免卡死）
        for path in paths_to_try:
            if os.path.isfile(path) or shutil.which(path):
                self._libreoffice_path = path
                self._available = True
                return

        self._libreoffice_path = None
        self._available = False

    def is_available(self) -> bool:
        """返回 LibreOffice 是否可用"""
        return self._available is True

    @property
    def libreoffice_path(self) -> Optional[str]:
        """返回检测到的 LibreOffice 路径"""
        return self._libreoffice_path

    # ---------- 转换核心 ----------

    async def convert(self, input_path: str, direction: str) -> str:
        """
        执行文件转换。
        direction: 'word-to-pdf' 或 'pdf-to-word'
        返回转换后的输出文件路径。
        """
        if not self._available:
            raise LibreOfficeNotFoundError(
                "LibreOffice 不可用。请安装 LibreOffice 后重试。\n"
                "下载地址: https://www.libreoffice.org/download/"
            )

        target_format = "pdf" if direction == "word-to-pdf" else "docx"
        is_pdf_input = (direction == "pdf-to-word")

        # 确保输出目录存在
        os.makedirs(settings.CONVERTED_DIR, exist_ok=True)

        # 使用 asyncio Lock 串行化（LibreOffice 不支持真正并发）
        async with self._lock:
            output_path = await self._run_conversion(input_path, target_format, is_pdf_input)

        # PDF→Word：微调文本框宽度（仅含文字的形状，放大 5%）
        if is_pdf_input and output_path:
            try:
                from ..utils.docx_fixer import fix_docx
                fix_docx(output_path)
            except Exception:
                pass

        return output_path

    def _get_executable_path(self) -> str:
        """获取最适合 headless 模式的可执行文件路径"""
        if sys.platform != "win32":
            return self._libreoffice_path

        # 在 Windows 上优先使用 soffice.com（控制台版本），headless 模式更稳定
        if self._libreoffice_path:
            com_path = self._libreoffice_path.replace(".exe", ".com")
            if os.path.exists(com_path):
                return com_path
        return self._libreoffice_path

    # ---------- 加密 PDF 预处理 ----------

    def _handle_encrypted_pdf(self, input_path: str) -> str:
        """
        检测 PDF 是否加密，若是则用 PyMuPDF 另存为无加密副本。
        返回实际用于转换的 PDF 路径（可能是原路径或解密后的临时文件路径）。
        """
        doc = None
        try:
            doc = fitz.open(input_path)

            if doc.is_encrypted:
                logger.info("检测到加密 PDF，尝试用 PyMuPDF 解密: %s", input_path)
                # PyMuPDF 可以处理有所有者密码的 PDF（无需用户密码）
                # 只要文件能打开，就说明不需要用户密码，另存即可移除加密
                decrypted_fd, decrypted_path = tempfile.mkstemp(suffix=".pdf")
                os.close(decrypted_fd)
                doc.save(decrypted_path, encryption=fitz.PDF_ENCRYPT_NONE)
                doc.close()
                doc = None
                logger.info("PDF 解密成功: %s -> %s", input_path, decrypted_path)
                # 注册临时文件以便后续清理
                if not hasattr(self, '_temp_files'):
                    self._temp_files = []
                self._temp_files.append(decrypted_path)
                return decrypted_path

            doc.close()
            doc = None
            return input_path  # 未加密，直接使用原文件

        except Exception as e:
            if doc is not None:
                try:
                    doc.close()
                except Exception:
                    pass
            error_msg = str(e)
            if "password" in error_msg.lower() or "encrypt" in error_msg.lower():
                raise EncryptedPDFError(
                    "该 PDF 文件已加密且需要密码才能打开。"
                    "请先移除 PDF 密码保护后再尝试转换。"
                )
            # 其他错误（如 PDF 损坏）→ 原样抛出，让 LibreOffice 尝试处理
            logger.warning("PyMuPDF 预处理 PDF 时出错: %s，将直接使用 LibreOffice 尝试", error_msg)
            return input_path

    def _cleanup_temp_files(self):
        """清理解密产生的临时文件"""
        if hasattr(self, '_temp_files'):
            for path in self._temp_files:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except OSError:
                    pass
            self._temp_files.clear()

    async def _run_conversion(self, input_path: str, target_format: str, is_pdf_input: bool = False) -> str:
        """实际执行 LibreOffice 子进程调用"""
        # 加密 PDF 预处理：用 PyMuPDF 解密后再交给 LibreOffice
        actual_input = input_path
        if is_pdf_input:
            actual_input = self._handle_encrypted_pdf(input_path)

        # 为每次转换创建独立临时 profile（避免锁冲突）
        temp_profile = tempfile.mkdtemp(prefix="lo_profile_")

        # 使用 LibreOffice 输出目录参数来控制输出位置
        output_dir = settings.CONVERTED_DIR

        # 选择最合适的可执行文件（Windows 上优先 soffice.com）
        executable = self._get_executable_path()

        # LibreOffice 的 program 目录（Windows 下需要加到 PATH 中）
        program_dir = os.path.dirname(executable)

        cmd = [
            executable,
            "--headless",
            "--norestore",
            "--nofirststartwizard",
            f"-env:UserInstallation=file:///{temp_profile.replace(os.sep, '/')}",
        ]

        # PDF 输入时必须指定 infilter，否则 LibreOffice 会错误地导入为 Draw 文档
        if is_pdf_input:
            cmd.extend(["--infilter=writer_pdf_import"])

        cmd.extend([
            "--convert-to",
            target_format,
            "--outdir",
            output_dir,
            actual_input,
        ])

        # 构建环境变量：确保 LibreOffice 能找到自己的库
        env = os.environ.copy()
        # 将 LibreOffice program 目录加到 PATH 最前面
        if program_dir and os.path.isdir(program_dir):
            env["PATH"] = program_dir + os.pathsep + env.get("PATH", "")
        # 设置 UNO_PATH 帮助 LibreOffice 定位组件
        env["UNO_PATH"] = program_dir

        loop = asyncio.get_event_loop()

        def _run():
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=settings.CONVERSION_TIMEOUT_SECONDS,
                env=env,
            )

        try:
            result = await loop.run_in_executor(None, _run)
        except subprocess.TimeoutExpired:
            self._kill_lingering_processes()
            raise ConversionTimeoutError(
                f"转换超时（{settings.CONVERSION_TIMEOUT_SECONDS}秒），请重试"
            )
        finally:
            # 清理临时 profile
            try:
                shutil.rmtree(temp_profile, ignore_errors=True)
            except Exception:
                pass
            # 清理解密产生的临时 PDF 文件
            self._cleanup_temp_files()

        if result.returncode != 0:
            # 提取错误信息
            stderr = result.stderr or ""
            stderr_lower = stderr.lower()
            if "encrypted" in stderr_lower or "can't be opened" in stderr_lower:
                raise EncryptedPDFError(
                    "该 PDF 文件已加密或受保护，LibreOffice 无法打开。\n"
                    "请尝试以下方法：\n"
                    "1. 使用 Adobe Acrobat 或在线工具移除 PDF 密码保护\n"
                    "2. 使用 qpdf 命令解密: qpdf --decrypt input.pdf output.pdf\n"
                    "3. 确认 PDF 文件未被数字签名锁定"
                )
            raise ConversionError(
                f"转换失败 (exit code {result.returncode}): {stderr[:300]}"
            )

        # 推断输出文件名
        # 优先用 actual_input 的 basename（LibreOffice 以此命名），再尝试原 input_path
        actual_basename = os.path.splitext(os.path.basename(actual_input))[0]
        input_basename = os.path.splitext(os.path.basename(input_path))[0]
        output_filename = f"{actual_basename}.{target_format}"
        output_path = os.path.join(output_dir, output_filename)

        if not os.path.exists(output_path):
            output_path = self._find_output(output_dir, actual_basename, target_format)
        if not output_path or not os.path.exists(output_path):
            # 再尝试原文件名的 basename
            output_path = self._find_output(output_dir, input_basename, target_format)

        if not output_path or not os.path.exists(output_path):
            raise ConversionError(
                f"转换后的文件未找到。stderr: {result.stderr[:300] if result.stderr else '无'}"
            )

        return output_path

    def _find_output(
        self, output_dir: str, input_basename: str, target_format: str
    ) -> Optional[str]:
        """在输出目录中查找匹配的输出文件"""
        if not os.path.isdir(output_dir):
            return None
        for filename in os.listdir(output_dir):
            if filename.startswith(input_basename) and filename.endswith(
                f".{target_format}"
            ):
                return os.path.join(output_dir, filename)
        return None

    def _kill_lingering_processes(self):
        """强制结束卡死的 LibreOffice 进程"""
        try:
            import psutil

            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    name = (proc.info.get("name") or "").lower()
                    if "soffice" in name:
                        proc.kill()
                except Exception:
                    continue
        except ImportError:
            # psutil 不可用，使用平台命令
            try:
                if sys.platform == "win32":
                    os.system("taskkill /F /IM soffice.exe 2>nul")
                else:
                    os.system("pkill -9 soffice 2>/dev/null")
            except Exception:
                pass


# ---------- 自定义异常 ----------

class ConversionError(Exception):
    """转换失败异常"""
    pass


class ConversionTimeoutError(Exception):
    """转换超时异常"""
    pass


class EncryptedPDFError(Exception):
    """PDF 已加密且需要密码才能打开"""
    pass


class LibreOfficeNotFoundError(Exception):
    """LibreOffice 未找到异常"""
    pass


# 全局单例
converter = LibreOfficeConverter()
