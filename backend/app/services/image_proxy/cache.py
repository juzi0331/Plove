"""图片代理磁盘缓存与统计清理。"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from app.core.config import BACKEND_DIR
from app.schemas.admin_extended import (
    ImageProxyClearResult,
    ImageProxyStats,
)

CACHE_DIR = BACKEND_DIR / "data" / "img_cache"


def ensure_cache_dir() -> Path:
    """确保本地图片代理缓存目录存在。"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


def _hash_url(url: str) -> str:
    """根据 URL 计算 SHA256 哈希值作为缓存文件名。"""
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()


def get_proxy_stats() -> ImageProxyStats:
    """统计图片代理缓存文件数量与占用空间大小。"""
    cdir = ensure_cache_dir()
    files = list(cdir.glob("*.bin"))
    total_bytes = sum(f.stat().st_size for f in files if f.is_file())
    total_mb = round(total_bytes / (1024 * 1024), 2)
    return ImageProxyStats(
        cached_files=len(files),
        total_size_mb=total_mb,
        cache_dir=str(cdir.resolve()),
    )


def clear_proxy_cache() -> ImageProxyClearResult:
    """清空图片代理缓存。"""
    cdir = ensure_cache_dir()
    stats = get_proxy_stats()
    try:
        shutil.rmtree(cdir)
        ensure_cache_dir()
    except Exception:
        pass
    return ImageProxyClearResult(
        cleared_files=stats.cached_files,
        freed_mb=stats.total_size_mb,
    )
