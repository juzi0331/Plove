from fastapi.testclient import TestClient
from crawler.service.main import app

client = TestClient(app)


def test_health_check():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "crawler_service"


def test_list_rules():
    resp = client.get("/api/v1/rules")
    assert resp.status_code == 200
    envelope = resp.json()
    assert envelope["ok"] is True
    assert len(envelope["data"]) >= 2
    keys = [r["key"] for r in envelope["data"]]
    assert "huangguoai_com" in keys
    assert "maccms_demo" in keys


def test_rule_extractor_debugger():
    payload = {
        "sample_content": '<div class="film-title"><span class="name">大笑江湖</span></div>',
        "data_type": "html",
        "rule": {
            "type": "css",
            "selector": ".film-title .name",
            "strip": True,
        },
        "base_url": "https://example.com",
    }
    resp = client.post("/api/v1/rules/test", json=payload)
    assert resp.status_code == 200
    res = resp.json()
    assert res["ok"] is True
    assert res["data"]["extracted_value"] == "大笑江湖"


def test_smart_visual_taxonomy_and_code_generation():
    # Test prompt generation with custom categories tree and detail fields
    custom_categories = [
        {
            "type_id": "v",
            "type_name": "影片庫",
            "selected": True,
            "subcategories": [
                {"type_id": "国产", "type_name": "国产", "selected": True},
                {"type_id": "日韩", "type_name": "日韩", "selected": True}
            ]
        }
    ]
    custom_fields = [
        {"field_key": "vod_name", "field_label": "视频标题", "required": True, "selected": True},
        {"field_key": "vod_pic", "field_label": "封面海报", "required": True, "selected": True}
    ]
    prompt_resp = client.post(
        "/api/v1/smart/generate-prompt",
        json={
            "url": "https://example-test.com",
            "site_name": "测试站点",
            "site_key": "test_site",
            "categories_tree": custom_categories,
            "detail_fields": custom_fields
        }
    )
    assert prompt_resp.status_code == 200
    prompt_json = prompt_resp.json()
    assert prompt_json["ok"] is True
    prompt_text = prompt_json["data"]["prompt"]
    assert "影片庫" in prompt_text
    assert "vod_name" in prompt_text

    # Test code generation with custom visual taxonomy tree
    code_resp = client.post(
        "/api/v1/smart/generate-code",
        json={
            "url": "https://example-test.com",
            "site_name": "测试站点",
            "site_key": "test_site",
            "categories_tree": custom_categories,
            "detail_fields": custom_fields
        }
    )
    assert code_resp.status_code == 200
    code_json = code_resp.json()
    assert code_json["ok"] is True
    python_code = code_json["data"]["python_code"]
    assert "class TestSiteCrawler" in python_code or "NAME = " in python_code
    assert "影片庫" in python_code


def test_visual_proxy_injection():
    # 测试 visual-proxy 注入及参数校验
    resp = client.get("/api/v1/smart/visual-proxy?url=")
    assert resp.status_code == 400

    # 测试 HTML 注入逻辑与默认 pick 模式
    from crawler.service.api.routes_smart import _build_injected_visual_proxy_html
    raw_html = "<html><head><title>Demo</title></head><body><h1>Title</h1></body></html>"
    injected_pick = _build_injected_visual_proxy_html("https://example.com/page", raw_html, mode="pick")
    assert '<base href="https://example.com/page"/>' in injected_pick
    assert '__plove_inspect_overlay' in injected_pick
    assert '__plove_picker_installed' in injected_pick
    assert 'var currentMode = "pick";' in injected_pick
    assert 'findSimilarElements' in injected_pick
    assert 'isCtrlClick' in injected_pick

    # 测试 browse 自由浏览模式注入与状态维持
    injected_browse = _build_injected_visual_proxy_html("https://example.com/page2", raw_html, mode="browse")
    assert 'var currentMode = "browse";' in injected_browse
    assert 'PLOVE_PAGE_READY' in injected_browse


def test_dashboard_and_static_css_assets():
    resp = client.get("/")
    assert resp.status_code == 200
    assert '<link rel="stylesheet" href="/static/css/tokens.css">' in resp.text
    assert '<link rel="stylesheet" href="/static/css/base.css">' in resp.text
    assert '<link rel="stylesheet" href="/static/css/components.css">' in resp.text
    assert '<link rel="stylesheet" href="/static/css/visual-picker.css">' in resp.text

    for css in ["tokens.css", "base.css", "components.css", "visual-picker.css"]:
        css_resp = client.get(f"/static/css/{css}")
        assert css_resp.status_code == 200
        assert len(css_resp.text) > 100




