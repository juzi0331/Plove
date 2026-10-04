"""图片防盗链代理与持久化缓存服务子包。

模块结构：
- config: 代理配置持久化与规则注册
- cache: 磁盘持久化缓存目录管理、统计与清理
- transform: 多级动态图片解密调度链与站点插件适配
- fetch: 代理请求发起、安全校验与缓存协同
"""

from __future__ import annotations

from app.services.image_proxy.cache import (
    CACHE_DIR,
    _hash_url,
    clear_proxy_cache,
    ensure_cache_dir,
    get_proxy_stats,
)
from app.services.image_proxy.config import (
    PROXY_CONFIG_KEY,
    _cached_config,
    get_image_proxy_config,
    register_or_update_decryption_rule,
    update_image_proxy_config,
)
from app.services.image_proxy.fetch import (
    _is_safe_url,
    fetch_image_with_cache,
)
from app.services.image_proxy.transform import (
    _crawler_base_dir,
    _crawler_sites_dir,
    _decode_image_dynamic,
    _decode_image_via_sites,
    _decrypt_with_rule,
    _get_crawler_sites_dir,
    _get_site_decoder,
    _site_decoders,
    test_decrypt_image,
)

__all__ = [
    "CACHE_DIR",
    "PROXY_CONFIG_KEY",
    "_cached_config",
    "_crawler_base_dir",
    "_crawler_sites_dir",
    "_decode_image_dynamic",
    "_decode_image_via_sites",
    "_decrypt_with_rule",
    "_get_crawler_sites_dir",
    "_get_site_decoder",
    "_hash_url",
    "_is_safe_url",
    "_site_decoders",
    "clear_proxy_cache",
    "ensure_cache_dir",
    "fetch_image_with_cache",
    "get_image_proxy_config",
    "get_proxy_stats",
    "register_or_update_decryption_rule",
    "test_decrypt_image",
    "update_image_proxy_config",
]
