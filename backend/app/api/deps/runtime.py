"""运行时核心单例与缓存依赖（爬虫注册表、内容缓存、预热执行器）。"""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import threading

from fastapi import Depends

from app.cache.content import ContentCache
from app.core.config import Settings, get_settings
from app.crawler.guard import SiteGuard
from app.crawler.registry import SiteRegistry
from app.crawler.runner import CrawlerRunner
from app.services import site_settings
from app.services.warmup_service import WarmupRunner


# ------------------------------------------------------------------ 爬虫

@lru_cache(maxsize=8)
def _registry_for(
    sites_dir: str,
    timeout: float,
    timeout_play: float,
    max_concurrency: int,
    queue_timeout: float,
    fail_threshold: int,
    reset_seconds: float,
    global_max_concurrency: int,
) -> SiteRegistry:
    """按配置造注册表。

    参数一律用标量而不是 Settings 对象：这个函数被 lru_cache 包着，
    而 Pydantic 模型默认不可哈希（放进去会直接报 unhashable）。
    顺带一个好处：配置变了会自然造出新的注册表，不会拿旧配置继续跑。
    """
    runner = CrawlerRunner(Path(sites_dir), timeout=timeout, timeout_play=timeout_play)

    def guard_factory(key: str) -> SiteGuard:
        return SiteGuard(
            key,
            max_concurrency=max_concurrency,
            queue_timeout=queue_timeout,
            fail_threshold=fail_threshold,
            reset_seconds=reset_seconds,
        )

    return SiteRegistry(
        runner,
        guard_factory=guard_factory,
        max_global_concurrency=global_max_concurrency,
        # 被后台停用的源：注册表是唯一通往爬虫的关口，拦在这里就不会漏掉新加的调用路径。
        # 传的是模块级函数（不是闭包）——它只是个回调，不参与上面那个 lru_cache 的键。
        disabled_keys_provider=site_settings.disabled_keys,
    )


def get_registry(settings: Settings = Depends(get_settings)) -> SiteRegistry:
    """进程内共用同一个注册表 —— meta 的缓存、每站的守护都在它身上，
    每次重建就白缓存了（而且熔断计数会被清零）。"""
    return _registry_for(
        str(settings.sites_dir),
        settings.crawler_timeout,
        settings.crawler_timeout_play,
        settings.site_max_concurrency,
        settings.site_queue_timeout,
        settings.breaker_fail_threshold,
        settings.breaker_reset_seconds,
        settings.global_max_concurrency,
    )


# ------------------------------------------------------------------ 内容缓存

@lru_cache(maxsize=8)
def _content_cache_for(
    ttl_home: float,
    ttl_category: float,
    ttl_detail: float,
    maxsize: int,
    enabled: bool = False,
) -> ContentCache:
    return ContentCache(
        ttl_home=ttl_home,
        ttl_category=ttl_category,
        ttl_detail=ttl_detail,
        maxsize=maxsize,
        enabled=enabled,
    )


def get_content_cache(settings: Settings = Depends(get_settings)) -> ContentCache:
    """目录内容的缓存。必须进程内共用 —— 每次请求造一个就等于没有缓存。"""
    # 优先读取持久化数据库配置
    enabled = settings.cache_enabled
    try:
        from app.db.session import get_session_factory
        from app.models.system_setting import SystemSetting
        with get_session_factory()() as session:
            row = session.query(SystemSetting).filter_by(key="content_cache_config").first()
            if row and row.value_json:
                data = json.loads(row.value_json)
                if "cache_enabled" in data:
                    enabled = bool(data["cache_enabled"])
    except Exception:
        pass

    return _content_cache_for(
        settings.cache_ttl_home,
        settings.cache_ttl_category,
        settings.cache_ttl_detail,
        settings.cache_maxsize,
        enabled,
    )


# ------------------------------------------------------------------ 主动预热

#: 进程内唯一的预热执行器。它必须唯一：定时任务与"立即刷新"按钮
#: 打的是同一个对象，否则后台看到的"上次预热时间"永远来自空白实例。
_warmup: WarmupRunner | None = None
_warmup_lock = threading.Lock()


def get_warmup_runner(settings: Settings = Depends(get_settings)) -> WarmupRunner:
    global _warmup
    with _warmup_lock:
        if _warmup is None:
            enabled = settings.warmup_enabled
            try:
                from app.db.session import session_scope
                from app.models.system_setting import SystemSetting
                with session_scope() as session:
                    row = session.query(SystemSetting).filter_by(key="warmup_config").first()
                    if row and row.value_json:
                        data = json.loads(row.value_json)
                        if "warmup_enabled" in data:
                            enabled = bool(data["warmup_enabled"])
            except Exception:
                pass

            _warmup = WarmupRunner(
                get_registry(settings),
                get_content_cache(settings),
                max_categories=settings.warmup_max_categories,
                enabled=enabled,
                interval_seconds=settings.warmup_interval_seconds,
            )
        return _warmup


def reset_runtime() -> None:
    """丢掉注册表、内容缓存、预热执行器的单例。

    三种时候要用：测试之间隔离；换了爬虫文件后让 meta 重新取；
    改了缓存/守护/预热配置后让新参数生效。
    """
    global _warmup
    with _warmup_lock:
        _warmup = None
    _registry_for.cache_clear()
    _content_cache_for.cache_clear()
    # 丢掉持久化磁盘幽灵缓存，确保测试环境与重置运行时纯净
    try:
        from app.cache.disk_cache import get_disk_store

        get_disk_store().clear()
    except Exception:
        pass
    # 源开关的快照也要清：测试之间不隔离的话，上一个用例停用的源会“幽灵”到下一个用例。
    site_settings.reset_store()
