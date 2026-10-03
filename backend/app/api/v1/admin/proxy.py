"""后台 — 图片防盗链代理监控与体验样本。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import (
    get_content_cache,
    get_db,
    get_registry,
)
from app.api.v1.admin._audit import audit
from app.cache.content import ContentCache
from app.core.middleware import get_request_id
from app.crawler.registry import SiteRegistry
from app.schemas.admin_extended import (
    ImageProxyClearResult,
    ImageProxyConfig,
    ImageProxyStats,
    SamplePosterItem,
    SamplePostersPayload,
)
from app.schemas.envelope import Envelope, ok
from app.services import catalog_service, image_proxy_service

router = APIRouter(tags=["后台-图片代理"])


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
    audit("update_image_proxy_config", request_id, enabled=updated.global_proxy_enabled)
    return ok(updated, request_id)


@router.post("/proxy/clear", response_model=Envelope[ImageProxyClearResult], summary="清空图片代理缓存")
def clear_image_proxy(
    request_id: str = Depends(get_request_id),
) -> Envelope[ImageProxyClearResult]:
    res = image_proxy_service.clear_proxy_cache()
    audit("clear_image_proxy", request_id, freed_mb=res.freed_mb)
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
        for t, u, s_name in default_samples:
            posters.append(SamplePosterItem(title=t, url=u, site=s_name))

    return ok(SamplePostersPayload(items=posters), request_id)
