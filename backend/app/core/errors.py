"""统一错误码与异常。

错误码分两类：

* **上游错误**（爬虫给的）一律映射成 ``UPSTREAM_*``。前端因此不需要知道
  爬虫长什么样，也不需要认识爬虫那套 ``TIMEOUT`` / ``BLOCKED``；
* **本端错误**（参数、鉴权、限流、激活码）各用各的码。

映射集中在 :data:`CRAWLER_CODE_MAP`。测试会**直接读爬虫那侧的码表**比对，
任何一边新增错误码而另一边没跟上，测试立刻红——这是防两端漂移的关键一条。
"""

from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    """对外暴露的全部错误码。加新码时记得补 :data:`HTTP_STATUS`。"""

    # ---- 上游（爬虫）----
    UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"
    UPSTREAM_HTTP_ERROR = "UPSTREAM_HTTP_ERROR"
    UPSTREAM_PARSE_ERROR = "UPSTREAM_PARSE_ERROR"
    UPSTREAM_BLOCKED = "UPSTREAM_BLOCKED"
    UPSTREAM_UNKNOWN = "UPSTREAM_UNKNOWN"
    #: 该源的并发槽位排满了，排队也等不到（我们这边的容量，不是源站拒我们）
    UPSTREAM_BUSY = "UPSTREAM_BUSY"
    #: 该源连续失败已熔断，正在冷却（或正在探测恢复）。**立刻返回，不碰源站**
    UPSTREAM_CIRCUIT_OPEN = "UPSTREAM_CIRCUIT_OPEN"

    # ---- 通用 ----
    NOT_FOUND = "NOT_FOUND"
    UNSUPPORTED = "UNSUPPORTED"
    #: 这个源被后台停用了。**必须和 NOT_FOUND 分开** ——
    #: "这个源不存在"与"这个源被我们主动关掉了"对用户和处理方式都不同，
    #: 混成一个码就等于把运维动作伪装成源站故障。
    SITE_DISABLED = "SITE_DISABLED"
    BAD_REQUEST = "BAD_REQUEST"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    RATE_LIMITED = "RATE_LIMITED"

    # ---- 业务：激活码 / 单会话 ----
    ACTIVATION_INVALID = "ACTIVATION_INVALID"
    ACTIVATION_EXPIRED = "ACTIVATION_EXPIRED"
    SESSION_KICKED = "SESSION_KICKED"

    # ---- 兜底 ----
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    INTERNAL = "INTERNAL"


#: 错误码 -> HTTP 状态码
HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.UPSTREAM_TIMEOUT: 504,
    ErrorCode.UPSTREAM_HTTP_ERROR: 502,
    ErrorCode.UPSTREAM_PARSE_ERROR: 502,
    ErrorCode.UPSTREAM_BLOCKED: 503,
    ErrorCode.UPSTREAM_UNKNOWN: 502,
    ErrorCode.UPSTREAM_BUSY: 503,
    ErrorCode.UPSTREAM_CIRCUIT_OPEN: 503,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.UNSUPPORTED: 501,
    ErrorCode.SITE_DISABLED: 503,
    ErrorCode.BAD_REQUEST: 400,
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.ACTIVATION_INVALID: 403,
    ErrorCode.ACTIVATION_EXPIRED: 403,
    ErrorCode.SESSION_KICKED: 409,
    ErrorCode.NOT_IMPLEMENTED: 501,
    ErrorCode.INTERNAL: 500,
}

#: HTTP 状态码 -> 错误码（处理框架自己抛出的 HTTPException 时用）
STATUS_TO_CODE: dict[int, ErrorCode] = {
    400: ErrorCode.BAD_REQUEST,
    401: ErrorCode.UNAUTHORIZED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.BAD_REQUEST,
    409: ErrorCode.SESSION_KICKED,
    422: ErrorCode.VALIDATION_ERROR,
    429: ErrorCode.RATE_LIMITED,
    501: ErrorCode.NOT_IMPLEMENTED,
    502: ErrorCode.UPSTREAM_UNKNOWN,
    503: ErrorCode.UPSTREAM_BLOCKED,
    504: ErrorCode.UPSTREAM_TIMEOUT,
}

#: 爬虫信封里的错误码 -> 本端错误码
#: 与 ``crawler/crawler_kit/errors.py`` 的 ``CODES`` 一一对应
CRAWLER_CODE_MAP: dict[str, ErrorCode] = {
    "TIMEOUT": ErrorCode.UPSTREAM_TIMEOUT,
    "HTTP_ERROR": ErrorCode.UPSTREAM_HTTP_ERROR,
    "PARSE_ERROR": ErrorCode.UPSTREAM_PARSE_ERROR,
    "BLOCKED": ErrorCode.UPSTREAM_BLOCKED,
    "NOT_FOUND": ErrorCode.NOT_FOUND,
    "UNSUPPORTED": ErrorCode.UNSUPPORTED,
    "UNKNOWN": ErrorCode.UPSTREAM_UNKNOWN,
}


def http_status(code: ErrorCode) -> int:
    return HTTP_STATUS.get(code, 500)


def code_for_status(status: int) -> ErrorCode:
    return STATUS_TO_CODE.get(status, ErrorCode.INTERNAL)


class AppError(Exception):
    """带错误码的异常。异常处理器会把它翻译成统一的失败信封。"""

    def __init__(self, code, message: str, detail=None, status: int | None = None):
        super().__init__(message)
        self.code = code if isinstance(code, ErrorCode) else ErrorCode(code)
        self.message = message
        self.detail = detail
        self.status = status or http_status(self.code)

    @classmethod
    def from_crawler(cls, code: str, message: str) -> "AppError":
        """把爬虫信封里的错误码翻译成本端的码；不认识的一律算上游未知错误。"""
        mapped = CRAWLER_CODE_MAP.get(str(code).upper(), ErrorCode.UPSTREAM_UNKNOWN)
        return cls(mapped, message)

    def __str__(self) -> str:  # pragma: no cover - 便于日志
        return f"[{self.code.value}] {self.message}"
