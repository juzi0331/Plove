"""后台 — 缓存中心与预热控制。"""

from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    commit_now,
    get_content_cache,
    get_db,
    get_registry,
    get_warmup_runner,
)
from app.api.v1.admin._audit import audit
from app.api.v1.admin._helpers import preheat_single_site, save_system_setting_json
from app.cache.content import ContentCache
from app.core.errors import AppError, ErrorCode
from app.core.middleware import get_request_id
from app.crawler.registry import SiteRegistry
from app.schemas.admin_extended import (
    CacheClearRequest,
    CacheClearResult,
    CacheEntryDetail,
    CacheGlobalConfig,
    CacheKeyEntry,
    CachePreheatRequest,
    CachePreheatResult,
    CacheStatsPayload,
    SitePreheatDetail,
)
from app.schemas.envelope import Envelope, ok
from app.services.warmup_service import WarmupRunner

router = APIRouter(tags=["后台-缓存中心"])


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
    cache.enabled = payload.cache_enabled
    warmup.enabled = payload.warmup_enabled
    if payload.warmup_interval_seconds > 0:
        warmup.interval_seconds = payload.warmup_interval_seconds

    save_system_setting_json(db, "content_cache_config", {"cache_enabled": payload.cache_enabled})
    save_system_setting_json(
        db,
        "warmup_config",
        {"warmup_enabled": payload.warmup_enabled, "warmup_interval_seconds": payload.warmup_interval_seconds},
    )
    commit_now(db)
    audit(
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
    raw_keys = cache.list_keys(site=site, namespace=namespace)
    entries = [CacheKeyEntry(**k) for k in raw_keys]
    return ok(entries, request_id)


@router.get("/cache/entry", response_model=Envelope[CacheEntryDetail], summary="查看单条缓存数据详情")
def get_cache_entry(
    key: str = Query(..., description="完整的缓存 Key"),
    request_id: str = Depends(get_request_id),
    cache: ContentCache = Depends(get_content_cache),
) -> Envelope[CacheEntryDetail]:
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

    dumped = raw_val.model_dump() if hasattr(raw_val, "model_dump") else raw_val
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
    if payload.key:
        cache.invalidate_key(payload.key)
        audit("cache_clear_key", request_id, key=payload.key)
        return ok(CacheClearResult(cleared_count=1, message=f"已成功删除缓存键: {payload.key}"), request_id)
    if payload.site:
        count = cache.invalidate_site(payload.site)
        audit("cache_clear_site", request_id, site=payload.site, count=count)
        return ok(CacheClearResult(cleared_count=count, message=f"已成功清除站点 [{payload.site}] 的 {count} 条缓存"), request_id)

    before = len(cache._store)
    cache.clear()
    audit("cache_clear_all", request_id, count=before)
    return ok(CacheClearResult(cleared_count=before, message=f"已全量清空所有系统缓存（共 {before} 条）"), request_id)


@router.post("/cache/preheat", response_model=Envelope[CachePreheatResult], summary="主动预热缓存")
def preheat_cache(
    payload: CachePreheatRequest,
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
    cache: ContentCache = Depends(get_content_cache),
) -> Envelope[CachePreheatResult]:
    t0 = time.perf_counter()
    target_sites = [payload.site] if payload.site else registry.keys()
    preheated: list[str] = []
    details: list[SitePreheatDetail] = []

    for s in target_sites:
        detail = preheat_single_site(registry, cache, s)
        if detail:
            preheated.append(s)
            details.append(detail)  # type: ignore

    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    audit("cache_preheat", request_id, sites=preheated, elapsed_ms=elapsed)
    return ok(
        CachePreheatResult(
            success=len(preheated) > 0,
            preheated_sites=preheated,
            elapsed_ms=elapsed,
            details=details,
        ),
        request_id,
    )
