"""安全审计修复专项测试集。

覆盖：
1. S1: 代理接口鉴权（未授权 401，已激活设备或管理员放行）
2. S2: 弱管理员口令拦截
3. S3: 激活码暴力破解速率限制
4. H1: 生产环境文档关停
5. H2: 生产环境健康检查信息脱敏
6. B6: 安全响应头注入
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import ADMIN_TOKEN_HEADER, DEVICE_TOKEN_HEADER, get_settings
from app.core.config import Settings
from app.main import create_app
from app.services import activation_service


def test_proxy_endpoints_reject_unauthenticated(anon_client):
    """S1: 未携带凭证直接调用代理接口必须返回 401 UNAUTHORIZED。"""
    test_urls = [
        "/api/v1/proxy/image?url=https://example.com/test.jpg",
        "/api/v1/proxy/stream/m3u8?url=https://example.com/index.m3u8",
        "/api/v1/proxy/stream/segment?url=https://example.com/001.ts",
        "/api/v1/proxy/stream/key?url=https://example.com/enc.key",
    ]
    for url in test_urls:
        resp = anon_client.get(url)
        assert resp.status_code == 401, f"{url} 应当被 401 拦截"
        assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_proxy_endpoints_allow_active_device(anon_client, activation):
    """S1: 携带有效设备令牌允许访问代理接口。"""
    dev_token = activation["token"]

    # 1. 通过请求头携带
    resp = anon_client.get(
        "/api/v1/proxy/image?url=https://127.0.0.1/bad.jpg",
        headers={DEVICE_TOKEN_HEADER: dev_token},
    )
    # 鉴权通过，进入下游逻辑（由于 127.0.0.1 被 SSRF 拦截返回 502/错误，但绝对不是 401）
    assert resp.status_code != 401

    # 2. 通过 URL 参数 token 携带（兼容 img 与媒体分片）
    resp2 = anon_client.get(
        f"/api/v1/proxy/image?url=https://127.0.0.1/bad.jpg&token={dev_token}"
    )
    assert resp2.status_code != 401


def test_proxy_endpoints_allow_admin(authed_client, fake_app):
    """S1: 管理员凭证也可访问代理接口。"""
    settings = fake_app.dependency_overrides[get_settings]()
    fake_app.dependency_overrides[get_settings] = lambda: settings.model_copy(
        update={"admin_token": "valid-admin-secret-token"}
    )
    resp = authed_client.get(
        "/api/v1/proxy/image?url=https://127.0.0.1/bad.jpg",
        headers={ADMIN_TOKEN_HEADER: "valid-admin-secret-token"},
    )
    assert resp.status_code != 401


def test_weak_admin_token_is_blocked(authed_client, fake_app):
    """S2: 弱口令如 admin / 123456 在鉴权层直接被拒绝（403）。"""
    settings = fake_app.dependency_overrides[get_settings]()
    fake_app.dependency_overrides[get_settings] = lambda: settings.model_copy(
        update={"admin_token": "admin"}
    )
    resp = authed_client.get(
        "/api/v1/admin/status",
        headers={ADMIN_TOKEN_HEADER: "admin"},
    )
    assert resp.status_code == 403
    assert "过于简单" in resp.json()["error"]["message"]


def test_redeem_rate_limiter_blocks_rapid_attempts(anon_client, fake_app):
    """S3: 激活码高频尝试触发 429 限流保护。"""
    settings = fake_app.dependency_overrides[get_settings]()
    fake_app.dependency_overrides[get_settings] = lambda: settings.model_copy(
        update={"rate_limit_enabled": True}
    )

    # 允许连续 5 次，第 6 次触发 429
    blocked = False
    for _ in range(8):
        resp = anon_client.post("/api/v1/activation/redeem", json={"code": "PLV-INVALID-TEST"})
        if resp.status_code == 429:
            blocked = True
            assert resp.json()["error"]["code"] == "RATE_LIMITED"
            break
    assert blocked is True, "高频激活请求必须触发 429 速率限制"


def test_security_headers_injected(anon_client):
    """B6: 每一个响应都必须包含安全防护响应头。"""
    resp = anon_client.get("/api/v1/health")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_health_and_docs_in_production_mode():
    """H1 & H2 & SEC-08: 生产环境下脱敏健康检查、关闭 /docs 并彻底禁用 /portal。"""
    import os
    from unittest.mock import patch
    from app.core.config import get_settings

    prod_env = {
        "PLOVE_ENV": "prod",
        "PLOVE_DATABASE_URL": "sqlite:///:memory:",
        "PLOVE_SECRET_KEY": "super-secure-production-secret-key-32bytes",
    }
    with patch.dict(os.environ, prod_env):
        get_settings.cache_clear()
        try:
            prod_app = create_app()
            client = TestClient(prod_app)
            resp = client.get("/api/v1/health")
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["env"] == "production"
            assert data["version"] == "*"

            # H1: 验证生产环境彻底关闭 Swagger 文档
            docs_resp = client.get("/docs")
            assert docs_resp.status_code == 404

            # SEC-08: 验证生产环境彻底禁用 Portal
            portal_resp = client.get("/portal")
            assert portal_resp.status_code == 404
        finally:
            get_settings.cache_clear()


def test_production_rejects_default_secret_key():
    """SEC-06: 生产环境下如果使用默认或过短 secret_key 必须拒绝启动。"""
    import os
    from unittest.mock import patch
    from pydantic import ValidationError
    from app.core.config import get_settings, Settings

    prod_env = {
        "PLOVE_ENV": "prod",
        "PLOVE_DATABASE_URL": "sqlite:///:memory:",
    }
    with patch.dict(os.environ, prod_env):
        get_settings.cache_clear()
        try:
            with pytest.raises(ValidationError) as exc:
                Settings()
            assert "PLOVE_SECRET_KEY" in str(exc.value)
        finally:
            get_settings.cache_clear()


def test_admin_brute_force_protection(anon_client, fake_app):
    """SEC-04: 后台管理接口连续 10 次错误口令尝试触发 429 锁定。"""
    settings = fake_app.dependency_overrides[get_settings]()
    fake_app.dependency_overrides[get_settings] = lambda: settings.model_copy(
        update={"admin_token": "valid-secret-token-32bytes!!", "rate_limit_enabled": True}
    )

    # 连续尝试 10 次错误口令
    for _ in range(10):
        resp = anon_client.get(
            "/api/v1/admin/status",
            headers={ADMIN_TOKEN_HEADER: "wrong-guess"},
        )
        assert resp.status_code == 401

    # 第 11 次尝试触发 429 RATE_LIMITED
    locked_resp = anon_client.get(
        "/api/v1/admin/status",
        headers={ADMIN_TOKEN_HEADER: "wrong-guess"},
    )
    assert locked_resp.status_code == 429
    assert locked_resp.json()["error"]["code"] == "RATE_LIMITED"
