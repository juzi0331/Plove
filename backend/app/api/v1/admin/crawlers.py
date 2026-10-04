"""后台 — 采集器上传与管理。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import (
    get_db,
    get_registry,
    get_site_settings,
)
from app.api.v1.admin._audit import audit
from app.api.v1.admin._helpers import require_known_site
from app.core.middleware import get_request_id
from app.crawler.registry import SiteRegistry
from app.schemas.admin_site_control import (
    CrawlerCodePayload,
    CrawlerUploadRequest,
    CrawlerUploadResult,
    CrawlerValidateRequest,
    CrawlerValidateResult,
)
from app.schemas.envelope import Envelope, ok
from app.services import crawler_manage_service
from app.services.site_settings import SiteSettingsStore

router = APIRouter(tags=["后台-采集器管理"])


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
        custom_version=payload.custom_version,
        python_exe=registry.runner.python,
    )
    # 清空 meta 缓存并刷新快照
    registry.forget_meta(payload.key)
    store.refresh(db, force=True)

    # 若脚本中包含图片解密逻辑，自动提取 Key/IV 并同步注册到后台图片代理规则库
    try:
        crawler_manage_service.extract_and_sync_image_cipher(payload.code, payload.key, db=db)
    except Exception:
        pass

    audit("upload_crawler", request_id, key=payload.key, name=meta.name)
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
    require_known_site(registry, key)
    crawler_manage_service.delete_crawler(registry.runner.sites_dir, key)
    registry.forget_meta(key)
    store.refresh(db, force=True)
    audit("delete_crawler", request_id, key=key)
    return ok({"message": f"已成功删除采集器 {key}"}, request_id)
