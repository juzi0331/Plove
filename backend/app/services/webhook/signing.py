"""Webhook 鉴权签名与速率限制器。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
import time


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


def generate_feishu_sign(secret: str, timestamp: str | None = None) -> tuple[str, str]:
    """生成飞书群机器人签名与对应时间戳。"""
    ts = timestamp or str(int(time.time()))
    string_to_sign = f"{ts}\n{secret}"
    hmac_code = hmac.new(
        string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
    ).digest()
    sign = base64.b64encode(hmac_code).decode("utf-8")
    return ts, sign
