"""站点注册表：有哪些源、每个源会什么、能力路由、以及每站的守护。

三件事都在这里，因为它们共用同一个前提：**每个源是一份可能随时坏掉的资产。**

**meta 要缓存。** ``/sites`` 每次请求都去 fork 一遍爬虫是不可接受的，
但 meta 又极少变（除非换了爬虫文件），所以给个短 TTL。

**能力路由要做在这里。** 源没声明 ``search``，就该明确回"该源不支持搜索"，
而不是把空列表伪装成"搜到 0 条"—— 这两件事对用户完全不同。

**每站的并发上限与熔断也挂在这里**（见 :mod:`app.crawler.guard`）。
选这里是因为它是**唯一**通往爬虫的关口：只要是跟源站说话，就一定从这里过。
换个地方加，早晚会漏掉一条新加的调用路径。
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger
from app.crawler.guard import SiteGuard
from app.crawler.runner import SITE_KEY_PATTERN, CrawlerRunner
from app.crawler.validate import validate_payload
from app.schemas.site import SiteMeta

logger = get_logger(__name__)

#: meta 缓存的存活时间（秒）
DEFAULT_META_TTL = 300.0


def _default_guard_factory(key: str) -> SiteGuard:
    return SiteGuard(key)


class SiteRegistry:
    def __init__(
        self,
        runner: CrawlerRunner,
        meta_ttl: float = DEFAULT_META_TTL,
        guard_factory: Callable[[str], SiteGuard] | None = None,
        max_global_concurrency: int = 0,
        disabled_keys_provider: Callable[[], frozenset[str]] | None = None,
    ) -> None:
        self.runner = runner
        self.meta_ttl = meta_ttl
        self._meta: dict[str, tuple[SiteMeta, float]] = {}
        self._guard_factory = guard_factory or _default_guard_factory
        #: 每站一把守护。懒建 —— 没碰过的源不用先付一笔内存。
        self._guards: dict[str, SiteGuard] = {}
        self._guards_lock = threading.Lock()
        #: 全站共享的并发额。0 或负数 = 不做全局限额。
        self._global_limit = max(0, max_global_concurrency)
        self._global_slots = (
            threading.BoundedSemaphore(self._global_limit) if self._global_limit else None
        )
        #: “哪些源被后台停用了”。用**回调**而不是直接读库：注册表在 crawler 层，
        #: 它不该认识 SQLAlchemy；而且它是进程内单例、跑在请求之外（预热线程也要用），
        #: 根本拿不到 Session。默认空集合 = 全部可用。
        self._disabled_keys_provider = disabled_keys_provider or (lambda: frozenset())

    # ------------------------------------------------------------------ 站点

    def keys(self) -> list[str]:
        """扫目录拿到有哪些源。

        ``        __init__.py`` 必须排除：它首字符是下划线，**恰好能通过**
        :data:`SITE_KEY_PATTERN`，不特判的话它会被当成一个站点。

        **这里不过滤"被后台停用"的源** —— 运维要能在后台看到全部（包括关掉的）。
        用户端请用 :meth:`enabled_keys`。
        """
        return sorted(
            path.stem
            for path in self.runner.sites_dir.glob("*.py")
            if not path.stem.startswith("_") and SITE_KEY_PATTERN.match(path.stem)
        )

    def disabled_keys(self) -> frozenset[str]:
        """被后台停用的源（每次向提供者要一次最新的快照）。"""
        return frozenset(self._disabled_keys_provider())

    def is_enabled(self, key: str) -> bool:
        return key not in self.disabled_keys()

    def enabled_keys(self) -> list[str]:
        """用户端会看到的源：目录里有、且没被停用。"""
        disabled = self.disabled_keys()
        return [key for key in self.keys() if key not in disabled]

    def ensure_enabled(self, key: str) -> None:
        """停用的源必须在 **fork 之前**就被拦掉。

        拦在 :meth:`run`（唯一通往爬虫的关口）而不是各个 service 里，理由和守护一样：
        用户端、后台预览、预热、将来任何新加的调用路径都会被同一条规则挡住，
        而在某个 service 上拦，早晚会漏掉一条新路径。

        **不碰源站、不占并发槽位、也不计入熔断** —— 停用是我们自己的决定，
        不该在守护里记成"源站又失败了一次"。
        """
        if not self.is_enabled(key):
            raise AppError(
                ErrorCode.SITE_DISABLED,
                f"源 {key} 已在后台停用（要恢复请到后台的站点管理里打开）",
            )

    def guard(self, key: str) -> SiteGuard:
        """取（必要时建）某个源的守护。"""
        found = self._guards.get(key)
        if found is not None:
            return found
        with self._guards_lock:
            return self._guards.setdefault(key, self._build_guard(key))

    def _build_guard(self, key: str) -> SiteGuard:
        guard = self._guard_factory(key)
        # 全局限额在这里挂上去：它属于注册表（也就是整个进程），不属于某一个源
        guard.global_slots = self._global_slots
        return guard

    def guards(self) -> list[dict[str, Any]]:
        """**这台机器上每个源**的状态快照（给日志和后台面板）。

        为什么按目录扫（``keys()``）而不是遍历 ``self._guards``：
        守护是懒建的，没被碰过的源不在里面 —— 于是**运维打开后台会看到一张空表**，
        而实际上这台机器上明明有两个源。那种空白比没有这个页面更糟：
        它会让人以为"源都没了"。

        这个改动是安全的，因为：

        * ``keys()`` 只是一次目录 ``glob``，不 fork 爬虫；
        * ``guard()`` 只创建一个守护对象，同样没有 I/O。

        ``probed`` 字段说明这个源的 meta 是否真的取到过 —— 它把"新的守护"
        和"已验证过的源"分开，免得看板上出现一个轻易的误解：
        ``state=closed, failures=0`` 在两种情况下一模一样。
        """
        snapshots: list[dict[str, Any]] = []
        for key in self.keys():
            item = self.guard(key).snapshot()
            # 全局限额是整站共享的，每个源上都标一份，看的时候不用再对照文档
            item["global_limit"] = self._global_limit
            item["probed"] = key in self._meta
            snapshots.append(item)
        return snapshots

    def meta(self, key: str) -> SiteMeta:
        """取站点元信息，带缓存。站点不存在会抛 ``NOT_FOUND``。

        **取不到时拿上一次的值顶上。** 这比"这个源从列表里消失"好：
        源临时抽风不该让前端的下拉框少一项 —— 用户会以为这个站被下架了，
        而实际上他点进去就会发现真正的错误（这个错误是诚实的）。
        从没成功过的源（比如爬虫文件一开始就是坏的）照旧会被跳过。
        """
        cached = self._meta.get(key)
        if cached is not None and time.monotonic() - cached[1] < self.meta_ttl:
            return cached[0]

        try:
            # counts_as_health=False：meta 成功不代表现在抓得到内容，
            # 而且它每请求都跑一遍 —— 让它参与计数会把内容失败的计数一次次清零，
            # 结果就是"meta 能通、抓内容就超时"的源永远熔断不掉。
            payload = self.guard(key).call(
                lambda: self.runner.run(key, "meta"),
                action="meta",
                counts_as_health=False,
            )
        except AppError as exc:
            if cached is None:
                raise
            logger.warning("站点 %s 的 meta 取不到（%s），先用上一次的值", key, exc.message)
            # 刷新时间戳：不然下一个请求会再接再厉去撞同一面墙
            self._meta[key] = (cached[0], time.monotonic())
            return cached[0]

        meta = validate_payload(SiteMeta, payload, key=key, command="meta")
        self._meta[key] = (meta, time.monotonic())
        return meta

    def forget_meta(self, key: str) -> None:
        """清空指定站点的 meta 缓存（在脚本更新或上传时调用）。"""
        self._meta.pop(key, None)

    def all_meta(self) -> list[SiteMeta]:
        """所有能拿到 meta 的源。

        某一个源挂了**不该让整个列表挂掉**，所以这里吞掉异常、记日志、跳过它。
        （本 step 不往前端暴露"这个源坏了"，等后台面板再补。）
        """
        out: list[SiteMeta] = []
        # 停用的源不进这个列表（用户端就是拿它渲染站点列表的）
        for key in self.enabled_keys():
            try:
                out.append(self.meta(key))
            except AppError as exc:
                logger.warning("站点 %s 的 meta 取不到，已跳过: %s", key, exc)
        return out

    # ------------------------------------------------------------------ 执行

    def run(self, key: str, command: str, custom_timeout: float | None = None, **options: Any) -> Any:
        """带能力路由与守护的执行。

        顺序很重要：**先做能力路由，再进守护**。反过来的话，一个源根本不支持
        的调用也会占掉一个并发槽位、还会被计入熔断。
        停用检查放在**这一步之前**：被后台关掉的源不该走到这里来。
        """
        self.ensure_enabled(key)
        meta = self.meta(key)
        if command != "meta" and command not in meta.capabilities:
            raise AppError(ErrorCode.UNSUPPORTED, f"{meta.name} 不支持 {command}")
        return self.guard(key).call(
            lambda: self.runner.run(key, command, custom_timeout=custom_timeout, **options),
            action=command,
        )

    def supports(self, key: str, capability: str) -> bool:
        return capability in self.meta(key).capabilities

    # ------------------------------------------------------------------ 缓存

    def invalidate(self, key: str | None = None) -> None:
        """丢掉 meta 缓存（守护状态不动）。换过爬虫文件或改过能力清单时调它。"""
        if key is None:
            self._meta.clear()
        else:
            self._meta.pop(key, None)
