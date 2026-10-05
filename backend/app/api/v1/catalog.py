"""目录接口：首页 / 列表 / 详情 / 播放 / 搜索。

**id 一律走查询参数，不走路径段。** 原因：``vod_id`` 的约定是"可复现的定位符"，
多线路源会用**完整路径**当 id（见 crawler-plan.md 里那个"最容易踩的坑"），
而路径段里塞斜杠要额外转义、还容易被反代改写。查询参数没这个问题。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query

from app.api.deps import get_content_cache, get_registry, require_device
from app.cache.content import ContentCache
from app.core.middleware import get_request_id
from app.crawler.registry import SiteRegistry
from app.schemas.catalog import DetailPayload, HomePayload, ListPayload
from app.schemas.envelope import Envelope, ok
from app.schemas.playback import Playback
from app.services import catalog_service

#: 内容接口全部需要「当前活跃设备」才放行
router = APIRouter(tags=["目录"], dependencies=[Depends(require_device)])


@router.get("/sites/{key}/home", response_model=Envelope[HomePayload], summary="首页")
def home(
    key: str,
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
    cache: ContentCache = Depends(get_content_cache),
) -> Envelope[HomePayload]:
    return ok(catalog_service.home(registry, cache, key), request_id)


@router.get("/sites/{key}/category", response_model=Envelope[ListPayload], summary="分类列表")
def category(
    key: str,
    tid: str | None = Query(None, description="站内分类 id；留空表示该源的默认分类"),
    page: int = Query(1, ge=1),
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
    cache: ContentCache = Depends(get_content_cache),
) -> Envelope[ListPayload]:
    return ok(catalog_service.category(registry, cache, key, tid=tid, page=page), request_id)


@router.get("/sites/{key}/search", response_model=Envelope[ListPayload], summary="搜索")
def search(
    key: str,
    kw: str = Query(..., min_length=1, description="关键词"),
    page: int = Query(1, ge=1),
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
) -> Envelope[ListPayload]:
    """目前两个源都还没实现搜索，都会明确返回 ``UNSUPPORTED``。

    这不是"没做完"，而是设计要的：**"该源不支持搜索"必须和"搜到 0 条"分开**。
    """
    return ok(catalog_service.search(registry, key, kw=kw, page=page), request_id)


@router.get("/sites/{key}/detail", response_model=Envelope[DetailPayload], summary="详情")
def detail(
    key: str,
    vod_id: str = Query(..., description="影片 id（爬虫给的定位符，原样回传）"),
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
    cache: ContentCache = Depends(get_content_cache),
) -> Envelope[DetailPayload]:
    return ok(catalog_service.detail(registry, cache, key, vod_id), request_id)


@router.get("/sites/{key}/playback", response_model=Envelope[Playback], summary="播放地址")
def playback(
    key: str,
    vod_id: str = Query(..., description="影片 id"),
    ep: int = Query(1, ge=1, description="集号，1 起算"),
    line: int | None = Query(None, ge=1, description="线路号，多线路源才需要"),
    play_id: str | None = Query(
        None,
        max_length=300,
        description="详情里那一集的 play_id，原样回传可省掉爬虫的一次源站请求；"
        "不传也能用，只是慢一点",
    ),
    token: str | None = Query(None, description="可选的设备或鉴权令牌"),
    x_device_token: str | None = Header(None, alias="X-Device-Token"),
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
) -> Envelope[Playback]:
    """**每次播放现取，绝不缓存地址。**

    m3u8 普遍带时效签名（2048ai 的 ``auth_key``、ncat21 的 ``timestamp``），
    存下来的地址几分钟后一定是废的。所以这条路径**刻意不接**缓存。

    ``play_id`` 走的是"**丢掉不报错**"策略（见
    :func:`app.services.catalog_service._clean_play_id`）：不像站内定位符就忽略它，
    而不是回 4xx —— 它是加速用的，不该成为一个新的失败原因。
    """
    active_token = x_device_token or token
    return ok(
        catalog_service.playback(
            registry, key, vod_id, ep=ep, line=line, play_id=play_id, token=active_token
        ),
        request_id,
    )
