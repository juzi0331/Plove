"""后台 — 全站公告与紧急维护模式管理。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1.admin._audit import audit
from app.core.middleware import get_request_id
from app.schemas.admin_extended import (
    SystemMaintenancePayload,
    SystemNoticePayload,
)
from app.schemas.envelope import Envelope, ok
from app.services import system_service

router = APIRouter(tags=["后台-系统公告与维护"])


@router.get("/system/notice", response_model=Envelope[SystemNoticePayload], summary="获取全站公告配置")
def get_system_notice(
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[SystemNoticePayload]:
    n = system_service.get_notice(db)
    return ok(n, request_id)


@router.put("/system/notice", response_model=Envelope[SystemNoticePayload], summary="更新全站公告配置")
def update_system_notice(
    payload: SystemNoticePayload,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[SystemNoticePayload]:
    res = system_service.update_notice(db, payload)
    audit("update_system_notice", request_id, enabled=res.enabled, title=res.title)
    return ok(res, request_id)


@router.get("/system/maintenance", response_model=Envelope[SystemMaintenancePayload], summary="获取维护模式状态")
def get_system_maintenance(
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[SystemMaintenancePayload]:
    m = system_service.get_maintenance(db)
    return ok(m, request_id)


@router.put("/system/maintenance", response_model=Envelope[SystemMaintenancePayload], summary="开关紧急维护模式")
def update_system_maintenance(
    payload: SystemMaintenancePayload,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[SystemMaintenancePayload]:
    res = system_service.update_maintenance(db, payload)
    audit("update_system_maintenance", request_id, enabled=res.enabled)
    return ok(res, request_id)
