"""SingleFlight：同一个 key 的并发调用只真跑一次，其余等同一份结果。

解决的是**缓存击穿**：缓存刚好过期的那一瞬间，5 个请求同时进来，
如果都去"重新算一遍"，那就是 5 个子进程、5 次源站请求 —— 而它们要的
是同一份东西。缓存本来是为了省压力，结果在最坏的时刻把压力放了五倍。

分工很明确：

* :class:`~app.cache.ttl.TTLCache` 挡住**先后到达**的重复请求；
* :class:`SingleFlight` 挡住**同时到达**的重复请求。

只靠缓存不行，只靠这个也不行。

**异常也会传给所有等待者** —— 等待者等的是"那次调用的结果"，失败也是结果。
否则第一个人的失败会变成其他人的"缓存未命中"，于是他们又各自重试一遍，
Source 站承受的正是我们想避免的重复流量。
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


class _Flight:
    """一次在飞的调用：一个事件 + 结果（或异常）。"""

    __slots__ = ("_event", "_value", "_error")

    def __init__(self) -> None:
        self._event = threading.Event()
        self._value: Any = None
        self._error: BaseException | None = None

    def finish(self, value: Any) -> None:
        self._value = value
        self._event.set()

    def fail(self, error: BaseException) -> None:
        self._error = error
        self._event.set()

    def wait(self, timeout: float | None = None) -> Any:
        if not self._event.wait(timeout):
            raise TimeoutError("等待同一个 key 的在飞调用超时")
        if self._error is not None:
            raise self._error
        return self._value


class SingleFlight:
    """按 key 合并并发调用。"""

    def __init__(self, wait_timeout: float | None = None) -> None:
        #: 等待者最多等多久。默认不限 —— 领跑者自己受爬虫超时约束，
        #: 一定会结束。给个上限只是为了极端情况（领跑者所在线程卡死）不留挂。
        self.wait_timeout = wait_timeout
        self._lock = threading.Lock()
        self._flights: dict[str, _Flight] = {}

    def do(self, key: str, work: Callable[[], T]) -> T:
        """执行 ``work``，但同一个 ``key`` 同时只会有一次真正在跑。"""
        with self._lock:
            flight = self._flights.get(key)
            leader = flight is None
            if leader:
                flight = _Flight()
                self._flights[key] = flight

        assert flight is not None
        if not leader:
            # 跟着别人走：他成功我就成功，他失败我就失败
            return flight.wait(self.wait_timeout)

        try:
            value = work()
        except BaseException as exc:
            flight.fail(exc)
            raise
        else:
            flight.finish(value)
            return value
        finally:
            # 一定要摘掉，否则后面的人会永远等到一个"已经结束的调用"
            with self._lock:
                self._flights.pop(key, None)

    def active(self) -> int:
        """当前有几个 key 在飞（观测用）。"""
        with self._lock:
            return len(self._flights)
