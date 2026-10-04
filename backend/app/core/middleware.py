"""请求级 ``request_id``。

每个请求分配一个 id，做两件事：写进 ``request.state``（供信封使用），
回写响应头 ``X-Request-Id``（供前端上报问题时带上）。

这样排查问题时，一个 id 能从网关日志一路串到爬虫的 stderr。
"""

from __future__ import annotations

import time
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.system_service import get_maintenance_message, is_maintenance_active

REQUEST_ID_HEADER = "X-Request-Id"


def new_request_id() -> str:
    return uuid4().hex


def get_request_id(request: Request) -> str:
    """取当前请求的 request_id。中间件已写入；兜底再生成一个（测试直接调时用）。"""
    return getattr(request.state, "request_id", None) or new_request_id()


class RequestIdMiddleware(BaseHTTPMiddleware):
    """客户端带了 ``X-Request-Id`` 就沿用，方便跨端串联；没带就生成。
    同时注入 X-Response-Time-Ms 耗时与 X-Cache 状态，并在全站开启维护时拦截非管理端请求。
    """

    async def dispatch(self, request: Request, call_next):
        t0 = time.perf_counter()
        request_id = request.headers.get(REQUEST_ID_HEADER) or new_request_id()
        request.state.request_id = request_id

        # 维护模式拦截：仅允许管理端、全站运行状态与图标在开启维护时访问
        path = request.url.path
        if is_maintenance_active():
            is_exempt = (
                path.startswith("/api/v1/admin")
                or path.startswith("/api/v1/system/status")
                or path == "/favicon.ico"
            )
            if not is_exempt:
                msg = get_maintenance_message()
                return JSONResponse(
                    status_code=503,
                    headers={REQUEST_ID_HEADER: request_id},
                    content={
                        "error": {
                            "code": "SERVER_MAINTENANCE",
                            "message": msg,
                            "details": {"maintenance": True},
                        },
                        "request_id": request_id,
                    },
                )

        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers["X-Response-Time-Ms"] = str(elapsed_ms)

        # 注入安全响应头 (防嗅探、防点击劫持、跨域安全)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 注入缓存状态（若服务层有记录）
        cache_status = getattr(request.state, "cache_status", None)
        if cache_status:
            response.headers["X-Cache"] = cache_status

        return response

