"""激活码与单会话。

规则（已确认）：

* 时长制、无注册；**时长从首次激活那一刻起算**，换设备不重置、不重算；
* **一码多设备，但同时只能一台在线**；
* 被踢的设备**不自动重抢** —— 服务端只负责在它心跳时告诉它 ``is_active=false``，
  客户端应当停下来等用户手动点"在此设备继续"。
  这条规矩写在客户端，但服务端必须把状态如实告诉它，否则它会无限互踢。

活跃位只有一个字段（``activation_codes.active_device_id``），
改它就是一条 UPDATE，**不存在两台设备同时活跃的中间态**。
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import as_aware, utcnow
from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.models.activation import ActivationCode
from app.models.device import Device
from app.schemas.activation import ActivationResult, SessionState

#: 生成激活码用的字符集：去掉了容易看错的 I / O / 0 / 1
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_PREFIX = "PLV"
CODE_GROUPS = 3
CODE_GROUP_SIZE = 4


def generate_code() -> str:
    """形如 ``PLV-A7K2-M9QP-3XZT``。人要在纸上/聊天里转抄，所以不用易混字符。"""
    body = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_GROUPS * CODE_GROUP_SIZE))
    groups = [body[i : i + CODE_GROUP_SIZE] for i in range(0, len(body), CODE_GROUP_SIZE)]
    return "-".join([CODE_PREFIX, *groups])


def normalize_code(code: str) -> str:
    """用户手打会有空格、小写、中文全角横线，都替它消化掉。"""
    cleaned = (
        str(code)
        .strip()
        .upper()
        .replace(" ", "")
        .replace("－", "-")
        .replace("—", "-")
        .replace("_", "-")
    )
    return cleaned


def hash_code(code: str) -> str:
    """使用全局配置密钥计算激活码的 HMAC-SHA256 哈希值，防止彩虹表反查。"""
    cleaned = normalize_code(code)
    secret = getattr(get_settings(), "secret_key", "plove-activation-hmac-secret-default")
    return hmac.new(secret.encode("utf-8"), cleaned.encode("utf-8"), hashlib.sha256).hexdigest()


# ------------------------------------------------------------------ 发码


def issue_code(
    session: Session,
    *,
    duration_hours: int,
    note: str = "",
    max_devices: int | None = None,
) -> ActivationCode:
    """签发一个新码。同时生成 HMAC-SHA256 哈希索引。"""
    if duration_hours <= 0:
        raise AppError(ErrorCode.BAD_REQUEST, "时长必须大于 0 小时")

    for _ in range(20):  # 撞了就换一个，实际不可能连续撞 20 次
        code = generate_code()
        c_hash = hash_code(code)
        exists = session.scalar(
            select(ActivationCode.id).where(
                (ActivationCode.code == code) | (ActivationCode.code_hash == c_hash)
            )
        )
        if exists is None:
            record = ActivationCode(
                code=code,
                code_hash=c_hash,
                duration_hours=duration_hours,
                note=note,
                max_devices=max_devices if (max_devices and max_devices > 0) else 0,
            )
            session.add(record)
            session.flush()
            return record
    raise AppError(ErrorCode.INTERNAL, "生成激活码失败，请重试")


# ------------------------------------------------------------------ 激活

_redeem_lock = threading.RLock()


def redeem(
    session: Session,
    *,
    code: str | None,
    device_token: str | None = None,
    device_name: str = "",
    auto_commit: bool = True,
) -> ActivationResult:
    """激活 / 抢回活跃位。

    优先通过 HMAC-SHA256 哈希比对查库，未命中时回退明文查库并补齐哈希（零停机平滑迁移）。
    通过进程级锁与事务提交防止并发超限接入设备。
    """
    with _redeem_lock:
        record: ActivationCode | None = None
        device: Device | None = None

        # 有 token 就先用 token 找回这台设备（"在此设备继续"走这条路）
        if device_token:
            device = session.scalar(select(Device).where(Device.token == device_token))
            if device is not None:
                record = device.activation

        # 找不到就用码
        if record is None:
            if not code:
                raise AppError(ErrorCode.ACTIVATION_INVALID, "请输入激活码")
            clean_code = normalize_code(code)
            target_hash = hash_code(clean_code)

            # 1. 优先按 HMAC-SHA256 哈希查找
            stmt = select(ActivationCode).where(ActivationCode.code_hash == target_hash)
            if session.bind and session.bind.dialect.name != "sqlite":
                stmt = stmt.with_for_update()
            record = session.scalar(stmt)

            # 2. 兼容回退：老码可能尚未写入 hash，按明文查找并在首次命中时补齐 hash
            if record is None:
                fallback_stmt = select(ActivationCode).where(ActivationCode.code == clean_code)
                if session.bind and session.bind.dialect.name != "sqlite":
                    fallback_stmt = fallback_stmt.with_for_update()
                record = session.scalar(fallback_stmt)
                if record is not None and record.code_hash is None:
                    record.code_hash = target_hash
                    session.flush()

            if record is None:
                raise AppError(ErrorCode.ACTIVATION_INVALID, "激活码无效或已到期")
            # 拿别的码来，且这码被停用/过期 → 拦掉
            _ensure_usable(record)

        _ensure_usable(record)

        # 首次激活：把计时起点钉死，之后永远不再改
        is_first_activation = record.activated_at is None or record.expires_at is None
        if is_first_activation:
            record.activated_at = utcnow()
            record.expires_at = record.activated_at + timedelta(hours=record.duration_hours)

        if device is None:
            # 设备上限检查（使用数据库聚合 count 保证跨进程事务一致性，报错文案通用化保密）
            max_dev = getattr(record, "max_devices", None)
            if max_dev is not None and max_dev > 0:
                dev_count = session.scalar(
                    select(func.count(Device.id)).where(Device.activation_id == record.id)
                ) or 0
                if dev_count >= max_dev:
                    raise AppError(
                        ErrorCode.ACTIVATION_INVALID,
                        "激活码无效或无法接入新设备，请联系管理员",
                    )

            device = Device(
                activation_id=record.id,
                token=secrets.token_urlsafe(32),
                name=device_name,
            )
            session.add(device)
            session.flush()

        if device_name and device.name != device_name:
            device.name = device_name

        device.last_seen_at = utcnow()
        record.active_device_id = device.id

        session.flush()

        # 提前提取响应属性，避免 commit 后延迟属性加载失败
        result = ActivationResult(
            device_token=device.token,
            device_name=device.name,
            expires_at=as_aware(record.expires_at),
            remaining_seconds=_remaining_seconds(record),
            heartbeat_interval_seconds=_heartbeat_interval(),
        )
        record_code = record.code
        duration_hours = record.duration_hours
        exp_time = record.expires_at

        if auto_commit:
            session.commit()

    if is_first_activation:
        try:
            from app.services.admin_service import mask_code
            from app.services.webhook_service import webhook_service

            masked_code = mask_code(record_code)
            exp_text = exp_time.strftime("%Y-%m-%d %H:%M:%S") if exp_time else "永久"
            webhook_service.dispatch_event(
                event_type="code_activated",
                title="激活码首次激活通知",
                content=f"激活码 {masked_code} 已被设备「{device_name or '默认设备'}」首次成功绑定激活。",
                fields={
                    "激活码": masked_code,
                    "绑定设备": device_name or "默认设备",
                    "有效时长": f"{duration_hours} 小时",
                    "到期时间": exp_text,
                },
                sync=False,
            )
        except Exception:
            pass

    return result


# ------------------------------------------------------------------ 心跳与守卫


def heartbeat(session: Session, device_token: str | None) -> SessionState:
    """心跳。

    它**不改变**活跃位，只如实汇报。这样"被踢"是一个观测结果，
    而不是某个后台任务推断出来的东西 —— 不需要超时阈值，也就不会误踢。
    """
    device = _require_device(session, device_token)
    record = device.activation
    _ensure_usable(record)

    device.last_seen_at = utcnow()
    session.flush()

    return SessionState(
        is_active=record.active_device_id == device.id,
        expires_at=as_aware(record.expires_at),
        remaining_seconds=_remaining_seconds(record),
        server_time=as_aware(utcnow()),
        heartbeat_interval_seconds=_heartbeat_interval(),
    )


def require_active(session: Session, device_token: str | None) -> Device:
    """所有内容接口的守卫：必须是**当前活跃设备**才放行。

    四种拒绝要分开报，否则前端分不清"该重新激活"还是"被别的设备顶了"：

    * 没带 token / token 不认识 → ``UNAUTHORIZED``
    * 码被停用 → ``FORBIDDEN``
    * 码到期 → ``ACTIVATION_EXPIRED``
    * 活跃位在别的设备上 → ``SESSION_KICKED``
    """
    device = _require_device(session, device_token)
    record = device.activation
    _ensure_usable(record)

    if record.active_device_id != device.id:
        raise AppError(ErrorCode.SESSION_KICKED, "该激活码已在其他设备登录")

    # 顺带刷新一下"最后出现时间"（带 60s 写节流，消除高频内容/播放请求写放大）
    now = utcnow()
    if device.last_seen_at is None or (now - device.last_seen_at).total_seconds() >= 60.0:
        device.last_seen_at = now
        session.flush()
    return device


# ------------------------------------------------------------------ 内部


def _require_device(session: Session, device_token: str | None) -> Device:
    if not device_token:
        raise AppError(ErrorCode.UNAUTHORIZED, "未激活：请先输入激活码")
    device = session.scalar(select(Device).where(Device.token == device_token))
    if device is None:
        raise AppError(ErrorCode.UNAUTHORIZED, "设备令牌无效，请重新激活")
    return device


def _ensure_usable(record: ActivationCode) -> None:
    if record.disabled_at is not None:
        raise AppError(ErrorCode.FORBIDDEN, "该激活码已被停用")
    if record.expires_at is not None and utcnow() >= record.expires_at:
        raise AppError(ErrorCode.ACTIVATION_EXPIRED, "该激活码已到期")


def _remaining_seconds(record: ActivationCode) -> int:
    if record.expires_at is None:
        return 0
    return max(0, int((record.expires_at - utcnow()).total_seconds()))


def _heartbeat_interval() -> int:
    from app.core.config import get_settings

    return get_settings().heartbeat_interval_seconds
