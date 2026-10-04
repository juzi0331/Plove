"""外部机器人与 Webhook 自动化推送服务。

支持：
1. Telegram 机器人 (sendMessage API，含 HTML 转义、4096 字符截断、429 规避与指数重试)
2. 企业微信群机器人 (Markdown 消息，含 SSRF 校验)
3. 飞书自定义群机器人 (支持签名校验或纯文本/卡片，含 SSRF 校验)
4. 自定义 HTTP POST Webhook (带 X-Plove-Token 校验与严格 SSRF 校验)
5. 异步线程池投递，绝不阻塞主业务与 API 响应；
6. 自动记录投递日志（内存保留最近 50 条）。
"""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import html
import hmac
import json
import logging
import os
from pathlib import Path
import threading
import time
from typing import Any
import urllib.error
import urllib.request
import uuid

import httpx

from app.core.security import is_safe_public_url
from app.schemas.webhook import (
    CustomHttpConfig,
    EventSubscriptions,
    FeishuConfig,
    TelegramConfig,
    TelegramVerifyResult,
    WeChatWorkConfig,
    WebhookConfigPayload,
    WebhookDeliveryLogItem,
    WebhookTestResult,
)

logger = logging.getLogger(__name__)


def _get_default_config_path() -> Path:
    backend_root = Path(__file__).resolve().parent.parent.parent
    data_dir = backend_root / "data"
    data_candidate = data_dir / "webhook_config.json"
    if data_candidate.is_file():
        return data_candidate
    legacy_candidate = backend_root / "webhook_config.json"
    if legacy_candidate.is_file():
        return legacy_candidate
    return data_candidate


DEFAULT_CONFIG_PATH = _get_default_config_path()


class TelegramRateLimiter:
    """Telegram 群组消息频率限制令牌桶（约 20 条/分钟）。"""

    def __init__(self, rate: float = 20.0, per: float = 60.0) -> None:
        self.capacity = rate
        self.tokens = rate
        self.rate = rate / per
        self.last = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self) -> bool:
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last
            self.last = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            return False


