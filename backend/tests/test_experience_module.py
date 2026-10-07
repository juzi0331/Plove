"""前台体验模块集成测试：后台编辑主题/首页 -> 草稿 -> 预览 -> 发布 -> 自动生效 -> 回滚闭环。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import ADMIN_TOKEN_HEADER

ADMIN_HEADERS = {ADMIN_TOKEN_HEADER: "plove-admin-secret-token-32bytes!!"}


@pytest.fixture(autouse=True)
def _enable_admin(fake_settings):
    fake_settings.admin_token = "plove-admin-secret-token-32bytes!!"


def test_public_bootstrap_and_etag(anon_client: TestClient):
    """测试客户端匿名获取 Bootstrap 与 304 ETag 协商。"""
    resp = anon_client.post("/api/v2/client/bootstrap")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["schema_version"] == "1.0"
    assert data["brand"]["name"] == "Plove"
    assert data["theme"]["color"]["primary"] == "#E50914"
    assert data["player_defaults"]["auto_next"] is True
    assert len(data["navigation"]) > 0

    # 测试条件版本轮询接口
    resp = anon_client.get("/api/v2/client/releases/current")
    assert resp.status_code == 200
    etag = resp.headers.get("etag")
    assert etag is not None

    # 带上 If-None-Match，期待返回 304 Not Modified
    resp_304 = anon_client.get("/api/v2/client/releases/current", headers={"If-None-Match": etag})
    assert resp_304.status_code == 304


def test_public_page_view_model(anon_client: TestClient, authed_client: TestClient):
    """测试客户端获取首页 ViewModel：未激活拒绝（SEC-02），已激活设备正常放行。"""
    resp_anon = anon_client.get("/api/v2/client/pages/home")
    assert resp_anon.status_code == 401

    resp = authed_client.get("/api/v2/client/pages/home")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["page_id"] == "home_default"
    assert len(data["sections"]) >= 2
    # 确认组件为白名单安全组件
    assert any(s["component"] == "hero" for s in data["sections"])
    assert any(s["component"] in ("video_rail", "video_grid") for s in data["sections"])


def test_admin_draft_concurrency_and_validation(anon_client: TestClient):
    """测试草稿保存、乐观并发版本锁与安全规则校验。"""
    # 1. 读取当前草稿
    resp = anon_client.get("/api/v2/admin/experience/drafts/default", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    draft = resp.json()["data"]
    current_rev = draft["revision"]

    # 2. 尝试提交非法色彩（CSS 注入）
    bad_theme_payload = {
        "revision": current_rev,
        "theme": {
            "color": {"primary": "red; background: url(https://evil.test)"},
        },
    }
    resp = anon_client.put(
        "/api/v2/admin/experience/drafts/default",
        headers=ADMIN_HEADERS,
        json=bad_theme_payload,
    )
    assert resp.status_code == 400
    assert "非合法 Hex 颜色" in resp.json()["error"]["message"]

    # 3. 尝试提交未知未授权组件
    bad_comp_payload = {
        "revision": current_rev,
        "pages": {
            "home_default": {
                "id": "home_default",
                "title": "首页",
                "sections": [{"id": "s1", "component": "malicious_script_runner", "props": {}}],
            }
        },
    }
    resp = anon_client.put(
        "/api/v2/admin/experience/drafts/default",
        headers=ADMIN_HEADERS,
        json=bad_comp_payload,
    )
    assert resp.status_code == 400
    assert "未支持的未知组件" in resp.json()["error"]["message"]

    # 4. 提交合法修改并验证版本递增
    good_payload = {
        "revision": current_rev,
        "brand": {"name": "Plove Cinema Pro", "logo_url": ""},
        "theme": {
            "color": {
                "background": "#0a0a0a",
                "surface": "#161616",
                "primary": "#00E5FF",
                "text": "#FFFFFF",
                "muted": "#999999",
                "border": "#222222",
                "danger": "#FF3366",
            },
            "card": {"radius_px": 12, "aspect_ratio": "16:9", "image_fit": "cover"},
        },
    }
    resp = anon_client.put(
        "/api/v2/admin/experience/drafts/default",
        headers=ADMIN_HEADERS,
        json=good_payload,
    )
    assert resp.status_code == 200
    new_rev = resp.json()["data"]["revision"]
    assert new_rev == current_rev + 1

    # 5. 用旧版本号再次提交，验证并发冲突被拦截
    resp_conflict = anon_client.put(
        "/api/v2/admin/experience/drafts/default",
        headers=ADMIN_HEADERS,
        json=good_payload,
    )
    assert resp_conflict.status_code == 400
    assert "已被其他管理员修改" in resp_conflict.json()["error"]["message"]


def test_preview_isolation(anon_client: TestClient):
    """测试预览隔离：草稿预览不改变线上已发布版本。"""
    # 获取线上当前公开配置
    pub_resp = anon_client.post("/api/v2/client/bootstrap")
    online_color = pub_resp.json()["data"]["theme"]["color"]["primary"]

    # 读取草稿当前 revision 并修改草稿颜色
    resp = anon_client.get("/api/v2/admin/experience/drafts/default", headers=ADMIN_HEADERS)
    rev = resp.json()["data"]["revision"]
    anon_client.put(
        "/api/v2/admin/experience/drafts/default",
        headers=ADMIN_HEADERS,
        json={
            "revision": rev,
            "theme": {
                "color": {
                    "background": "#141414",
                    "surface": "#202020",
                    "primary": "#A020F0",
                    "text": "#FFFFFF",
                    "muted": "#B8B8B8",
                    "border": "#2A2A2A",
                    "danger": "#E50914",
                }
            },
        },
    )

    # 请求预览接口：应看到新紫色 #A020F0
    prev_resp = anon_client.get(
        "/api/v2/admin/experience/drafts/default/preview/bootstrap",
        headers=ADMIN_HEADERS,
    )
    assert prev_resp.status_code == 200
    assert prev_resp.json()["data"]["theme"]["color"]["primary"] == "#A020F0"
    assert prev_resp.json()["data"]["release_id"].startswith("preview_")

    # 再次请求公开接口：线上颜色依然保持原样，未被草稿污染！
    pub_resp2 = anon_client.post("/api/v2/client/bootstrap")
    assert pub_resp2.json()["data"]["theme"]["color"]["primary"] == online_color


def test_publish_and_rollback_closed_loop(anon_client: TestClient):
    """测试完整发布与回滚闭环：发布生效 -> ETag变更 -> 回滚生成更高修订号。"""
    # 1. 记录初始发布信息
    init_info = anon_client.get("/api/v2/client/releases/current").json()["data"]
    init_rel_id = init_info["release_id"]
    init_rev = init_info["revision"]

    # 2. 修改草稿并发布
    draft_info = anon_client.get("/api/v2/admin/experience/drafts/default", headers=ADMIN_HEADERS).json()["data"]
    draft_rev = draft_info["revision"]

    anon_client.put(
        "/api/v2/admin/experience/drafts/default",
        headers=ADMIN_HEADERS,
        json={
            "revision": draft_rev,
            "brand": {"name": "Plove Gold Edition", "logo_url": ""},
            "theme": {
                "color": {
                    "background": "#121212",
                    "surface": "#1e1e1e",
                    "primary": "#FFD700",
                    "text": "#FFFFFF",
                    "muted": "#AAAAAA",
                    "border": "#333333",
                    "danger": "#FF4444",
                }
            },
        },
    )

    # 发布新版本
    pub_resp = anon_client.post(
        "/api/v2/admin/experience/drafts/default/publish",
        headers=ADMIN_HEADERS,
        json={"note": "上线金色版主题"},
    )
    assert pub_resp.status_code == 200
    pub_data = pub_resp.json()["data"]
    published_rel_id = pub_data["release_id"]
    published_rev = pub_data["revision"]
    assert published_rev > init_rev

    # 3. 验证公开客户端自动感知新发布
    curr_info = anon_client.get("/api/v2/client/releases/current").json()["data"]
    assert curr_info["release_id"] == published_rel_id
    assert curr_info["revision"] == published_rev

    boot_data = anon_client.post("/api/v2/client/bootstrap").json()["data"]
    assert boot_data["brand"]["name"] == "Plove Gold Edition"
    assert boot_data["theme"]["color"]["primary"] == "#FFD700"

    # 4. 执行回滚至初始版本
    rollback_resp = anon_client.post(
        f"/api/v2/admin/experience/releases/{init_rel_id}/rollback",
        headers=ADMIN_HEADERS,
        json={"note": "紧急回滚至出厂配置"},
    )
    assert rollback_resp.status_code == 200
    rb_data = rollback_resp.json()["data"]
    # 关键断言：回滚生成的修订号必须严格大于刚刚发布的修订号，防止客户端缓存忽略
    assert rb_data["revision"] > published_rev

    # 5. 验证回滚后公开客户端自动恢复原品牌配置，且版本号为最新的更大值
    final_info = anon_client.get("/api/v2/client/releases/current").json()["data"]
    assert final_info["revision"] == rb_data["revision"]

    final_boot = anon_client.post("/api/v2/client/bootstrap").json()["data"]
    assert final_boot["brand"]["name"] == "Plove"
    assert final_boot["theme"]["color"]["primary"] == "#E50914"
