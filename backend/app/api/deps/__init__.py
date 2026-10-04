"""路由层依赖的构造与对外统一导出。

模块结构：
- auth: 设备鉴权、管理令牌鉴权与代理接口守卫
- db: 请求级数据库会话与即时提交支持
- runtime: 爬虫注册表、内容缓存与预热单例管理器
"""

from __future__ import annotations

from app.api.deps.auth import (
    ADMIN_TOKEN_HEADER,
    DEVICE_TOKEN_HEADER,
    admin_token_header,
    device_token_header,
    require_admin,
    require_device,
    require_proxy_access,
)
from app.api.deps.db import (
    commit_now,
    get_db,
    get_site_settings,
)
from app.api.deps.runtime import (
    _content_cache_for,
    _registry_for,
    _warmup,
    _warmup_lock,
    get_content_cache,
    get_registry,
    get_warmup_runner,
    reset_runtime,
)
from app.core.config import Settings, get_settings

__all__ = [
    "ADMIN_TOKEN_HEADER",
    "DEVICE_TOKEN_HEADER",
    "Settings",
    "_content_cache_for",
    "_registry_for",
    "_warmup",
    "_warmup_lock",
    "admin_token_header",
    "commit_now",
    "device_token_header",
    "get_content_cache",
    "get_db",
    "get_registry",
    "get_settings",
    "get_site_settings",
    "get_warmup_runner",
    "require_admin",
    "require_device",
    "require_proxy_access",
    "reset_runtime",
]
