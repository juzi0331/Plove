"""信封的形状是前端唯一依赖的东西，所以要逐字段钉死。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.envelope import Envelope, ErrorInfo, fail, ok


def test_ok_shape_is_exactly_four_keys():
    dumped = ok({"a": 1}, "0123456789abcdef").model_dump(mode="json")
    assert dumped == {
        "ok": True,
        "data": {"a": 1},
        "error": None,
        "request_id": "0123456789abcdef",
    }


def test_fail_shape_has_null_data():
    dumped = fail("NOT_FOUND", "没找到", "0123456789abcdef").model_dump(mode="json")
    assert dumped["ok"] is False
    assert dumped["data"] is None
    assert dumped["error"] == {
        "code": "NOT_FOUND",
        "message": "没找到",
        "detail": None,
    }


def test_fail_rejects_unknown_code():
    with pytest.raises(ValidationError):
        ErrorInfo(code="NO_SUCH_CODE", message="x")


def test_short_request_id_is_rejected():
    with pytest.raises(ValidationError):
        Envelope[None](ok=True, data=None, error=None, request_id="short")
