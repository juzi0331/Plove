"""后台 — 设备管理。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import commit_now, get_db
from app.api.v1.admin._audit import audit
from app.core.middleware import get_request_id
from app.schemas.admin import DeviceListPayload, DevicePlaybackHistoryPayload, KickResult
from app.schemas.envelope import Envelope, ok
from app.services import admin_service

router = APIRouter(tags=["后台-设备"])


@router.get("/codes/{code_id}/devices", response_model=Envelope[DeviceListPayload], summary="这个码用过的设备")
def list_devices(
    code_id: int,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[DeviceListPayload]:
    """按最近出现排序。载荷里没有令牌明文，只有前 6 位掩码。"""
    record, devices = admin_service.list_devices(db, code_id)
    return ok(
        DeviceListPayload(devices=devices, active_device_id=record.active_device_id),
        request_id,
    )


@router.post("/devices/{device_id}/kick", response_model=Envelope[KickResult], summary="踢设备下线")
def kick_device(
    device_id: int,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[KickResult]:
    """把活跃位清掉。那台设备会被提示并被停播，但它还能自己抢回来。"""
    record = admin_service.kick_device(db, device_id)
    commit_now(db)
    audit(
        "kick_device",
        request_id,
        device_id=device_id,
        code=admin_service.mask_code(record.code),
    )
    return ok(
        KickResult(
            message="已把该设备下线（它下次心跳会收到通知）",
            code=admin_service.to_code_item(record),
        ),
        request_id,
    )


@router.post("/devices/{device_id}/unbind", response_model=Envelope[KickResult], summary="解绑并移除设备")
def unbind_device(
    device_id: int,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[KickResult]:
    """彻底解绑该设备并释放名额，新设备即可接入。"""
    record = admin_service.unbind_device(db, device_id)
    commit_now(db)
    audit(
        "unbind_device",
        request_id,
        device_id=device_id,
        code=admin_service.mask_code(record.code),
    )
    return ok(
        KickResult(
            message="已成功解绑该设备，已释放绑定名额",
            code=admin_service.to_code_item(record),
        ),
        request_id,
    )


@router.get(
    "/devices/{device_id}/history",
    response_model=Envelope[DevicePlaybackHistoryPayload],
    summary="查询设备观看历史记录",
)
def get_device_history(
    device_id: int,
    limit: int = 50,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[DevicePlaybackHistoryPayload]:
    """查询指定设备最近看过的影片流水（影片、海报、集数、进度、时间）。"""
    history = admin_service.get_device_playback_history(db, device_id, limit=limit)
    return ok(history, request_id)
