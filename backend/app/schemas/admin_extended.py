"""后台扩展契约：缓存管理透视、在线探针/试播台、图片防盗链代理、全站公告与维护模式、跨源聚合搜索。

所有字段带完整 description 与默认值，确保生成 TypeScript 契约精准严密。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ------------------------------------------------------------------ 缓存管理透视

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


class CodeCleanupResult(BaseModel):
    """批量清理失效激活码结果。"""

    deleted_count: int = Field(description="删除的失效激活码数量")
    message: str = Field(description="提示信息")



# ------------------------------------------------------------------ 在线探针与试播台

class PlaygroundProbeRequest(BaseModel):
    """发起探针测试请求。"""

    site: str = Field(description="目标站点 key")
    command: Literal["home", "category", "detail", "play"] = Field(
        description="测试命令：home(首页推荐), category(分类列表), detail(影视详情), play(播放地址解析)"
    )
    tid: str | None = Field(default=None, description="分类 ID（category 命令可用）")
    page: int = Field(default=1, ge=1, description="页码")
    vod_id: str | None = Field(default=None, description="影片 ID（detail / play 命令必填）")
    ep: int = Field(default=1, ge=1, description="集数（play 命令可用）")
    bypass_cache: bool = Field(default=False, description="是否强制穿透缓存（即强制调用真实爬虫进程）")


class PlaygroundProbeResult(BaseModel):
    """探针执行响应：包含清洗前后的数据差分、耗时与视频流。"""

    site: str = Field(description="站点 key")
    command: str = Field(description="执行命令")
    elapsed_ms: float = Field(description="总耗时毫秒数")
    cache_hit: bool = Field(description="本次请求是否命中了系统缓存（HIT 为 true，MISS 为 false）")
    status: Literal["OK", "ERROR"] = Field(description="执行状态")
    raw_data: Any | None = Field(default=None, description="爬虫原始返回的 JSON 结构")
    cleaned_data: Any | None = Field(default=None, description="经过清洗策略（广告清洗/分类规则）后的数据")
    playback_url: str | None = Field(default=None, description="如果是 play 命令，提取出的直接播放地址（如 m3u8）")
    error_detail: str | None = Field(default=None, description="如果执行失败，返回的错误详情")


# ------------------------------------------------------------------ 图片防盗链代理与缓存

class ImageProxyConfig(BaseModel):
    """全局图片防盗链代理总控配置。"""

    global_proxy_enabled: bool = Field(
        default=False,
        description="是否全局启用海报防盗链中继（开启后前台所有海报经由本站代理中继并高速缓存，彻底免除第三方防盗链 403 破图）",
    )
    disk_cache_enabled: bool = Field(
        default=False,
        description="是否开启图片本地持久化磁盘缓存（默认关闭，需手动开启；开启后将图片缓存在本地 backend/data/img_cache 避免重复请求源站）",
    )
    auto_strip_referer: bool = Field(
        default=True,
        description="中继时是否自动去除 Referer 或伪造为源站同源 Referer",
    )
    custom_referer: str = Field(
        default="",
        description="全局自定义伪造 Referer（若为空则自动根据图片 URL 提取 host）",
    )
    cache_max_mb: int = Field(
        default=1024,
        description="磁盘缓存最大容量限制（MB）",
    )
    updated_at: str = Field(
        default="",
        description="配置最后更新时间",
    )


class ImageProxyStats(BaseModel):
    """图片代理缓存看板数据。"""

    cached_files: int = Field(description="已持久化缓存的图片文件总数")
    total_size_mb: float = Field(description="图片缓存占用磁盘大小（MB）")
    cache_dir: str = Field(description="缓存存储绝对路径")


class ImageProxyClearResult(BaseModel):
    """图片缓存清理结果。"""

    cleared_files: int = Field(description="清理的文件数")
    freed_mb: float = Field(description="释放的磁盘空间（MB）")


# ------------------------------------------------------------------ 全站公告与维护模式

class SystemNoticePayload(BaseModel):
    """全站公告内容与弹窗策略。"""

    enabled: bool = Field(default=False, description="是否发布并生效")
    title: str = Field(default="", description="公告标题")
    content: str = Field(default="", description="公告详细正文")
    level: Literal["info", "warning", "danger"] = Field(
        default="info", description="展示等级：info 提示, warning 警告, danger 紧急"
    )
    display_type: Literal["banner", "modal", "both"] = Field(
        default="banner", description="展示形式：banner 顶部条幅, modal 首次强弹窗, both 两者兼具"
    )
    dismissible: bool = Field(default=True, description="用户是否可手动点击关闭")
    updated_at: str = Field(default="", description="最后更新时间")


class SystemMaintenancePayload(BaseModel):
    """紧急停服维护模式。"""

    enabled: bool = Field(default=False, description="是否开启维护模式（开启后非管理员请求一律被拦截并提示维护）")
    message: str = Field(default="系统维护升级中，请稍后访问", description="前台展示给用户的维护文案")
    allow_admin: bool = Field(default=True, description="是否放行后台管理界面访问")
    updated_at: str = Field(default="", description="最后更新时间")


class SystemStatusPayload(BaseModel):
    """公共系统状态（客户端 App / Web 启动时调用的公开接口）。"""

    maintenance: bool = Field(default=False, description="当前是否处于全站维护中")
    maintenance_message: str = Field(default="", description="维护文案")
    notice: SystemNoticePayload | None = Field(default=None, description="当前生效的公告信息")
    image_proxy_enabled: bool = Field(default=False, description="是否全局开启图片防盗链代理")


# ------------------------------------------------------------------ 跨源聚合搜索增强

class AggregateSearchSiteResult(BaseModel):
    """单站搜索聚合结果。"""

    site: str = Field(description="站点 key")
    site_name: str = Field(description="站点名称")
    supported: bool = Field(description="该站点爬虫是否支持搜索能力")
    count: int = Field(description="找到的影视结果条数")
    elapsed_ms: float = Field(description="该站点爬虫搜索耗时（毫秒）")
    error: str | None = Field(default=None, description="搜索失败时的错误信息")
    items: list[Any] = Field(default_factory=list, description="搜索出的前几部视频摘要条目")


class AggregateSearchPayload(BaseModel):
    """跨源聚合搜索比对总览。"""

    kw: str = Field(description="搜索关键词")
    total_sites: int = Field(description="参与并发搜索的站点总数")
    total_count: int = Field(description="全源累计命中的视频结果条数")
    results: list[AggregateSearchSiteResult] = Field(default_factory=list, description="各站点的独立比对结果")
