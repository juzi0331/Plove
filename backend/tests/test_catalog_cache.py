"""缓存与降级的端到端测试（从 HTTP 入口一路到子进程）。

这里**必须**用"爬虫真跑了几次"来验证：缓存命中的响应和有网抓回来的响应
在字面上完全一样。只看响应体，缓存坏了也测不出来 —— 那是自欺欺人。
所以每个用例都盯着 :func:`tests.helpers.crawler_calls`。
"""

from __future__ import annotations

import threading
import time

from tests.helpers import crawler_calls


def test_home_is_cached(authed_client, crawler_counter):
    authed_client.get("/api/v1/sites/fake/home")
    assert crawler_calls(crawler_counter, "home") == 1

    body = authed_client.get("/api/v1/sites/fake/home").json()
    assert body["ok"] is True
    assert body["data"]["recommend"][0]["vod_id"] == "1"
    assert crawler_calls(crawler_counter, "home") == 1, "第二次还在抓，等于没缓存"


def test_meta_is_cached_too(authed_client, crawler_counter):
    """``/sites`` 每次请求都 fork 一遍爬虫是不可接受的。"""
    for _ in range(3):
        authed_client.get("/api/v1/sites")
    assert crawler_calls(crawler_counter, "meta") == 1


def test_category_is_cached_per_tid_and_page(authed_client, crawler_counter):
    authed_client.get("/api/v1/sites/fake/category", params={"tid": "1", "page": 1})
    authed_client.get("/api/v1/sites/fake/category", params={"tid": "1", "page": 1})
    assert crawler_calls(crawler_counter, "category") == 1

    assert authed_client.get("/api/v1/sites/fake/category", params={"tid": "1", "page": 2}).json()["data"]["page"] == 2
    assert authed_client.get("/api/v1/sites/fake/category", params={"tid": "2", "page": 1}).status_code == 200
    assert crawler_calls(crawler_counter, "category") == 3, "不同 page / tid 被当成同一份了"


def test_detail_is_cached_per_vod_id(authed_client, crawler_counter):
    authed_client.get("/api/v1/sites/fake/detail", params={"vod_id": "1"})
    authed_client.get("/api/v1/sites/fake/detail", params={"vod_id": "1"})
    assert crawler_calls(crawler_counter, "detail") == 1

    authed_client.get("/api/v1/sites/fake/detail", params={"vod_id": "2"})
    assert crawler_calls(crawler_counter, "detail") == 2


def test_playback_is_never_cached(authed_client, crawler_counter):
    """地址带时效签名（``auth_key`` / ``timestamp``），缓存等于把失效地址发给用户。"""
    for _ in range(3):
        authed_client.get("/api/v1/sites/fake/playback", params={"vod_id": "1", "ep": 1})
    assert crawler_calls(crawler_counter, "play") == 3


def test_errors_are_not_cached(authed_client, crawler_counter, monkeypatch):
    """一次网络抖动被缓存 5 分钟的话，用户会以为整个源站坏了。"""
    monkeypatch.setenv("FAKE_MODE", "error")
    assert authed_client.get("/api/v1/sites/fake/home").status_code == 503

    monkeypatch.delenv("FAKE_MODE")
    body = authed_client.get("/api/v1/sites/fake/home").json()
    assert body["ok"] is True
    assert crawler_calls(crawler_counter, "home") == 2


def test_concurrent_identical_requests_hit_the_crawler_once(authed_client, crawler_counter, monkeypatch):
    """缓存击穿：**刚好过期的那一瞬间**并发进来的请求，只该有一个真去抓。

    这正是"只靠缓存不够"的地方 —— 缓存挡的是先后到达，挡不住同时到达。
    """
    monkeypatch.setenv("FAKE_MODE", "slow")
    monkeypatch.setenv("FAKE_SLEEP", "0.6")

    results: list[int] = []
    lock = threading.Lock()

    def call() -> None:
        response = authed_client.get("/api/v1/sites/fake/home")
        with lock:
            results.append(response.status_code)

    threads = [threading.Thread(target=call) for _ in range(4)]
    for thread in threads:
        thread.start()
    time.sleep(0.2)  # 让请求都落到同一个 key 上
    for thread in threads:
        thread.join()

    assert results == [200] * 4
    assert crawler_calls(crawler_counter, "home") == 1, "4 个并发请求抓了不止 1 次"


def test_a_dead_source_does_not_take_down_the_other_endpoints(authed_client, crawler_counter, monkeypatch):
    """源挂了的时候，本站该做的是**只降级**，不是全站崩。

    ``/sites``、健康检查、心跳都不经过爬虫，所以源挂了它们必须照样好；
    而源自己的内容接口要给出**诚实**的错误，而不是空白页或 500。
    """
    monkeypatch.setenv("FAKE_MODE", "error")

    assert authed_client.get("/api/v1/health").status_code == 200
    assert authed_client.post("/api/v1/activation/heartbeat").status_code == 200
    assert authed_client.get("/api/v1/sites").json()["ok"] is True

    failed = authed_client.get("/api/v1/sites/fake/home")
    assert failed.status_code == 503
    body = failed.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "UPSTREAM_BLOCKED"
    assert body["request_id"], "错误信封也要能拿 request_id 去串日志"

    assert crawler_calls(crawler_counter, "home") >= 1
