"""路由层依赖的构造。

**为什么这些工厂放在 api 层而不是 services：** ``services`` 有一条硬规矩是
"不 import fastapi"。构建依赖需要 :func:`Depends`，所以只能待在 api 层。
"""

from __future__ import annotations

import secrets
import threading
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.cache.content import ContentCache
from app.core.config import Settings, get_settings
from app.core.errors import AppError, ErrorCode
from app.crawler.guard import SiteGuard
from app.crawler.registry import SiteRegistry
from app.crawler.runner import CrawlerRunner
from app.db.session import get_session_factory
from app.models.device import Device
from app.services import activation_service, site_settings
from app.services.warmup_service import WarmupRunner

#: 客户端保存这个令牌，之后每次请求都带上它。
#: 注意：设备身份是**后端签发**的，客户端自报的 device_id 一律不认。
DEVICE_TOKEN_HEADER = "X-Device-Token"

#: 后台管理令牌。它是**运维凭证**，与激活码完全无关：
#: 激活码管"谁能看内容"，它管"谁能管这台机器"。
ADMIN_TOKEN_HEADER = "X-Admin-Token"

#: 把它声明成 OpenAPI 的 security scheme，Swagger 里才会出现 **Authorize** 按钮。
#: 不声明的后果很具体：你在 /docs 里**根本无法**带上这个头，
#: 所有内容接口都只会返回 401，手动测试就只剩写 curl 一条路。
#: ``auto_error=False``：缺失时返回 None，交给业务层报出更准确的错误码。
#: ⚠️ **`scheme_name` 必须给，而且两个必须不同。**
#: 不给的话 FastAPI 用类名（都是 ``"APIKeyHeader"``）当 scheme 名，
#: 于是后者**直接覆盖**前者 —— 后果很具体：
#: OpenAPI 里只剩一个叫 ``APIKeyHeader`` 的 scheme（内容那个被后台那个顶掉了），
#: Swagger 里点内容接口会发 ``X-Admin-Token``，每个请求都 401。
#: 测试里有一条盯着这个（``test_openapi_declares_both_credentials``）。
device_token_header = APIKeyHeader(
    name=DEVICE_TOKEN_HEADER,
    scheme_name="DeviceToken",
    auto_error=False,
    description="激活后由 POST /api/v1/activation/redeem 返回的设备令牌",
)

#: 同样要声明成 security scheme，否则 Swagger 里无处可填这个头。
admin_token_header = APIKeyHeader(
    name=ADMIN_TOKEN_HEADER,
    scheme_name="AdminToken",
    auto_error=False,
    description="后台管理令牌（.env 里的 PLOVE_ADMIN_TOKEN）",
)


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

    参数一律用**标量**而不是 ``Settings`` 对象：这个函数被 ``lru_cache`` 包着，
    而 Pydantic 模型默认不可哈希（放进去会直接报 ``unhashable``）。
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
        # 传的是**模块级函数**（不是闭包）——它只是个回调，不参与上面那个 lru_cache 的键。
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
    """目录内容的缓存。**必须进程内共用** —— 每次请求造一个就等于没有缓存。"""
    # 优先读取持久化数据库配置
    enabled = settings.cache_enabled
    try:
        from app.db.session import SessionLocal
        from app.models.system_setting import SystemSetting
        import json
        with SessionLocal() as session:
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


# ------------------------------------------------------------------ 主动预热

#: 进程内唯一的预热执行器。它**必须唯一**：定时任务与"立即刷新"按钮
#: 打的是同一个对象，否则后台看到的"上次预热时间"永远来自空白实例。
_warmup: WarmupRunner | None = None
_warmup_lock = threading.Lock()


def get_warmup_runner(settings: Settings = Depends(get_settings)) -> WarmupRunner:
    global _warmup
    with _warmup_lock:
        if _warmup is None:
            enabled = settings.warmup_enabled
            try:
                from app.db.session import SessionLocal
                from app.models.system_setting import SystemSetting
                import json
                with SessionLocal() as session:
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


