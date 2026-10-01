"""后台管理接口的载荷。

分三块：

1. **看一眼**：``AdminStatusPayload``（缓存 / 预热 / 每个源的健康）；
2. **刷一次**：``RefreshResult``；
3. **动手**：激活码与设备的增改（发码、停用、延长、看设备、踢设备）。

第三块是后加的，但**契约先定、界面后做**这条规矩没变 —— 界面反过来推着接口变形
是这类系统里最常见的技术债。

### 一条贯穿全文件的原则

**设备令牌（``Device.token``）永远不以明文出现在任何载荷里。**
它是客户端凭证、等于密码；后台只需要能区分"是哪一台"，
所以只给 ``token_prefix``。给一个"查看明文"的功能就等于多一个泄露面，
而这个需求本身不存在。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class CacheTtl(BaseModel):
    """三类内容的缓存时长（秒）。0 表示该类缓存已关闭。"""

    home: float
    category: float
    detail: float


class CacheStats(BaseModel):
    """缓存现状。``hits`` / ``misses`` 是进程启动以来的累计值。"""

    size: int = Field(description="当前条目数")
    maxsize: int
    hits: int
    misses: int
    inflight: int = Field(description="正在合并中的 key 数（防击穿那一层）")
    ttl: CacheTtl
    disk: dict[str, Any] | None = Field(default=None, description="L2 磁盘持久化缓存统计")


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


class WarmupSiteResult(BaseModel):
    """一次预热里某个源的结果。"""

    site: str
    ok: bool
    home_items: int = Field(default=0, description="首页预热回来的推荐条数")
    categories: int = Field(default=0, description="成功预热的分类个数")
    seconds: float = 0.0
    error: str | None = Field(default=None, description="失败原因，形如 ``UPSTREAM_TIMEOUT: …``")


class WarmupStatus(BaseModel):
    """主动预热的状态。``last_*`` 为空表示这个进程还从没跑过。"""

    enabled: bool
    running: bool
    interval_seconds: float
    last_reason: str | None = None
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    last_seconds: float | None = None
    sites: list[WarmupSiteResult] = Field(default_factory=list)


class AdminStatusPayload(BaseModel):
    """后台一眼看全：缓存、预热、每个源的健康。"""

    env: str
    sites: list[SiteHealth] = Field(default_factory=list)
    cache: CacheStats
    warmup: WarmupStatus


# ------------------------------------------------------------------ 激活码

class CodeListItem(BaseModel):
    """后台列表里的一行激活码。"""

    id: int
    code: str
    note: str = ""
    duration_hours: int = Field(description="发码时给的时长（小时）—— **历史记录**，不是当前剩余")
    created_at: datetime
    activated_at: datetime | None = Field(default=None, description="首次激活时间；为空 = 还没被用过")
    expires_at: datetime | None = Field(default=None, description="到期时间；为空 = 还没开始计时")
    disabled_at: datetime | None = Field(default=None, description="停用时间；非空 = 这个码现在用不了")
    remaining_seconds: int = Field(
        default=0,
        description="还剩多少秒。**0 有两种含义**：还没激活（``activated_at`` 为空），"
        "或者已经到期了。界面必须结合 ``activated_at`` 才能说清是哪种",
    )
    device_count: int = Field(default=0, description="这个码用过几台设备")
    max_devices: int = Field(default=1, description="最多允许绑定的设备数（仅后台可见）")
    active_device_name: str | None = Field(default=None, description="当前活跃的那台设备名")

    @property
    def is_disabled(self) -> bool:  # pragma: no cover - 方便 Python 侧读
        return self.disabled_at is not None


class CodeListPayload(BaseModel):
    """激活码列表（分页）。"""

    codes: list[CodeListItem] = Field(default_factory=list)
    total: int = Field(default=0, description="**满足搜索条件的总数**，不是本页条数")
    page: int = 1
    page_size: int = 20


class IssueCodesRequest(BaseModel):
    """发码。``hours`` / ``days`` 二选一。"""

    hours: int | None = Field(default=None, ge=1, le=24 * 365)
    days: int | None = Field(default=None, ge=1, le=365)
    count: int = Field(default=1, ge=1, le=50, description="一次发几个（上限 50，防止手滑发出 5000 个）")
    max_devices: int = Field(default=1, ge=1, le=100, description="最多允许几台设备使用该码（对用户端严格保密）")
    note: str = Field(default="", max_length=255, description="备注：发给谁 / 哪一批")

    @model_validator(mode="after")
    def _exactly_one_duration(self) -> IssueCodesRequest:
        if (self.hours is None) == (self.days is None):
            raise ValueError("hours 与 days 必须给一个、且只能给一个")
        return self

    @property
    def total_hours(self) -> int:
        return self.hours if self.hours is not None else (self.days or 0) * 24


class IssueCodesResult(BaseModel):
    """发码的回执。**码本身一定要回给调用方** —— 它是唯一的交付物。"""

    codes: list[str] = Field(default_factory=list)
    duration_hours: int
    note: str = ""


class ExtendRequest(BaseModel):
    """延长时长。**只能加时间，不能减** —— 减时间应该用停用。"""

    hours: int = Field(ge=1, le=24 * 365)


class CodeActionResult(BaseModel):
    """停用 / 启用 / 延长之后的回执：说明 + 变更后的那一行。

    回带整行而不是只回一个 ``ok``：界面可以直接用它刷新那一行，
    不用再多发一次列表请求（也就不会出现"操作成功了但列表还是旧值"）。
    """

    message: str
    code: CodeListItem


# ------------------------------------------------------------------ 设备

class DeviceItem(BaseModel):
    """一台设备。**没有 token 字段，只有掩码前缀**（见文件头）。"""

    id: int
    name: str = ""
    token_prefix: str = Field(description="令牌前 6 位，只为让后台能区分是哪一台")
    created_at: datetime
    last_seen_at: datetime = Field(description="最后一次心跳/请求时间")
    is_active: bool = Field(description="它是不是当前占着活跃位的那台")


class DeviceListPayload(BaseModel):
    """某个码用过的所有设备。"""

    devices: list[DeviceItem] = Field(default_factory=list)
    active_device_id: int | None = None


class KickResult(BaseModel):
    """踢设备的回执。"""

    message: str
    code: CodeListItem


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


# ------------------------------------------------------------------ 状态与刷新

class RefreshResult(BaseModel):
    """``POST /admin/cache/refresh`` 的回执。

    ``started=False`` 不是错误：可能只是**已经有一轮在跑**，
    这时应该去看 ``GET /admin/status`` 里的 ``warmup.running``。
    """

    started: bool
    message: str
    warmup: WarmupStatus | None = Field(
        default=None,
        description="只在 ``?wait=true`` 时返回（等这一轮跑完的结果）",
    )
