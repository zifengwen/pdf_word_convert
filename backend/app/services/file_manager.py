"""文件生命周期管理 - 上传保存、token 管理、过期清理"""

import asyncio
import json
import os
import time
import uuid
from typing import Optional

from ..config import settings


class FileManager:
    """管理上传文件和转换结果的生命周期"""

    def __init__(self):
        self._registry: dict = {}  # token -> 文件元信息
        self._registry_path = os.path.join(settings.UPLOAD_DIR, "registry.json")
        self._cleanup_task = None
        self._load_registry()

    # ---------- 注册表持久化 ----------

    def _load_registry(self):
        """从磁盘加载注册表（用于 crash 恢复）"""
        try:
            if os.path.exists(self._registry_path):
                with open(self._registry_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                now = time.time()
                # 只恢复未过期的记录
                for token, info in data.items():
                    if info.get("expires_at", 0) > now:
                        self._registry[token] = info
        except Exception:
            pass

    def _save_registry(self):
        """将注册表写入磁盘"""
        try:
            os.makedirs(os.path.dirname(self._registry_path), exist_ok=True)
            with open(self._registry_path, "w", encoding="utf-8") as f:
                json.dump(self._registry, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---------- 文件操作 ----------

    def save_upload(self, file_data: bytes, original_name: str) -> dict:
        """
        保存上传文件到磁盘。
        返回 {token, original_name, saved_path, size}
        """
        token = str(uuid.uuid4())
        # 使用 UUID 作为存储文件名，防止路径遍历和冲突
        _, ext = os.path.splitext(original_name)
        saved_name = f"{token}{ext}"
        saved_path = os.path.join(settings.UPLOAD_DIR, saved_name)

        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        with open(saved_path, "wb") as f:
            f.write(file_data)

        file_size = len(file_data)

        self._registry[token] = {
            "original_name": original_name,
            "saved_path": saved_path,
            "size": file_size,
            "direction": None,
            "converted_path": None,
            "created_at": time.time(),
            "expires_at": time.time() + settings.FILE_EXPIRY_MINUTES * 60,
        }
        self._save_registry()

        return {
            "token": token,
            "original_name": original_name,
            "saved_path": saved_path,
            "size": file_size,
        }

    def register_conversion(
        self, token: str, converted_path: str, direction: str
    ):
        """记录转换完成信息"""
        if token in self._registry:
            self._registry[token]["converted_path"] = converted_path
            self._registry[token]["direction"] = direction
            self._registry[token]["expires_at"] = (
                time.time() + settings.FILE_EXPIRY_MINUTES * 60
            )
            self._save_registry()

    def get_info(self, token: str) -> Optional[dict]:
        """根据 token 获取文件元信息"""
        info = self._registry.get(token)
        if info is None:
            return None
        # 检查是否过期
        if time.time() > info.get("expires_at", 0):
            self._delete_files(token)
            return None
        return info

    def get_converted_path(self, token: str) -> Optional[str]:
        """获取转换结果文件路径"""
        info = self.get_info(token)
        if info is None:
            return None
        path = info.get("converted_path")
        if path and os.path.exists(path):
            return path
        return None

    # ---------- 清理 ----------

    def _delete_files(self, token: str):
        """删除指定 token 关联的所有文件"""
        info = self._registry.pop(token, None)
        if info:
            for key in ("saved_path", "converted_path"):
                path = info.get(key)
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
            self._save_registry()

    def _cleanup_expired(self):
        """清理所有过期文件"""
        now = time.time()
        expired_tokens = [
            token
            for token, info in self._registry.items()
            if now > info.get("expires_at", 0)
        ]
        for token in expired_tokens:
            self._delete_files(token)

        # 同时清理 uploads 和 converted 目录中的孤立文件
        for directory in (settings.UPLOAD_DIR, settings.CONVERTED_DIR):
            if not os.path.isdir(directory):
                continue
            for filename in os.listdir(directory):
                if filename in (".gitkeep", "registry.json"):
                    continue
                filepath = os.path.join(directory, filename)
                try:
                    mtime = os.path.getmtime(filepath)
                    age_minutes = (now - mtime) / 60
                    if age_minutes > settings.FILE_EXPIRY_MINUTES:
                        os.remove(filepath)
                except OSError:
                    pass

    async def _cleanup_loop(self):
        """后台定期清理任务"""
        while True:
            try:
                await asyncio.sleep(settings.CLEANUP_INTERVAL_MINUTES * 60)
                self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    def start_cleanup(self):
        """启动后台清理任务"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    def stop_cleanup(self):
        """停止后台清理任务"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None


# 全局单例
file_manager = FileManager()
