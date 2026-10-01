"""后台的源开关（站点管理）：列表 / 启用停用 / 排序，以及它对用户端的影响。

这一批最要紧的不是"接口返回 200"，而是**副作用精确**：

* 停用之后用户端的站点列表里没有它；
* 停用之后内容接口**不再 fork 爬虫**（靠 ``crawler_counter`` 数真调用次数）；
* **连缓存里的内容也不再发出** —— 首页有缓存，只在注册表里拦是不够的，
  那条路径根本走不到注册表。漏掉这一条，症状就是"关掉了但还能看"；
* 排序真的改变了用户端拿到的顺序，而不是只在后台里显示成那样。

自带的假爬虫目录里只有**一个**源（``fake``），测不了"藏一个留一个"和"顺序"，
所以这里自己造一个两源的临时目录。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.api.deps import ADMIN_TOKEN_HEADER, get_settings, get_warmup_runner, reset_runtime
from tests.helpers import crawler_calls

ADMIN = "test-admin-token"
HEADERS = {ADMIN_TOKEN_HEADER: ADMIN}


def _site_script(key: str, name: str) -> str:
    """一个最小的假源：只吐 meta / home，并且照样记 ``FAKE_COUNTER``。"""
    return f'''#!/usr/bin/env python
"""测试用的源。"""
from __future__ import annotations

import json
import os
import sys

KEY = "{key}"


def _emit(ok, data=None, code=None, message=None):
    error = None if ok else {{"code": code, "message": message}}
    print(json.dumps({{"ok": ok, "data": data, "error": error}}, ensure_ascii=False))


def _count(command):
    path = os.environ.get("FAKE_COUNTER")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(command + "\\n")


def main() -> int:
    command = "meta"
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        command = sys.argv[1]
    _count(command)

    if command == "meta":
        _emit(True, {{
            "key": KEY,
            "name": "{name}",
            "version": "1.0.0",
            "base_url": "https://example.test",
            "mode": "direct",
            "capabilities": ["meta", "home", "category", "detail", "play"],
            "play_format": ["m3u8"],
        }})
        return 0
    if command == "home":
        _emit(True, {{
            "categories": [{{"tid": "1", "name": "分类一"}}],
            "recommend": [
                {{
                    "vod_id": "1",
                    "vod_name": "测试影片",
                    "vod_pic": "https://example.test/1.jpg",
                    "vod_remarks": "全2集",
                }}
            ],
        }})
        return 0

    _emit(False, code="UNSUPPORTED", message="该源不支持 " + command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


@pytest.fixture()
def two_sites(tmp_path: Path) -> Path:
    """一个带两个源的爬虫目录（结构要和真的 ``crawler/`` 一致：下面有 ``sites/``）。"""
    sites = tmp_path / "sites"
    sites.mkdir()
    for key, name in (("alpha", "阿尔法"), ("beta", "贝塔")):
        (sites / f"{key}.py").write_text(_site_script(key, name), encoding="utf-8")
    return tmp_path


def _configure(app, crawler_dir: Path, *, token: str = ADMIN):
    """把 app 指到临时爬虫目录、打开后台令牌，并丢掉进程内单例。

    丢掉单例是必须的：注册表（meta 缓存 + 每站守护）与源开关快照都是进程级的，
    不清的话上一个用例的状态会跟到这个用例里来。
    """
    settings = app.dependency_overrides[get_settings]()
    updated = settings.model_copy(update={"crawler_dir": crawler_dir, "admin_token": token})
    app.dependency_overrides[get_settings] = lambda: updated
    reset_runtime()
    return updated


# ------------------------------------------------------------------ 读

def test_admin_lists_every_source_with_switch_and_order(authed_client, fake_app, two_sites):
    _configure(fake_app, two_sites)

    body = authed_client.get("/api/v1/admin/sites", headers=HEADERS).json()
    assert body["ok"] is True

    sites = body["data"]["sites"]
    assert [item["key"] for item in sites] == ["alpha", "beta"]
    assert all(item["enabled"] is True for item in sites), "没有记录 = 启用"
    assert sites[0]["name"] == "阿尔法"
    assert "home" in sites[0]["capabilities"]
    assert sites[0]["sort_order"] == 0
    assert sites[0]["meta_error"] is None
    # 健康是同一份快照：能顺手看到"这个源现在是不是被熔断了"
    assert sites[0]["health"]["site"] == "alpha"
    assert sites[0]["health"]["state"] == "closed"


def test_a_broken_meta_still_shows_up_in_the_list(authed_client, fake_app, tmp_path):
    """一个**刚上传、还没跑通**的源最需要被看见 —— 它不该让整张表炸掉。"""
    sites = tmp_path / "sites"
    sites.mkdir()
    (sites / "broken.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    _configure(fake_app, tmp_path)

    items = authed_client.get("/api/v1/admin/sites", headers=HEADERS).json()["data"]["sites"]
    assert [item["key"] for item in items] == ["broken"]
    assert items[0]["meta_error"], "取不到 meta 要把原因写出来，而不是安静地少一行"
    assert items[0]["name"] == "broken", "取不到名字时退化成 key"


# ------------------------------------------------------------------ 停用 / 启用

def test_disable_hides_the_source_from_users(authed_client, fake_app, two_sites):
    _configure(fake_app, two_sites)
    assert [item["key"] for item in authed_client.get("/api/v1/sites").json()["data"]["sites"]] == [
        "alpha",
        "beta",
    ]

    response = authed_client.post("/api/v1/admin/sites/alpha/disable", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["data"]["site"]["enabled"] is False

    assert [item["key"] for item in authed_client.get("/api/v1/sites").json()["data"]["sites"]] == ["beta"]
    # 后台仍然看得见它 —— 运维要能看到自己关掉了什么
    assert [item["key"] for item in authed_client.get("/api/v1/admin/sites", headers=HEADERS).json()["data"]["sites"]] == [
        "alpha",
        "beta",
    ]


def test_disabled_source_reports_a_dedicated_error_code(authed_client, fake_app, two_sites):
    """它和"源坏了"是两件事：坏了是 ``UPSTREAM_*``（用户看得到、只是打不开），
    被我们关掉是 ``SITE_DISABLED``（它根本不该出现）。"""
    _configure(fake_app, two_sites)
    authed_client.post("/api/v1/admin/sites/alpha/disable", headers=HEADERS)

    detail = authed_client.get("/api/v1/sites/alpha")
    assert detail.status_code == 503
    assert detail.json()["error"]["code"] == "SITE_DISABLED"

    home = authed_client.get("/api/v1/sites/alpha/home")
    assert home.status_code == 503
    assert home.json()["error"]["code"] == "SITE_DISABLED"


def test_disable_beats_the_cache(authed_client, fake_app, two_sites):
    """**连缓存里的内容也不再发出。**

    首页/分类/详情都有缓存，所以只在注册表（唯一通往爬虫的关口）里拦是不够的：
    缓存命中根本走不到那里。漏掉这条的症状就是"关掉了但还能看"。
    """
    _configure(fake_app, two_sites)
    assert authed_client.get("/api/v1/sites/alpha/home").status_code == 200, "先把缓存捂热"

    authed_client.post("/api/v1/admin/sites/alpha/disable", headers=HEADERS)

    cached = authed_client.get("/api/v1/sites/alpha/home")
    assert cached.status_code == 503, "缓存热着也不能放行"
    assert cached.json()["error"]["code"] == "SITE_DISABLED"


def test_disable_stops_calling_the_crawler(authed_client, fake_app, two_sites, crawler_counter):
    """停用之后 `alpha` **一次内容抓取都不该再被 fork** —— 这是"关掉"的实际含义。

    只数 ``home``：列表接口会去取**别的源**的 meta（那是应该的），
    数总数会把那份合法的调用也算进来。
    """
    _configure(fake_app, two_sites)
    authed_client.get("/api/v1/sites/alpha/home")
    before = crawler_calls(crawler_counter, "home")

    authed_client.post("/api/v1/admin/sites/alpha/disable", headers=HEADERS)
    authed_client.get("/api/v1/sites/alpha/home")
    authed_client.get("/api/v1/sites")

    assert crawler_calls(crawler_counter, "home") == before


def test_enable_brings_it_back(authed_client, fake_app, two_sites):
    _configure(fake_app, two_sites)
    authed_client.post("/api/v1/admin/sites/alpha/disable", headers=HEADERS)

    assert authed_client.post("/api/v1/admin/sites/alpha/enable", headers=HEADERS).status_code == 200
    assert [item["key"] for item in authed_client.get("/api/v1/sites").json()["data"]["sites"]] == [
        "alpha",
        "beta",
    ]
    assert authed_client.get("/api/v1/sites/alpha/home").status_code == 200


def test_unknown_source_is_rejected(authed_client, fake_app, two_sites):
    """拼错的 key 必须报错，而不是在库里静静生成一条永远的垃圾记录。"""
    _configure(fake_app, two_sites)

    response = authed_client.post("/api/v1/admin/sites/typo/disable", headers=HEADERS)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# ------------------------------------------------------------------ 顺序

def test_order_changes_what_users_see(authed_client, fake_app, two_sites):
    _configure(fake_app, two_sites)

    body = authed_client.post(
        "/api/v1/admin/sites/order", headers=HEADERS, json={"keys": ["beta", "alpha"]}
    ).json()
    assert body["ok"] is True
    assert [item["key"] for item in body["data"]["sites"]] == ["beta", "alpha"]
    assert body["data"]["sites"][0]["sort_order"] > 0

    assert [item["key"] for item in authed_client.get("/api/v1/sites").json()["data"]["sites"]] == [
        "beta",
        "alpha",
    ]


def test_order_puts_unmentioned_sources_last(authed_client, fake_app, two_sites):
    """没提到的 key 排在后面，而不是报错 —— "没提到"通常就是"这期间新加了一个源"。"""
    _configure(fake_app, two_sites)

    body = authed_client.post("/api/v1/admin/sites/order", headers=HEADERS, json={"keys": ["beta"]}).json()
    assert [item["key"] for item in body["data"]["sites"]] == ["beta", "alpha"]


def test_order_rejects_an_unknown_key(authed_client, fake_app, two_sites):
    """静默忽略会让人以为"设过了"，然后在用户端看到顺序没变 —— 那比报错难查得多。"""
    _configure(fake_app, two_sites)

    response = authed_client.post(
        "/api/v1/admin/sites/order", headers=HEADERS, json={"keys": ["beta", "typo"]}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"


# ------------------------------------------------------------------ 预热

def test_warmup_skips_disabled_sources(authed_client, fake_app, two_sites):
    """被关掉的源不该每天被我们准点去捅一次。"""
    settings = _configure(fake_app, two_sites)
    authed_client.post("/api/v1/admin/sites/alpha/disable", headers=HEADERS)

    status = get_warmup_runner(settings).run_once(reason="测试")
    assert [item.site for item in status.sites] == ["beta"]


# ------------------------------------------------------------------ 鉴权

def test_site_management_needs_the_admin_token(authed_client, fake_app, two_sites):
    _configure(fake_app, two_sites, token="")

    assert authed_client.get("/api/v1/admin/sites").status_code == 403
    assert authed_client.post("/api/v1/admin/sites/alpha/disable", headers=HEADERS).status_code == 403
    assert authed_client.post(
        "/api/v1/admin/sites/order", headers=HEADERS, json={"keys": ["alpha"]}
    ).status_code == 403
