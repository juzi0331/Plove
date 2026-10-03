"""缓存：TTL/LRU 原语，以及目录内容的缓存策略。

用**假时钟**而不是 ``time.sleep``：过期这件事靠 sleep 来测，
测试会变得又慢又不稳（sleep 0.05 秒验 0.1 秒的 TTL，在负载高的机器上就飘了）。
"""

from __future__ import annotations

import threading
import time

import pytest

from app.cache.content import ContentCache
from app.cache.ttl import TTLCache
from app.core.errors import AppError, ErrorCode


class FakeClock:
    """手动推进的时钟。"""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture(autouse=True)
def _clean_disk_cache():
    from app.cache.disk_cache import get_disk_store

    get_disk_store().clear()
    yield
    get_disk_store().clear()


# ------------------------------------------------------------------ TTLCache

def test_set_get_roundtrip():
    cache: TTLCache[str] = TTLCache(maxsize=4, ttl=60)
    cache.set("a", "1")
    assert cache.get("a") == "1"


def test_missing_key_is_none():
    cache: TTLCache[str] = TTLCache(maxsize=4, ttl=60)
    assert cache.get("没有这个") is None


def test_entry_expires():
    clock = FakeClock()
    cache: TTLCache[str] = TTLCache(maxsize=4, ttl=10, clock=clock)
    cache.set("a", "1")

    clock.advance(9.9)
    assert cache.get("a") == "1", "还没到点就被判过期了"

    clock.advance(0.2)
    assert cache.get("a") is None
    assert len(cache) == 0, "过期项应该顺手删掉，不能留着占容量"


def test_ttl_can_be_overridden_per_entry():
    """首页和详情的合理缓存时长不一样，共用一个 cache 就得能按次覆盖。"""
    clock = FakeClock()
    cache: TTLCache[str] = TTLCache(maxsize=4, ttl=10, clock=clock)
    cache.set("短", "x", ttl=5)
    cache.set("长", "y", ttl=100)

    clock.advance(6)
    assert cache.get("短") is None
    assert cache.get("长") == "y"


def test_zero_ttl_means_do_not_cache():
    cache: TTLCache[str] = TTLCache(maxsize=4, ttl=60)
    cache.set("a", "1", ttl=0)
    assert cache.get("a") is None


def test_maxsize_evicts_least_recently_used():
    cache: TTLCache[int] = TTLCache(maxsize=2, ttl=60)
    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.get("a") == 1  # 摸一下 a，让它变成"最近用过"
    cache.set("c", 3)  # 放不下三个，该被砍的是 b

    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3


def test_invalidate_and_clear():
    cache: TTLCache[str] = TTLCache(maxsize=8, ttl=60)
    cache.set("a", "1")
    cache.set("b", "2")
    cache.invalidate("a")
    assert cache.get("a") is None
    assert cache.get("b") == "2"
    cache.clear()
    assert len(cache) == 0


def test_stats_counts_hits_and_misses():
    cache: TTLCache[str] = TTLCache(maxsize=8, ttl=60)
    cache.set("a", "1")
    cache.get("a")
    cache.get("没有")
    stats = cache.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["size"] == 1


def test_maxsize_must_be_positive():
    with pytest.raises(ValueError):
        TTLCache(maxsize=0, ttl=60)


def test_cache_is_thread_safe_under_contention():
    """服务是同步的，FastAPI 会把路由丢进线程池 —— 并发写是常态，不是意外。"""
    cache: TTLCache[int] = TTLCache(maxsize=64, ttl=60)
    errors: list[BaseException] = []

    def hammer(worker: int) -> None:
        try:
            for index in range(200):
                cache.set(f"k{(worker * 200 + index) % 32}", index)
                cache.get(f"k{index % 32}")
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=hammer, args=(n,)) for n in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(cache) <= 32


# ------------------------------------------------------------- ContentCache

def test_content_cache_computes_once_then_reuses():
    clock = FakeClock()
    cache = ContentCache(ttl_home=60, ttl_category=60, ttl_detail=60, clock=clock)
    calls = []

    def compute() -> str:
        calls.append(1)
        return "首页"

    assert cache.home("fake", compute) == "首页"
    assert cache.home("fake", compute) == "首页"
    assert len(calls) == 1, "第二次应该吃缓存，不该再去抓一次"


