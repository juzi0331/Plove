"""外部机器人与 Webhook 自动化分发服务。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import logging
from pathlib import Path
import time
from typing import Any
import urllib.error
import urllib.request
import uuid

import httpx

from app.core.security import is_safe_public_url
from app.schemas.webhook import (
    CustomHttpConfig,
    FeishuConfig,
    TelegramConfig,
    TelegramVerifyResult,
    WeChatWorkConfig,
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
    generate_feishu_sign,
)
from app.services.webhook.templates import (
    collect_daily_report_metrics,
    format_custom_http_payload,
    format_feishu_content,
    format_telegram_message,
    format_wechat_markdown,
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
    ) -> WebhookTestResult:
        """针对指定通道进行单次推送投递。"""
        start = time.perf_counter()
        channel = channel.lower()
        cfg = self.get_config()

        try:
            if channel == "telegram":
                res = self._send_telegram(cfg.telegram, title, content, fields)
            elif channel == "wechat_work":
                res = self._send_wechat(cfg.wechat_work, title, content, fields)
            elif channel == "feishu":
                res = self._send_feishu(cfg.feishu, title, content, fields)
            elif channel == "custom_http":
                res = self._send_custom_http(cfg.custom_http, event_type, title, content, fields)
            else:
                return WebhookTestResult(
                    channel=channel,
                    ok=False,
                    status_code=400,
                    duration_ms=0,
                    message="未知的推送通道类型",
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

    def _send_telegram(
        self,
        cfg: TelegramConfig,
        title: str,
        content: str,
        fields: dict[str, Any] | None = None,
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
        text = format_telegram_message(title, content, fields)

        payload = {
            "chat_id": cfg.chat_id.strip(),
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

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

    def _send_wechat(
        self,
        cfg: WeChatWorkConfig,
        title: str,
        content: str,
        fields: dict[str, Any] | None = None,
    ) -> WebhookTestResult:
        if not cfg.webhook_url or not cfg.webhook_url.startswith("http"):
            return WebhookTestResult(
                channel="wechat_work",
                ok=False,
                status_code=400,
                message="企业微信群机器人 Webhook 地址不合法",
                error="INVALID_WEBHOOK_URL",
            )

        if not is_safe_public_url(cfg.webhook_url):
            return WebhookTestResult(
                channel="wechat_work",
                ok=False,
                status_code=400,
                message="企业微信 Webhook 目标地址不合法或指向受限内网",
                error="UNSAFE_URL",
            )

        md = format_wechat_markdown(title, content, fields)
        payload = {
            "msgtype": "markdown",
            "markdown": {"content": md},
        }
        return self._http_post(cfg.webhook_url, payload, channel="wechat_work")

    def _send_feishu(
        self,
        cfg: FeishuConfig,
        title: str,
        content: str,
        fields: dict[str, Any] | None = None,
    ) -> WebhookTestResult:
        if not cfg.webhook_url or not cfg.webhook_url.startswith("http"):
            return WebhookTestResult(
                channel="feishu",
                ok=False,
                status_code=400,
                message="飞书群机器人 Webhook 地址不合法",
                error="INVALID_WEBHOOK_URL",
            )

        if not is_safe_public_url(cfg.webhook_url):
            return WebhookTestResult(
                channel="feishu",
                ok=False,
                status_code=400,
                message="飞书 Webhook 目标地址不合法或指向受限内网",
                error="UNSAFE_URL",
            )

        text = format_feishu_content(title, content, fields)
        payload: dict[str, Any] = {
            "msg_type": "text",
            "content": {"text": text},
        }

        # 飞书签名校验
        if cfg.secret:
            timestamp, sign = generate_feishu_sign(cfg.secret)
            payload["timestamp"] = timestamp
            payload["sign"] = sign

        return self._http_post(cfg.webhook_url, payload, channel="feishu")

    def _send_custom_http(
        self,
        cfg: CustomHttpConfig,
        event_type: str,
        title: str,
        content: str,
        fields: dict[str, Any] | None = None,
    ) -> WebhookTestResult:
        if not cfg.url or not cfg.url.startswith("http"):
            return WebhookTestResult(
                channel="custom_http",
                ok=False,
                status_code=400,
                message="自定义 HTTP Webhook 地址未配置或不合法",
                error="INVALID_URL",
            )

        # 严格防御针对云元数据、本地回环或内网端口的 SSRF
        if not is_safe_public_url(cfg.url):
            return WebhookTestResult(
                channel="custom_http",
                ok=False,
                status_code=400,
                message="目标地址不合法或指向内网受限网段",
                error="UNSAFE_URL",
            )

        payload = format_custom_http_payload(event_type, title, content, fields)
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Plove-Webhook-Dispatcher/1.0",
        }
        if cfg.secret_token:
            headers["X-Plove-Token"] = cfg.secret_token

        return self._http_post(cfg.url, payload, headers=headers, channel="custom_http")

    def _http_post(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
        channel: str = "",
    ) -> WebhookTestResult:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req_headers = {"Content-Type": "application/json"}
        if headers:
            req_headers.update(headers)

        req = urllib.request.Request(url, data=data, headers=req_headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                status = resp.status
                ok = 200 <= status < 300
                return WebhookTestResult(
                    channel=channel,
                    ok=ok,
                    status_code=status,
                    message="投递成功" if ok else f"远端响应状态码 {status}",
                )
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            return WebhookTestResult(
                channel=channel,
                ok=False,
                status_code=exc.code,
                message=f"HTTP 错误 {exc.code}: {exc.reason}",
                error=err_body[:200] or str(exc),
            )
        except Exception as exc:
            return WebhookTestResult(
                channel=channel,
                ok=False,
                status_code=0,
                message=f"网络请求失败: {exc}",
                error=str(exc),
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

        # 校验各事件类型的订阅开关
        if event_type == "circuit_break" and not events.circuit_break:
            return []
        if event_type == "code_activated" and not events.code_activated:
            return []
        if event_type == "proxy_offline" and not events.proxy_offline:
            return []
        if event_type == "daily_report" and not events.daily_report:
            return []

        results = []
        if cfg.telegram.enabled:
            results.append(self.send_to_channel("telegram", event_type, title, content, fields))
        if cfg.wechat_work.enabled:
            results.append(self.send_to_channel("wechat_work", event_type, title, content, fields))
        if cfg.feishu.enabled:
            results.append(self.send_to_channel("feishu", event_type, title, content, fields))
        if cfg.custom_http.enabled:
            results.append(self.send_to_channel("custom_http", event_type, title, content, fields))
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
