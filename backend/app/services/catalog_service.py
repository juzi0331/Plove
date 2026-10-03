"""目录类编排：首页 / 列表 / 详情 / 播放 / 搜索。

这一层只做三件事：**走注册表拿数据**、**按契约校验**、**抛业务错误**。
超时、子进程、并发上限、熔断、解析全在 crawler 层，这里看不见。

缓存也在这里接，而不是塞进 crawler 层：crawler 层管的是"怎么跟源站说话"
（每次都该真说话，还要记熔断），而"这份数据能重复用多久"是业务判断。
两者混在一起，就会出现"熔断器要不要统计缓存命中"这种答不上来的问题。

**播放与搜索不缓存**，理由见 :mod:`app.cache.content`：

* 播放地址带时效签名，缓存等于把失效地址发给用户；
* 搜索关键词近乎无穷，命中率低。

``force=True`` 是给**主动预热**用的：跳过读缓存、把旧值换掉。
"""

from __future__ import annotations

import re
from typing import TypeVar
from urllib.parse import quote

from pydantic import BaseModel

from app.cache.content import ContentCache
from app.crawler.registry import SiteRegistry
from app.crawler.validate import validate_payload
from app.schemas.catalog import DetailPayload, HomePayload, ListPayload
from app.schemas.playback import Playback

T = TypeVar("T", bound=BaseModel)

#: ``play_id`` 里不允许出现的东西：空白、反斜杠、协议分隔符。
#: 另外凡是**以 ``//`` 开头**的一律拒绝 —— 那是"协议相对 URL"，
#: 拼上 base 之后主机就被换掉了（只检查"以 / 开头"会正好把它放过去）。
_FORBIDDEN_PLAY_ID = re.compile(r"[\s\\]|://|^//|(?:^|/)\.\.(?:/|$)")


def _clean_play_id(value: str | None) -> str | None:
    """把上层回传的 ``play_id`` 收敛一下：**不像站内定位符就丢掉**。

    ``play_id`` 会被原样交给爬虫去抓取，所以它是一处信任边界：一个绝对 URL
    就能让我们顺手代理任意地址（SSRF），抓回来的东西还会当成播放地址吐给用户。

    这里刻意选择**丢掉并回退**（退回"爬虫自己再抓一次详情页"那条慢路径），
    而不是报错拒绝 —— 一个奇怪的值不该让用户看不了片。
    爬虫那侧还有同样的兜底（``clean.safe_relative_path``），两边都拦。
    """
    if not value:
        return None
    text = value.strip()
    if not text or len(text) > 300 or _FORBIDDEN_PLAY_ID.search(text):
        return None
    return text


def _ensure_enabled(registry: SiteRegistry, key: str) -> None:
    """被后台停用的源，要在**查缓存之前**就被拦掉。

    只在注册表（``registry.run``）里拦是不够的：首页 / 分类 / 详情都有缓存，
    一个还热着的条目会在 TTL 内继续被发出去 —— 那正是"已经关掉了，用户却还能看"。

    所以两处都拦，各自管一条路：

    * 这里（service 层）管 **读缓存**这条捷径；
    * 注册表管 **真去抓**那条路（也是唯一通往爬虫的关口）。
    """
    registry.ensure_enabled(key)


def _load(model: type[T], registry: SiteRegistry, key: str, command: str, **options: object) -> T:
    """抓一次 + 过契约。支持单站自定义超时。"""
    store = site_settings.store()
    cfg = store.config(key)
    timeout = cfg.timeout_seconds if cfg.timeout_seconds > 0 else None
    return validate_payload(
        model,
        registry.run(key, command, custom_timeout=timeout, **options),
        key=key,
        command=command,
    )


from app.services import site_control_service, site_settings
from app.services.site_settings import SiteSettingsStore


