"""异常 → 统一失败信封。

**所有**出错路径都必须经过这里，不允许有裸的 HTML 错误页或裸 JSON 漏出去——
否则前端就得为"正常响应"和"框架报错"写两套解析逻辑。
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError, ErrorCode, code_for_status, http_status
from app.core.middleware import REQUEST_ID_HEADER, new_request_id
from app.schemas.envelope import fail

logger = logging.getLogger(__name__)

#: 框架自己抛的 HTTPException 文案没有信息量，这里统一换成可读的说法
_DEFAULT_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.NOT_FOUND: "接口或资源不存在",
    ErrorCode.BAD_REQUEST: "请求不合法",
    ErrorCode.UNAUTHORIZED: "未授权",
    ErrorCode.FORBIDDEN: "无权访问",
    ErrorCode.RATE_LIMITED: "请求过于频繁",
    ErrorCode.NOT_IMPLEMENTED: "该能力尚未实现",
}


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or new_request_id()


def _response(
    code: ErrorCode,
    message: str,
    request_id: str,
    detail=None,
    status: int | None = None,
) -> JSONResponse:
    body = fail(code, message, request_id, detail).model_dump(mode="json")
    return JSONResponse(
        status_code=http_status(code) if status is None else status,
        content=body,
        headers={REQUEST_ID_HEADER: request_id},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """挂四类处理器，覆盖到"任何一种出错"为止。"""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return _response(exc.code, exc.message, _request_id(request), exc.detail, exc.status)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # errors() 里可能含异常对象，先过一遍 jsonable_encoder 才好序列化
        return _response(
            ErrorCode.VALIDATION_ERROR,
            "请求参数不合法",
            _request_id(request),
            detail=jsonable_encoder(exc.errors()),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = code_for_status(exc.status_code)
        message = _DEFAULT_MESSAGES.get(code) or str(exc.detail or code.value)
        return _response(code, message, _request_id(request), status=exc.status_code)

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        request_id = _request_id(request)
        logger.exception("未预期异常 request_id=%s", request_id)
        return _response(ErrorCode.INTERNAL, "服务内部错误", request_id)
