"""外部机器人与 Webhook 自动化推送服务测试。"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
from app.schemas.webhook import (
    CustomHttpConfig,
    EventSubscriptions,
    TelegramConfig,
    WebhookConfigPayload,
)
from app.services.webhook_service import WebhookService, TelegramRateLimiter


def test_telegram_rate_limiter():
    limiter = TelegramRateLimiter(rate=2.0, per=1.0)
    assert limiter.acquire() is True
    assert limiter.acquire() is True
    assert limiter.acquire() is False


def test_custom_http_ssrf_blocked(tmp_path):
    cfg_file = tmp_path / "webhook_config.json"
    service = WebhookService(config_path=cfg_file)

    unsafe_urls = [
        "http://127.0.0.1:8000/webhook",
        "http://localhost:3000/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::ffff:127.0.0.1]/test",
        "http://0.0.0.0:8080/",
    ]

    for u in unsafe_urls:
        cfg = CustomHttpConfig(enabled=True, url=u)
        res = service._send_custom_http(cfg, "test", "测试", "内容")
        assert res.ok is False
        assert res.error == "UNSAFE_URL"


def test_telegram_html_escape_and_truncation(tmp_path):
    cfg_file = tmp_path / "webhook_config.json"
    service = WebhookService(config_path=cfg_file)

    cfg = TelegramConfig(
        enabled=True,
        bot_token="fake_token",
        chat_id="fake_chat",
    )

    long_text = "A" * 5000
    captured_payload = {}

    def mock_post(url, json=None, **kwargs):
        nonlocal captured_payload
        captured_payload = json
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {"ok": True}
        return mock_resp

    with patch("httpx.Client.post", side_effect=mock_post):
        res = service._send_telegram(
            cfg,
            title="<危险标签 & 注入>",
            content=f"测试内容 <script>alert(1)</script> {long_text}",
            fields={"<Key & 特殊字符>": "<Val & 注入>"},
        )
        assert res.ok is True
        msg_text = captured_payload.get("text", "")
        # 断言已被 HTML 转义
        assert "<script>" not in msg_text
        assert "&lt;script&gt;" in msg_text
        assert "&lt;Key &amp; 特殊字符&gt;" in msg_text
        assert "&lt;Val &amp; 注入&gt;" in msg_text
        # 断言消息长度受到 4096 字符硬上限约束截断
        assert len(msg_text) <= 4096
        assert "内容已截断" in msg_text


def test_dispatch_event_subscription_filtering(tmp_path):
    cfg_file = tmp_path / "webhook_config.json"
    service = WebhookService(config_path=cfg_file)

    # 默认只订阅 circuit_break, code_activated, proxy_offline，未订阅 daily_report
    cfg = WebhookConfigPayload(
        events=EventSubscriptions(
            circuit_break=True,
            code_activated=False,
            proxy_offline=True,
            daily_report=False,
        )
    )
    service.save(cfg)

    # code_activated 未勾选订阅 -> 返回空列表，不投递
    res = service.dispatch_event("code_activated", "激活", "内容", sync=True)
    assert res == []

    # daily_report 未勾选订阅 -> 返回空列表，不投递
    res = service.dispatch_event("daily_report", "简报", "内容", sync=True)
    assert res == []


def test_dispatch_event_async_non_blocking(tmp_path):
    cfg_file = tmp_path / "webhook_config.json"
    service = WebhookService(config_path=cfg_file)

    cfg = WebhookConfigPayload(
        custom_http=CustomHttpConfig(
            enabled=True,
            url="https://httpbin.org/post",
        ),
        events=EventSubscriptions(circuit_break=True),
    )
    service.save(cfg)

    start = time.perf_counter()
    # 异步投递必须瞬时返回
    res = service.dispatch_event("circuit_break", "熔断", "内容", sync=False)
    duration = time.perf_counter() - start
    assert res == []
    assert duration < 0.1, f"dispatch_event 耗时 {duration}s，违反非阻塞异步要求"
