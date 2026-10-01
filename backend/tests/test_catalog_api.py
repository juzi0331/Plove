"""目录接口的端到端测试。

全部走假爬虫，**不联网**：从 HTTP 入口一路穿到子进程，再回到信封。
所以这里测的是"整条链路"，而不是某个函数。
"""

from __future__ import annotations


def test_list_sites(authed_client):
    body = authed_client.get("/api/v1/sites").json()
    assert body["ok"] is True
    assert [site["key"] for site in body["data"]["sites"]] == ["fake"]


def test_get_single_site(authed_client):
    body = authed_client.get("/api/v1/sites/fake").json()
    assert body["data"]["name"] == "假站点"
    assert body["data"]["mode"] == "direct"


def test_home(authed_client):
    body = authed_client.get("/api/v1/sites/fake/home").json()
    assert body["data"]["categories"][0]["tid"] == "1"
    assert body["data"]["recommend"][0]["vod_id"] == "1"


def test_category_passes_page_through(authed_client):
    body = authed_client.get(
        "/api/v1/sites/fake/category", params={"tid": "1", "page": 4}
    ).json()
    assert body["data"]["page"] == 4
    assert body["data"]["videos"][0]["vod_name"] == "测试影片"


def test_detail_has_episodes_and_lines(authed_client):
    body = authed_client.get("/api/v1/sites/fake/detail", params={"vod_id": "1"}).json()
    assert body["data"]["episodes"][0]["ep_index"] == 1
    assert body["data"]["lines"][0]["line"] == 1


def test_playback_returns_url_and_headers(authed_client):
    body = authed_client.get(
        "/api/v1/sites/fake/playback", params={"vod_id": "1", "ep": 1}
    ).json()
    assert body["data"]["url"].endswith(".m3u8")
    assert body["data"]["headers"]["Referer"]


def test_unsupported_capability_is_not_an_empty_list(authed_client):
    """没有搜索能力时必须明确报错 —— 不许用空列表假装"搜到 0 条"。"""
    response = authed_client.get("/api/v1/sites/fake/search", params={"kw": "任意"})
    assert response.status_code == 501

    body = response.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "UNSUPPORTED"


def test_unknown_site_is_404(authed_client):
    response = authed_client.get("/api/v1/sites/nope/home")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_upstream_error_keeps_the_envelope(authed_client, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "error")
    response = authed_client.get("/api/v1/sites/fake/home")
    assert response.status_code == 503

    body = response.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "UPSTREAM_BLOCKED"
    assert body["request_id"]


def test_malformed_payload_is_rejected(authed_client, monkeypatch):
    """契约在这里兑现：爬虫回了缺必填字段的卡片，直接拒收，并指出错在哪。"""
    monkeypatch.setenv("FAKE_MODE", "bad_data")
    response = authed_client.get("/api/v1/sites/fake/home")
    assert response.status_code == 502

    body = response.json()
    assert body["error"]["code"] == "UPSTREAM_PARSE_ERROR"
    assert body["error"]["detail"][0]["loc"]


def test_broken_site_is_skipped_instead_of_breaking_the_list(authed_client, monkeypatch):
    """一个源挂了，不该让整张站点列表跟着挂。"""
    monkeypatch.setenv("FAKE_MODE", "meta_broken")
    body = authed_client.get("/api/v1/sites").json()
    assert body["ok"] is True
    assert body["data"]["sites"] == []


def test_missing_required_query_param_is_a_validation_error(authed_client):
    response = authed_client.get("/api/v1/sites/fake/detail")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
