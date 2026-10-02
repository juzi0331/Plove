"""在线探针、试播台与跨源聚合搜索服务。

允许后台运维人员：
1. 实时向任意内容源发起命令探测（home / category / detail / play）；
2. 毫秒级耗时监控、精确判断缓存命中（CACHE HIT vs CRAWLER FETCH）；
3. 对比源站爬虫原始返回 JSON vs 经过系统清洗策略（去广告/分类重命名）后的结构；
4. 解析出可直接在线试播的视频流地址（m3u8）；
5. 跨源聚合并发搜索比对。
"""

from __future__ import annotations

import time
from typing import Any

from app.cache.content import ContentCache
from app.crawler.registry import SiteRegistry
from app.schemas.admin_extended import (
    AggregateSearchPayload,
    AggregateSearchSiteResult,
    PlaygroundProbeRequest,
    PlaygroundProbeResult,
)
from app.services import catalog_service


def run_probe(
    registry: SiteRegistry,
    cache: ContentCache,
    req: PlaygroundProbeRequest,
) -> PlaygroundProbeResult:
    """执行单次探针测试。"""
    site = req.site
    command = req.command
    t0 = time.perf_counter()

    # 1. 尝试探测缓存命中状态
    cache_hit = False
    raw_data: Any = None
    cleaned_data: Any = None
    playback_url: str | None = None

    try:
        if command == "home":
            cache_key = f"{site}|home|-"
            if not req.bypass_cache:
                raw_cache = cache._store.get(cache_key)
                if raw_cache is not None:
                    cache_hit = True

            # 清洗后的业务数据
            cleaned = catalog_service.home(registry, cache, site, force=req.bypass_cache)
            cleaned_data = cleaned.model_dump()
            # 原始爬虫未清洗数据
            try:
                raw_data = registry.run(site, "home")
            except Exception:
                raw_data = cleaned_data

        elif command == "category":
            tid = req.tid
            page = req.page
            cache_key = f"{site}|category|{tid or '-'}:{page}"
            if not req.bypass_cache:
                raw_cache = cache._store.get(cache_key)
                if raw_cache is not None:
                    cache_hit = True

            cleaned = catalog_service.category(registry, cache, site, tid=tid, page=page, force=req.bypass_cache)
            cleaned_data = cleaned.model_dump()
            try:
                options: dict[str, Any] = {"page": page}
                if tid:
                    options["tid"] = tid
                raw_data = registry.run(site, "category", **options)
            except Exception:
                raw_data = cleaned_data

        elif command == "detail":
            if not req.vod_id:
                raise ValueError("detail 命令必须指定 vod_id 参数")
            vod_id = req.vod_id
            cache_key = f"{site}|detail|{vod_id}"
            if not req.bypass_cache:
                raw_cache = cache._store.get(cache_key)
                if raw_cache is not None:
                    cache_hit = True

            cleaned = catalog_service.detail(registry, cache, site, vod_id=vod_id, force=req.bypass_cache)
            cleaned_data = cleaned.model_dump()
            try:
                raw_data = registry.run(site, "detail", vod_id=vod_id)
            except Exception:
                raw_data = cleaned_data

        elif command == "play":
            if not req.vod_id:
                raise ValueError("play 命令必须指定 vod_id 参数")
            # 播放永远不缓存
            cache_hit = False
            pb = catalog_service.playback(registry, site, req.vod_id, ep=req.ep)
            cleaned_data = pb.model_dump()
            raw_data = cleaned_data
            playback_url = pb.url

        else:
            raise ValueError(f"未知探针命令: {command}")

        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        return PlaygroundProbeResult(
            site=site,
            command=command,
            elapsed_ms=elapsed,
            cache_hit=cache_hit,
            status="OK",
            raw_data=raw_data,
            cleaned_data=cleaned_data,
            playback_url=playback_url,
        )

    except Exception as exc:
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        return PlaygroundProbeResult(
            site=site,
            command=command,
            elapsed_ms=elapsed,
            cache_hit=False,
            status="ERROR",
            error_detail=str(exc),
        )


def aggregate_search(
    registry: SiteRegistry,
    kw: str,
    timeout_seconds: float = 8.0,
) -> AggregateSearchPayload:
    """跨源并发搜索比对。"""
    keys = registry.enabled_keys()
    results: list[AggregateSearchSiteResult] = []

    def _search_single(k: str) -> AggregateSearchSiteResult:
        t_start = time.perf_counter()
        meta = registry.meta(k)
        site_name = meta.name if meta else k
        if not registry.supports(k, "search"):
            return AggregateSearchSiteResult(
                site=k,
                site_name=site_name,
                supported=False,
                count=0,
                elapsed_ms=round((time.perf_counter() - t_start) * 1000, 2),
                error="该源声明不支持搜索能力",
            )
        try:
            res = catalog_service.search(registry, k, kw=kw, page=1)
            items = [item.model_dump() for item in res.items[:6]]
            return AggregateSearchSiteResult(
                site=k,
                site_name=site_name,
                supported=True,
                count=len(res.items),
                elapsed_ms=round((time.perf_counter() - t_start) * 1000, 2),
                items=items,
            )
        except Exception as exc:
            return AggregateSearchSiteResult(
                site=k,
                site_name=site_name,
                supported=True,
                count=0,
                elapsed_ms=round((time.perf_counter() - t_start) * 1000, 2),
                error=str(exc),
            )

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(keys) or 1)) as pool:
        future_map = {pool.submit(_search_single, k): k for k in keys}
        for fut in concurrent.futures.as_completed(future_map, timeout=timeout_seconds + 1):
            try:
                results.append(fut.result())
            except Exception as e:
                k = future_map[fut]
                results.append(
                    AggregateSearchSiteResult(
                        site=k,
                        site_name=k,
                        supported=True,
                        count=0,
                        elapsed_ms=timeout_seconds * 1000,
                        error=f"并发超时或异常: {e}",
                    )
                )

    total_count = sum(r.count for r in results)
    return AggregateSearchPayload(
        kw=kw,
        total_sites=len(results),
        total_count=total_count,
        results=results,
    )
