"""后台管理接口。

三块能力：

======================  ==========================================
看一眼                   ``/status``（缓存 / 预热 / 每个源的健康）
刷一次                   ``/cache/refresh``
动手                     ``/codes/*``、``/devices/*``（发码 / 停用 / 延长 / 踢设备）
======================  ==========================================

爬虫上传与源开关**还不在这里** —— 前者要先想清楚形态（那是远程代码执行入口），
后者要先有"远程配置"那张表（阶段 6b-3）。

### 写操作都会留一条审计日志

包含 ** 做了什么 / 对象是谁 / 这一次请求的 request_id** 三样。
理由很实际：这些操作（踢设备、封码）在用户那边**不会产生任何提示**，
用户只会发现"突然看不了了"。事后能对上"几点几分谁干了什么"，
才不会去怀疑是代码的锅。日志里对码做掩码（它也是凭证，见 admin_service）。

守卫（:func:`app.api.deps.require_admin`）挂在 router 上，理由和内容接口一样：
加新接口时才不会忘记加鉴权。

**为什么"看状态"值得单独做一个接口：** 排查"为什么这个源没内容了"时，
需要同时看到四件事 —— 缓存命中了没、熔断是不是开着、上次预热什么时候跑的、
失败的是哪个错误码。少了任何一件，都只能靠猜。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    commit_now,
    get_content_cache,
    get_db,
    get_registry,
    get_site_settings,
    get_warmup_runner,
    require_admin,
)
from app.cache.content import ContentCache
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.middleware import get_request_id
from app.crawler.registry import SiteRegistry
from app.schemas.admin import (
    AdminSiteActionResult,
    AdminSiteListPayload,
    AdminSiteOrderRequest,
    AdminStatusPayload,
    CacheStats,
    CodeActionResult,
    CodeListPayload,
    DeviceListPayload,
    ExtendRequest,
    IssueCodesRequest,
    IssueCodesResult,
    KickResult,
    RefreshResult,
    SiteHealth,
)
from app.core.errors import AppError, ErrorCode
from app.schemas.admin_site_control import (
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
)
from app.schemas.admin_extended import (
    AggregateSearchPayload,
    CacheClearRequest,
    CacheClearResult,
    CacheEntryDetail,
    CacheGlobalConfig,
    CacheKeyEntry,
    CachePreheatRequest,
    CachePreheatResult,
    CacheStatsPayload,
    CodeCleanupResult,
    ImageProxyClearResult,
    ImageProxyConfig,
    ImageProxyStats,
    PlaygroundProbeRequest,
    PlaygroundProbeResult,
    SamplePosterItem,
    SamplePostersPayload,
    SiteCachePolicy,
    SitePreheatDetail,
    SystemMaintenancePayload,
    SystemNoticePayload,
)
from app.schemas.envelope import Envelope, ok
from app.services import (
    admin_service,
    crawler_manage_service,
    image_proxy_service,
    playground_service,
    site_control_service,
    site_service,
    site_settings,
    system_service,
)
from app.services.site_settings import SiteSettingsStore
from app.services.warmup_service import WarmupRunner

logger = get_logger(__name__)


def _audit(action: str, request_id: str, **fields: object) -> None:
    """写操作的审计记录。

    只记 INFO 一行：这些操作频率极低（人工点击），但解释力很强。
    **不要在这里记设备令牌** —— 那是客户端凭证，日志里不该有它的明文。
    """
    detail = " ".join(f"{key}={value}" for key, value in fields.items())
    logger.info("后台操作 action=%s %s request_id=%s", action, detail, request_id)

#: 后台接口全部要管理员令牌；挂在 router 上，避免漏加
router = APIRouter(prefix="/admin", tags=["后台"], dependencies=[Depends(require_admin)])


@router.get("/status", response_model=Envelope[AdminStatusPayload], summary="后台总览")
def status(
    request_id: str = Depends(get_request_id),
    settings: Settings = Depends(get_settings),
    registry: SiteRegistry = Depends(get_registry),
    cache: ContentCache = Depends(get_content_cache),
    warmup: WarmupRunner = Depends(get_warmup_runner),
) -> Envelope[AdminStatusPayload]:
    """缓存 + 每个源的健康 + 上次预热的结果，一次拿全。"""
    payload = AdminStatusPayload(
        env=settings.env,
        sites=[SiteHealth(**item) for item in registry.guards()],
        cache=CacheStats(**cache.stats()),
        warmup=warmup.status(),
    )
    return ok(payload, request_id)


@router.post("/cache/refresh", response_model=Envelope[RefreshResult], summary="立即刷新缓存")
def refresh_cache(
    wait: bool = Query(
        False,
        description="true = 等这一轮跑完再返回（会慢，可能十几秒）；"
        "默认立刻返回，用 /admin/status 看结果",
    ),
    request_id: str = Depends(get_request_id),
    warmup: WarmupRunner = Depends(get_warmup_runner),
) -> Envelope[RefreshResult]:
    """手动跑一次预热：把每个源的首页与前几个分类重新抓一遍。

    **为什么默认不等待：** 一轮预热要逐个请求源站，可能十几秒。
    把它卡在一个 HTTP 请求里，先超时的是反向代理，而你会以为"按钮坏了"。
    默认立刻返回 + 用 ``/admin/status`` 看进度，是更诚实的做法。
    """
    if wait:
        result = warmup.run_once(reason="手动")
        return ok(
            RefreshResult(
                started=True,
                message="已同步完成一轮预热",
                warmup=result,
            ),
            request_id,
        )

    started = warmup.start_in_background(reason="手动")
    return ok(
        RefreshResult(
            started=started,
            message=(
                "已开始预热，用 GET /api/v1/admin/status 看进度"
                if started
                else "已经有一轮预热在进行中，没有重复启动"
            ),
        ),
        request_id,
    )


# ------------------------------------------------------------------ 激活码

@router.get("/codes", response_model=Envelope[CodeListPayload], summary="激活码列表")
def list_codes(
    query: str | None = Query(
        None,
        description="搜索词，同时匹配码本身和备注 —— 运维常记得的是发给谁",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[CodeListPayload]:
    """新的在前。``total`` 是**满足搜索条件的总数**，不是本页条数。"""
    result = admin_service.list_codes(db, query=query, page=page, page_size=page_size)
    return ok(
        CodeListPayload(
            codes=result.items,
            total=result.total,
            page=result.page,
            page_size=result.page_size,
        ),
        request_id,
    )


@router.post("/codes", response_model=Envelope[IssueCodesResult], summary="发码")
def issue_codes(
    payload: IssueCodesRequest,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[IssueCodesResult]:
    """一次可以发多个（``count``，上限 50）。"""
    codes = admin_service.issue_codes(
        db,
        duration_hours=payload.total_hours,
        count=payload.count,
        note=payload.note,
        max_devices=payload.max_devices,
    )
    commit_now(db)
    _audit(
        "issue_codes",
        request_id,
        count=len(codes),
        hours=payload.total_hours,
        note=payload.note or "",
        codes=",".join(admin_service.mask_code(code) for code in codes),
    )
    return ok(
        IssueCodesResult(
            codes=codes,
            duration_hours=payload.total_hours,
            note=payload.note,
        ),
        request_id,
    )


@router.post("/codes/{code_id}/disable", response_model=Envelope[CodeActionResult], summary="停用激活码")
def disable_code(
    code_id: int,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[CodeActionResult]:
    """立即生效：那台设备的下一次请求（内容或心跳）就会拿到 ``FORBIDDEN``。"""
    record = admin_service.set_disabled(db, code_id, disabled=True)
    commit_now(db)
    _audit("disable_code", request_id, id=record.id, code=admin_service.mask_code(record.code))
    return ok(
        CodeActionResult(message="已停用", code=admin_service.to_code_item(record)),
        request_id,
    )


@router.post("/codes/{code_id}/enable", response_model=Envelope[CodeActionResult], summary="解封激活码")
def enable_code(
    code_id: int,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[CodeActionResult]:
    """只有清 ``disabled_at``。**已经到期的码不会因为解封而恢复** （两件事）。"""
    record = admin_service.set_disabled(db, code_id, disabled=False)
    commit_now(db)
    _audit("enable_code", request_id, id=record.id, code=admin_service.mask_code(record.code))
    return ok(
        CodeActionResult(message="已解封", code=admin_service.to_code_item(record)),
        request_id,
    )


@router.post("/codes/{code_id}/extend", response_model=Envelope[CodeActionResult], summary="延长时长")
def extend_code(
    payload: ExtendRequest,
    code_id: int,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[CodeActionResult]:
    """往后加时间。**只能加不能减**，要减用停用。

    对已激活的码是给 ``expires_at`` 加时间；对还没激活的码是加 ``duration_hours``
    （它还没有到期时间）。这个区别在 :func:`admin_service.extend` 里有详细说明。
    """
    before = admin_service.get_code(db, code_id)
    was_started = before.expires_at is not None
    record = admin_service.extend(db, code_id, hours=payload.hours)
    commit_now(db)
    _audit(
        "extend_code",
        request_id,
        id=record.id,
        code=admin_service.mask_code(record.code),
        hours=payload.hours,
        target="expires_at" if was_started else "duration_hours",
    )
    message = (
        f"已延长 {payload.hours} 小时（到期时间往后挪）"
        if was_started
        else f"已延长 {payload.hours} 小时（这个码还没激活，加在时长上）"
    )
    return ok(CodeActionResult(message=message, code=admin_service.to_code_item(record)), request_id)


@router.delete("/codes/{code_id}", response_model=Envelope[dict], summary="删除激活码")
def delete_code(
    code_id: int,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[dict]:
    """彻底删除激活码及其绑定的设备记录。"""
    masked = admin_service.delete_code(db, code_id)
    commit_now(db)
    _audit("delete_code", request_id, id=code_id, code=masked)
    return ok({"message": f"激活码已彻底删除（{masked}）", "id": code_id}, request_id)


@router.post("/codes/cleanup-expired", response_model=Envelope[CodeCleanupResult], summary="批量清理失效激活码")
def cleanup_expired_codes(
    days: int = Query(7, ge=0, description="清理过期超过天数的码，默认为 7 天前到期的码"),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[CodeCleanupResult]:
    """清理已过期超过指定天数的失效激活码，释放数据库存储。"""
    count = admin_service.cleanup_expired_codes(db, days=days)
    commit_now(db)
    _audit("cleanup_expired_codes", request_id, days=days, count=count)
    return ok(CodeCleanupResult(
        deleted_count=count,
        message=f"已成功清理 {count} 个到期超过 {days} 天的失效激活码",
    ), request_id)



# ------------------------------------------------------------------ 设备

@router.get("/codes/{code_id}/devices", response_model=Envelope[DeviceListPayload], summary="这个码用过的设备")
def list_devices(
    code_id: int,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[DeviceListPayload]:
    """按最近出现排序。**载荷里没有令牌明文，只有前 6 位掩码。**"""
    record, devices = admin_service.list_devices(db, code_id)
    return ok(
        DeviceListPayload(devices=devices, active_device_id=record.active_device_id),
        request_id,
    )


@router.post("/devices/{device_id}/kick", response_model=Envelope[KickResult], summary="踢设备下线")
def kick_device(
    device_id: int,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[KickResult]:
    """把活跃位清掉。那台设备会被提示并被停播，**但它还能自己抢回来**。

    想要"彻底用不了"，应该停用整个码 —— 踢是"请下线"，不是"封设备"。
    """
    record = admin_service.kick_device(db, device_id)
    commit_now(db)
    _audit(
        "kick_device",
        request_id,
        device_id=device_id,
        code=admin_service.mask_code(record.code),
    )
    return ok(
        KickResult(
            message="已把该设备下线（它下次心跳会收到通知）",
            code=admin_service.to_code_item(record),
        ),
        request_id,
    )


@router.post("/devices/{device_id}/unbind", response_model=Envelope[KickResult], summary="解绑并移除设备")
def unbind_device(
    device_id: int,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[KickResult]:
    """彻底解绑该设备并释放名额，新设备即可接入。"""
    record = admin_service.unbind_device(db, device_id)
    commit_now(db)
    _audit(
        "unbind_device",
        request_id,
        device_id=device_id,
        code=admin_service.mask_code(record.code),
    )
    return ok(
        KickResult(
            message="已成功解绑该设备，已释放绑定名额",
            code=admin_service.to_code_item(record),
        ),
        request_id,
    )


# ------------------------------------------------------------------ 站点（内容源）


def _require_known_site(registry: SiteRegistry, key: str) -> None:
    """在写之前确认这个源真的存在。

    不确认的话，一个拼错的 key 会在库里静静生成一条永远的垃圾记录，
    而运维看到的是"设置成功"。
    """
    if key not in registry.keys():
        raise AppError(ErrorCode.NOT_FOUND, f"没有这个源：{key}")


def _after_site_write(
    db: Session,
    registry: SiteRegistry,
    store: SiteSettingsStore,
    key: str,
    action: str,
    request_id: str,
    message: str,
) -> Envelope[AdminSiteActionResult]:
    """三个写操作共用的尾巴：**先落库、再刷快照、再记审计**。

    ``refresh(force=True)`` 是这里的关键：不强制刷的话，用户端要多等一个 TTL（几秒）
    才看到变化，而"点了没反应"会让人再点一次。
    """
    commit_now(db)
    store.refresh(db, force=True)
    _audit(action, request_id, site=key)
    return ok(
        AdminSiteActionResult(
            message=message,
            site=site_service.site_item(registry, store, key),
        ),
        request_id,
    )


@router.get("/sites", response_model=Envelope[AdminSiteListPayload], summary="源列表（含开关、顺序与健康）")
def list_sites(
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[AdminSiteListPayload]:
    """**包含被停用的源** —— 运维要能看到自己关掉了什么，而不是关掉之后就消失了。"""
    return ok(site_service.list_admin_sites(registry, store), request_id)


@router.post("/sites/{key}/disable", response_model=Envelope[AdminSiteActionResult], summary="停用源")
def disable_site(
    key: str,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[AdminSiteActionResult]:
    """把某个源从用户端藏起来，并且**不再调用它**（连 fork 都不会）。

    它和"源坏了"是两件事，所以错误码也是两个：源坏了是 ``UPSTREAM_*``
    （用户还能看到它，只是打不开），被我们关掉是 ``SITE_DISABLED``（它根本不该出现）。
    因此**不要**拿熔断去实现"关掉"：熔断会自己恢复，而这是运维的决定。
    """
    _require_known_site(registry, key)
    site_settings.set_enabled(db, key, enabled=False)
    return _after_site_write(
        db,
        registry,
        store,
        key,
        "disable_site",
        request_id,
        f"已停用 {key}：用户端不再显示它，内容接口会回 SITE_DISABLED",
    )


@router.post("/sites/{key}/enable", response_model=Envelope[AdminSiteActionResult], summary="启用源")
def enable_site(
    key: str,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[AdminSiteActionResult]:
    """恢复显示。守护状态**刻意不动** —— 停用期间它没被调用过，旧状态本来就不代表现在，
    真要看它行不行应该用"立即探针"，而不是靠启用这一下。"""
    _require_known_site(registry, key)
    site_settings.set_enabled(db, key, enabled=True)
    return _after_site_write(
        db,
        registry,
        store,
        key,
        "enable_site",
        request_id,
        f"已启用 {key}",
    )


@router.post("/sites/order", response_model=Envelope[AdminSiteListPayload], summary="调整源的顺序")
def order_sites(
    payload: AdminSiteOrderRequest,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[AdminSiteListPayload]:
    """按给定顺序重排用户端列表（小的在前）。

    提交的是**完整顺序**（不是单条改动）——一次提交就是一个一致的最终状态。
    **未知的 key 直接拒**：多半是拼错了，静默忽略会让人以为设过了，
    然后在用户端看到顺序没变，那比报错难查得多。
    """
    site_settings.set_order(db, payload.keys, known=set(registry.keys()))
    commit_now(db)
    store.refresh(db, force=True)
    _audit("order_sites", request_id, order=",".join(payload.keys))
    return ok(site_service.list_admin_sites(registry, store), request_id)


# ------------------------------------------------------------------ 采集器上传与管理


@router.post("/crawlers/validate", response_model=Envelope[CrawlerValidateResult], summary="校验采集器脚本代码")
def validate_crawler(
    payload: CrawlerValidateRequest,
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
) -> Envelope[CrawlerValidateResult]:
    """静态语法检查 + 安全特征审计 + 子进程 meta 冒烟协议测试。"""
    res = crawler_manage_service.validate_crawler_code(
        code=payload.code,
        sites_dir=registry.runner.sites_dir,
        python_exe=registry.runner.python,
        suggested_key=payload.key,
    )
    return ok(res, request_id)


@router.post("/crawlers/upload", response_model=Envelope[CrawlerUploadResult], summary="上传/更新采集器脚本")
def upload_crawler(
    payload: CrawlerUploadRequest,
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
    db: Session = Depends(get_db),
) -> Envelope[CrawlerUploadResult]:
    """校验并安全落盘采集器脚本，热加载使之对系统可用。"""
    meta = crawler_manage_service.save_crawler(
        sites_dir=registry.runner.sites_dir,
        key=payload.key,
        code=payload.code,
        overwrite=payload.overwrite,
        auto_bump_version=payload.auto_bump_version,
        python_exe=registry.runner.python,
    )
    # 清空 meta 缓存并刷新快照
    registry.forget_meta(payload.key)
    store.refresh(db, force=True)
    _audit("upload_crawler", request_id, key=payload.key, name=meta.name)
    return ok(
        CrawlerUploadResult(
            success=True,
            message=f"采集器 {payload.key} ({meta.name}) 上传成功并已就绪",
            meta=meta,
        ),
        request_id,
    )


@router.get("/crawlers/{key}/code", response_model=Envelope[CrawlerCodePayload], summary="查看采集器脚本源码")
def get_crawler_code(
    key: str,
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
) -> Envelope[CrawlerCodePayload]:
    """读取指定采集器的源代码。"""
    payload = crawler_manage_service.get_crawler_code(registry.runner.sites_dir, key)
    return ok(payload, request_id)


@router.delete("/crawlers/{key}", response_model=Envelope[dict], summary="删除采集器脚本")
def delete_crawler(
    key: str,
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
    db: Session = Depends(get_db),
) -> Envelope[dict]:
    """下线并删除采集器脚本文件。"""
    _require_known_site(registry, key)
    crawler_manage_service.delete_crawler(registry.runner.sites_dir, key)
    registry.forget_meta(key)
    store.refresh(db, force=True)
    _audit("delete_crawler", request_id, key=key)
    return ok({"message": f"已成功删除采集器 {key}"}, request_id)


# ------------------------------------------------------------------ 单站高级控制


@router.get("/sites/{key}/advanced", response_model=Envelope[SiteAdvancedSettingPayload], summary="获取单站高级设置")
def get_site_advanced(
    key: str,
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[SiteAdvancedSettingPayload]:
    """包含前台自定义别名、角标、自定义超时、备注与独立代理配置。"""
    _require_known_site(registry, key)
    config = store.config(key)
    return ok(
        SiteAdvancedSettingPayload(
            key=key,
            custom_name=config.custom_name,
            badge=config.badge,
            timeout_seconds=config.timeout_seconds,
            note=config.note,
            proxy_enabled=getattr(config, "proxy_enabled", False),
            proxy_url=getattr(config, "proxy_url", "") or "",
        ),
        request_id,
    )


@router.put("/sites/{key}/advanced", response_model=Envelope[SiteAdvancedSettingPayload], summary="更新单站高级设置")
def update_site_advanced(
    key: str,
    payload: SiteAdvancedSettingUpdateRequest,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[SiteAdvancedSettingPayload]:
    """更新别名、角标、超时秒数、备注及独立代理开关/地址。"""
    _require_known_site(registry, key)
    conf = site_settings.update_advanced(
        db,
        key,
        custom_name=payload.custom_name,
        badge=payload.badge,
        timeout_seconds=payload.timeout_seconds,
        note=payload.note,
        proxy_enabled=payload.proxy_enabled,
        proxy_url=payload.proxy_url,
    )
    commit_now(db)
    store.refresh(db, force=True)
    _audit("update_site_advanced", request_id, key=key)
    return ok(
        SiteAdvancedSettingPayload(
            key=key,
            custom_name=conf.custom_name,
            badge=conf.badge,
            timeout_seconds=conf.timeout_seconds,
            note=conf.note,
            proxy_enabled=getattr(conf, "proxy_enabled", False),
            proxy_url=getattr(conf, "proxy_url", "") or "",
        ),
        request_id,
    )


# ------------------------------------------------------------------ 站点分类与子分类控制


@router.get("/sites/{key}/categories", response_model=Envelope[SiteCategoryRulePayload], summary="获取站点分类控制规则")
def get_site_categories(
    key: str,
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[SiteCategoryRulePayload]:
    """拉取源站真实分类并合并后台保存的隐藏、重命名、排序和子分类规则。"""
    _require_known_site(registry, key)
    payload = site_control_service.get_category_rules_payload(registry, store, key)
    return ok(payload, request_id)


@router.put("/sites/{key}/categories", response_model=Envelope[SiteCategoryRulePayload], summary="更新站点分类控制规则")
def update_site_categories(
    key: str,
    payload: SiteCategoryRuleUpdateRequest,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[SiteCategoryRulePayload]:
    """批量更新分类隐藏/重命名/排序/子分类及默认推荐分类。"""
    _require_known_site(registry, key)
    res = site_control_service.save_category_rules_payload(db, store, key, payload)
    commit_now(db)
    store.refresh(db, force=True)
    _audit("update_site_categories", request_id, key=key, count=len(payload.rules))
    return ok(res, request_id)


# ------------------------------------------------------------------ 详情页清洗与展示策略


@router.get("/sites/{key}/detail-policy", response_model=Envelope[SiteDetailPolicyPayload], summary="获取详情页策略")
def get_site_detail_policy(
    key: str,
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[SiteDetailPolicyPayload]:
    """获取广告过滤模式、线路名称映射、集数命名规则与兜底海报。"""
    _require_known_site(registry, key)
    payload = site_control_service.get_detail_policy_payload(store, key)
    return ok(payload, request_id)


@router.put("/sites/{key}/detail-policy", response_model=Envelope[SiteDetailPolicyPayload], summary="更新详情页策略")
def update_site_detail_policy(
    key: str,
    payload: SiteDetailPolicyUpdateRequest,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[SiteDetailPolicyPayload]:
    """更新详情页广告清洗词汇、线路映射、集数命名及海报配置。"""
    _require_known_site(registry, key)
    res = site_control_service.save_detail_policy_payload(db, key, payload)
    commit_now(db)
    store.refresh(db, force=True)
    _audit("update_site_detail_policy", request_id, key=key)
    return ok(res, request_id)


# ------------------------------------------------------------------ 缓存中心控制


@router.get("/cache/stats", response_model=Envelope[CacheStatsPayload], summary="获取缓存统计与命中率")
def get_cache_stats(
    request_id: str = Depends(get_request_id),
    cache: ContentCache = Depends(get_content_cache),
    warmup: WarmupRunner = Depends(get_warmup_runner),
) -> Envelope[CacheStatsPayload]:
    """返回内存缓存的条目数、命中次数、未命中次数、命中率百分比及 inflight 并发请求。"""
    st = cache.stats()
    st["enabled"] = cache.enabled
    st["warmup_enabled"] = warmup.enabled
    return ok(CacheStatsPayload(**st), request_id)


@router.get("/cache/config", response_model=Envelope[CacheGlobalConfig], summary="获取全局缓存与主动预热总控配置")
def get_cache_global_config(
    request_id: str = Depends(get_request_id),
    cache: ContentCache = Depends(get_content_cache),
    warmup: WarmupRunner = Depends(get_warmup_runner),
) -> Envelope[CacheGlobalConfig]:
    """获取当前全局内容缓存是否开启、自动预热是否开启。"""
    return ok(
        CacheGlobalConfig(
            cache_enabled=cache.enabled,
            warmup_enabled=warmup.enabled,
            warmup_interval_seconds=warmup.interval_seconds,
        ),
        request_id,
    )


@router.put("/cache/config", response_model=Envelope[CacheGlobalConfig], summary="更新全局缓存与主动预热总控配置")
def update_cache_global_config(
    payload: CacheGlobalConfig,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
    cache: ContentCache = Depends(get_content_cache),
    warmup: WarmupRunner = Depends(get_warmup_runner),
) -> Envelope[CacheGlobalConfig]:
    """更新全局内容缓存开关（开/关）与自动定时预热开关（开/关），实时生效并持久化到数据库。"""
    import json
    from app.models.system_setting import SystemSetting

    # 1. 实时修改进程单例状态
    cache.enabled = payload.cache_enabled
    warmup.enabled = payload.warmup_enabled
    if payload.warmup_interval_seconds > 0:
        warmup.interval_seconds = payload.warmup_interval_seconds

    # 2. 持久化存入 system_settings
    row_cache = db.query(SystemSetting).filter_by(key="content_cache_config").first()
    cache_json = json.dumps({"cache_enabled": payload.cache_enabled}, ensure_ascii=False)
    if not row_cache:
        row_cache = SystemSetting(key="content_cache_config", value_json=cache_json)
        db.add(row_cache)
    else:
        row_cache.value_json = cache_json

    row_warm = db.query(SystemSetting).filter_by(key="warmup_config").first()
    warm_json = json.dumps(
        {
            "warmup_enabled": payload.warmup_enabled,
            "warmup_interval_seconds": payload.warmup_interval_seconds,
        },
        ensure_ascii=False,
    )
    if not row_warm:
        row_warm = SystemSetting(key="warmup_config", value_json=warm_json)
        db.add(row_warm)
    else:
        row_warm.value_json = warm_json

    commit_now(db)
    _audit(
        "update_cache_global_config",
        request_id,
        cache_enabled=payload.cache_enabled,
        warmup_enabled=payload.warmup_enabled,
    )
    return ok(payload, request_id)


@router.get("/cache/keys", response_model=Envelope[list[CacheKeyEntry]], summary="列出当前缓存条目")
def list_cache_keys(
    site: str | None = None,
    namespace: str | None = None,
    request_id: str = Depends(get_request_id),
    cache: ContentCache = Depends(get_content_cache),
) -> Envelope[list[CacheKeyEntry]]:
    """透视内存缓存中的具体 Key、所属站点、命名空间与剩余 TTL 倒计时。"""
    raw_keys = cache.list_keys(site=site, namespace=namespace)
    entries = [CacheKeyEntry(**k) for k in raw_keys]
    return ok(entries, request_id)


@router.get("/cache/entry", response_model=Envelope[CacheEntryDetail], summary="查看单条缓存数据详情")
def get_cache_entry(
    key: str = Query(..., description="完整的缓存 Key"),
    request_id: str = Depends(get_request_id),
    cache: ContentCache = Depends(get_content_cache),
) -> Envelope[CacheEntryDetail]:
    """查看某条内存缓存中实际保存的具体数据内容（如影片、分类列表）。"""
    raw_val, hit = cache._store.get_detailed(key)
    if not hit or raw_val is None:
        raise AppError(ErrorCode.NOT_FOUND, f"未找到缓存条目或已过期: {key}")

    parts = key.split("|", 2)
    e_site, e_ns, e_ident = (parts[0], parts[1], parts[2]) if len(parts) == 3 else ("unknown", "unknown", key)

    rem = 0.0
    for e in cache._store.list_entries():
        if e["key"] == key:
            rem = e["remaining_seconds"]
            break

    if hasattr(raw_val, "model_dump"):
        dumped = raw_val.model_dump()
    else:
        dumped = raw_val

    return ok(
        CacheEntryDetail(
            key=key,
            site=e_site,
            namespace=e_ns,
            ident=e_ident,
            remaining_seconds=rem,
            data=dumped,
        ),
        request_id,
    )


@router.post("/cache/clear", response_model=Envelope[CacheClearResult], summary="清理缓存")
def clear_cache(
    payload: CacheClearRequest,
    request_id: str = Depends(get_request_id),
    cache: ContentCache = Depends(get_content_cache),
) -> Envelope[CacheClearResult]:
    """支持全站清空、指定站点清空或指定单一 Key 精准清空。"""
    if payload.key:
        cache.invalidate_key(payload.key)
        _audit("cache_clear_key", request_id, key=payload.key)
        return ok(CacheClearResult(cleared_count=1, message=f"已成功删除缓存键: {payload.key}"), request_id)
    elif payload.site:
        count = cache.invalidate_site(payload.site)
        _audit("cache_clear_site", request_id, site=payload.site, count=count)
        return ok(CacheClearResult(cleared_count=count, message=f"已成功清除站点 [{payload.site}] 的 {count} 条缓存"), request_id)
    else:
        before = len(cache._store)
        cache.clear()
        _audit("cache_clear_all", request_id, count=before)
        return ok(CacheClearResult(cleared_count=before, message=f"已全量清空所有系统缓存（共 {before} 条）"), request_id)


@router.post("/cache/preheat", response_model=Envelope[CachePreheatResult], summary="主动预热缓存")
def preheat_cache(
    payload: CachePreheatRequest,
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
    cache: ContentCache = Depends(get_content_cache),
) -> Envelope[CachePreheatResult]:
    """主动把指定站点或全部启用站点的首页拉入缓存，并返回成果明细。"""
    import time
    t0 = time.perf_counter()
    target_sites = [payload.site] if payload.site else registry.keys()
    preheated: list[str] = []
    details: list[SitePreheatDetail] = []

    for s in target_sites:
        t_site = time.perf_counter()
        try:
            home_data = catalog_service.home(registry, cache, s, force=True)
            preheated.append(s)
            meta = registry.meta(s)
            s_name = meta.name if meta else s
            cat_names = [c.name for c in home_data.categories[:8] if c.name]
            rec_titles = [r.vod_name for r in home_data.recommend[:8] if r.vod_name]
            posters = [r.vod_pic for r in home_data.recommend if r.vod_pic][:4]
            details.append(
                SitePreheatDetail(
                    site=s,
                    site_name=s_name,
                    categories_count=len(home_data.categories),
                    categories=cat_names,
                    recommend_count=len(home_data.recommend),
                    recommend_titles=rec_titles,
                    sample_posters=posters,
                    elapsed_ms=round((time.perf_counter() - t_site) * 1000, 2),
                )
            )
        except Exception:
            pass

    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    _audit("cache_preheat", request_id, sites=preheated, elapsed_ms=elapsed)
    return ok(CachePreheatResult(
        success=len(preheated) > 0,
        preheated_sites=preheated,
        elapsed_ms=elapsed,
        details=details,
    ), request_id)



@router.get("/sites/{key}/cache-policy", response_model=Envelope[SiteCachePolicy], summary="获取单站独立缓存策略")
def get_site_cache_policy(
    key: str,
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[SiteCachePolicy]:
    """读取某站点的 home_ttl, category_ttl, detail_ttl。"""
    _require_known_site(registry, key)
    policy = site_control_service.get_site_cache_policy(store, key)
    return ok(policy, request_id)


@router.put("/sites/{key}/cache-policy", response_model=Envelope[SiteCachePolicy], summary="更新单站独立缓存策略")
def update_site_cache_policy(
    key: str,
    payload: SiteCachePolicy,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[SiteCachePolicy]:
    """保存某站点的独立缓存策略。"""
    _require_known_site(registry, key)
    policy = site_control_service.save_site_cache_policy(db, key, payload)
    store.refresh(db, force=True)
    _audit("update_site_cache_policy", request_id, key=key)
    return ok(policy, request_id)


# ------------------------------------------------------------------ 在线探针与试播台


@router.post("/playground/probe", response_model=Envelope[PlaygroundProbeResult], summary="在线探针探测与试播解析")
def playground_probe(
    payload: PlaygroundProbeRequest,
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
    cache: ContentCache = Depends(get_content_cache),
) -> Envelope[PlaygroundProbeResult]:
    """选站测试 home/category/detail/play，输出精准耗时、缓存命中状态、原始与洗后对比及 m3u8。"""
    _require_known_site(registry, payload.site)
    res = playground_service.run_probe(registry, cache, payload)
    _audit("playground_probe", request_id, site=payload.site, command=payload.command, status=res.status)
    return ok(res, request_id)


# ------------------------------------------------------------------ 跨源聚合搜索


@router.get("/search/aggregate", response_model=Envelope[AggregateSearchPayload], summary="跨源并发聚合搜索")
def search_aggregate(
    kw: str = Query(..., min_length=1, description="搜索关键词"),
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
) -> Envelope[AggregateSearchPayload]:
    """并发调度所有已启用的爬虫，横向比对各站点返回结果条数、耗时与支持状态。"""
    res = playground_service.aggregate_search(registry, kw=kw)
    return ok(res, request_id)


# ------------------------------------------------------------------ 图片防盗链代理监控


@router.get("/proxy/stats", response_model=Envelope[ImageProxyStats], summary="图片代理缓存看板")
def get_image_proxy_stats(
    request_id: str = Depends(get_request_id),
) -> Envelope[ImageProxyStats]:
    stats = image_proxy_service.get_proxy_stats()
    return ok(stats, request_id)


@router.get("/proxy/config", response_model=Envelope[ImageProxyConfig], summary="获取图片防盗链全局配置")
def get_image_proxy_config(
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[ImageProxyConfig]:
    cfg = image_proxy_service.get_image_proxy_config(db)
    return ok(cfg, request_id)


@router.put("/proxy/config", response_model=Envelope[ImageProxyConfig], summary="更新图片防盗链全局配置")
def update_image_proxy_config(
    payload: ImageProxyConfig,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[ImageProxyConfig]:
    updated = image_proxy_service.update_image_proxy_config(db, payload)
    _audit("update_image_proxy_config", request_id, enabled=updated.global_proxy_enabled)
    return ok(updated, request_id)


@router.post("/proxy/clear", response_model=Envelope[ImageProxyClearResult], summary="清空图片代理缓存")
def clear_image_proxy(
    request_id: str = Depends(get_request_id),
) -> Envelope[ImageProxyClearResult]:
    res = image_proxy_service.clear_proxy_cache()
    _audit("clear_image_proxy", request_id, freed_mb=res.freed_mb)
    return ok(res, request_id)


@router.get("/proxy/sample-posters", response_model=Envelope[SamplePostersPayload], summary="自动从内容源提取样例海报")
def get_sample_posters(
    site: str | None = None,
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
    cache: ContentCache = Depends(get_content_cache),
) -> Envelope[SamplePostersPayload]:
    """无需用户手动去寻找或复制图片链接，从内容源首页自动提取真实影视封面用于快速体验防盗链。"""
    sites_to_check = [site] if site else [s for s in registry.keys() if registry.is_enabled(s)]
    posters: list[SamplePosterItem] = []
    for s in sites_to_check:
        try:
            home_data = catalog_service.home(registry, cache, s, force=False)
            for item in home_data.recommend:
                if item.vod_pic and item.vod_pic.startswith("http"):
                    posters.append(
                        SamplePosterItem(
                            title=item.vod_name or "未命名影视",
                            url=item.vod_pic,
                            site=s,
                        )
                    )
                if len(posters) >= 24:
                    break
        except Exception:
            pass
        if len(posters) >= 24:
            break

    # 若内容源尚未预热或爬虫超时返回空，提供高质量影视真实海报作为防盗链体验样本
    if not posters:
        default_samples = [
            ("星际穿越 (Interstellar)", "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=500&q=80", "演示样例"),
            ("流浪地球 (The Wandering Earth)", "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=500&q=80", "演示样例"),
            ("千与千寻 (Spirited Away)", "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=500&q=80", "演示样例"),
            ("盗梦空间 (Inception)", "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=500&q=80", "演示样例"),
            ("黑客帝国 (The Matrix)", "https://images.unsplash.com/photo-1534447677768-be436bb09401?w=500&q=80", "演示样例"),
            ("银翼杀手2049 (Blade Runner)", "https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=500&q=80", "演示样例"),
        ]
        for t, u, s in default_samples:
            posters.append(SamplePosterItem(title=t, url=u, site=s))

    return ok(SamplePostersPayload(items=posters), request_id)



# ------------------------------------------------------------------ 全站公告与维护模式


@router.get("/system/notice", response_model=Envelope[SystemNoticePayload], summary="获取全站公告配置")
def get_system_notice(
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[SystemNoticePayload]:
    n = system_service.get_notice(db)
    return ok(n, request_id)


@router.put("/system/notice", response_model=Envelope[SystemNoticePayload], summary="更新全站公告配置")
def update_system_notice(
    payload: SystemNoticePayload,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[SystemNoticePayload]:
    res = system_service.update_notice(db, payload)
    _audit("update_system_notice", request_id, enabled=res.enabled, title=res.title)
    return ok(res, request_id)


@router.get("/system/maintenance", response_model=Envelope[SystemMaintenancePayload], summary="获取维护模式状态")
def get_system_maintenance(
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[SystemMaintenancePayload]:
    m = system_service.get_maintenance(db)
    return ok(m, request_id)


@router.put("/system/maintenance", response_model=Envelope[SystemMaintenancePayload], summary="开关紧急维护模式")
def update_system_maintenance(
    payload: SystemMaintenancePayload,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[SystemMaintenancePayload]:
    res = system_service.update_maintenance(db, payload)
    _audit("update_system_maintenance", request_id, enabled=res.enabled)
    return ok(res, request_id)

