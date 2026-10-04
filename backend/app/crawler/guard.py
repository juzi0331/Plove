"""站点守护：并发上限 + 熔断。

两个东西回答同一个问题：**某个源出问题时，怎么让本站活得体面。**

**并发上限。** 一个人连点两下、或者十个人同时打开同一个源，不该变成
十几个子进程一起去打源站。抢不到槽位就排队，排太久就明确回
``UPSTREAM_BUSY`` —— 让请求**快速失败**比让它无限等待好：等待会连着
占住连接和线程，最后大家一起超时。

限额分**两层**，因为防的是两件事：

* **每站**上限（默认 2）保护的是**源站**的耐心，也顺便保护我们自己；
* **全局**上限（默认 4）保护的是**这台 VPS** —— 没有它，源变多之后
  "每站 2" 会乘出 20 个并发子进程，内存和 CPU 一起完蛋。

两层都用固定的获取顺序（**先每站、再全局**）—— 顺序固定就不可能形成环，
也就不会死锁。反过来写就会：一个人持着全局等某个站，另一个持着那个站等全局。

**熔断。** 某源连续失败到阈值就"打开电路"，之后一段时间里每个请求
**立刻**拿到 ``UPSTREAM_CIRCUIT_OPEN``，不再去陪它耗满超时。冷却过后放入
**一个**探针（半开）：成功就恢复，失败就重新开始下一轮冷却。

熔断真正省下的是最贵的东西 —— 超时。一个挂掉的源如果每次请求都要
耗满 10 秒才失败，50 个请求就是 500 秒的线程被占着；熔断之后它们
在微秒级返回。

## 为什么 ``meta`` 不参与计数

一个源的健康状况由**内容**调用判定，不由 ``meta`` 判定：

* ``meta`` 是"源的身份证"，它被缓存、还可能拿旧值顶替（见
  :meth:`app.crawler.registry.SiteRegistry.meta`），所以它成功
  **不代表**现在抓得到内容；
* 每请求都会先跑一次 ``meta`` 再跑内容。如果两者都参与计数，
  序列就变成"内容失败、meta 成功、计数清零"，于是**那种 "meta 能通、
  抓内容就超时" 的源永远熔断不了** —— 而这正是我们最想熔断的一类源。

所以 ``meta`` 只走并发限流（它也是跟源站说话），不参与熔断判定：
``counts_as_health=False``。

## 什么算"源站故障"

:data:`SITE_FAILURE_CODES` 是白名单，不是"非零即失败"。这个区分很关键：

* ``NOT_FOUND``（这部片下架了）和 ``UNSUPPORTED``（该源没有搜索）
  都是**正确的回答**，不是故障。把它们算进失败计数，用户点几个
  失效链接就能把整个源"熔断"掉 —— 典型的误伤。
* 反过来，一个探针拿到 ``NOT_FOUND`` 也**不能**用来判定恢复
  （它只说明这一条数据不在，不说明源站活了），所以探针遇非故障错误时
  保持半开，等下一次探测。
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar

from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

#: 判为"源站有问题"的错误码。见模块开头为什么**不含** NOT_FOUND / UNSUPPORTED。
SITE_FAILURE_CODES: frozenset[ErrorCode] = frozenset(
    {
        ErrorCode.UPSTREAM_TIMEOUT,
        ErrorCode.UPSTREAM_HTTP_ERROR,
        ErrorCode.UPSTREAM_PARSE_ERROR,
        ErrorCode.UPSTREAM_BLOCKED,
        ErrorCode.UPSTREAM_UNKNOWN,
    }
)

CLOSED = "closed"
OPEN = "open"
HALF_OPEN = "half_open"


class SiteGuard:
    """一个源一把。并发槽 + 熔断器。"""

    def __init__(
        self,
        site: str,
        max_concurrency: int = 2,
        queue_timeout: float = 20.0,
        fail_threshold: int = 5,
        reset_seconds: float = 60.0,
        clock: Callable[[], float] | None = None,
        global_slots: threading.BoundedSemaphore | None = None,
    ) -> None:
        self.site = site
        self.max_concurrency = max(1, max_concurrency)
        self.queue_timeout = queue_timeout
        self.fail_threshold = max(1, fail_threshold)
        self.reset_seconds = reset_seconds
        self._clock: Callable[[], float] = clock or time.monotonic
        #: 全站共享的并发额。**故意是可写的属性**：这个名额不属于任何一个源，
        #: 由 :class:`app.crawler.registry.SiteRegistry` 造一份、分给每个守护。
        #: 为 ``None`` 表示不做全局限额（测试与小规模场景）。
        self.global_slots = global_slots

        #: 信号量就是并发上限本身 —— 不需要自己数"现在有几个"
        self._slots = threading.BoundedSemaphore(self.max_concurrency)
        self._lock = threading.Lock()
        self._failures = 0
        self._opened_at: float | None = None
        #: 半开状态下是否已有一个探针在路上。半开只放**一个** —— 放开全部
        #: 等于把刚缓过来的源站又打一遍（惊群）。
        self._probing = False

    # ------------------------------------------------------------------ 主流程

    def call(self, work: Callable[[], T], *, action: str = "", counts_as_health: bool = True) -> T:
        """在守护下执行一次上游调用。

        ``counts_as_health=False`` 用于 :meth:`app.crawler.registry.SiteRegistry.meta`：
        它照样受并发上限保护，但不参与熔断的开启与恢复（理由见模块开头
        "为什么 meta 不参与计数"）。
        """
        if counts_as_health:
            self._before(action)

        # 两层限额共用一个**总等待预算**（而不是各等一次 queue_timeout），
        # 否则最坏情况要干等两个周期，前端早就超时了。
        deadline = self._clock() + self.queue_timeout

        if not self._slots.acquire(timeout=self.queue_timeout):
            self._give_up(counts_as_health)
            raise AppError(
                ErrorCode.UPSTREAM_BUSY,
                f"{self.site} 正忙（并发上限 {self.max_concurrency}），"
                f"排队 {self.queue_timeout:g}s 仍没有空位",
            )

        holds_global = False
        try:
            if self.global_slots is not None:
                remaining = max(0.0, deadline - self._clock())
                if not self.global_slots.acquire(timeout=remaining):
                    self._give_up(counts_as_health)
                    raise AppError(
                        ErrorCode.UPSTREAM_BUSY,
                        "全站并发已满（请稍后重试，或调大 PLOVE_GLOBAL_MAX_CONCURRENCY）",
                    )
                holds_global = True

            try:
                result = work()
            except AppError as exc:
                if counts_as_health:
                    self._after_error(exc)
                raise
            except BaseException:
                # 非业务异常（比如我们自己代码的 bug）：不计进熔断，
                # 但也别把探针名额一直占着，否则这个源会永远停在"探测中"
                self._give_up(counts_as_health)
                raise
            else:
                if counts_as_health:
                    self._after_success()
                return result
        finally:
            # 释放顺序与获取相反（后拿的先放）
            if holds_global and self.global_slots is not None:
                self.global_slots.release()
            self._slots.release()

    # ------------------------------------------------------------------ 状态

    @property
    def state(self) -> str:
        with self._lock:
            if self._opened_at is None:
                return CLOSED
            if self._clock() - self._opened_at < self.reset_seconds:
                return OPEN
            return HALF_OPEN

    def snapshot(self) -> dict[str, Any]:
        """给日志和后台面板看的一眼状态。"""
        with self._lock:
            info: dict[str, Any] = {
                "site": self.site,
                "state": CLOSED,
                "failures": self._failures,
                "fail_threshold": self.fail_threshold,
                "reset_seconds": self.reset_seconds,
                "max_concurrency": self.max_concurrency,
                "probing": self._probing,
            }
            if self._opened_at is not None:
                remaining = self.reset_seconds - (self._clock() - self._opened_at)
                info["state"] = OPEN if remaining > 0 else HALF_OPEN
                if remaining > 0:
                    info["retry_after"] = round(remaining, 1)
            return info

    # ------------------------------------------------------------------ 内部

    def _before(self, action: str) -> None:
        with self._lock:
            if self._opened_at is None:
                return

            elapsed = self._clock() - self._opened_at
            if elapsed < self.reset_seconds:
                raise AppError(
                    ErrorCode.UPSTREAM_CIRCUIT_OPEN,
                    f"{self.site} 连续失败 {self._failures} 次已熔断，"
                    f"{self.reset_seconds - elapsed:.0f}s 后重试",
                )
            if self._probing:
                raise AppError(
                    ErrorCode.UPSTREAM_CIRCUIT_OPEN,
                    f"{self.site} 正在探测恢复中，请稍后再试",
                )
            # 半开：只放这一个探针
            self._probing = True
            logger.info("站点 %s 冷却结束，放一个探针试探%s", self.site, f"（{action}）" if action else "")

    def _after_success(self) -> None:
        with self._lock:
            if self._opened_at is not None:
                logger.info("站点 %s 探针成功，熔断解除", self.site)
            self._failures = 0
            self._opened_at = None
            self._probing = False

    def _after_error(self, exc: AppError) -> None:
        with self._lock:
            self._probing = False
            if exc.code not in SITE_FAILURE_CODES:
                # 404 / 501 都是"正常的回答"，不该把源判成有病
                logger.debug("站点 %s 返回 %s，不计入熔断", self.site, exc.code.value)
                return
            self._failures += 1
            if self._failures >= self.fail_threshold:
                first_break = (self._opened_at is None)
                self._opened_at = self._clock()
                logger.warning(
                    "站点 %s 连续失败 %d 次（%s），熔断 %.0fs",
                    self.site,
                    self._failures,
                    exc.code.value,
                    self.reset_seconds,
                )
                if first_break:
                    try:
                        from app.services.webhook_service import webhook_service

                        webhook_service.dispatch_event(
                            event_type="circuit_break",
                            title=f"内容源 [{self.site}] 触发熔断保护",
                            content=f"内容源 [{self.site}] 连续请求失败已达阈值 {self.fail_threshold} 次，已进入熔断冷却状态（冷却时长 {self.reset_seconds:.0f} 秒）。",
                            fields={
                                "故障源站": self.site,
                                "失败原因": exc.code.value,
                                "失败次数": self._failures,
                                "冷却时长": f"{self.reset_seconds:.0f}s",
                            },
                            sync=False,
                        )
                    except Exception:
                        pass

    def _give_up(self, counts_as_health: bool) -> None:
        """没拿到名额就退出：把半开探针的名额还回去（否则这个源会卡在"探测中"）。"""
        if counts_as_health:
            self._release_probe()

    def _release_probe(self) -> None:
        with self._lock:
            self._probing = False