def test_content_cache_expires():
    clock = FakeClock()
    cache = ContentCache(ttl_home=10, ttl_category=10, ttl_detail=10, clock=clock)
    calls = []

    def compute() -> str:
        calls.append(1)
        return "首页"

    cache.home("fake", compute)
    clock.advance(11)
    cache.home("fake", compute)
    assert len(calls) == 2


def test_content_cache_separates_namespaces_and_keys():
    """站点、命名空间、标识三者任一不同就该是不同的一份 —— 否则会串数据。"""
    cache = ContentCache(ttl_home=60, ttl_category=60, ttl_detail=60)

    def make(tag: str):
        def compute() -> str:
            return tag

        return compute

    cache.home("a", make("a-home"))
    cache.home("b", make("b-home"))
    assert cache.home("a", make("又一次")) == "a-home", "不同站点的首页混在一起了"

    cache.category("a", "1", 1, make("a-cat-1-1"))
    cache.category("a", "1", 2, make("a-cat-1-2"))
    cache.category("a", "2", 1, make("a-cat-2-1"))
    cache.category("a", None, 1, make("a-cat-none-1"))
    assert cache.category("a", "1", 2, make("不该被调用")) == "a-cat-1-2"
    assert cache.category("a", "2", 1, make("不该被调用")) == "a-cat-2-1"
    # tid 空 和 tid="1" 不能互相顶掉
    assert cache.category("a", None, 1, make("不该被调用")) == "a-cat-none-1"

    cache.detail("a", "100", make("a-detail-100"))
    assert cache.detail("a", "100", make("不该被调用")) == "a-detail-100"
    assert cache.detail("a", "101", make("a-detail-101")) == "a-detail-101"


def test_zero_ttl_disables_the_cache():
    """运维要能一键关掉缓存：把 TTL 设成 0 就行，不用改代码。"""
    cache = ContentCache(ttl_home=0, ttl_category=0, ttl_detail=0)
    calls = []

    def compute() -> str:
        calls.append(1)
        return "首页"

    cache.home("fake", compute)
    cache.home("fake", compute)
    assert len(calls) == 2


def test_errors_are_not_cached():
    """把一次网络抖动缓存 5 分钟，用户会以为整个源站坏了。"""
    cache = ContentCache(ttl_home=60, ttl_category=60, ttl_detail=60)
    attempts = []

    def flaky() -> str:
        attempts.append(1)
        if len(attempts) == 1:
            raise AppError(ErrorCode.UPSTREAM_TIMEOUT, "第一次超时")
        return "第二次好了"

    with pytest.raises(AppError):
        cache.home("fake", flaky)

    assert cache.home("fake", flaky) == "第二次好了"
    assert len(attempts) == 2


def test_second_compute_does_not_clobber_a_fresh_entry():
    """领跑者跑完才发现别人已经填上了，就该用别人那份，别覆盖。"""
    cache = ContentCache(ttl_home=60, ttl_category=60, ttl_detail=60)
    assert cache._fill("k", 60, lambda: "领跑者") == "领跑者"
    assert cache._fill("k", 60, lambda: "后到者") == "领跑者"


def test_concurrent_identical_computes_run_once():
    """缓存击穿：过期那一瞬间 N 个请求同时进来，只该有一个真的去抓。

    领跑者卡在 ``work`` 里，等 3 个跟随者都排上队再放行。
    那个 ``sleep`` 是刻意留的宽裕余量（跟随者只是走到 ``dict.get``），
    不是为了掩盖竞态。
    """
    cache = ContentCache(ttl_home=60, ttl_category=60, ttl_detail=60, enable_disk=False)
    release = threading.Event()
    lock = threading.Lock()
    invocations = []
    results: list[str] = []
    errors: list[BaseException] = []

    def work() -> str:
        with lock:
            invocations.append(1)
        release.wait(timeout=5)
        return "结果"

    def worker() -> None:
        try:
            results.append(cache.home("fake", work))
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    time.sleep(0.2)  # 让跟随者排上队
    release.set()
    for thread in threads:
        thread.join()

    assert errors == []
    assert results == ["结果"] * 4
    assert len(invocations) == 1, f"应该只抓 1 次，实际 {len(invocations)} 次"

    def boom() -> str:  # pragma: no cover - 只用来确认缓存已填上
        raise AssertionError("缓存填上了，不该再算一次")

    assert cache.home("fake", boom) == "结果"
