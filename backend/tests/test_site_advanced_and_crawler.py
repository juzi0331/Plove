"""测试单站高级控制、采集器上传/校验、分类/子分类规则与详情页清洗策略。"""

from __future__ import annotations

from pathlib import Path
import tempfile

from fastapi.testclient import TestClient
import pytest

from app.api.deps import ADMIN_TOKEN_HEADER, get_settings, reset_runtime
from app.core.errors import ErrorCode
from app.services import crawler_manage_service

ADMIN = "test-admin-token"
ADMIN_HEADERS = {ADMIN_TOKEN_HEADER: ADMIN}


@pytest.fixture(autouse=True)
def _setup_admin(authed_client: TestClient):
    """自动给测试 app 注入 admin_token 并重置运行时。"""
    settings = authed_client.app.dependency_overrides[get_settings]()
    updated = settings.model_copy(update={"admin_token": ADMIN})
    authed_client.app.dependency_overrides[get_settings] = lambda: updated
    reset_runtime()
    yield
    reset_runtime()


def test_crawler_audit_blocks_dangerous_code():
    """测试采集器 AST 审计阻断危险代码与语法错误。"""
    # 语法错误
    res = crawler_manage_service.validate_crawler_code("def foo( broken", Path("."))
    assert not res.valid
    assert "语法错误" in (res.error or "")

    # 导入受限模块
    bad_code_import = """
import subprocess
print("hack")
"""
    res = crawler_manage_service.validate_crawler_code(bad_code_import, Path("."))
    assert not res.valid
    assert "禁止导入受限模块" in (res.error or "")

    # 危险调用
    bad_code_exec = """
import os
os.system("whoami")
"""
    res = crawler_manage_service.validate_crawler_code(bad_code_exec, Path("."))
    assert not res.valid
    assert "禁止调用受限属性" in (res.error or "")


