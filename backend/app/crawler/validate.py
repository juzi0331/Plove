"""把爬虫的输出塞进契约模型。

契约的意义全在这里兑现：**不合格就拒收，绝不"凑合入库"**。
爬虫回了个字段名拼错的空列表，不如直接报错 —— 至少你能在日志里看见，
而不是让用户对着空白页猜。
"""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.errors import AppError, ErrorCode

T = TypeVar("T", bound=BaseModel)


def validate_payload(model: type[T], payload: Any, *, key: str, command: str) -> T:
    """校验失败一律翻译成 ``UPSTREAM_PARSE_ERROR``，并把错误点放进 ``detail``。

    ``detail`` 只保留 ``loc`` / ``msg`` / ``type`` 三个字符串字段 —— 不直接塞
    Pydantic 的原始错误，因为里面可能带异常对象，序列化时会炸。
    """
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        detail = [
            {
                "loc": ".".join(str(part) for part in item["loc"]),
                "msg": item["msg"],
                "type": item["type"],
            }
            for item in exc.errors()
        ]
        raise AppError(
            ErrorCode.UPSTREAM_PARSE_ERROR,
            f"{key} 的 {command} 输出不符合契约（{len(detail)} 处）",
            detail=detail,
        ) from exc
