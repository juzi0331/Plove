"""统一数据抓取 API，同时支持 Python 独立采集脚本与 JSON 规则。"""

from typing import Any
from fastapi import APIRouter, Query

from ..engine.rule_manager import rule_manager
from ..engine.scraper import UniversalScraper

router = APIRouter(prefix="/api/v1/scrape", tags=["scrape"])


async def _execute_scrape(site_key: str, action: str, **kwargs: Any) -> dict[str, Any]:
    """统一调度器：优先运行 sites/<key>.py 独立采集器，次选运行 JSON 规则引擎。"""
    if rule_manager.has_script(site_key):
        return await rule_manager.execute_script_action(site_key, action, **kwargs)

    rule = rule_manager.get_rule(site_key)
    scraper = UniversalScraper(rule)
    return await scraper.execute(action, **kwargs)


@router.post("/{site_key}/home")
async def scrape_home(site_key: str):
    data = await _execute_scrape(site_key, "home")
    return {"ok": True, "data": data, "error": None}


@router.post("/{site_key}/category")
async def scrape_category(
    site_key: str,
    tid: str = Query(..., description="分类 ID"),
    page: int = Query(1, ge=1, description="页码"),
):
    data = await _execute_scrape(site_key, "category", tid=tid, page=page)
    return {"ok": True, "data": data, "error": None}


@router.post("/{site_key}/detail")
async def scrape_detail(
    site_key: str,
    id: str = Query(..., description="影片 ID"),
):
    data = await _execute_scrape(site_key, "detail", id=id)
    return {"ok": True, "data": data, "error": None}


@router.post("/{site_key}/play")
async def scrape_play(
    site_key: str,
    id: str = Query("", description="影片 ID"),
    ep: int = Query(1, ge=1, description="集数编号"),
    play_id: str = Query("", description="加速通道 play_id"),
    line: str = Query("", description="播放线路标识"),
):
    data = await _execute_scrape(site_key, "play", id=id, ep=ep, play_id=play_id, line=line)
    return {"ok": True, "data": data, "error": None}


@router.post("/{site_key}/search")
async def scrape_search(
    site_key: str,
    kw: str = Query(..., description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
):
    data = await _execute_scrape(site_key, "search", kw=kw, page=page)
    return {"ok": True, "data": data, "error": None}