def _resolve_telegram_proxy(cfg_proxy: str | None = None) -> str | None:
    """按优先级解析用于 Telegram API 调用的网络代理。"""
    if cfg_proxy and cfg_proxy.strip():
        return cfg_proxy.strip()

    # 自动探测项目 proxy_config.json 中的默认代理
    try:
        from app.services.proxy_node import get_proxy_config_path

        cfg_path = get_proxy_config_path()
        if cfg_path.is_file():
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            p = data.get("default_proxy_url") or data.get("proxy_url")
            if p and str(p).startswith("http"):
                return str(p).strip()
    except Exception:
        pass

    # 探测环境变量
    for env_k in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY"):
        val = os.environ.get(env_k)
        if val and (val.startswith("http://") or val.startswith("socks5://")):
            return val.strip()

    return None


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
        if self.config_path.is_file():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                self._config = WebhookConfigPayload.model_validate(data)
            except Exception as exc:
                logger.warning("读取 Webhook 配置文件失败: %s", exc)

        # 环境变量加固覆盖（敏感凭据优先走环境变量）
        if env_tg_token := os.environ.get("PLOVE_TELEGRAM_BOT_TOKEN"):
            self._config.telegram.bot_token = env_tg_token.strip()
        if env_tg_chat := os.environ.get("PLOVE_TELEGRAM_CHAT_ID"):
            self._config.telegram.chat_id = env_tg_chat.strip()
        if env_tg_proxy := os.environ.get("PLOVE_TELEGRAM_PROXY_URL"):
            self._config.telegram.proxy_url = env_tg_proxy.strip()
        if env_wechat := os.environ.get("PLOVE_WECHAT_WEBHOOK_URL"):
            self._config.wechat_work.webhook_url = env_wechat.strip()
        if env_feishu_url := os.environ.get("PLOVE_FEISHU_WEBHOOK_URL"):
            self._config.feishu.webhook_url = env_feishu_url.strip()
        if env_feishu_sec := os.environ.get("PLOVE_FEISHU_SECRET"):
            self._config.feishu.secret = env_feishu_sec.strip()
        if env_custom_url := os.environ.get("PLOVE_CUSTOM_HTTP_URL"):
            self._config.custom_http.url = env_custom_url.strip()
        if env_custom_token := os.environ.get("PLOVE_CUSTOM_HTTP_TOKEN"):
            self._config.custom_http.secret_token = env_custom_token.strip()

    def save(self, payload: WebhookConfigPayload | None = None) -> None:
        if payload is not None:
            self._config = payload
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(
                json.dumps(self._config.model_dump(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("保存 Webhook 配置文件失败: %s", exc)

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

        # HTML 转义防护与格式化构造
        esc_title = html.escape(title)
        esc_content = html.escape(content)
        lines = [f"<b>[Plove 监控通知] {esc_title}</b>", "", esc_content]
        if fields:
            lines.append("")
            for k, v in fields.items():
                lines.append(f"• <b>{html.escape(str(k))}</b>: <code>{html.escape(str(v))}</code>")
        lines.append(f"\n<i>时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>")
        text = "\n".join(lines)

        # Telegram 4096 字符上限拦截与截断
        if len(text) > 4000:
            budget = 4000 - (len(text) - len(esc_content)) - 35
            if budget > 50:
                esc_content = esc_content[:budget] + "...\n<i>(内容已截断)</i>"
            else:
                esc_content = esc_content[:50] + "..."
            lines[2] = esc_content
            text = "\n".join(lines)[:4090]

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

        md = f"### [Plove 监控告警] {title}\n>{content}\n\n"
        if fields:
            for k, v in fields.items():
                md += f">**{k}**: <font color=\"comment\">{v}</font>\n"
        md += f"\n>推送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

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

        text_lines = [f"【Plove 告警通知】{title}", "", content]
        if fields:
            text_lines.append("")
            for k, v in fields.items():
                text_lines.append(f"{k}: {v}")
        text_lines.append(f"\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        payload: dict[str, Any] = {
            "msg_type": "text",
            "content": {"text": "\n".join(text_lines)},
        }

        # 飞书签名校验
        if cfg.secret:
            timestamp = str(int(time.time()))
            string_to_sign = f"{timestamp}\n{cfg.secret}"
            hmac_code = hmac.new(
                string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
            ).digest()
            sign = base64.b64encode(hmac_code).decode("utf-8")
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

        payload = {
            "event": event_type,
            "title": title,
            "content": content,
            "fields": fields or {},
            "timestamp": int(time.time()),
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
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
        try:
            from app.db.session import session_scope
            from app.models.activation import ActivationCode, Device
            from app.models.site_setting import SiteSetting
            from sqlalchemy import func, select

            with session_scope() as session:
                total_codes = session.scalar(select(func.count(ActivationCode.id))) or 0
                activated_codes = (
                    session.scalar(
                        select(func.count(ActivationCode.id)).where(ActivationCode.activated_at.is_not(None))
                    )
                    or 0
                )
                active_devices = session.scalar(select(func.count(Device.id))) or 0
                total_sites = session.scalar(select(func.count(SiteSetting.key))) or 0
                enabled_sites = (
                    session.scalar(select(func.count(SiteSetting.key)).where(SiteSetting.enabled.is_(True)))
                    or 0
                )
        except Exception as exc:
            logger.warning("每日简报收集数据库指标失败: %s", exc)
            total_codes = activated_codes = active_devices = total_sites = enabled_sites = 0

        return self.dispatch_event(
            event_type="daily_report",
            title="Plove 每日运行简报",
            content=f"系统状态正常。激活码累计 {total_codes} 个（已激活 {activated_codes} 个），当前绑定设备 {active_devices} 台，聚合内容源 {enabled_sites}/{total_sites} 已启用。",
            fields={
                "激活码总数": total_codes,
                "已激活数量": activated_codes,
                "绑定设备数": active_devices,
                "可用内容源": f"{enabled_sites}/{total_sites}",
                "简报生成时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            sync=False,
        )


# 单例服务
webhook_service = WebhookService()
