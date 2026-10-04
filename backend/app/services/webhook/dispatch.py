"""外部机器人与 Webhook 自动化分发服务。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import html
import json
import logging
from pathlib import Path
import time
from typing import Any
import urllib.error
import urllib.request
import uuid

import httpx

from app.schemas.webhook import (
    TelegramConfig,
    TelegramDetectChatResult,
    TelegramVerifyResult,
    WebhookConfigPayload,
    WebhookDeliveryLogItem,
    WebhookTestResult,
)
from app.services.webhook.config import (
    DEFAULT_CONFIG_PATH,
    load_config,
    save_config,
)
from app.services.webhook.signing import (
    TelegramRateLimiter,
    _resolve_telegram_proxy,
)
from app.services.webhook.templates import (
    build_telegram_reply_markup,
    collect_daily_report_metrics,
    format_telegram_message,
)

logger = logging.getLogger(__name__)


class WebhookService:
    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self._config = WebhookConfigPayload()
        self._logs: list[WebhookDeliveryLogItem] = []
        self._max_logs = 50
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="webhook_worker")
        self._tg_limiter = TelegramRateLimiter(rate=20.0, per=60.0)
        self.load()

    def load(self) -> None:
        self._config = load_config(self.config_path)

    def save(self, payload: WebhookConfigPayload | None = None) -> None:
        if payload is not None:
            self._config = payload
        save_config(self.config_path, self._config)

    def get_config(self) -> WebhookConfigPayload:
        self.load()
        return self._config

    def _append_log(
        self,
        channel: str,
        event_type: str,
        title: str,
        status: str,
        status_code: int = 0,
        duration_ms: int = 0,
        error: str | None = None,
        summary: str = "",
    ) -> None:
        item = WebhookDeliveryLogItem(
            id=uuid.uuid4().hex[:12],
            channel=channel,
            event_type=event_type,
            title=title,
            status=status,
            status_code=status_code,
            duration_ms=duration_ms,
            error=error,
            sent_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            payload_summary=summary[:200],
        )
        self._logs.insert(0, item)
        if len(self._logs) > self._max_logs:
            self._logs = self._logs[: self._max_logs]

    def get_logs(self, limit: int = 30) -> list[WebhookDeliveryLogItem]:
        return self._logs[:limit]

    def clear_logs(self) -> None:
        self._logs.clear()

    # ------------------------------------------------------------------ 核心发送逻辑

    def send_to_channel(
        self,
        channel: str,
        event_type: str,
        title: str,
        content: str,
        fields: dict[str, Any] | None = None,
        raw_html: bool = False,
    ) -> WebhookTestResult:
        """针对指定通道进行单次推送投递。"""
        start = time.perf_counter()
        channel = channel.lower()
        cfg = self.get_config()

        try:
            if channel == "telegram":
                res = self._send_telegram(cfg.telegram, title, content, fields, event_type=event_type, raw_html=raw_html)
            else:
                return WebhookTestResult(
                    channel=channel,
                    ok=False,
                    status_code=400,
                    duration_ms=0,
                    message="未知的推送通道类型（目前仅支持 Telegram 机器人）",
                    error="INVALID_CHANNEL",
                )

            duration_ms = int((time.perf_counter() - start) * 1000)
            res.duration_ms = duration_ms

            self._append_log(
                channel=channel,
                event_type=event_type,
                title=title,
                status="success" if res.ok else "failed",
                status_code=res.status_code,
                duration_ms=duration_ms,
                error=res.error,
                summary=f"{title}: {content[:60]}",
            )
            return res

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            err_msg = str(exc)
            self._append_log(
                channel=channel,
                event_type=event_type,
                title=title,
                status="failed",
                status_code=500,
                duration_ms=duration_ms,
                error=err_msg,
                summary=f"{title}: {content[:60]}",
            )
            return WebhookTestResult(
                channel=channel,
                ok=False,
                status_code=500,
                duration_ms=duration_ms,
                message=f"投递异常: {err_msg}",
                error=err_msg,
            )

    def verify_telegram(self, bot_token: str, proxy_url: str = "") -> TelegramVerifyResult:
        """校验 Telegram Bot Token 并拉取 Bot 自身信息。"""
        token = bot_token.strip()
        if not token:
            return TelegramVerifyResult(ok=False, error="Bot Token 不能为空")

        url = f"https://api.telegram.org/bot{token}/getMe"
        proxy = _resolve_telegram_proxy(proxy_url)
        try:
            with httpx.Client(proxy=proxy, timeout=8.0) as client:
                resp = client.get(url)
                data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                if resp.status_code == 200 and data.get("ok"):
                    res = data.get("result", {})
                    if self._config.telegram.bot_token == token:
                        self._config.telegram.bot_username = res.get("username", "")
                        self._config.telegram.bot_name = res.get("first_name", "")
                        self.save()
                    return TelegramVerifyResult(
                        ok=True,
                        id=res.get("id", 0),
                        username=res.get("username", ""),
                        first_name=res.get("first_name", ""),
                    )
                err_desc = data.get("description") or f"HTTP {resp.status_code}"
                return TelegramVerifyResult(ok=False, error=f"Telegram API 拒绝: {err_desc}")
        except Exception as exc:
            return TelegramVerifyResult(ok=False, error=f"网络连接失败 (代理: {proxy or '直连'}): {exc}")

    def detect_telegram_chat(self, bot_token: str, proxy_url: str = "") -> TelegramDetectChatResult:
        """从 Telegram getUpdates 抓取最新与 Bot 互动的 Chat ID。"""
        token = bot_token.strip()
        if not token:
            return TelegramDetectChatResult(ok=False, error="Bot Token 不能为空")

        url = f"https://api.telegram.org/bot{token}/getUpdates?limit=10&offset=-10"
        proxy = _resolve_telegram_proxy(proxy_url)
        try:
            with httpx.Client(proxy=proxy, timeout=8.0) as client:
                resp = client.get(url)
                data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                if resp.status_code == 200 and data.get("ok"):
                    results = data.get("result", [])
                    if not results:
                        return TelegramDetectChatResult(
                            ok=False,
                            error="未检测到近期对话。请先在 Telegram 搜索该机器人并点击【Start】或发送一条任意消息（如 hi），稍等 2 秒后重试！",
                        )
                    for item in reversed(results):
                        chat = (
                            item.get("message")
                            or item.get("channel_post")
                            or item.get("my_chat_member")
                            or item.get("edited_message")
                            or {}
                        ).get("chat")
                        if chat and "id" in chat:
                            cid = str(chat["id"])
                            ctype = chat.get("type", "private")
                            title = chat.get("title") or chat.get("first_name") or chat.get("username") or ""
                            uname = chat.get("username") or ""
                            return TelegramDetectChatResult(
                                ok=True,
                                chat_id=cid,
                                chat_title=title,
                                username=uname,
                                chat_type=ctype,
                            )
                    return TelegramDetectChatResult(
                        ok=False,
                        error="对话记录中未解析到有效 Chat ID，请向机器人发送一条文本消息后重试",
                    )
                err_desc = data.get("description") or f"HTTP {resp.status_code}"
                return TelegramDetectChatResult(ok=False, error=f"Telegram API 拒绝: {err_desc}")
        except Exception as exc:
            return TelegramDetectChatResult(ok=False, error=f"网络连接失败 (代理: {proxy or '直连'}): {exc}")

    def _send_telegram(
        self,
        cfg: TelegramConfig,
        title: str,
        content: str,
        fields: dict[str, Any] | None = None,
        event_type: str = "",
        raw_html: bool = False,
    ) -> WebhookTestResult:
        if not cfg.bot_token or not cfg.chat_id:
            return WebhookTestResult(
                channel="telegram",
                ok=False,
                status_code=400,
                message="Telegram 未配置 Bot Token 或 Chat ID",
                error="MISSING_CREDENTIALS",
            )

        # 频率保护令牌桶
        if not self._tg_limiter.acquire():
            return WebhookTestResult(
                channel="telegram",
                ok=False,
                status_code=429,
                message="触发 Telegram 频率保护限制（上限 20条/分钟），消息已丢弃",
                error="RATE_LIMITED",
            )

        url = f"https://api.telegram.org/bot{cfg.bot_token.strip()}/sendMessage"
        is_html = raw_html or (event_type == "custom" and any(tag in content for tag in ("<b>", "<code>", "<i>", "<blockquote>", "<pre>", "<tg-spoiler>")))
        if is_html:
            text = content.strip()
            if fields:
                field_lines = [""]
                for k, v in fields.items():
                    field_lines.append(f"▫️ <b>{html.escape(str(k))}：</b> <code>{html.escape(str(v))}</code>")
                text += "\n" + "\n".join(field_lines)
        else:
            text = format_telegram_message(title, content, fields, event_type=event_type)

        payload: dict[str, Any] = {
            "chat_id": cfg.chat_id.strip(),
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        # 挂载快捷控制台 Inline 按钮
        reply_markup = build_telegram_reply_markup(event_type, cfg.console_url)
        if reply_markup:
            payload["reply_markup"] = reply_markup

        proxy = _resolve_telegram_proxy(cfg.proxy_url)
        start = time.perf_counter()

        max_retries = 3
        retry_delays = [1.0, 2.0]

        for attempt in range(max_retries):
            try:
                with httpx.Client(proxy=proxy, timeout=8.0) as client:
                    resp = client.post(url, json=payload)
                    duration_ms = int((time.perf_counter() - start) * 1000)
                    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}

                    if resp.status_code == 200 and data.get("ok", False):
                        return WebhookTestResult(
                            channel="telegram",
                            ok=True,
                            status_code=resp.status_code,
                            duration_ms=duration_ms,
                            message="Telegram 消息投递成功",
                        )

                    # 识别 429 速率限制并在安全范围内等待重试
                    if resp.status_code == 429:
                        retry_after = data.get("parameters", {}).get("retry_after", 1)
                        if attempt < max_retries - 1 and retry_after <= 5:
                            time.sleep(retry_after)
                            continue

                    # 5xx 服务端错误指数退避重试
                    if attempt < max_retries - 1 and resp.status_code >= 500:
                        time.sleep(retry_delays[attempt])
                        continue

                    err_msg = data.get("description") or f"HTTP {resp.status_code}"

                    # 若由于 HTML 格式解析异常（如特殊符号未闭合），自动降级为普通纯文本投递
                    if resp.status_code == 400 and "can't parse entities" in err_msg.lower():
                        logger.warning("Telegram HTML 解析异常，自动降级为纯文本重试: %s", err_msg)
                        try:
                            fallback_payload = dict(payload)
                            fallback_payload.pop("parse_mode", None)
                            fb_resp = client.post(url, json=fallback_payload)
                            if fb_resp.status_code == 200:
                                fb_data = fb_resp.json() if fb_resp.headers.get("content-type", "").startswith("application/json") else {}
                                if fb_data.get("ok", False):
                                    return WebhookTestResult(
                                        channel="telegram",
                                        ok=True,
                                        status_code=200,
                                        duration_ms=int((time.perf_counter() - start) * 1000),
                                        message="Telegram 消息投递成功（HTML降级纯文本）",
                                    )
                        except Exception as fb_exc:
                            logger.error("Telegram 纯文本降级投递异常: %s", fb_exc)

                    return WebhookTestResult(
                        channel="telegram",
                        ok=False,
                        status_code=resp.status_code,
                        duration_ms=duration_ms,
                        message=f"Telegram 投递失败: {err_msg}",
                        error=err_msg,
                    )
            except Exception as exc:
                if attempt < max_retries - 1:
                    time.sleep(retry_delays[attempt])
                    continue
                duration_ms = int((time.perf_counter() - start) * 1000)
                return WebhookTestResult(
                    channel="telegram",
                    ok=False,
                    status_code=500,
                    duration_ms=duration_ms,
                    message=f"网络连接失败 (代理: {proxy or '直连'}): {exc}",
                    error=str(exc),
                )

        return WebhookTestResult(
            channel="telegram",
            ok=False,
            status_code=500,
            duration_ms=int((time.perf_counter() - start) * 1000),
            message="Telegram 投递重试超限失败",
            error="MAX_RETRIES_EXCEEDED",
        )

    # ------------------------------------------------------------------ 广播与告警接口

    def _do_dispatch(
        self,
        event_type: str,
        title: str,
        content: str,
        fields: dict[str, Any] | None = None,
    ) -> list[WebhookTestResult]:
        cfg = self.get_config()
        events = cfg.events

        # 校验 8 大事件类型的订阅开关
        if event_type == "circuit_break" and not events.circuit_break:
            return []
        if event_type == "circuit_recover" and not events.circuit_recover:
            return []
        if event_type == "site_health_report" and not events.site_health_report:
            return []
        if event_type == "code_activated" and not events.code_activated:
            return []
        if event_type == "device_conflict" and not events.device_conflict:
            return []
        if event_type == "security_alert" and not events.security_alert:
            return []
        if event_type == "proxy_offline" and not events.proxy_offline:
            return []
        if event_type == "daily_report" and not events.daily_report:
            return []
        if event_type == "system_startup" and not events.system_startup:
            return []

        results = []
        if cfg.telegram.enabled:
            results.append(self.send_to_channel("telegram", event_type, title, content, fields))
        return results

    def dispatch_event(
        self,
        event_type: str,
        title: str,
        content: str,
        fields: dict[str, Any] | None = None,
        sync: bool = False,
    ) -> list[WebhookTestResult]:
        """按订阅规则向所有已启用通道分发事件通知。
        
        默认通过内部线程池异步投递，绝对不阻塞业务主线程；显式指定 sync=True 时同步等待结果。
        """
        if sync:
            return self._do_dispatch(event_type, title, content, fields)

        def _async_worker():
            try:
                self._do_dispatch(event_type, title, content, fields)
            except Exception as exc:
                logger.error("异步投递 Webhook 事件 [%s] 异常: %s", event_type, exc)

        self._executor.submit(_async_worker)
        return []

    def send_daily_report(self) -> list[WebhookTestResult]:
        """收集系统统计指标并发送每日运营简报。"""
        title, content, fields = collect_daily_report_metrics()
        return self.dispatch_event(
            event_type="daily_report",
            title=title,
            content=content,
            fields=fields,
            sync=False,
        )


# 单例服务
webhook_service = WebhookService()
