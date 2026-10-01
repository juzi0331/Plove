"""带 TTL 与容量上限的内存缓存。

两条行为要记牢：

* **``get`` 返回 ``None`` 表示"没有"** —— 所以它缓存不了 ``None`` 本身。
  这里存的全是校验过的模型，从来不是 ``None``，所以这个限制无害。
* **过期即当作不存在**（顺手删掉），不做"过期了但还能捞出来"那套。
  需要"拿旧值兜底"的地方自己决定，不在这里偷偷兜。

线程安全：所有操作都在同一把 ``RLock`` 下。服务是同步的（FastAPI 把同步路由
丢进线程池），所以必须有锁 —— 不加锁的 dict 在并发写时会出现"键在、值没了"。
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    """容量有限、条目会过期的字典。淘汰顺序是 LRU。"""

    def __init__(
        self,
        maxsize: int = 512,
        ttl: float = 60.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if maxsize <= 0:
            raise ValueError("maxsize 必须为正数")
        self.maxsize = maxsize
        #: 默认存活时间（秒）。单次 ``set`` 可以覆盖它。
        self.default_ttl = ttl
        #: 单调时钟。测试注入假时钟，就不用为了验过期真的 sleep。
        #: 刻意用 ``monotonic`` 而不是 ``time.time`` —— 系统时间被改（NTP 回拨）时，
        #: 用 ``time.time`` 计算过期会让缓存集体"穿越"，要么永不失效要么瞬间全空。
        self._clock: Callable[[], float] = clock or time.monotonic
        self._lock = threading.RLock()
        #: key -> (值, 到期时刻)。OrderedDict 的顺序就是 LRU 顺序（最旧在最前）。
        self._data: OrderedDict[str, tuple[T, float]] = OrderedDict()
        self.hits = 0
        self.misses = 0

    # ------------------------------------------------------------------ 读写

    def get(self, key: str) -> T | None:
        """取值。没有或已过期都返回 ``None``。"""
        with self._lock:
            item = self._data.get(key)
            if item is None:
                self.misses += 1
                return None
            value, expires_at = item
            if expires_at <= self._clock():
                del self._data[key]
                self.misses += 1
                return None
            # 摸一下就挪到尾巴：LRU 淘汰时最先被砍的是最久没用的那个
            self._data.move_to_end(key)
            self.hits += 1
            return value

    def set(self, key: str, value: T, ttl: float | None = None) -> None:
        with self._lock:
            lifetime = self.default_ttl if ttl is None else ttl
            if lifetime <= 0:
                # TTL 为 0 的意思是"这类东西不要缓存"，而不是"存一个立刻过期的"
                self._data.pop(key, None)
                return
            self._data[key] = (value, self._clock() + lifetime)
            self._data.move_to_end(key)
            self._evict()

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    # ------------------------------------------------------------------ 内部

    def _evict(self) -> None:
        """先清过期项，再按 LRU 砍到容量以内。"""
        now = self._clock()
        for key in [k for k, (_, expires_at) in self._data.items() if expires_at <= now]:
            del self._data[key]
        while len(self._data) > self.maxsize:
            self._data.popitem(last=False)

    def get_detailed(self, key: str) -> tuple[T | None, bool]:
        """取值并明确指出是否命中。"""
        with self._lock:
            val = self.get(key)
            return val, val is not None

    def invalidate_prefix(self, prefix: str) -> int:
        """按前缀批量清除（如批量清除单个站点的所有缓存条目）。"""
        with self._lock:
            to_remove = [k for k in self._data if k.startswith(prefix)]
            for k in to_remove:
                del self._data[k]
            return len(to_remove)

    def list_entries(self) -> list[dict[str, Any]]:
        """列出当前所有有效未过期条目及剩余存活秒数。"""
        with self._lock:
            now = self._clock()
            res: list[dict[str, Any]] = []
            for k, (_, expires_at) in list(self._data.items()):
                remaining = max(0.0, expires_at - now)
                if remaining > 0:
                    res.append({"key": k, "remaining_seconds": round(remaining, 1)})
            return res

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {"size": len(self._data), "maxsize": self.maxsize, "hits": self.hits, "misses": self.misses}

