"""健康检查。

它有两个身份：给运维探活用，以及**信封本身的活体样例**——
所以这里也用 ``ok()`` 包装，而不是裸返回一个字典。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app import __version__
from app.core.config import Settings, get_settings
from app.core.middleware import get_request_id
from app.schemas.envelope import Envelope, ok
from app.schemas.system import HealthPayload

router = APIRouter(tags=["system"])


@router.get("/health", response_model=Envelope[HealthPayload], summary="健康检查")
def health(
    request_id: str = Depends(get_request_id),
    settings: Settings = Depends(get_settings),
) -> Envelope[HealthPayload]:
    # 生产模式下避免泄露精确构建版本与内部环境名称
    env = settings.env if settings.is_dev else "production"
    version = __version__ if settings.is_dev else "*"
    payload = HealthPayload(env=env, version=version)
    return ok(payload, request_id)
