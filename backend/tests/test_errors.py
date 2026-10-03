"""错误码测试。

最有价值的是 :func:`test_crawler_codes_are_all_covered`：它**直接读爬虫那侧的码表**
（``crawler/crawler_kit/errors.py``）来比对。爬虫新增一个错误码而网关没跟上，
这里就会红——两端不可能悄悄漂移。
"""

from __future__ import annotations

import importlib.util

import pytest

from app.core.config import get_settings
from app.core.errors import (
    CRAWLER_CODE_MAP,
    HTTP_STATUS,
    AppError,
    ErrorCode,
    code_for_status,
    http_status,
)


def test_every_code_has_http_status():
    missing = [code.value for code in ErrorCode if code not in HTTP_STATUS]
    assert not missing, f"这些错误码没有映射 HTTP 状态: {missing}"


def test_known_code_maps_to_http_status():
    assert http_status(ErrorCode.NOT_FOUND) == 404
    assert http_status(ErrorCode.UPSTREAM_TIMEOUT) == 504
    assert code_for_status(404) is ErrorCode.NOT_FOUND
    # 没见过状态码不许漏出去，一律算内部错误
    assert code_for_status(418) is ErrorCode.INTERNAL


def test_from_crawler_translates_codes():
    error = AppError.from_crawler("TIMEOUT", "上游超时")
    assert error.code is ErrorCode.UPSTREAM_TIMEOUT
    assert error.status == 504
    assert error.message == "上游超时"


def test_from_crawler_unknown_code_falls_back():
    error = AppError.from_crawler("SOMETHING_NEW", "x")
    assert error.code is ErrorCode.UPSTREAM_UNKNOWN


def test_crawler_codes_are_all_covered():
    """读爬虫那侧的真实码表，防止两端漂移。"""
    path = get_settings().crawler_dir / "crawler_kit" / "errors.py"
    if not path.exists():
        pytest.skip(f"找不到爬虫错误码表: {path}")

    spec = importlib.util.spec_from_file_location("_crawler_errors", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    missing = sorted(set(module.CODES) - set(CRAWLER_CODE_MAP))
    assert not missing, f"爬虫的错误码没被网关映射: {missing}"
