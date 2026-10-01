"""系统公告与维护模式管理服务。

持久化基于 SystemSetting 键值配置表，内存维护极速只读状态，
保证前台高并发判断无需频繁打库。
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.db.session import commit_now
from app.models.system_setting import SystemSetting
from app.schemas.admin_extended import (
    SystemMaintenancePayload,
    SystemNoticePayload,
    SystemStatusPayload,
)

NOTICE_KEY = "system_notice"
MAINTENANCE_KEY = "system_maintenance"

# 内存快速缓存，避免每个 HTTP 请求都查数据库
_cached_status = {
    "maintenance_enabled": False,
    "maintenance_message": "系统维护中，请稍后重试",
}
_cached_notice: SystemNoticePayload | None = None


def is_maintenance_active() -> bool:
    return _cached_status["maintenance_enabled"]


def get_maintenance_message() -> str:
    return _cached_status["maintenance_message"]


def get_notice(db: Session) -> SystemNoticePayload:
    global _cached_notice
    if _cached_notice is not None:
        return _cached_notice
    row = db.query(SystemSetting).filter_by(key=NOTICE_KEY).first()
    if not row or not row.value_json:
        return SystemNoticePayload()
    try:
        data = json.loads(row.value_json)
        _cached_notice = SystemNoticePayload(**data)
        return _cached_notice
    except Exception:
        return SystemNoticePayload()


def update_notice(db: Session, payload: SystemNoticePayload) -> SystemNoticePayload:
    global _cached_notice
    payload.updated_at = utcnow().strftime("%Y-%m-%d %H:%M:%S")
    row = db.query(SystemSetting).filter_by(key=NOTICE_KEY).first()
    if not row:
        row = SystemSetting(key=NOTICE_KEY, value_json=payload.model_dump_json())
        db.add(row)
    else:
        row.value_json = payload.model_dump_json()
    commit_now(db)
    _cached_notice = payload
    return payload



def get_maintenance(db: Session) -> SystemMaintenancePayload:
    row = db.query(SystemSetting).filter_by(key=MAINTENANCE_KEY).first()
    if not row or not row.value_json:
        return SystemMaintenancePayload()
    try:
        data = json.loads(row.value_json)
        return SystemMaintenancePayload(**data)
    except Exception:
        return SystemMaintenancePayload()


def update_maintenance(db: Session, payload: SystemMaintenancePayload) -> SystemMaintenancePayload:
    payload.updated_at = utcnow().strftime("%Y-%m-%d %H:%M:%S")
    row = db.query(SystemSetting).filter_by(key=MAINTENANCE_KEY).first()
    if not row:
        row = SystemSetting(key=MAINTENANCE_KEY, value_json=payload.model_dump_json())
        db.add(row)
    else:
        row.value_json = payload.model_dump_json()
    commit_now(db)

    # 同步内存只读缓存
    _cached_status["maintenance_enabled"] = payload.enabled
    _cached_status["maintenance_message"] = payload.message
    return payload


def init_system_settings_cache(db: Session) -> None:
    """服务启动时，从数据库恢复维护模式内存标记。"""
    m = get_maintenance(db)
    _cached_status["maintenance_enabled"] = m.enabled
    _cached_status["maintenance_message"] = m.message


def get_public_system_status(db: Session) -> SystemStatusPayload:
    """供前台公开调用的系统状态接口。

    维护模式本来就有进程内缓存，公开状态不应每次再查数据库；这既减少首页
    热路径的数据库访问，也避免数据库尚未完成初始化时把整个公共状态接口打成 500。
    """
    n = get_notice(db)
    return SystemStatusPayload(
        maintenance=bool(_cached_status["maintenance_enabled"]),
        maintenance_message=str(_cached_status["maintenance_message"]),
        notice=n if n.enabled else None,
    )