def home(
    registry: SiteRegistry,
    cache: ContentCache,
    key: str,
    store: SiteSettingsStore | None = None,
    *,
    force: bool = False,
) -> HomePayload:
    _ensure_enabled(registry, key)
    actual_store = store or site_settings.store()

    def _assemble() -> HomePayload:
        raw = _load(HomePayload, registry, key, "home")
        filtered_categories = site_control_service.apply_category_rules(key, raw.categories, actual_store)

        # 计算应在首页展示的分类计划（后台勾选 或 新站点默认前 3 个）
        plans = site_control_service.get_home_display_category_plans(key, filtered_categories, actual_store)
        custom_sections: list[HomeSection] = []
        from app.schemas.catalog import HomeSection

        for plan in plans:
            try:
                cat_res = category(
                    registry,
                    cache,
                    key,
                    tid=plan["tid"],
                    page=1,
                    store=actual_store,
                    force=force,
                )
                if cat_res and cat_res.videos:
                    # 严格只展示前 10 个视频
                    custom_sections.append(
                        HomeSection(
                            title=plan["title"],
                            tid=plan["tid"],
                            videos=cat_res.videos[:10],
                        )
                    )
            except Exception:
                pass

        if custom_sections:
            # 用户确认选择方案 A（前台完全替代）：以真实分类横幅注入 sections
            return raw.model_copy(
                update={
                    "categories": filtered_categories,
                    "sections": custom_sections,
                }
            )

        return raw.model_copy(update={"categories": filtered_categories})

    policy = site_control_service.get_site_cache_policy(actual_store, key)
    return cache.home(key, _assemble, force=force, ttl=policy.home_ttl)


def category(
    registry: SiteRegistry,
    cache: ContentCache,
    key: str,
    tid: str | None = None,
    page: int = 1,
    store: SiteSettingsStore | None = None,
    *,
    force: bool = False,
) -> ListPayload:
    _ensure_enabled(registry, key)
    actual_store = store or site_settings.store()
    site_control_service.check_category_allowed(key, tid, actual_store)
    options: dict[str, object] = {"page": page}
    if tid:
        options["tid"] = tid
    policy = site_control_service.get_site_cache_policy(actual_store, key)
    return cache.category(
        key,
        tid,
        page,
        lambda: _load(ListPayload, registry, key, "category", **options),
        force=force,
        ttl=policy.category_ttl,
    )


def search(registry: SiteRegistry, key: str, kw: str, page: int = 1) -> ListPayload:
    """搜索。源没这个能力的话，注册表会先抛 ``UNSUPPORTED``。

    这个区分很重要：**"该源不支持搜索"和"搜到 0 条"对用户是两件事**，
    不允许用空列表蒙混过去。
    """
    _ensure_enabled(registry, key)
    return _load(ListPayload, registry, key, "search", kw=kw, page=page)


def detail(
    registry: SiteRegistry,
    cache: ContentCache,
    key: str,
    vod_id: str,
    store: SiteSettingsStore | None = None,
    *,
    force: bool = False,
) -> DetailPayload:
    _ensure_enabled(registry, key)
    actual_store = store or site_settings.store()
    policy = site_control_service.get_site_cache_policy(actual_store, key)
    raw = cache.detail(
        key,
        vod_id,
        lambda: _load(DetailPayload, registry, key, "detail", id=vod_id),
        force=force,
        ttl=policy.detail_ttl,
    )
    return site_control_service.apply_detail_policy(
        key, raw, actual_store, registry=registry
    )


def playback(
    registry: SiteRegistry,
    key: str,
    vod_id: str,
    ep: int = 1,
    line: int | None = None,
    play_id: str | None = None,
) -> Playback:
    """取播放地址。

    注意：**地址绝不入库、也绝不缓存**。m3u8 普遍带时效签名（2048ai 的
    ``auth_key``、ncat21 的 ``timestamp``），所以每次播放都得现取。

    ``play_id`` 是**加速通道**：详情里每集都带着它，上层原样传回来，
    源就不用"为了找到这一集而再抓一遍详情页"。实测 ncat21 的详情要 3.5 秒，
    而它的播放页只需一次请求。传不传都能用 —— 不传就退回慢路径。
    """
    _ensure_enabled(registry, key)
    meta = registry.meta(key)

    if line is None:
        cached_line = site_control_service.get_cached_fastest_line(key, vod_id)
        if cached_line is not None:
            line = cached_line

    options: dict[str, object] = {"id": vod_id, "ep": ep}
    if line is not None:
        options["line"] = line
    cleaned = _clean_play_id(play_id)
    if cleaned is not None:
        options["play_id"] = cleaned

    raw = _load(Playback, registry, key, "play", **options)

    # 阶段 9 流代理：若该源标记为 mode == "proxy"，通过后端流中继代理以支持伪装容器解封装与防盗链穿透
    if meta.mode == "proxy":
        proxy_url = f"/api/v1/proxy/stream/m3u8?site={quote(key)}&url={quote(raw.url)}"
        return raw.model_copy(update={"url": proxy_url, "headers": {}})

    return raw
