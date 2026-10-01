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
    assert "ai2048" in keys
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

