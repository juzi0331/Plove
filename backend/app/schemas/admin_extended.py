"""后台扩展契约：在线探针/试播台、图片防盗链代理、全站公告与维护模式、跨源聚合搜索。

缓存中心契约与激活码清理契约已模块化抽取至 admin_cache 与 admin_code，在本模块保持完全兼容重导出。
"""

from __future__ import annotations

from typing import Any, Literal
import uuid

from pydantic import BaseModel, Field

# 保持向前兼容重导出
from app.schemas.admin_cache import (
    CacheClearRequest,
    CacheClearResult,
    CacheEntryDetail,
    CacheGlobalConfig,
    CacheKeyEntry,
    CachePreheatRequest,
    CachePreheatResult,
    CacheStatsPayload,
    SamplePosterItem,
    SamplePostersPayload,
    SiteCachePolicy,
    SitePreheatDetail,
)
from app.schemas.admin_code import (
    CodeCleanupResult,
)


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

class ImageDecryptionRule(BaseModel):
    """站点图片解密规则配置。"""

    id: str = Field(default="", description="规则唯一标识（如 UUID 或简短 ID）")
    name: str = Field(default="", description="规则名称或备注（如 黄果艾加密封面）")
    site_key: str = Field(default="", description="对应站点标识（如 huangguoai_com，留空表示全站通用匹配）")
    match_domains: list[str] = Field(default_factory=list, description="匹配的加密图床域名特征列表（如 pic.wirqed.cn）")
    algorithm: Literal["AES-128-CBC", "AES-128-ECB"] = Field(default="AES-128-CBC", description="解密算法")
    key: str = Field(default="", description="解密密钥 Key（16/24/32字符Hex或UTF-8字符串）")
    iv: str = Field(default="", description="偏移量 IV（CBC模式需16字符）")
    is_hex: bool = Field(default=False, description="Key/IV 是否为 Hex 编码十六进制字符串")
    enabled: bool = Field(default=True, description="是否启用该解密规则")
    created_at: str = Field(default="", description="规则创建时间")


class TestDecryptRequest(BaseModel):
    """测试解密请求。"""

    url: str = Field(description="待测试的图片链接")
    site_key: str = Field(default="", description="可选的站点标识")
    rule: ImageDecryptionRule | None = Field(default=None, description="临时测试的解密规则（若不提供则套用已保存的规则）")


class TestDecryptResult(BaseModel):
    """测试解密响应。"""

    success: bool = Field(description="是否成功解密或验证为合法图片")
    message: str = Field(description="结果或诊断信息")
    matched_rule_id: str | None = Field(default=None, description="命中的解密规则 ID")
    mime_type: str = Field(default="", description="图片 MIME 类型，如 image/jpeg")
    size_bytes: int = Field(default=0, description="图片字节大小")
    elapsed_ms: float = Field(default=0.0, description="解密与请求耗时（毫秒）")
    preview_data_url: str | None = Field(default=None, description="解密成功后的 Base64 Data URL 预览图片")


class ImageCdnPrefixRule(BaseModel):
    """图床加速与代理前缀规则（如 wsrv.nl 等公共边缘 CDN 反代）。"""

    id: str = Field(default_factory=lambda: f"prefix_{uuid.uuid4().hex[:8]}")
    name: str = Field(default="", description="规则名称，例如：网飞猫图床加速")
    site_key: str = Field(default="", description="适用的站点 Key（例如：www_ncat21_com，留空则匹配所有站点）")
    match_domain: str = Field(default="", description="匹配的域名或 URL 关键词（例如：vres.cyscyy.com）")
    prefix: str = Field(default="https://wsrv.nl/?url=", description="代理前缀，例如：https://wsrv.nl/?url=")
    enabled: bool = Field(default=True, description="是否启用该规则")


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
    decryption_rules: list[ImageDecryptionRule] = Field(
        default_factory=list,
        description="各站点自定义图片解密密钥规则库（支持动态配置 AES-128-CBC 等算法，解密各源站加密海报）",
    )
    cdn_prefix_rules: list[ImageCdnPrefixRule] = Field(
        default_factory=lambda: [
            ImageCdnPrefixRule(
                id="rule_ncat21",
                name="网飞猫图床加速",
                site_key="www_ncat21_com",
                match_domain="vres.cyscyy.com",
                prefix="https://wsrv.nl/?url=",
                enabled=True,
            )
        ],
        description="各站点/域名的外部 CDN 代理加速前缀规则列表",
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
    display_type: Literal["banner", "modal", "both", "float", "header_bar", "all"] = Field(
        default="banner",
        description="展示形式：banner 顶部跑马灯, modal 大厅强弹窗, header_bar 顶部常驻横幅, float 右下角悬浮卡片, both 弹窗+跑马灯, all 全渠道广播",
    )
    action_text: str = Field(default="", description="操作按钮文案（如：查看详情/立即加群，选填）")
    action_url: str = Field(default="", description="操作跳转链接（如：官网/群链接，选填）")
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
    image_decrypt_domains: list[str] = Field(default_factory=list, description="需要中继解密的图床域名特征列表")
    image_cdn_prefix_rules: list[ImageCdnPrefixRule] = Field(
        default_factory=list,
        description="需要添加外部 CDN 前缀代理的图床规则",
    )


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


__all__ = [
    "PlaygroundProbeRequest",
    "PlaygroundProbeResult",
    "ImageDecryptionRule",
    "TestDecryptRequest",
    "TestDecryptResult",
    "ImageProxyConfig",
    "ImageProxyStats",
    "ImageProxyClearResult",
    "SystemNoticePayload",
    "SystemMaintenancePayload",
    "SystemStatusPayload",
    "AggregateSearchSiteResult",
    "AggregateSearchPayload",
    # 重导出
    "CacheKeyEntry",
    "CacheStatsPayload",
    "CacheGlobalConfig",
    "CacheClearRequest",
    "CacheClearResult",
    "CachePreheatRequest",
    "SitePreheatDetail",
    "CachePreheatResult",
    "CacheEntryDetail",
    "SiteCachePolicy",
    "SamplePosterItem",
    "SamplePostersPayload",
    "CodeCleanupResult",
]
