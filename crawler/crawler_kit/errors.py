"""统一错误码与异常类型。

协议约定：爬虫正常退出码永远是 0，失败用 ``ok:false`` + ``error.code`` 表达。
"""

from __future__ import annotations

TIMEOUT = "TIMEOUT"
HTTP_ERROR = "HTTP_ERROR"
PARSE_ERROR = "PARSE_ERROR"
NOT_FOUND = "NOT_FOUND"
BLOCKED = "BLOCKED"
UNSUPPORTED = "UNSUPPORTED"
UNKNOWN = "UNKNOWN"

CODES = (TIMEOUT, HTTP_ERROR, PARSE_ERROR, NOT_FOUND, BLOCKED, UNSUPPORTED, UNKNOWN)


class CrawlerError(Exception):
    """带错误码的业务异常。CLI 会把它翻译成 ok:false 信封。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code if code in CODES else UNKNOWN
        self.message = message

    def __str__(self) -> str:  # pragma: no cover - 便于日志
        return f"[{self.code}] {self.message}"


def timeout(message: str) -> CrawlerError:
    return CrawlerError(TIMEOUT, message)


def http_error(message: str) -> CrawlerError:
    return CrawlerError(HTTP_ERROR, message)


def parse_error(message: str) -> CrawlerError:
    return CrawlerError(PARSE_ERROR, message)


def not_found(message: str) -> CrawlerError:
    return CrawlerError(NOT_FOUND, message)


def blocked(message: str) -> CrawlerError:
    return CrawlerError(BLOCKED, message)


def unsupported(message: str) -> CrawlerError:
    return CrawlerError(UNSUPPORTED, message)
