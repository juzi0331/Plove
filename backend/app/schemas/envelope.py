"""统一响应信封。

与爬虫命令行信封**同构**（``ok`` / ``data`` / ``error``），只多一个 ``request_id``：

* ``ok: true``  → ``data`` 有值，``error`` 为 null
* ``ok: false`` → ``data`` 为 null，``error`` 有值

前端因此只写一套拆信封 + 一套错误处理。
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from app.core.errors import ErrorCode

T = TypeVar("T")


class ErrorInfo(BaseModel):
    """错误对象。``code`` / ``message`` 与爬虫那侧完全一致，多一个可选 ``detail``。"""

    code: ErrorCode
    message: str
    detail: Any | None = None


class Envelope(BaseModel, Generic[T]):
    """所有接口的响应外形。"""

    ok: bool
    data: T | None = None
    error: ErrorInfo | None = None
    request_id: str = Field(min_length=8, description="请求 id，排查问题时用它串日志")


def ok(data: T, request_id: str) -> Envelope[T]:
    """成功信封。"""
    return Envelope[T](ok=True, data=data, error=None, request_id=request_id)


def fail(
    code: ErrorCode | str,
    message: str,
    request_id: str,
    detail: Any | None = None,
) -> Envelope[None]:
    """失败信封。``data`` 一定是 null。"""
    return Envelope[None](
        ok=False,
        data=None,
        error=ErrorInfo(code=code, message=message, detail=detail),
        request_id=request_id,
    )
