"""站点守护：并发上限与熔断。

同样是假时钟 —— 验"冷却 60 秒后恢复"不该真的等 60 秒。
"""

from __future__ import annotations

import threading
import time

import pytest

from app.core.errors import AppError, ErrorCode
from app.crawler.guard import SiteGuard
from app.crawler.registry import SiteRegistry
from tests.helpers import crawler_calls


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _failing(code: ErrorCode):
    def work():
        raise AppError(code, f"假失败 {code.value}")

    return work


# ------------------------------------------------------------------ 并发上限

def test_concurrency_limit_is_enforced():
    guard = SiteGuard("fake", max_concurrency=2, queue_timeout=5)
    lock = threading.Lock()
    state = {"now": 0, "peak": 0}
    errors: list[BaseException] = []

    def work() -> str:
        with lock:
            state["now"] += 1
            state["peak"] = max(state["peak"], state["now"])
        time.sleep(0.05)
        with lock:
            state["now"] -= 1
        return "ok"

    def worker() -> None:
        try:
            guard.call(work)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert state["peak"] <= 2, f"同时在跑 {state['peak']} 个，超过上限了"


def test_global_limit_is_shared_across_sites():
    """每站上限保护源站，全站上限保护**这台机器**。

    只有每站上限的话，源变多之后总量是**乘出来**的：10 个源 × 2 = 20 个
    并发子进程，内存和 CPU 一起完蛋。
    """
    global_slots = threading.BoundedSemaphore(1)
    holder_guard = SiteGuard("a", queue_timeout=1, global_slots=global_slots)
    other_guard = SiteGuard("b", max_concurrency=4, queue_timeout=0.05, global_slots=global_slots)

    release = threading.Event()
    holder = threading.Thread(target=lambda: holder_guard.call(lambda: release.wait(5) or "a"))
    holder.start()
    time.sleep(0.05)

    try:
        # b 自己还有 4 个空位，但全站名额被 a 占着
        with pytest.raises(AppError) as exc:
            other_guard.call(lambda: "我不该被跑到")
        assert exc.value.code is ErrorCode.UPSTREAM_BUSY
        assert "全站并发" in exc.value.message, "要说清是哪种忙，否则排查时只能猜"
    finally:
        release.set()
        holder.join()


def test_wait_budget_is_shared_between_the_two_limits():
    """两层限额共用一个等待预算，而不是各等一次 queue_timeout。

    各等一次的话，最坏情况要干等两个周期，前面那些请求早超时了。
    """
    global_slots = threading.BoundedSemaphore(1)
    other = SiteGuard("b", queue_timeout=1, global_slots=global_slots)
    guard = SiteGuard("a", max_concurrency=1, queue_timeout=0.2, global_slots=global_slots)

    release = threading.Event()
    holder = threading.Thread(target=lambda: other.call(lambda: release.wait(5) or "b"))
    holder.start()
    time.sleep(0.05)

    begin = time.monotonic()
    try:
        with pytest.raises(AppError) as exc:
            guard.call(lambda: "不该跑到")
        elapsed = time.monotonic() - begin
        assert exc.value.code is ErrorCode.UPSTREAM_BUSY
        assert elapsed < 0.35, f"等了 {elapsed:.2f}s，看起来两层限额各等了一次"
    finally:
        release.set()
        holder.join()


def test_queue_timeout_reports_upstream_busy():
    """占满了就明确说"忙"，不许让请求无限排队 —— 排队会连着占住连接和线程。"""
    guard = SiteGuard("fake", max_concurrency=1, queue_timeout=0.05)
    release = threading.Event()

    def slow() -> str:
        release.wait(timeout=5)
        return "慢慢跑完了"

    holder = threading.Thread(target=lambda: guard.call(slow))
    holder.start()
    time.sleep(0.05)  # 等它占住那唯一的槽位

    try:
        with pytest.raises(AppError) as exc:
            guard.call(lambda: "我不该被跑到")
        assert exc.value.code is ErrorCode.UPSTREAM_BUSY
        assert "并发上限" in exc.value.message
    finally:
        release.set()
        holder.join()


# ---------------------------------------------------------------------- 熔断

def test_breaker_opens_after_threshold():
    guard = SiteGuard("fake", fail_threshold=3, reset_seconds=60)
    runs = []

    def work():
        runs.append(1)
        raise AppError(ErrorCode.UPSTREAM_TIMEOUT, "超时")

    for _ in range(3):
        with pytest.raises(AppError) as exc:
            guard.call(work)
        assert exc.value.code is ErrorCode.UPSTREAM_TIMEOUT

    assert guard.state == "open"

    # 第 4 次：**根本不碰源站**，直接快速失败
    with pytest.raises(AppError) as exc:
        guard.call(work)
    assert exc.value.code is ErrorCode.UPSTREAM_CIRCUIT_OPEN
    assert len(runs) == 3, "熔断之后还在往下跑，等于没熔断"


