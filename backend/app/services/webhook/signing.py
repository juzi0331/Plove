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
    """按优先级解析用于 Telegram API 调用的网络代理。
    
    支持:
    1. 用户添加的代理节点 ID (从代理节点池中自动映射其本地代理地址)
    2. 完整的 HTTP / SOCKS5 代理 URL (如 http://127.0.0.1:10809)
    3. 特殊标识 direct / none 直连
    4. 系统全局 proxy_config.json 中的默认代理配置
    5. 系统环境变量 (HTTPS_PROXY, HTTP_PROXY, ALL_PROXY 等)
    """
    if cfg_proxy and cfg_proxy.strip():
        val = cfg_proxy.strip()

        # 特殊直连标识
        if val.lower() in ("direct", "none", "null", "直连"):
            return None

        # 尝试匹配代理节点池中的节点 ID
        try:
            from app.services.proxy_node import proxy_node_service

            node = proxy_node_service.get_node(val)
            if node and node.get("proxy_url"):
                return str(node["proxy_url"]).strip()
        except Exception:
            pass

        # 如果已经是标准协议 URL
        if val.startswith(("http://", "https://", "socks5://", "socks5h://")):
            return val

        # 针对 127.0.0.1:10809 这种简写补充 http://
        if ":" in val:
            return f"http://{val}"

        return val

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
