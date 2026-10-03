"""异常路径测试：三条出错路线都必须落进同一个信封。"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import AppError, ErrorCode
from app.main import create_app


def _app_with_traps() -> FastAPI:
    app = create_app()

    @app.get("/trap/app-error")
    def _app_error() -> None:
        raise AppError(ErrorCode.UPSTREAM_TIMEOUT, "上游超时")

    @app.get("/trap/crash")
    def _crash() -> None:
        raise RuntimeError("假装这里炸了")

    @app.get("/trap/validate")
    def _validate(page: int) -> dict:
        return {"page": page}

    return app


def test_app_error_keeps_code_and_status():
    with TestClient(_app_with_traps()) as client:
        response = client.get("/trap/app-error")

    assert response.status_code == 504
    body = response.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "UPSTREAM_TIMEOUT"
    assert body["error"]["message"] == "上游超时"


def test_unexpected_exception_becomes_internal_envelope():
    # 不让 TestClient 把异常重新抛出来，才能看到网关真实返回的东西
    with TestClient(_app_with_traps(), raise_server_exceptions=False) as client:
        response = client.get("/trap/crash")

    assert response.status_code == 500
    body = response.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "INTERNAL"
    # 内部细节不泄漏给前端
    assert "假装这里炸了" not in body["error"]["message"]


def test_validation_error_becomes_envelope():
    with TestClient(_app_with_traps()) as client:
        response = client.get("/trap/validate", params={"page": "不是数字"})

    assert response.status_code == 422
    body = response.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["detail"]
