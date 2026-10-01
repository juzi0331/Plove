"""接口形状（Pydantic）—— **契约的唯一来源**。

``contracts/schemas/*.json`` 由 :data:`EXPORTS` 导出，不要手改那些 JSON。
改完这里的模型后运行::

    python tools/export_contracts.py

并把生成物一起提交；测试会比对生成物是否过期。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.schemas.activation import ActivationResult, RedeemRequest, SessionState
from app.schemas.admin import (
    AdminSiteActionResult,
    AdminSiteItem,
    AdminSiteListPayload,
    AdminSiteOrderRequest,
    AdminStatusPayload,
    CacheStats,
    CacheTtl,
    CodeActionResult,
    CodeListItem,
    CodeListPayload,
    DeviceItem,
    DeviceListPayload,
    ExtendRequest,
    IssueCodesRequest,
    IssueCodesResult,
    KickResult,
    RefreshResult,
    SiteHealth,
    WarmupSiteResult,
    WarmupStatus,
)
from app.schemas.admin_site_control import (
    CategoryRuleItem,
    CrawlerCodePayload,
    CrawlerUploadRequest,
    CrawlerUploadResult,
    CrawlerValidateRequest,
    CrawlerValidateResult,
    SiteAdvancedSettingPayload,
    SiteAdvancedSettingUpdateRequest,
    SiteCategoryRulePayload,
    SiteCategoryRuleUpdateRequest,
    SiteDetailPolicyPayload,
    SiteDetailPolicyUpdateRequest,
    SubCategoryItem,
)
from app.schemas.catalog import DetailPayload, HomePayload, HomeSection, ListPayload
from app.schemas.envelope import Envelope, ErrorInfo
from app.schemas.episode import Episode, LineInfo
from app.schemas.playback import Playback
from app.schemas.site import SiteListPayload, SiteMeta
from app.schemas.system import HealthPayload
from app.schemas.vod import SubCategory, VodCategory, VodItem

__all__ = [
    "EXPORTS",
    "ActivationResult",
    "AdminSiteActionResult",
    "AdminSiteItem",
    "AdminSiteListPayload",
    "AdminSiteOrderRequest",
    "AdminStatusPayload",
    "CacheStats",
    "CacheTtl",
    "CategoryRuleItem",
    "CodeActionResult",
    "CodeListItem",
    "CodeListPayload",
    "CrawlerCodePayload",
    "CrawlerUploadRequest",
    "CrawlerUploadResult",
    "CrawlerValidateRequest",
    "CrawlerValidateResult",
    "DetailPayload",
    "DeviceItem",
    "DeviceListPayload",
    "ExtendRequest",
    "IssueCodesRequest",
    "IssueCodesResult",
    "KickResult",
    "Envelope",
    "Episode",
    "ErrorInfo",
    "HealthPayload",
    "HomePayload",
    "HomeSection",
    "LineInfo",
    "ListPayload",
    "Playback",
    "RedeemRequest",
    "RefreshResult",
    "SessionState",
    "SiteAdvancedSettingPayload",
    "SiteAdvancedSettingUpdateRequest",
    "SiteCategoryRulePayload",
    "SiteCategoryRuleUpdateRequest",
    "SiteDetailPolicyPayload",
    "SiteDetailPolicyUpdateRequest",
    "SiteHealth",
    "SiteListPayload",
    "SiteMeta",
    "SubCategory",
    "SubCategoryItem",
    "VodCategory",
    "VodItem",
    "WarmupSiteResult",
    "WarmupStatus",
    # 扩展契约
    "AggregateSearchPayload",
    "AggregateSearchSiteResult",
    "CacheClearRequest",
    "CacheClearResult",
    "CacheKeyEntry",
    "CacheEntryDetail",
    "CachePreheatRequest",
    "CachePreheatResult",
    "SitePreheatDetail",
    "CacheStatsPayload",
    "ImageProxyClearResult",
    "ImageProxyStats",
    "SamplePostersPayload",
    "PlaygroundProbeRequest",
    "PlaygroundProbeResult",
    "SiteCachePolicy",
    "SystemMaintenancePayload",
    "SystemNoticePayload",
    "SystemStatusPayload",
    "CodeCleanupResult",
]

from app.schemas.admin_extended import (
    AggregateSearchPayload,
    AggregateSearchSiteResult,
    CacheClearRequest,
    CacheClearResult,
    CacheEntryDetail,
    CacheKeyEntry,
    CachePreheatRequest,
    CachePreheatResult,
    CacheStatsPayload,
    CodeCleanupResult,
    ImageProxyClearResult,
    ImageProxyStats,
    PlaygroundProbeRequest,
    PlaygroundProbeResult,
    SamplePostersPayload,
    SiteCachePolicy,
    SitePreheatDetail,
    SystemMaintenancePayload,
    SystemNoticePayload,
    SystemStatusPayload,
)

#: 导出清单：文件名（不含扩展名） -> 模型
#: ``Envelope`` 有类型参数，导出时用 ``Envelope[Any]`` 固定下来
EXPORTS: dict[str, type[BaseModel]] = {
    "envelope": Envelope[Any],  # type: ignore[dict-item]
    "error-info": ErrorInfo,
    "vod-item": VodItem,
    "vod-category": VodCategory,
    "sub-category": SubCategory,
    "episode": Episode,
    "line-info": LineInfo,
    "playback": Playback,
    "site-meta": SiteMeta,
    "site-list": SiteListPayload,
    "catalog-home": HomePayload,
    "catalog-list": ListPayload,
    "catalog-detail": DetailPayload,
    "health": HealthPayload,
    "activation-redeem": RedeemRequest,
    "activation-result": ActivationResult,
    "session-state": SessionState,
    "admin-status": AdminStatusPayload,
    "admin-refresh-result": RefreshResult,
    # 后台"动手"类接口的载荷（阶段 7）。
    "admin-code-item": CodeListItem,
    "admin-code-list": CodeListPayload,
    "admin-issue-request": IssueCodesRequest,
    "admin-issue-result": IssueCodesResult,
    "admin-extend-request": ExtendRequest,
    "admin-code-action": CodeActionResult,
    "admin-device-item": DeviceItem,
    "admin-device-list": DeviceListPayload,
    "admin-kick-result": KickResult,
    # 站点（源）管理：列表 / 开与关 / 重排（步骤 10）
    "admin-site-item": AdminSiteItem,
    "admin-site-list": AdminSiteListPayload,
    "admin-site-order-request": AdminSiteOrderRequest,
    "admin-site-action": AdminSiteActionResult,
    # 采集器上传与校验
    "admin-crawler-validate-request": CrawlerValidateRequest,
    "admin-crawler-validate-result": CrawlerValidateResult,
    "admin-crawler-upload-request": CrawlerUploadRequest,
    "admin-crawler-upload-result": CrawlerUploadResult,
    "admin-crawler-code": CrawlerCodePayload,
    # 单站高级控制、分类/子分类控制、详情页清洗策略
    "admin-site-advanced": SiteAdvancedSettingPayload,
    "admin-site-advanced-update": SiteAdvancedSettingUpdateRequest,
    "admin-site-category-rules": SiteCategoryRulePayload,
    "admin-site-category-rules-update": SiteCategoryRuleUpdateRequest,
    "admin-site-detail-policy": SiteDetailPolicyPayload,
    "admin-site-detail-policy-update": SiteDetailPolicyUpdateRequest,
    # 缓存中心透视与控制
    "admin-cache-stats": CacheStatsPayload,
    "admin-cache-key-entry": CacheKeyEntry,
    "admin-cache-entry-detail": CacheEntryDetail,
    "admin-cache-clear-request": CacheClearRequest,
    "admin-cache-clear-result": CacheClearResult,
    "admin-cache-preheat-request": CachePreheatRequest,
    "admin-cache-preheat-result": CachePreheatResult,
    "admin-preheat-detail": SitePreheatDetail,
    "admin-cache-policy": SiteCachePolicy,
    # 在线探针与试播台
    "admin-playground-probe-request": PlaygroundProbeRequest,
    "admin-playground-probe-result": PlaygroundProbeResult,
    # 图片防盗链代理
    "admin-image-proxy-stats": ImageProxyStats,
    "admin-image-proxy-clear": ImageProxyClearResult,
    "admin-sample-posters": SamplePostersPayload,
    # 系统公告与维护模式
    "system-notice": SystemNoticePayload,
    "system-maintenance": SystemMaintenancePayload,
    "system-status": SystemStatusPayload,
    # 聚合搜索
    "admin-aggregate-search": AggregateSearchPayload,
    # 激活码批量清理
    "admin-code-cleanup": CodeCleanupResult,
}
