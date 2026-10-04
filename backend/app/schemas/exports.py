"""契约导出字典定义。

存放 EXPORTS 字典：stem（contracts/schemas/*.json 文件名） -> Pydantic Model 类。
所有与前端 TypeScript 代码生成、爬虫数据校验和契约防漂移测试相关的契约均在此集中注册。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.modules.experience.schemas import (
    ClientBootstrapPayload,
    DraftSaveResult,
    ExperienceDraftPayload,
    ExperienceDraftUpdateRequest,
    ExperienceReleaseItem,
    PageViewModel,
    ReleaseCurrentPayload,
    ReleasePublishRequest,
    ReleasePublishResult,
    ReleaseRollbackRequest,
)
from app.schemas.activation import ActivationResult, RedeemRequest, SessionState
from app.schemas.admin import (
    AdminSiteActionResult,
    AdminSiteItem,
    AdminSiteListPayload,
    AdminSiteOrderRequest,
    AdminStatusPayload,
)
from app.schemas.admin_cache import (
    CacheClearRequest,
    CacheClearResult,
    CacheEntryDetail,
    CacheKeyEntry,
    CachePreheatRequest,
    CachePreheatResult,
    CacheStatsPayload,
    RefreshResult,
    SamplePostersPayload,
    SiteCachePolicy,
    SitePreheatDetail,
)
from app.schemas.admin_code import (
    CodeActionResult,
    CodeCleanupResult,
    CodeListItem,
    CodeListPayload,
    ExtendRequest,
    IssueCodesRequest,
    IssueCodesResult,
)
from app.schemas.admin_crawler import (
    CrawlerCodePayload,
    CrawlerUploadRequest,
    CrawlerUploadResult,
    CrawlerValidateRequest,
    CrawlerValidateResult,
)
from app.schemas.admin_device import (
    DeviceItem,
    DeviceListPayload,
    KickResult,
)
from app.schemas.admin_extended import (
    AggregateSearchPayload,
    ImageProxyClearResult,
    ImageProxyConfig,
    ImageProxyStats,
    PlaygroundProbeRequest,
    PlaygroundProbeResult,
    SystemMaintenancePayload,
    SystemNoticePayload,
    SystemStatusPayload,
    TestDecryptRequest,
    TestDecryptResult,
)
from app.schemas.admin_proxy import (
    ProxyEngineActionResponse,
    ProxyEngineStatusPayload,
    ProxyNodeBindRequest,
    ProxyNodeCreateRequest,
    ProxyNodeItem,
    ProxyNodeListPayload,
    ProxyTestRequest,
    ProxyTestResult,
)
from app.schemas.admin_site_control import (
    SiteAdvancedSettingPayload,
    SiteAdvancedSettingUpdateRequest,
    SiteCategoryRulePayload,
    SiteCategoryRuleUpdateRequest,
    SiteDetailPolicyPayload,
    SiteDetailPolicyUpdateRequest,
)
from app.schemas.catalog import DetailPayload, HomePayload, ListPayload
from app.schemas.envelope import Envelope, ErrorInfo
from app.schemas.episode import Episode, LineInfo
from app.schemas.playback import Playback
from app.schemas.site import SiteListPayload, SiteMeta
from app.schemas.system import HealthPayload
from app.schemas.vod import SubCategory, VodCategory, VodItem
from app.schemas.webhook import (
    TelegramDetectChatRequest,
    TelegramDetectChatResult,
    TelegramVerifyRequest,
    TelegramVerifyResult,
    WebhookConfigPayload,
    WebhookDeliveryLogItem,
    WebhookLogsPayload,
    WebhookTestRequest,
    WebhookTestResult,
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
    "admin-image-proxy-config": ImageProxyConfig,
    "admin-sample-posters": SamplePostersPayload,
    # 系统公告与维护模式
    "system-notice": SystemNoticePayload,
    "system-maintenance": SystemMaintenancePayload,
    "system-status": SystemStatusPayload,
    # 聚合搜索
    "admin-aggregate-search": AggregateSearchPayload,
    # 激活码批量清理
    "admin-code-cleanup": CodeCleanupResult,
    # 代理节点池与引擎管理
    "admin-proxy-node-item": ProxyNodeItem,
    "admin-proxy-node-list": ProxyNodeListPayload,
    "admin-proxy-node-create-request": ProxyNodeCreateRequest,
    "admin-proxy-test-request": ProxyTestRequest,
    "admin-proxy-test-result": ProxyTestResult,
    "admin-proxy-node-bind-request": ProxyNodeBindRequest,
    "admin-proxy-engine-status": ProxyEngineStatusPayload,
    "admin-proxy-engine-action-response": ProxyEngineActionResponse,
    "admin-test-decrypt-request": TestDecryptRequest,
    "admin-test-decrypt-result": TestDecryptResult,
    # 前台体验与发布中心
    "client-bootstrap": ClientBootstrapPayload,
    "client-release-current": ReleaseCurrentPayload,
    "client-page-view-model": PageViewModel,
    "admin-experience-draft": ExperienceDraftPayload,
    "admin-experience-draft-update": ExperienceDraftUpdateRequest,
    "admin-draft-save-result": DraftSaveResult,
    "admin-experience-release-item": ExperienceReleaseItem,
    "admin-release-publish-request": ReleasePublishRequest,
    "admin-release-publish-result": ReleasePublishResult,
    "admin-release-rollback-request": ReleaseRollbackRequest,
    # 外部通知与 Webhook
    "admin-webhook-config": WebhookConfigPayload,
    "admin-webhook-logs": WebhookLogsPayload,
    "admin-webhook-test-request": WebhookTestRequest,
    "admin-webhook-test-result": WebhookTestResult,
    "admin-telegram-verify-request": TelegramVerifyRequest,
    "admin-telegram-verify-result": TelegramVerifyResult,
    "admin-telegram-detect-chat-request": TelegramDetectChatRequest,
    "admin-telegram-detect-chat-result": TelegramDetectChatResult,
    "admin-webhook-delivery-log-item": WebhookDeliveryLogItem,
}
