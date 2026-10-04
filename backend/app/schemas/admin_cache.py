"""后台缓存中心与预热透视契约。

包含全局缓存命中统计、内存键透视、主动预热、L2磁盘镜像、单站TTL策略及采样海报契约。
对应契约: admin-cache-*.json
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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


class CacheKeyEntry(BaseModel):
    """当前内存缓存里的单个 Key 条目。"""

    key: str = Field(description="完整的缓存 Key，如 alpha|home|-")
    site: str = Field(description="所属站点 key")
    namespace: str = Field(description="命名空间：home / category / detail")
    ident: str = Field(description="标识符：- / tid:page / vod_id")
    remaining_seconds: float = Field(description="剩余存活秒数（TTL 倒计时）")
    is_disk: bool = Field(default=False, description="是否来自 L2 本地磁盘持久化镜像")


class CacheStatsPayload(BaseModel):
    """缓存全局命中率与容量看板数据。"""

    size: int = Field(description="当前已缓存的条目总数")
    maxsize: int = Field(description="缓存最大允许容量上限")
    hits: int = Field(description="累计命中次数")
    misses: int = Field(description="累计未命中（击穿查源）次数")
    hit_ratio_percent: float = Field(description="实时缓存命中率百分比（0.0 ~ 100.0）")
    inflight: int = Field(default=0, description="当前正在并发保护中的任务数")
    ttl: dict[str, float] = Field(default_factory=dict, description="全局默认 TTL 配置秒数")
    disk: dict[str, Any] | None = Field(default=None, description="L2 磁盘持久化统计（条数、占用体积等）")
    enabled: bool = Field(default=False, description="全局内容缓存是否开启（默认关闭，需手动开启）")
    warmup_enabled: bool = Field(default=False, description="自动定时预热是否开启（默认关闭，需手动开启）")


class CacheGlobalConfig(BaseModel):
    """全局内容缓存与预热总控配置。"""

    cache_enabled: bool = Field(
        default=False,
        description="是否开启全局内容缓存（默认关闭，需手动开启；开启后首页与分类等享受极速缓存）",
    )
    warmup_enabled: bool = Field(
        default=False,
        description="是否开启自动定时预热（默认关闭，需手动开启；开启后后台自动定期抓取入口页）",
    )
    warmup_interval_seconds: float = Field(
        default=86400.0,
        description="预热周期（秒），默认 86400（24小时）",
    )


class CacheClearRequest(BaseModel):
    """清除缓存请求。"""

    site: str | None = Field(default=None, description="若提供则仅清空该站点的缓存；若为空则清空全站")
    key: str | None = Field(default=None, description="若提供则精准删除指定 key")


class CacheClearResult(BaseModel):
    """清除缓存执行结果。"""

    cleared_count: int = Field(description="清除掉的条目数量")
    message: str = Field(description="执行结果提示")


class CachePreheatRequest(BaseModel):
    """主动预热缓存请求。"""

    site: str | None = Field(default=None, description="若提供则预热指定站点首页，为空则预热所有启用站点")


class SitePreheatDetail(BaseModel):
    """单站首页预热成果明细报表。"""

    site: str = Field(description="站点 key")
    site_name: str = Field(description="站点名称")
    categories_count: int = Field(description="成功装载的分类数")
    categories: list[str] = Field(default_factory=list, description="装载的分类标签列表")
    recommend_count: int = Field(description="推荐影视片单数量")
    recommend_titles: list[str] = Field(default_factory=list, description="装载的推荐影片片名")
    sample_posters: list[str] = Field(default_factory=list, description="抽样海报图片预览")
    elapsed_ms: float = Field(description="该站预热耗时（毫秒）")


class CachePreheatResult(BaseModel):
    """缓存预热结果。"""

    success: bool = Field(description="预热是否全部或部分成功")
    preheated_sites: list[str] = Field(default_factory=list, description="成功预热并落入缓存的站点列表")
    elapsed_ms: float = Field(description="预热整体耗时（毫秒）")
    details: list[SitePreheatDetail] = Field(
        default_factory=list,
        description="各站点的具体预热成果明细（分类数、推荐影视列表、海报样片）",
    )


class CacheEntryDetail(BaseModel):
    """单条缓存的具体数据透视。"""

    key: str = Field(description="缓存 Key")
    site: str = Field(description="所属站点")
    namespace: str = Field(description="命名空间")
    ident: str = Field(description="定位符")
    remaining_seconds: float = Field(description="剩余存活秒数")
    data: Any = Field(default=None, description="缓存中存储的具体 JSON 数据内容")


class SiteCachePolicy(BaseModel):
    """单站点独立定制的缓存 TTL 策略。"""

    home_ttl: float | None = Field(default=None, description="首页缓存秒数（None 跟随全局，0 表示不缓存）")
    category_ttl: float | None = Field(default=None, description="分类列表缓存秒数（None 跟随全局，0 表示不缓存）")
    detail_ttl: float | None = Field(default=None, description="详情页缓存秒数（None 跟随全局，0 表示不缓存）")
    long_term_static_ttl: float | None = Field(
        default=86400.0,
        description="海报与剧情简介等静态元信息长效缓存秒数（默认 24 小时）",
    )


class SamplePosterItem(BaseModel):
    """抽样的真实源站海报。"""

    title: str = Field(description="影视标题")
    url: str = Field(description="海报原始 URL")
    site: str = Field(description="所属站点")


class SamplePostersPayload(BaseModel):
    """自动从内容源提取的海报图库。"""

    items: list[SamplePosterItem] = Field(default_factory=list, description="抽样海报清单")


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
