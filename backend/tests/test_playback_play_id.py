"""播放链路的 ``play_id`` 加速通道。

它同时是**一处信任边界**：这个值会被原样交给爬虫去抓取，
所以"必须不放过绝对 URL"和"必须能省掉一次源站请求"一样重要。
"""

from __future__ import annotations

from tests.helpers import crawler_calls


def test_play_id_reaches_the_crawler(fake_runner, crawler_counter):
    """play_id 要真的被转成 ``--play-id`` 交给爬虫子进程。

    假爬虫会把"有没有收到 play_id"写进返回的 url（``via-play-id`` /
    ``via-detail``），所以这里验的是**端到端真的送到了**，不是"我们以为自己传了"。
    """
    from app.cache.content import ContentCache
    from app.crawler.registry import SiteRegistry
    from app.services import catalog_service

    registry = SiteRegistry(fake_runner, meta_ttl=0)
    cache = ContentCache()

    with_id = catalog_service.playback(registry, "fake", "1", ep=1, play_id="p1")
    without = catalog_service.playback(registry, "fake", "1", ep=1)

    assert "via-play-id" in str(with_id.url)
    assert "via-detail" in str(without.url)
    assert crawler_calls(crawler_counter, "play") == 2
    assert crawler_calls(crawler_counter, "detail") == 0, "播放这条路上不该出现详情"


def test_dangerous_play_id_is_dropped_not_rejected(authed_client, crawler_counter):
    """不可信的 play_id **丢掉并回退**，而不是报错 —— 它是加速用的，不该成为新的失败原因。"""
    for bad in (
        "https://evil.example/x",
        "//evil.example/x",
        "\\\\evil.example\\x",
        "/a/../../etc/passwd",
        "a b",
    ):
        with_sub = authed_client.get(
            "/api/v1/sites/fake/playback",
            params={"vod_id": "1", "ep": 1, "play_id": bad},
        )
        assert with_sub.status_code == 200, f"不该因为 play_id 失败: {bad}"
        payload = with_sub.json()
        assert payload["ok"] is True
        assert "via-detail" in payload["data"]["url"], "可疑的值还是被送下去了"

    assert crawler_calls(crawler_counter, "play") == 5


def test_a_reasonable_play_id_is_forwarded(authed_client, crawler_counter):
    body = authed_client.get(
        "/api/v1/sites/fake/playback",
        params={"vod_id": "1", "ep": 1, "play_id": "/play/318185-41-2946527.html"},
    ).json()
    assert body["ok"] is True
    assert "via-play-id" in body["data"]["url"]
    assert crawler_calls(crawler_counter, "play") == 1


def test_playback_still_works_without_play_id(authed_client):
    """老客户端不传它也必须能用 —— 这是"加速"，不是新要求。"""
    body = authed_client.get("/api/v1/sites/fake/playback", params={"vod_id": "1"}).json()
    assert body["ok"] is True
    assert body["data"]["url"].endswith(".m3u8")