def test_crawler_upload_and_manage_api(authed_client: TestClient, tmp_path: Path):
    """测试后台采集器上传、查看源码与删除端点。"""
    # 配置临时 crawler_dir
    sites_dir = tmp_path / "sites"
    sites_dir.mkdir(parents=True, exist_ok=True)
    settings = authed_client.app.dependency_overrides[get_settings]()
    updated = settings.model_copy(update={"crawler_dir": tmp_path})
    authed_client.app.dependency_overrides[get_settings] = lambda: updated
    reset_runtime()

    valid_script = '''"""合法演示采集器。"""
import json
import sys

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "meta"
    if cmd == "meta":
        data = {
            "key": "demo_test_site",
            "name": "演示测试站",
            "capabilities": ["meta", "home", "category", "detail", "play"],
            "mode": "direct"
        }
        print(json.dumps({"ok": True, "data": data}))
    else:
        print(json.dumps({"ok": True, "data": {}}))

if __name__ == "__main__":
    main()
'''

    # 1. 校验接口
    resp = authed_client.post(
        "/api/v1/admin/crawlers/validate",
        headers=ADMIN_HEADERS,
        json={"code": valid_script, "key": "demo_test_site"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["valid"] is True
    assert data["meta"]["name"] == "演示测试站"

    # 2. 上传脚本
    resp = authed_client.post(
        "/api/v1/admin/crawlers/upload",
        headers=ADMIN_HEADERS,
        json={"key": "demo_test_site", "code": valid_script},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["success"] is True

    # 3. 读取源码
    resp = authed_client.get(
        "/api/v1/admin/crawlers/demo_test_site/code",
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    assert "演示测试站" in resp.json()["data"]["code"]

    # 4. 删除脚本
    resp = authed_client.delete(
        "/api/v1/admin/crawlers/demo_test_site",
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200


def test_site_advanced_settings_api(authed_client: TestClient):
    """测试单站高级配置（别名、角标、超时）。"""
    resp = authed_client.put(
        "/api/v1/admin/sites/fake/advanced",
        headers=ADMIN_HEADERS,
        json={
            "custom_name": "VIP超清线路",
            "badge": "4K极速",
            "timeout_seconds": 15.0,
            "note": "测试单站高级控制",
            "proxy_enabled": True,
            "proxy_url": "http://192.168.31.5:10809",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["custom_name"] == "VIP超清线路"
    assert data["badge"] == "4K极速"
    assert data["timeout_seconds"] == 15.0
    assert data["proxy_enabled"] is True
    assert data["proxy_url"] == "http://192.168.31.5:10809"

    # 验证获取接口
    resp = authed_client.get(
        "/api/v1/admin/sites/fake/advanced",
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    adv_data = resp.json()["data"]
    assert adv_data["custom_name"] == "VIP超清线路"
    assert adv_data["proxy_enabled"] is True
    assert adv_data["proxy_url"] == "http://192.168.31.5:10809"

    # 验证后台站点列表接口携带了独立代理状态
    resp = authed_client.get("/api/v1/admin/sites", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    admin_sites = resp.json()["data"]["sites"]
    fake_admin_site = next(s for s in admin_sites if s["key"] == "fake")
    assert fake_admin_site["proxy_enabled"] is True
    assert fake_admin_site["proxy_url"] == "http://192.168.31.5:10809"

    # 验证用户端拉取站点列表时携带了自定义别名和角标
    resp = authed_client.get("/api/v1/sites")
    assert resp.status_code == 200
    sites = resp.json()["data"]["sites"]
    fake_site = next(s for s in sites if s["key"] == "fake")
    assert fake_site["name"] == "VIP超清线路"
    assert fake_site["badge"] == "4K极速"


def test_site_categories_control(authed_client: TestClient):
    """测试站点分类与子分类的控制规则（隐藏、重命名、子分类）。"""
    # 1. 抓取初始分类
    resp = authed_client.get(
        "/api/v1/admin/sites/fake/categories",
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    cats_data = resp.json()["data"]
    assert "rules" in cats_data

    # 2. 提交修改：将分类 1 隐藏，将分类 2 重命名为 "超级剧集"，并追加动作子分类
    rules = [
        {
            "tid": "1",
            "name": "分类一",
            "hidden": True,
            "custom_name": "",
            "sort_order": 10,
            "subcategories": [],
        },
        {
            "tid": "2",
            "name": "分类二",
            "hidden": False,
            "custom_name": "超级剧集",
            "sort_order": 1,
            "subcategories": [
                {"tid": "sub_action", "name": "动作剧", "custom_name": "猛男必看", "hidden": False},
                {"tid": "sub_hidden", "name": "隐藏子类", "custom_name": "", "hidden": True},
            ],
        },
    ]

    resp = authed_client.put(
        "/api/v1/admin/sites/fake/categories",
        headers=ADMIN_HEADERS,
        json={"rules": rules, "default_tid": "2"},
    )
    assert resp.status_code == 200, resp.text

    # 3. 验证用户端首页获取到的分类：分类 1 应该被隐藏，分类 2 重命名为超级剧集且带子分类
    resp = authed_client.get("/api/v1/sites/fake/home")
    assert resp.status_code == 200
    home_cats = resp.json()["data"]["categories"]
    tids = [c["tid"] for c in home_cats]
    assert "1" not in tids
    assert "2" in tids
    cat2 = next(c for c in home_cats if c["tid"] == "2")
    assert cat2["name"] == "分类二（超级剧集）"
    assert len(cat2["subcategories"]) == 1
    assert cat2["subcategories"][0]["name"] == "动作剧（猛男必看）"
    assert cat2["subcategories"][0]["tid"] == "sub_action"

    # 4. 尝试直接请求被隐藏的主分类 1 与被隐藏的子分类 sub_hidden，验证均被明确拦截
    resp = authed_client.get("/api/v1/sites/fake/category?tid=1")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == ErrorCode.FORBIDDEN.value

    resp = authed_client.get("/api/v1/sites/fake/category?tid=sub_hidden")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == ErrorCode.FORBIDDEN.value


def test_site_detail_policy(authed_client: TestClient):
    """测试详情页广告清洗、线路映射与集数格式化策略。"""
    # 配置策略：过滤 "全"、将线路映射为 "极速专线1"、强制 standard 集数命名
    resp = authed_client.put(
        "/api/v1/admin/sites/fake/detail-policy",
        headers=ADMIN_HEADERS,
        json={
            "ad_patterns": ["全"],
            "line_name_overrides": {"线路1": "极速专线1"},
            "ep_naming_rule": "standard",
            "default_poster": "https://cdn.example.com/fallback.jpg",
            "hide_fields": [],
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert "全" in data["ad_patterns"]
    assert data["line_name_overrides"]["线路1"] == "极速专线1"

    # 拉取详情页验证清洗结果
    resp = authed_client.get("/api/v1/sites/fake/detail?vod_id=1")
    assert resp.status_code == 200
    detail = resp.json()["data"]
    # 验证线路名称映射
    assert any(line["name"] == "极速专线1" for line in detail["lines"])
    # 验证集数命名被统一格式化为 "第 1 集"
    assert detail["episodes"][0]["ep_name"] == "第 1 集"


def test_proxy_nodes_and_site_binding(authed_client: TestClient):
    """测试独立代理节点池的添加、查询、采集器绑定与解绑全流程。"""
    # 1. 添加一个 VLESS 代理节点
    vless_url = (
        "vless://2b0281ef-93e1-450f-a365-5c1cfb9b87b7@hk01.example.com:443"
        "?encryption=none&flow=xtls-rprx-vision&security=reality&sni=hk01.example.com"
        "&fp=chrome&pbk=fakekey&sid=fakesid&type=tcp#香港01-VLESS高速"
    )
    resp = authed_client.post(
        "/api/v1/admin/proxy-nodes",
        headers=ADMIN_HEADERS,
        json={"raw_url": vless_url, "name": "香港01-VLESS高速", "local_port": 10819},
    )
    assert resp.status_code == 200, resp.text
    node_data = resp.json()["data"]
    node_id = node_data["id"]
    assert node_data["protocol"] == "vless"
    assert node_data["server"] == "hk01.example.com"
    assert node_data["local_port"] == 10819
    assert node_data["proxy_url"] == "http://127.0.0.1:10819"

    # 2. 查询节点列表
    resp = authed_client.get("/api/v1/admin/proxy-nodes", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    list_data = resp.json()["data"]
    assert any(n["id"] == node_id for n in list_data["nodes"])

    # 3. 导出 Xray 配置
    resp = authed_client.get(f"/api/v1/admin/proxy-nodes/{node_id}/xray", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    xray_cfg = resp.json()["data"]
    assert "inbounds" in xray_cfg
    assert "outbounds" in xray_cfg

    # 4. 在采集器高级配置中绑定该节点
    resp = authed_client.put(
        "/api/v1/admin/sites/fake/advanced",
        headers=ADMIN_HEADERS,
        json={
            "proxy_enabled": True,
            "proxy_node_id": node_id,
            "proxy_url": node_data["proxy_url"],
        },
    )
    assert resp.status_code == 200
    adv = resp.json()["data"]
    assert adv["proxy_enabled"] is True
    assert adv["proxy_node_id"] == node_id

    # 5. 验证在站点列表里也带出了 proxy_node_id
    resp = authed_client.get("/api/v1/admin/sites", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    sites = resp.json()["data"]["sites"]
    fake_site = next(s for s in sites if s["key"] == "fake")
    assert fake_site["proxy_node_id"] == node_id
    assert fake_site["proxy_enabled"] is True

    # 6. 解绑验证：切换为直连后，proxy-nodes 的 bindings 列表中不得残留该站点
    resp = authed_client.put(
        "/api/v1/admin/sites/fake/advanced",
        headers=ADMIN_HEADERS,
        json={"proxy_enabled": False, "proxy_node_id": ""},
    )
    assert resp.status_code == 200
    adv = resp.json()["data"]
    assert adv["proxy_enabled"] is False
    assert adv["proxy_node_id"] == ""

    # 验证 proxy-nodes 里的 bindings 绝对不再包含 fake 站点！
    resp = authed_client.get("/api/v1/admin/proxy-nodes", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    bindings = resp.json()["data"]["bindings"]
    assert "fake" not in bindings

    # 7. 测试内置 Xray 引擎状态查询端点
    resp = authed_client.get("/api/v1/admin/proxy-engine/status", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    engine_st = resp.json()["data"]
    assert "installed" in engine_st
    assert "running" in engine_st

    # 8. 清理：删除测试节点
    resp = authed_client.delete(f"/api/v1/admin/proxy-nodes/{node_id}", headers=ADMIN_HEADERS)
    assert resp.status_code == 200

