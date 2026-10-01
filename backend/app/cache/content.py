"""目录类内容的缓存策略：缓存哪些、缓存多久、失败怎么办。

三件事说清楚：

**缓存什么。** 只有"抓一次能给别人用"的东西 —— 首页、分类列表、详情。
**不缓存播放地址**：m3u8 普遍带时效签名（2048ai 的 ``auth_key``、
ncat21 的 ``timestamp``），存下来的地址几分钟后一定是废的。
也不缓存搜索：关键词近乎无穷，缓存命中率低，还会把"看错页面"留在缓存里。

**缓存多久。** 按"这东西多久会变"来定，而不是按"能省多少"来定：

===================  ========  ====================================================
命名空间             默认 TTL  为什么
===================  ========  ====================================================
``home``             10 分钟   分类树和首页推荐几乎不变，却要 fork 一次子进程去抓
``category``          5 分钟   列表会随新片上架变化，但不需要秒级
``detail``            5 分钟   剧集列表会更新；用户来回点同一部片很常见
``playback``          不缓存   **地址有时效**，缓存等于把失效地址发给用户
``search``            不缓存   命中率低，且结果随时间变化快
===================  ========  ====================================================

**失败怎么办。** **只缓存成功的结果。** 把一次网络抖动缓存 5 分钟，
用户会以为整个源站坏了；而重试一次很可能就好了。所以错误一律穿过缓存。

"拿旧值兜底"（stale-while-error）**刻意没做**：它会把"源站已经挂了"
伪装成"一切正常"，而这个项目一直在坚持"错误要诚实"（比如
"该源不支持搜索"不许伪装成"搜到 0 条"）。真要兜底，应该由使用者
显式决定，而不是在这里悄悄发生。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from app.cache.singleflight import SingleFlight
from app.cache.ttl import TTLCache

T = TypeVar("T")


class ContentCache:
    """目录内容的缓存 + 防击穿。TTL 设成 0 就等于关掉那一类缓存。"""

    def __init__(
        self,
        ttl_home: float = 600.0,
        ttl_category: float = 300.0,
        ttl_detail: float = 300.0,
        maxsize: int = 512,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.ttl_home = ttl_home
        self.ttl_category = ttl_category
        self.ttl_detail = ttl_detail
        self._store: TTLCache[Any] = TTLCache(maxsize=maxsize, ttl=ttl_home, clock=clock)
        self._inflight = SingleFlight()

    # ------------------------------------------------------------------ 取数

    def home(self, site: str, compute: Callable[[], T], *, force: bool = False) -> T:
        return self._fetch("home", site, "-", self.ttl_home, compute, force)

    def category(
        self,
        site: str,
        tid: str | None,
        page: int,
        compute: Callable[[], T],
        *,
        force: bool = False,
    ) -> T:
        return self._fetch("category", site, f"{tid or '-'}:{page}", self.ttl_category, compute, force)

    def detail(self, site: str, vod_id: str, compute: Callable[[], T], *, force: bool = False) -> T:
        return self._fetch("detail", site, vod_id, self.ttl_detail, compute, force)

    # ------------------------------------------------------------------ 维护

    def clear(self) -> None:
        self._store.clear()

    def invalidate_site(self, site: str) -> int:
        """清空指定站点的所有缓存数据。"""
        return self._store.invalidate_prefix(f"{site}|")

    def invalidate_key(self, key: str) -> None:
        """清空指定 key 的缓存。"""
        self._store.invalidate(key)

    def list_keys(
        self,
        site: str | None = None,
        namespace: str | None = None,
    ) -> list[dict[str, Any]]:
        """列出当前内存中的所有缓存条目，支持按站点和命名空间过滤。"""
        raw_entries = self._store.list_entries()
        items: list[dict[str, Any]] = []
        for entry in raw_entries:
            key = entry["key"]
            parts = key.split("|", 2)
            if len(parts) == 3:
                e_site, e_ns, e_ident = parts[0], parts[1], parts[2]
            else:
                e_site, e_ns, e_ident = "unknown", "unknown", key
            
            if site and e_site != site:
                continue
            if namespace and e_ns != namespace:
                continue

            items.append({
                "key": key,
                "site": e_site,
                "namespace": e_ns,
                "ident": e_ident,
                "remaining_seconds": entry["remaining_seconds"],
            })
        return items

    def stats(self) -> dict[str, Any]:
        base_stats = self._store.stats()
        hits = base_stats.get("hits", 0)
        misses = base_stats.get("misses", 0)
        total = hits + misses
        hit_ratio = round((hits / total) * 100, 1) if total > 0 else 0.0
        return {
            **base_stats,
            "hit_ratio_percent": hit_ratio,
            "inflight": self._inflight.active(),
            "ttl": {"home": self.ttl_home, "category": self.ttl_category, "detail": self.ttl_detail},
        }

    # ------------------------------------------------------------------ 内部

    def fetch_with_info(
        self,
        namespace: str,
        site: str,
        ident: str,
        ttl: float,
        compute: Callable[[], T],
        *,
        force: bool = False,
    ) -> tuple[T, bool, str]:
        """类似 _fetch，但同时返回 (结果, 是否命中缓存, cache_key)。"""
        key = f"{site}|{namespace}|{ident}"
        if ttl <= 0 and not force:
            return compute(), False, key

        if not force:
            val, hit = self._store.get_detailed(key)
            if hit and val is not None:
                return val, True, key

        res = self._inflight.do(key, lambda: self._fill(key, ttl, compute, force))
        return res, False, key

    def _fetch(
        self,
        namespace: str,
        site: str,
        ident: str,
        ttl: float,
        compute: Callable[[], T],
        force: bool = False,
    ) -> T:
        if ttl <= 0 and not force:
            return compute()

        key = f"{site}|{namespace}|{ident}"
        if not force:
            hit = self._store.get(key)
            if hit is not None:
                return hit

        # 未命中（或被要求强制重抓）：交给 SingleFlight 合并并发。
        # 击穿最容易发生在"刚好过期"的那一刻，所以判断和填值之间必须隔一层。
        return self._inflight.do(key, lambda: self._fill(key, ttl, compute, force))

    def _fill(self, key: str, ttl: float, compute: Callable[[], T], force: bool = False) -> T:
        # 轮到我们真跑了 —— 但可能在我们排队的那几毫秒里，别人已经填上了。
        # ``force`` 不看旧值：主动预热要的就是"把旧值换掉"。
        if not force:
            again = self._store.get(key)
            if again is not None:
                return again
        value = compute()
        self._store.set(key, value, ttl)
        return value