# ------------------------------------------------------------------ 数据库


def get_db() -> Iterator[Session]:
    """每个请求一个会话：成功才 commit，出异常回滚。

    注意**不要在 service 里 commit** —— 一次请求就是一个事务边界，
    事务归这里管，业务层只管改对象。

    但它**不够**：这里的 ``commit`` 跑在依赖清理阶段，也就是**响应送出之后**
    （这是框架的清理时机，不是我们能选的）。所以任何"客户端拿到 200 就会马上去读"
    的写接口，都要额外调一次 :func:`commit_now`。
    """
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def commit_now(db: Session) -> None:
    """写操作**显式提交**，让 200 真正意味着"已经落地"。

    为什么不能只依赖 :func:`get_db` 的自动提交：那跑在响应送出之后，
    于是"客户端拿到 200 → 立刻发下一个请求"这条最自然的时序里，
    第二个请求有可能还读不到第一个请求的写。两处真实事故：

    * 运维点完"停用"，列表里那一行偶尔还是旧的，他会以为没生效再点一次；
    * 用户点"在此设备继续"抢回活跃位，紧接着的页面重新加载又回了
      ``SESSION_KICKED`` —— 界面再弹一次"已在别的设备上使用"，
      看起来像点了没用。后者是**必然**会碰上的：抢回活跃位之后
      客户端一定会立刻重新拉数据，中间只隔一个响应往返。

    所以：**写接口的承诺是"客户端读到 200 时，变更已经落库"。**
    """
    db.commit()


def get_site_settings(db: Session = Depends(get_db)) -> site_settings.SiteSettingsStore:
    """源开关的进程内快照（按 TTL 刷新）。

    后台的写操作会再显式 ``refresh(force=True)`` 一次 ——
    "点了就生效"不能等 TTL，否则运维会以为没点上而再点一次。
    """
    store = site_settings.store()
    store.refresh(db)
    return store


# ------------------------------------------------------------------ 守卫


def require_device(
    db: Session = Depends(get_db),
    token: str | None = Security(device_token_header),
) -> Device:
    """内容接口的守卫：必须是**当前活跃设备**才放行。

    挂在 router 上（``dependencies=[Depends(require_device)]``）而不是塞进每个路由，
    这样加接口时不会忘记加鉴权 —— 忘记加鉴权是这类系统最常见的事故。
    """
    device = activation_service.require_active(db, token)
    # 顺手刷新“源开关”的快照（带 5 秒 TTL）。
    # 为什么挂在这里：它守在所有内容接口上（router 级），是唯一
    # **不会漏掉新增路由**的刷新点；而且这里手里已经有一个 Session。
    # 漏刷新的后果很具体：后台把源关掉了，内容接口却还在继续供应它。
    site_settings.store().refresh(db)
    return device


def require_admin(
    settings: Settings = Depends(get_settings),
    token: str | None = Security(admin_token_header),
) -> None:
    """后台接口的守卫。同样挂在 router 上。

    两条刻意的处理：

    * **没配令牌就一律拒绝。** 空令牌必须永远不能通过 —— 否则一个忘了配
      ``PLOVE_ADMIN_TOKEN`` 的部署就等于把后台裸奔在公网上。
    * **用 ``compare_digest`` 比较。** 普通 ``==`` 会在第一个不同的字符处
      提前返回，从响应时间上能一个字符一个字符地把令牌猜出来。
    """
    expected = settings.admin_token
    if not expected:
        raise AppError(
            ErrorCode.FORBIDDEN,
            "后台接口未启用：请先在 .env 里设置 PLOVE_ADMIN_TOKEN",
        )
    if not token or not secrets.compare_digest(token, expected):
        raise AppError(ErrorCode.UNAUTHORIZED, "后台令牌不正确")