def test_success_resets_the_failure_count():
    """失败计数是**连续**的：中间成功一次就该清零，否则长期运行必然误熔断。"""
    guard = SiteGuard("fake", fail_threshold=3, reset_seconds=60)
    for _ in range(2):
        with pytest.raises(AppError):
            guard.call(_failing(ErrorCode.UPSTREAM_TIMEOUT))

    assert guard.call(lambda: "好了一次") == "好了一次"
    assert guard.snapshot()["failures"] == 0

    for _ in range(2):
        with pytest.raises(AppError):
            guard.call(_failing(ErrorCode.UPSTREAM_TIMEOUT))
    assert guard.state == "closed", "清零之后又只失败了 2 次，不该熔断"


def test_not_found_and_unsupported_do_not_trip_the_breaker():
    """**关键区分。** 404 / 501 是"正确的回答"，不是源站故障。

    把它们算进失败计数，用户点几个失效链接就能把整个源熔断掉。
    """
    guard = SiteGuard("fake", fail_threshold=3, reset_seconds=60)
    for _ in range(10):
        with pytest.raises(AppError) as exc:
            guard.call(_failing(ErrorCode.NOT_FOUND))
        assert exc.value.code is ErrorCode.NOT_FOUND

    assert guard.state == "closed"
    assert guard.snapshot()["failures"] == 0
    assert guard.call(lambda: "照样能用") == "照样能用"


def test_probe_after_cooldown_recovers():
    clock = FakeClock()
    guard = SiteGuard("fake", fail_threshold=2, reset_seconds=60, clock=clock)
    for _ in range(2):
        with pytest.raises(AppError):
            guard.call(_failing(ErrorCode.UPSTREAM_TIMEOUT))
    assert guard.state == "open"

    clock.advance(61)
    assert guard.state == "half_open"

    assert guard.call(lambda: "活了") == "活了"
    assert guard.state == "closed"
    assert guard.snapshot()["failures"] == 0


def test_failed_probe_reopens_and_restarts_cooldown():
    clock = FakeClock()
    guard = SiteGuard("fake", fail_threshold=2, reset_seconds=60, clock=clock)
    for _ in range(2):
        with pytest.raises(AppError):
            guard.call(_failing(ErrorCode.UPSTREAM_TIMEOUT))

    clock.advance(61)
    with pytest.raises(AppError) as exc:
        guard.call(_failing(ErrorCode.UPSTREAM_TIMEOUT))
    assert exc.value.code is ErrorCode.UPSTREAM_TIMEOUT

    assert guard.state == "open"
    clock.advance(1)
    with pytest.raises(AppError) as exc:
        guard.call(lambda: "不该被跑到")
    assert exc.value.code is ErrorCode.UPSTREAM_CIRCUIT_OPEN
    assert guard.snapshot()["retry_after"] == 59


def test_half_open_lets_exactly_one_probe_through():
    """半开只放一个探针 —— 放开全部等于把刚缓过来的源站再打一遍。"""
    clock = FakeClock()
    guard = SiteGuard("fake", fail_threshold=1, reset_seconds=60, clock=clock)
    with pytest.raises(AppError):
        guard.call(_failing(ErrorCode.UPSTREAM_TIMEOUT))

    clock.advance(61)
    release = threading.Event()
    probing = threading.Thread(target=lambda: guard.call(lambda: release.wait(5) or "探针"))
    probing.start()
    time.sleep(0.05)

    try:
        with pytest.raises(AppError) as exc:
            guard.call(lambda: "我不该被跑到")
        assert exc.value.code is ErrorCode.UPSTREAM_CIRCUIT_OPEN
        assert "探测" in exc.value.message
    finally:
        release.set()
        probing.join()


def test_unexpected_exception_does_not_wedge_the_probe():
    """自己代码的 bug 不该把源永远停在"探测中"。"""
    clock = FakeClock()
    guard = SiteGuard("fake", fail_threshold=1, reset_seconds=60, clock=clock)
    with pytest.raises(AppError):
        guard.call(_failing(ErrorCode.UPSTREAM_TIMEOUT))

    clock.advance(61)
    with pytest.raises(ValueError):
        guard.call(lambda: (_ for _ in ()).throw(ValueError("我们自己的 bug")))

    assert guard.call(lambda: "还能继续探测") == "还能继续探测"


# ------------------------------------------------- 注册表：把守护接在唯一关口上

