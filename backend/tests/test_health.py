"""健康检查 + 统一信封的集成测试。

顺带验证一个容易被忽略的点：**框架自己抛的 404 也必须走信封**，
否则前端就会遇到"有的错是 JSON、有的错是 HTML"。
"""

from __future__ import annotations

import json

import pytest
from jsonschema import Draft202012Validator

from app.core.config import get_settings
from app.core.middleware import REQUEST_ID_HEADER


def test_health_returns_envelope(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    body = response.json()
    assert body["ok"] is True
    assert body["error"] is None
    assert body["data"]["status"] == "ok"
    assert body["data"]["version"]
    assert len(body["request_id"]) >= 8


def test_request_id_is_shared_between_header_and_body(client):
    response = client.get("/api/v1/health")
    assert response.headers[REQUEST_ID_HEADER] == response.json()["request_id"]


def test_incoming_request_id_is_reused(client):
    """客户端自带 id 就沿用，方便跨端串联。"""
    response = client.get("/api/v1/health", headers={REQUEST_ID_HEADER: "abcdef0123456789"})
    assert response.json()["request_id"] == "abcdef0123456789"


def test_unknown_route_returns_failure_envelope(client):
    response = client.get("/api/v1/definitely-not-here")
    assert response.status_code == 404

    body = response.json()
    assert body["ok"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "NOT_FOUND"
    assert response.headers[REQUEST_ID_HEADER] == body["request_id"]


def test_health_body_matches_exported_contract(client):
    """拿导出的契约文件校验真实响应——这是"生成物"与"运行时"对齐的证据。"""
    path = get_settings().schemas_dir / "envelope.json"
    if not path.exists():
        pytest.skip("契约还没导出，先运行 python tools/export_contracts.py")

    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(client.get("/api/v1/health").json())
