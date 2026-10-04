"""后台管理基础接口的载荷。

包含系统全局运维状态透视、多源站点管理等基础载荷。
子领域模型已模块化抽取至 admin_cache, admin_code, admin_device，并在本模块保持完全兼容重导出。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# 保持向前兼容重导出
from app.schemas.admin_cache import (
    CacheStats,
    CacheTtl,
    RefreshResult,
    WarmupSiteResult,
    WarmupStatus,
)
from app.schemas.admin_code import (
    CodeActionResult,
    CodeListItem,
    CodeListPayload,
    ExtendRequest,
    IssueCodesRequest,
    IssueCodesResult,
)
from app.schemas.admin_device import (
    DeviceItem,
    DeviceListPayload,
    KickResult,
)


class SiteHealth(BaseModel):
    """单个源的守护状态。"""

    site: str
    state: str = Field(description="closed（正常）/ open（已熔断）/ half_open（探测恢复中）")
    failures: int = Field(description="连续失败次数；任何一次内容调用成功都会清零")
    fail_threshold: int
    retry_after: float | None = Field(default=None, description="熔断中时还有多久冷却完（秒）")
    probing: bool
    max_concurrency: int = Field(description="该源的并发上限")
    reset_seconds: float
    global_limit: int = Field(default=0, description="全站并发上限；0 表示不限")
    probed: bool = Field(
        default=False,
        description="这个源的 meta 取到过没有。新的守护也是 state=closed 且 failures=0，"
        "所以只看那两个字段分不出「从没碰过」和「一直很正常」",
    )


class AdminStatusPayload(BaseModel):
    """后台一眼看全：缓存、预热、每个源的健康。"""

    env: str
    sites: list[SiteHealth] = Field(default_factory=list)
    cache: CacheStats
    warmup: WarmupStatus


# ------------------------------------------------------------------ 站点（源）管理

class AdminSiteItem(BaseModel):
    """后台「站点管理」里的一行。

    它比用户端的 ``SiteMeta`` 多三样东西：**开关、顺序、健康** ——
    这三样正好是"要不要动它、动完对不对"的全部依据。
    """

    key: str
    name: str = Field(description="源自己声明的名字；meta 取不到时退化成 key")
    enabled: bool = Field(
        description="是否对用户可见。停用后用户端列表里没有它，内容接口回 SITE_DISABLED"
    )
    sort_order: int = Field(description="用户端列表里的顺序，小的在前")
    note: str = ""
    version: str = ""
    mode: str = Field(default="direct", description="direct = 前端直连源站；proxy = 需要后端流代理")
    capabilities: list[str] = Field(default_factory=list, description="源声明支持的命令")
    meta_error: str | None = Field(
        default=None,
        description="meta 取不到的原因。**非空不代表这个源坏了**，"
        "但它是排查问题时第一个该看的东西（比如爬虫文件刚上传、还没跑通）",
    )
    health: SiteHealth
    proxy_enabled: bool = Field(default=False, description="是否为该站点开启独立代理")
    proxy_url: str = Field(default="", description="该站点使用的代理地址")
    proxy_node_id: str = Field(default="", description="绑定的代理节点 ID")


class AdminSiteListPayload(BaseModel):
    """站点管理页的全部数据：**包括被停用的源**（运维要能看到自己关掉了什么）。"""

    sites: list[AdminSiteItem] = Field(default_factory=list)


class AdminSiteOrderRequest(BaseModel):
    """重排用户端的站点顺序。

    给的是**完整顺序**，不是单条改动：这样一次提交就是一个一致的最终状态，
    不会出现"改到一半"的中间态（单条改动最怕的就是中途失败）。
    """

    keys: list[str] = Field(min_length=1, description="按用户端要显示的顺序列出全部 key")


class AdminSiteActionResult(BaseModel):
    """启用 / 停用 / 重排之后的回执：说一句 + 回带上这一行。"""

    message: str
    site: AdminSiteItem


__all__ = [
    "SiteHealth",
    "AdminStatusPayload",
    "AdminSiteItem",
    "AdminSiteListPayload",
    "AdminSiteOrderRequest",
    "AdminSiteActionResult",
    # 重导出
    "CacheTtl",
    "CacheStats",
    "WarmupSiteResult",
    "WarmupStatus",
    "RefreshResult",
    "CodeListItem",
    "CodeListPayload",
    "IssueCodesRequest",
    "IssueCodesResult",
    "ExtendRequest",
    "CodeActionResult",
    "DeviceItem",
    "DeviceListPayload",
    "KickResult",
]
