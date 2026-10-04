"""外部机器人与 Webhook 自动化推送服务测试。"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
from app.schemas.webhook import (
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


def test_detect_telegram_chat(tmp_path):
    cfg_file = tmp_path / "webhook_config.json"
    service = WebhookService(config_path=cfg_file)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {
        "ok": True,
        "result": [
            {
                "update_id": 1001,
                "message": {
                    "message_id": 1,
                    "chat": {
                        "id": 123456789,
                        "type": "private",
                        "first_name": "AdminUser",
                        "username": "admin_tg",
                    },
                    "text": "/start",
                },
            }
        ],
    }

    with patch("httpx.Client.get", return_value=mock_resp):
        res = service.detect_telegram_chat("fake_token", "")
        assert res.ok is True
        assert res.chat_id == "123456789"
        assert res.chat_type == "private"
        assert res.username == "admin_tg"
        assert res.chat_title == "AdminUser"


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
        telegram=TelegramConfig(
            enabled=True,
            bot_token="fake_bot_token",
            chat_id="123456",
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


def test_admin_webhooks_api_verify_and_detect(authed_client):
    from app.api.deps import ADMIN_TOKEN_HEADER, get_settings
    admin_token = "test-admin-token"
    settings = authed_client.app.dependency_overrides[get_settings]()
    authed_client.app.dependency_overrides[get_settings] = lambda: settings.model_copy(
        update={"admin_token": admin_token}
    )
    headers = {ADMIN_TOKEN_HEADER: admin_token}

    # 1. 验证 verify 接口参数接收与正常回显
    mock_verify_resp = MagicMock()
    mock_verify_resp.status_code = 200
    mock_verify_resp.headers = {"content-type": "application/json"}
    mock_verify_resp.json.return_value = {
        "ok": True,
        "result": {
            "id": 123456789,
            "is_bot": True,
            "first_name": "TestBot",
            "username": "my_test_bot",
        },
    }

    mock_detect_resp = MagicMock()
    mock_detect_resp.status_code = 200
    mock_detect_resp.headers = {"content-type": "application/json"}
    mock_detect_resp.json.return_value = {
        "ok": True,
        "result": [
            {
                "update_id": 9999,
                "message": {
                    "chat": {
                        "id": 987654321,
                        "type": "private",
                        "first_name": "Owner",
                        "username": "owner_tg",
                    }
                },
            }
        ],
    }

    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value = mock_verify_resp
        resp = authed_client.post(
            "/api/v1/admin/webhooks/telegram/verify",
            json={"bot_token": "123456:ABC-DEF", "proxy_url": ""},
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["username"] == "my_test_bot"

        mock_get.return_value = mock_detect_resp
        resp = authed_client.post(
            "/api/v1/admin/webhooks/telegram/detect-chat",
            json={"bot_token": "123456:ABC-DEF", "proxy_url": ""},
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["chat_id"] == "987654321"
        assert body["data"]["chat_type"] == "private"


def test_telegram_rich_template_and_inline_keyboard():
    from app.services.webhook.templates import (
        build_telegram_reply_markup,
        format_telegram_message,
    )

    msg = format_telegram_message(
        title="内容源异常告警",
        content="上游连续 3 次超时",
        fields={"源站": "Jable", "耗时": "5000ms"},
        event_type="circuit_break",
    )
    # 验证富文本卡片特征
    assert "🚨" in msg
    assert "<b>【熔断告警】内容源异常告警</b>" in msg
    assert "<blockquote>上游连续 3 次超时</blockquote>" in msg
    assert "▫️ <b>源站：</b> <code>Jable</code>" in msg
    assert "Plove Watchdog" in msg

    # 验证 Inline Keyboard 生成
    markup = build_telegram_reply_markup("circuit_break", "http://localhost:4000")
    assert markup is not None
    assert "inline_keyboard" in markup
    buttons = markup["inline_keyboard"][0]
    assert any("内容源管理" in b["text"] for b in buttons)
    assert any("http://localhost:4000/_manage/crawlers" in b["url"] for b in buttons)

    # 验证空 URL 不生成 markup
    assert build_telegram_reply_markup("circuit_break", "") is None


def test_telegram_html_parse_error_auto_fallback(tmp_path):
    cfg_file = tmp_path / "webhook_config.json"
    service = WebhookService(config_path=cfg_file)

    cfg = TelegramConfig(
        enabled=True,
        bot_token="fake_bot_token",
        chat_id="123456",
    )

    call_count = 0

    def mock_post(url, json=None, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_resp = MagicMock()
        if call_count == 1:
            # 首次：模拟 HTML 解析失败
            mock_resp.status_code = 400
            mock_resp.headers = {"content-type": "application/json"}
            mock_resp.json.return_value = {
                "ok": False,
                "error_code": 400,
                "description": "Bad Request: can't parse entities in message text: ...",
            }
        else:
            # 二次重试降级纯文本：成功
            assert "parse_mode" not in json
            mock_resp.status_code = 200
            mock_resp.headers = {"content-type": "application/json"}
            mock_resp.json.return_value = {"ok": True}
        return mock_resp

    with patch("httpx.Client.post", side_effect=mock_post):
        res = service._send_telegram(cfg, "测试", "内容", event_type="circuit_break")
        assert res.ok is True
        assert call_count == 2
        assert "降级纯文本" in res.message
