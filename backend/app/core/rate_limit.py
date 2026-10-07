"""轻量级内存滑动窗口限流器（无外部依赖，线程安全）。"""

import ipaddress
import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.core.errors import AppError, ErrorCode


class InMemoryRateLimiter:
    """基于时间戳双端队列的滑动窗口限流器。"""

    def __init__(self, limit: int = 5, window_seconds: int = 60, scope: str = "default") -> None:
        self.limit = limit
        self.window = window_seconds
        self.scope = scope
        self._records: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._last_cleanup = time.time()

    def check(self, key: str) -> None:
        now = time.time()
        with self._lock:
            # 每隔 120 秒自动清理过期 key，防内存泄露
            if now - self._last_cleanup > 120:
                self._cleanup(now)
                self._last_cleanup = now

            queue = self._records[key]
            cutoff = now - self.window
            while queue and queue[0] <= cutoff:
                queue.popleft()

            if len(queue) >= self.limit:
                retry_after = max(1, int(self.window - (now - queue[0])) + 1)
                raise AppError(
                    ErrorCode.RATE_LIMITED,
                    f"尝试过于频繁，请在 {retry_after} 秒后再试",
                )

            queue.append(now)

    def check_only(self, key: str) -> None:
        """只检查当前是否已被封锁，不增加计数（保护正常管理操作与防连续爆破）。"""
        now = time.time()
        with self._lock:
            queue = self._records.get(key)
            if not queue:
                return
            cutoff = now - self.window
            while queue and queue[0] <= cutoff:
                queue.popleft()
            if len(queue) >= self.limit:
                retry_after = max(1, int(self.window - (now - queue[0])) + 1)
                raise AppError(
                    ErrorCode.RATE_LIMITED,
                    f"连续失败过多，已被安全锁定，请在 {retry_after} 秒后再试",
                )

    def record_failure(self, key: str) -> None:
        """记录一次失败，并推进滑动窗口。"""
        now = time.time()
        with self._lock:
            queue = self._records[key]
            cutoff = now - self.window
            while queue and queue[0] <= cutoff:
                queue.popleft()
            queue.append(now)

    def _cleanup(self, now: float) -> None:
        cutoff = now - self.window
        stale_keys = [k for k, q in self._records.items() if not q or q[-1] <= cutoff]
        for k in stale_keys:
            del self._records[k]

    def reset(self) -> None:
        with self._lock:
            self._records.clear()


def _is_trusted_proxy_ip(host: str) -> bool:
    if host in ("127.0.0.1", "::1", "localhost", "testclient"):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_loopback or ip.is_private
    except ValueError:
        return False


def get_client_ip(request: Request) -> str:
    """获取请求来源真实 IP。
    当直连来源是受信任的本地回环或内网代理（如 Nginx、Docker 网桥、Traefik）时，
    优先取 x-real-ip 或 x-forwarded-for 首个真实客户端 IP，避免容器部署全站误连带限流或伪造穿透。
    """
    direct_host = request.client.host if request.client else "127.0.0.1"
    if _is_trusted_proxy_ip(direct_host):
        real_ip = request.headers.get("x-real-ip")
        if real_ip and real_ip.strip():
            return real_ip.strip()
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ips = [ip.strip() for ip in forwarded.split(",") if ip.strip()]
            if ips:
                return ips[0]
    return direct_host


class RateLimitGuard:
    """FastAPI 依赖包装器。"""

    def __init__(self, limit: int = 5, window_seconds: int = 60, scope: str = "default") -> None:
        self.limiter = InMemoryRateLimiter(limit, window_seconds, scope)

    @property
    def __globals__(self) -> dict:
        return globals()

    def __call__(
        self,
        request: Request,
        settings: Settings = Depends(get_settings),
    ) -> None:
        if not getattr(settings, "rate_limit_enabled", True):
            return
        ip = get_client_ip(request)
        key = f"{self.limiter.scope}:{ip}"
        try:
            self.limiter.check(key)
        except AppError as exc:
            if exc.code == ErrorCode.RATE_LIMITED:
                try:
                    from app.services.webhook_service import webhook_service

                    webhook_service.dispatch_event(
                        event_type="security_alert",
                        title="接口防刷与高频限流安全告警",
                        content=f"来源 IP [{ip}] 在接口范围「{self.limiter.scope}」触发高频访问限流拦截，疑似恶意探测或暴力猜解。",
                        fields={
                            "拦截范围": self.limiter.scope,
                            "来源 IP": ip,
                            "限制策略": f"{self.limiter.limit} 次 / {self.limiter.window} 秒",
                            "请求路径": request.url.path,
                            "处置策略": "自动拦截并返回 429 冷却",
                        },
                        sync=False,
                    )
                except Exception:
                    pass
            raise