def test_registry_run_goes_through_the_guard(fake_settings, fake_runner):
    """熔断之后，内容接口必须**快速失败**，而不是每个请求都去耗满超时。"""
    registry = SiteRegistry(
        fake_runner,
        meta_ttl=0,
        guard_factory=lambda key: SiteGuard(key, fail_threshold=2, reset_seconds=60),
    )

    def boom():
        raise AppError(ErrorCode.UPSTREAM_TIMEOUT, "假的超时")

    for _ in range(2):
        with pytest.raises(AppError):
            registry.guard("fake").call(boom)

    with pytest.raises(AppError) as exc:
        registry.run("fake", "home")
    assert exc.value.code is ErrorCode.UPSTREAM_CIRCUIT_OPEN


def test_breaker_prevents_further_crawler_processes(fake_runner, crawler_counter, monkeypatch):
    """熔断省下的正是最贵的东西：每个请求一次子进程 + 一次满超时等待。"""
    registry = SiteRegistry(
        fake_runner,
        meta_ttl=0,
        guard_factory=lambda key: SiteGuard(key, fail_threshold=2, reset_seconds=60),
    )
    monkeypatch.setenv("FAKE_MODE", "error")

    for _ in range(2):
        with pytest.raises(AppError):
            registry.run("fake", "home")

    before = crawler_calls(crawler_counter, "home")
    for _ in range(5):
        with pytest.raises(AppError) as exc:
            registry.run("fake", "home")
        assert exc.value.code is ErrorCode.UPSTREAM_CIRCUIT_OPEN

    assert crawler_calls(crawler_counter, "home") == before, "熔断后还在往下抓内容"


def test_healthy_meta_does_not_reset_content_failures(fake_runner, crawler_counter, monkeypatch):
    """**这是个真踩到过的坑。**

    ``run`` 每次都会先跑一次 meta。如果 meta 的成功也去清零失败计数，
    序列就变成"内容失败 → meta 成功 → 计数清零"，于是那种
    "meta 能通、抓内容就超时"的源**永远熔断不了** —— 而它正是最该被熔断的一类。
    """
    registry = SiteRegistry(
        fake_runner,
        meta_ttl=0,
        guard_factory=lambda key: SiteGuard(key, fail_threshold=2, reset_seconds=60),
    )
    monkeypatch.setenv("FAKE_MODE", "error")

    with pytest.raises(AppError) as first:
        registry.run("fake", "home")
    assert first.value.code is ErrorCode.UPSTREAM_BLOCKED

    # 中间夹一次成功的 meta（模拟下一次请求的必经步骤）
    assert registry.meta("fake").key == "fake"

    with pytest.raises(AppError) as second:
        registry.run("fake", "home")
    assert second.value.code is ErrorCode.UPSTREAM_BLOCKED

    with pytest.raises(AppError) as third:
        registry.run("fake", "home")
    assert third.value.code is ErrorCode.UPSTREAM_CIRCUIT_OPEN, "meta 的成功把计数清零了"


def test_capability_check_happens_before_the_guard(fake_settings, fake_runner):
    """源不支持的调用不该占并发槽、更不该计入熔断。"""
    registry = SiteRegistry(fake_runner, meta_ttl=0)
    with pytest.raises(AppError) as exc:
        registry.run("fake", "search", kw="任意")
    assert exc.value.code is ErrorCode.UNSUPPORTED
    assert registry.guard("fake").snapshot()["failures"] == 0


def test_seen_site_survives_a_broken_meta(fake_settings, fake_runner, monkeypatch):
    """见过的源即使 meta 取不到，也不该从站点列表里消失。

    消失了的话，前端的源下拉框会忽然少一项，用户会以为这个站被下架了 ——
    而实际上点进去就能看到真正的错误（那个错误是诚实的）。
    """
    registry = SiteRegistry(fake_runner, meta_ttl=0)
    assert [meta.key for meta in registry.all_meta()] == ["fake"]

    monkeypatch.setenv("FAKE_MODE", "meta_broken")
    assert [meta.key for meta in registry.all_meta()] == ["fake"]


def test_never_seen_site_is_skipped(fake_runner, monkeypatch):
    """从没成功过的源（爬虫文件一开始就是坏的）照旧被跳过，不许凭空出现。"""
    monkeypatch.setenv("FAKE_MODE", "meta_broken")
    registry = SiteRegistry(fake_runner, meta_ttl=0)
    assert registry.all_meta() == []


def test_registry_hands_the_global_limit_to_every_site(fake_runner):
    """全局限额属于**注册表**（也就是整个进程），不属于某一个源。"""
    registry = SiteRegistry(fake_runner, meta_ttl=0, max_global_concurrency=1)
    first = registry.guard("fake")
    second = registry.guard("另一个源")

    assert first.global_slots is not None
    assert first.global_slots is second.global_slots, "每个源各拿一份就等于没有全局上限"
    assert all(item["global_limit"] == 1 for item in registry.guards())
