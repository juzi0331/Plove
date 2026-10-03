"""轻量级内存滑动窗口限流器（无外部依赖，线程安全）。"""

from __future__ import annotations

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

    def _cleanup(self, now: float) -> None:
        cutoff = now - self.window
        stale_keys = [k for k, q in self._records.items() if not q or q[-1] <= cutoff]
        for k in stale_keys:
            del self._records[k]

    def reset(self) -> None:
        with self._lock:
            self._records.clear()


def get_client_ip(request: Request) -> str:
    """获取请求来源 IP，优先兼容反向代理标头。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "127.0.0.1"


class RateLimitGuard:
    """FastAPI 依赖包装器。"""

    def __init__(self, limit: int = 5, window_seconds: int = 60, scope: str = "default") -> None:
        self.limiter = InMemoryRateLimiter(limit, window_seconds, scope)

    def __call__(
        self,
        request: Request,
        settings: Settings = Depends(get_settings),
    ) -> None:
        if not getattr(settings, "rate_limit_enabled", True):
            return
        ip = get_client_ip(request)
        key = f"{self.limiter.scope}:{ip}"
        self.limiter.check(key)
