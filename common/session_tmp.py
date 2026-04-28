import hashlib
import os
import shutil


def _session_dir(session_id: str) -> str:
    h = hashlib.sha256(session_id.encode()).hexdigest()[:8]
    return os.path.join("tmp", h)


def get_session_tmp_dir(session_id: str) -> str:
    """创建并返回会话专属 tmp 目录路径。"""
    path = _session_dir(session_id)
    os.makedirs(path, exist_ok=True)
    return path


def cleanup_session_tmp(session_id: str):
    """删除会话 tmp 目录及其所有内容。"""
    path = _session_dir(session_id)
    if os.path.exists(path):
        shutil.rmtree(path, ignore_errors=True)
