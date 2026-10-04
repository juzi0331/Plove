"""系统公告与维护模式管理服务。

持久化基于 SystemSetting 键值配置表，内存维护极速只读状态，
保证前台高并发判断无需频繁打库。
"""

from __future__ import annotations

import json

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
    """供前台公开调用的系统状态接口。"""
    from app.services import image_proxy_service
    m = get_maintenance(db)
    n = get_notice(db)
    proxy_cfg = image_proxy_service.get_image_proxy_config(db)

    # 动态汇聚所有已启用的解密规则中的图床域名特征
    decrypt_domains: list[str] = []
    for r in (proxy_cfg.decryption_rules or []):
        if r.enabled and r.match_domains:
            for d in r.match_domains:
                if d and d.strip() and d.strip() not in decrypt_domains:
                    decrypt_domains.append(d.strip())

    return SystemStatusPayload(
        maintenance=m.enabled,
        maintenance_message=m.message,
        notice=n if n.enabled else None,
        image_proxy_enabled=proxy_cfg.global_proxy_enabled,
        image_decrypt_domains=decrypt_domains,
    )

