"""扩展功能与缓存透视自动化测试：
1. 缓存透视看板、按站点/按Key清空与首页预热
2. 单站独立缓存策略（TTL自定义）
3. 在线探针与试播台
4. 图片防盗链代理与缓存清理
5. 全站公告与紧急维护模式拦截
6. 请求耗时与响应头验证
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import ADMIN_TOKEN_HEADER, get_settings, reset_runtime
from app.cache.content import ContentCache
from app.cache.ttl import TTLCache

ADMIN = "test-admin-token"
ADMIN_HEADERS = {ADMIN_TOKEN_HEADER: ADMIN}


def _site_script(key: str, name: str) -> str:
    return f"""import json, sys
def _emit(ok, data=None, code="", message=""):
    print(json.dumps({{"ok": ok, "data": data, "error": {{"code": code, "message": message}} if not ok else None}}))
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "meta"
    if cmd == "meta":
        _emit(True, {{"key": "{key}", "name": "{name}", "version": "1.0.0", "mode": "direct", "capabilities": ["meta", "home", "category", "detail", "play"], "play_format": ["m3u8"]}})
    elif cmd == "home":
        _emit(True, {{"categories": [{{"tid": "1", "name": "电影"}}], "recommend": [{{"vod_id": "101", "vod_name": "测试电影", "vod_pic": "", "vod_remarks": "HD"}}]}})
    elif cmd == "play":
        _emit(True, {{"url": "https://example.com/live.m3u8", "format": "m3u8"}})
    else:
        _emit(False, code="UNSUPPORTED", message="not supported")
