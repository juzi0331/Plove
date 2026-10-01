"""统一数据抓取 API。"""

from typing import Optional
from fastapi import APIRouter, Query

from ..core.errors import CrawlerServiceError, ErrorCode
from ..engine.rule_manager import rule_manager
from ..engine.scraper import UniversalScraper

router = APIRouter(prefix="/api/v1/scrape", tags=["scrape"])


def _get_scraper(site_key: str) -> UniversalScraper:
    rule = rule_manager.get_rule(site_key)
    return UniversalScraper(rule)


@router.post("/{site_key}/home")
async def scrape_home(site_key: str):
    scraper = _get_scraper(site_key)
    data = await scraper.execute("home")
    return {"ok": True, "data": data, "error": None}


@router.post("/{site_key}/category")
async def scrape_category(
    site_key: str,
    tid: str = Query(..., description="分类 ID"),
    page: int = Query(1, ge=1, description="页码"),
):
    scraper = _get_scraper(site_key)
    data = await scraper.execute("category", tid=tid, page=page)
    return {"ok": True, "data": data, "error": None}


@router.post("/{site_key}/detail")
async def scrape_detail(
    site_key: str,
    id: str = Query(..., description="影片 ID"),
):
    scraper = _get_scraper(site_key)
    data = await scraper.execute("detail", id=id)
    return {"ok": True, "data": data, "error": None}


@router.post("/{site_key}/play")
async def scrape_play(
    site_key: str,
    id: str = Query("", description="影片 ID"),
    ep: int = Query(1, ge=1, description="集数编号"),
    play_id: str = Query("", description="加速通道 play_id"),
    line: str = Query("", description="播放线路标识"),
):
    scraper = _get_scraper(site_key)
    data = await scraper.execute("play", id=id, ep=ep, play_id=play_id, line=line)
    return {"ok": True, "data": data, "error": None}


@router.post("/{site_key}/search")
async def scrape_search(
    site_key: str,
    kw: str = Query(..., description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
):
    scraper = _get_scraper(site_key)
    data = await scraper.execute("search", kw=kw, page=page)
    return {"ok": True, "data": data, "error": None}
