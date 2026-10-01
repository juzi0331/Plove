"""极简的周期任务：一个线程，每隔一段时间跑一次。

**为什么不用 APScheduler / Celery：** 现在只有一个任务（缓存预热），
而这两个东西各自带来一套配置、一套概念、一套故障模式。
这里的全部需求就是"隔一会儿跑一次、别把进程搞崩、关的时候能停下"，
三十行就够了。等真的有"错过的任务要补跑""要看历史执行记录"这类需求，
再换成正经的调度器 —— 那时换的成本比现在背着的成本低。

**为什么是线程而不是 asyncio 任务：** 这类活基本都是**阻塞**的
（要等子进程、要等源站的网络往返）。丢进事件循环会卡住所有请求。
开一个专用线程最省事，也不会和"同步路由跑在线程池里"抢资源。

三条规矩：

1. 启动前先等 ``initial_delay`` —— 别和启动时的第一批请求抢源站；
2. 异常一律吞掉并记日志 —— **一个后台任务的失败绝不该让进程退出**；
3. ``stop()`` 时能立刻醒来，不等满一个周期（否则关闭要卡住整整 24 小时）。
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from app.core.logging import get_logger

logger = get_logger(__name__)


class PeriodicJob:
    """每隔 ``interval`` 秒跑一次 ``work`` 的后台线程。"""

    def __init__(
        self,
        name: str,
        interval: float,
        work: Callable[[], object],
        initial_delay: float = 0.0,
    ) -> None:
        if interval <= 0:
            raise ValueError("interval 必须为正数")
        self.name = name
        self.interval = interval
        self.initial_delay = max(0.0, initial_delay)
        self._work = work
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------ 生命周期

    def start(self) -> "PeriodicJob":
        if self._thread is not None:
            return self
        self._thread = threading.Thread(target=self._loop, name=f"job-{self.name}", daemon=True)
        self._thread.start()
        logger.info(
            "后台任务 %s 已启动：%s 后首次执行，之后每 %.0f 秒一次",
            self.name,
            f"{self.initial_delay:g} 秒" if self.initial_delay else "立刻",
            self.interval,
        )
        return self

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        thread = self._thread
        # 如果是"在工作线程里调 stop"（比如测试里直接跑），join 自己会死锁
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)
        self._thread = None
        logger.info("后台任务 %s 已停止", self.name)

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------ 内部

    def _loop(self) -> None:
        if self._stop.wait(self.initial_delay):
            return
        while not self._stop.is_set():
            try:
                self._work()
            except Exception:  # noqa: BLE001 - 后台任务失败绝不能让进程退出
                logger.exception("%s 执行失败（已忽略，不影响在线服务）", self.name)
            # 用 wait 当 sleep：stop() 一 set，这里立刻醒来
            if self._stop.wait(self.interval):
                return