"""


@pytest.fixture()
def two_sites(tmp_path, authed_client: TestClient):
    sites_dir = tmp_path / "sites"
    sites_dir.mkdir(parents=True, exist_ok=True)
    (sites_dir / "alpha.py").write_text(_site_script("alpha", "阿尔法源"), encoding="utf-8")
    (sites_dir / "beta.py").write_text(_site_script("beta", "贝塔源"), encoding="utf-8")
    settings = authed_client.app.dependency_overrides[get_settings]()
    updated = settings.model_copy(update={"crawler_dir": tmp_path, "admin_token": ADMIN})
    authed_client.app.dependency_overrides[get_settings] = lambda: updated
    reset_runtime()
    yield tmp_path
    reset_runtime()


@pytest.fixture(autouse=True)
def _setup_admin(authed_client: TestClient):
    """自动给测试 app 注入 admin_token 并重置运行时。"""
    settings = authed_client.app.dependency_overrides[get_settings]()
    updated = settings.model_copy(update={"admin_token": ADMIN})
    authed_client.app.dependency_overrides[get_settings] = lambda: updated
    reset_runtime()
    yield
    reset_runtime()




def test_ttl_cache_extended():
    cache = TTLCache(maxsize=10, ttl=60)
    cache.set("site_a|home|-", "val_a")
    cache.set("site_a|category|1:1", "val_cat")
    cache.set("site_b|home|-", "val_b")

    val, hit = cache.get_detailed("site_a|home|-")
    assert hit is True
    assert val == "val_a"

    val_miss, hit_miss = cache.get_detailed("non_existent")
    assert hit_miss is False
    assert val_miss is None

    entries = cache.list_entries()
    assert len(entries) == 3

    # 按前缀清理 site_a
    cleared = cache.invalidate_prefix("site_a|")
    assert cleared == 2
    assert len(cache) == 1
    assert cache.get("site_b|home|-") == "val_b"


def test_content_cache_extended():
    cc = ContentCache(ttl_home=60, ttl_category=30, ttl_detail=30)
    cc.home("alpha", lambda: "alpha_home")
    cc.category("alpha", "1", 1, lambda: "alpha_cat")
    cc.home("beta", lambda: "beta_home")

    stats = cc.stats()
    assert stats["size"] == 3
    assert "hit_ratio_percent" in stats

    # 查 key 列表
    keys_alpha = cc.list_keys(site="alpha")
    assert len(keys_alpha) == 2

    # 按站点清除
    cc.invalidate_site("alpha")
    assert len(cc.list_keys(site="alpha")) == 0
    assert len(cc.list_keys(site="beta")) == 1


def test_admin_cache_api(authed_client: TestClient, fake_app):
    # 1. 查 stats
    res = authed_client.get("/api/v1/admin/cache/stats", headers=ADMIN_HEADERS)
    assert res.status_code == 200
    data = res.json()["data"]
    assert "size" in data
    assert "hit_ratio_percent" in data

    # 2. 查 keys
    res_keys = authed_client.get("/api/v1/admin/cache/keys", headers=ADMIN_HEADERS)
    assert res_keys.status_code == 200
    assert isinstance(res_keys.json()["data"], list)

    # 3. 预热
    res_preheat = authed_client.post("/api/v1/admin/cache/preheat", json={}, headers=ADMIN_HEADERS)
    assert res_preheat.status_code == 200

    # 4. 清理
    res_clear = authed_client.post("/api/v1/admin/cache/clear", json={}, headers=ADMIN_HEADERS)
    assert res_clear.status_code == 200
    assert res_clear.json()["data"]["cleared_count"] >= 0


def test_site_cache_policy(authed_client: TestClient, fake_app, two_sites):
    # 获取默认单站缓存策略
    res = authed_client.get("/api/v1/admin/sites/alpha/cache-policy", headers=ADMIN_HEADERS)
    assert res.status_code == 200

    # 修改单站缓存策略
    update_res = authed_client.put(
        "/api/v1/admin/sites/alpha/cache-policy",
        json={"home_ttl": 120, "category_ttl": 60, "detail_ttl": 0},
        headers=ADMIN_HEADERS,
    )
    assert update_res.status_code == 200
    saved = update_res.json()["data"]
    assert saved["home_ttl"] == 120
    assert saved["detail_ttl"] == 0


def test_playground_probe(authed_client: TestClient, fake_app, two_sites):
    # 测试探针 home 命令
    res = authed_client.post(
        "/api/v1/admin/playground/probe",
        json={"site": "alpha", "command": "home", "bypass_cache": True},
        headers=ADMIN_HEADERS,
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["site"] == "alpha"
    assert data["command"] == "home"
    assert data["status"] in ("OK", "ERROR")
    assert "elapsed_ms" in data


def test_system_notice_and_maintenance(authed_client: TestClient, client: TestClient, fake_app):
    # 1. 读公告
    res_n = authed_client.get("/api/v1/admin/system/notice", headers=ADMIN_HEADERS)
    assert res_n.status_code == 200

    # 2. 发布公告
    up_n = authed_client.put(
        "/api/v1/admin/system/notice",
        json={
            "enabled": True,
            "title": "系统升级提示",
            "content": "今晚 24:00 进行例行维护",
            "level": "warning",
            "display_type": "banner",
        },
        headers=ADMIN_HEADERS,
    )
    assert up_n.status_code == 200
    assert up_n.json()["data"]["enabled"] is True

    # 3. 公开接口检查公告生效
    pub_res = client.get("/api/v1/system/status")
    assert pub_res.status_code == 200
    pub_data = pub_res.json()["data"]
    assert pub_data["notice"] is not None
    assert pub_data["notice"]["title"] == "系统升级提示"

    # 4. 开启维护模式
    m_res = authed_client.put(
        "/api/v1/admin/system/maintenance",
        json={"enabled": True, "message": "全站升级中"},
        headers=ADMIN_HEADERS,
    )
    assert m_res.status_code == 200

    # 5. 验证普通接口被 503 拦截，而后台放行
    normal_res = client.get("/api/v1/sites")
    assert normal_res.status_code == 503
    assert normal_res.json()["error"]["code"] == "SERVER_MAINTENANCE"

    admin_res = authed_client.get("/api/v1/admin/system/maintenance", headers=ADMIN_HEADERS)
    assert admin_res.status_code == 200

    # 6. 关闭维护模式
    authed_client.put(
        "/api/v1/admin/system/maintenance",
        json={"enabled": False, "message": ""},
        headers=ADMIN_HEADERS,
    )
    normal_res2 = client.get("/api/v1/sites")
    assert normal_res2.status_code != 503


def test_image_proxy_admin(authed_client: TestClient, fake_app):
    res = authed_client.get("/api/v1/admin/proxy/stats", headers=ADMIN_HEADERS)
    assert res.status_code == 200
    assert "cached_files" in res.json()["data"]

    clr = authed_client.post("/api/v1/admin/proxy/clear", headers=ADMIN_HEADERS)
    assert clr.status_code == 200
    assert "freed_mb" in clr.json()["data"]

