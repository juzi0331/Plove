"""主动预热：定期把每个源的**入口页**抓一遍、填进缓存。

## 它解决的是 TTL 的一个固有毛病

TTL 是**被动过期**：到点之后由**下一个来访者**触发重抓，于是

* 那**一个**倒霉的用户要等 1~5 秒（别人都是 0 毫秒）；
* 如果一直没人来，数据会一直旧着 —— 缓存**不会自己变新鲜**；
* 重启服务后缓存全空，第一批用户会一起等（冷启动）。

主动预热把这三件事一起解决：用户永远命中新鲜数据，也永远不用等。

## 只热"入口"，不热"全部"

| 对象 | 热不热 | 为什么 |
| --- | --- | --- |
| 每个源的首页 | ✅ | 入口，一个站一次请求，性价比最高 |
| 前几个分类的第一页 | ✅（默认 3 个） | 用户点进分类最先看的就是它 |
| 详情 | ❌ | 有无穷多部片，全热 = 定时自己去爬整个站，那是主动给源站压力 |
| 播放地址 | ❌ | 带时效签名，热了也是废的 |

## 两条必须守住的性质

**一、预热走的是和在线请求完全相同的那条路**（``catalog_service`` →
``registry.run``），所以并发上限、熔断、契约校验一个都不会绕过。
挂掉的源在熔断期内**根本不会被预热撞**——它会在 ``UPSTREAM_CIRCUIT_OPEN``
上瞬间返回，不会每 24 小时准点去捅它一次。

**二、失败绝不上抛。** 预热是后台行为，它失败不该影响任何在线请求；
每个源的结果都单独记下来，由后台面板去看。
"""

from __future__ import annotations

import threading
import time

from app.cache.content import ContentCache
from app.core.clock import as_aware, utcnow
from app.core.errors import AppError
from app.core.logging import get_logger
from app.crawler.registry import SiteRegistry
from app.schemas.admin import WarmupSiteResult, WarmupStatus
from app.services import catalog_service

logger = get_logger(__name__)


class WarmupRunner:
    """进程内唯一。定时任务和"立即刷新"按钮必须打**同一个**对象，

    否则后台看到的"上次预热时间"永远来自一个刚造出来的空白实例。
    """

    def __init__(
        self,
        registry: SiteRegistry,
        cache: ContentCache,
        max_categories: int = 3,
        enabled: bool = False,
        interval_seconds: float = 0.0,
        name: str = "缓存预热",
    ) -> None:
        self.registry = registry
        self.cache = cache
        self.max_categories = max(0, max_categories)
        self.enabled = enabled
        self.interval_seconds = interval_seconds
        self.name = name
        #: 保证同一时刻只有一轮预热在跑。用**非阻塞获取**来表达"抢"，不用排队。
        self._busy = threading.Lock()
        self._lock = threading.Lock()
        self._running = False
        self._last: WarmupStatus | None = None

    # ------------------------------------------------------------------ 触发

    def run_once(self, reason: str = "定时") -> WarmupStatus:
        """跑一轮并等它结束。**已经有一轮在跑就直接返回当前状态**，不排队。"""
        if not self._busy.acquire(blocking=False):
            logger.info("%s：已有一轮在进行中，这次跳过（%s）", self.name, reason)
            return self.status()
        try:
            return self._execute(reason)
        finally:
            self._busy.release()

    def start_in_background(self, reason: str = "手动") -> bool:
        """在后台线程里跑一轮，立刻返回是否真的启动了。

        "立即刷新"按钮用它：一次预热可能要十几秒（要等源站），
        让它卡在一个 HTTP 请求里，代理层先超时了。
        """
        if not self._busy.acquire(blocking=False):
            return False
        thread = threading.Thread(
            target=self._run_releasing,
            args=(reason,),
            name=f"{self.name}-manual",
            daemon=True,
        )
        thread.start()
        return True

    def status(self) -> WarmupStatus:
        """当前状态。没有历史时给一个"从没跑过"的干净对象。"""
        with self._lock:
            if self._last is not None:
                # 复制一份再交出去：调用方拿到的对象不能被后台线程改到一半
                return self._last.model_copy(update={"running": self._running})
            return WarmupStatus(
                enabled=self.enabled,
                running=self._running,
                interval_seconds=self.interval_seconds,
            )

    # ------------------------------------------------------------------ 内部

    def _run_releasing(self, reason: str) -> None:
        """后台线程入口：跑完/炸了都要把 ``_busy`` 还回去。"""
        try:
            self._execute(reason)
        finally:
            self._busy.release()

    def _execute(self, reason: str) -> WarmupStatus:
        started_at = utcnow()
        begin = time.monotonic()
        with self._lock:
            self._running = True

        results: list[WarmupSiteResult] = []
        try:
            # 只热**启用中**的源：被后台停用的源不该每天被我们准点去捅一次
            for key in self.registry.enabled_keys():
                results.append(self._warm_site(key))
        finally:
            with self._lock:
                self._running = False

        status = WarmupStatus(
            enabled=self.enabled,
            running=False,
            interval_seconds=self.interval_seconds,
            last_reason=reason,
            last_started_at=as_aware(started_at),
            last_finished_at=as_aware(utcnow()),
            last_seconds=round(time.monotonic() - begin, 3),
            sites=results,
        )
        with self._lock:
            self._last = status

        ok = sum(1 for item in results if item.ok)
        logger.info(
            "%s 完成（%s）：%d/%d 个源成功，耗时 %.1fs",
            self.name,
            reason,
            ok,
            len(results),
            status.last_seconds or 0.0,
        )
        return status

    def _warm_site(self, key: str) -> WarmupSiteResult:
        begin = time.monotonic()
        entry = WarmupSiteResult(site=key, ok=False)
        try:
            # force=True：跳过读缓存，把旧值**换掉**。
            # 没有它就变成"读一遍缓存"，而预热的意义正好相反。
            home = catalog_service.home(self.registry, self.cache, key, force=True)
            entry.home_items = len(home.recommend)

            for category in home.categories[: self.max_categories]:
                try:
                    catalog_service.category(
                        self.registry, self.cache, key, category.tid, 1, force=True
                    )
                    entry.categories += 1
                except AppError as exc:
                    # 单个分类失败不影响这个源的其余部分 —— 部分成功也比全废好
                    logger.warning(
                        "%s：源 %s 的分类 %s 预热失败（%s）",
                        self.name,
                        key,
                        category.tid,
                        exc.code.value,
                    )
            entry.ok = True
        except AppError as exc:
            entry.error = f"{exc.code.value}: {exc.message}"
            logger.warning("%s：源 %s 预热失败（%s）", self.name, key, entry.error)
        except Exception as exc:  # noqa: BLE001 - 后台任务绝不因一个源崩掉
            entry.error = f"{type(exc).__name__}: {exc}"
            logger.exception("%s：源 %s 预热出现未预期异常", self.name, key)
        entry.seconds = round(time.monotonic() - begin, 3)
        return entry
