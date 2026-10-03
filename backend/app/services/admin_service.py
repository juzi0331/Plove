"""后台对激活码与设备的操作。

它和 :mod:`app.services.activation_service` 的分工：

* ``activation_service`` 是**客户端**那条路（激活、心跳、守卫）——
  它只关心\"这个令牌能不能看内容\"；
* 这里是**运维**那条路（发码、封码、延长、踢设备）—— 它不关心现在谁在看，
  只关心\"账对不对、要不要止血\"。

两边共用同一张表，所以共用一组不变量（下面每条都有解释）。
**不 import fastapi**（services 层的硬规矩），也不 commit —— 事务归 :func:`app.api.deps.get_db`。

### 三条容易写错的地方

1. **延长时长要按情况分两路。** 码一旦激活过，``expires_at`` 就钉死了，
   改 ``duration_hours`` 对它**完全无效** —— 必须给 ``expires_at`` 加时间。
   还没激活的码则相反：它还没有 ``expires_at``，只能改 ``duration_hours``。
2. **踢设备 = 清掉活跃位**（置 ``None``），不是删设备。
   删了那台就找不回自己了（它的令牌会变成\"不认识\"，报 ``UNAUTHORIZED``），
   而\"被管理员请下线\"应当是 ``SESSION_KICKED``：它还能自己抢回来。
3. **停用是软删**（写 ``disabled_at``）。历史要留着：\"这个码什么时候被封的\"是有用信息，
   而且解封只需要清掉这个字段。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.clock import as_aware, utcnow
from app.core.errors import AppError, ErrorCode
from app.models.activation import ActivationCode
from app.models.device import Device
from app.schemas.admin import CodeListItem, DeviceItem
from app.services import activation_service

#: 设备令牌在后台只露前 6 位（见 schemas/admin.py 的说明）
TOKEN_PREFIX_LEN = 6


@dataclass(slots=True)
class CodePage:
    items: list[CodeListItem]
    total: int
    page: int
    page_size: int


# ------------------------------------------------------------------ 读


def to_code_item(record: ActivationCode) -> CodeListItem:
    """把一个 ``ActivationCode`` 行转成载荷。**所有出口都走这里**，字段口径才一致。"""
    devices = list(record.devices or [])
    active = next((d for d in devices if d.id == record.active_device_id), None)
    return CodeListItem(
        id=record.id,
        code=record.code,
        note=record.note or "",
        duration_hours=record.duration_hours,
        created_at=as_aware(record.created_at),
        activated_at=as_aware(record.activated_at) if record.activated_at else None,
        expires_at=as_aware(record.expires_at) if record.expires_at else None,
        disabled_at=as_aware(record.disabled_at) if record.disabled_at else None,
        remaining_seconds=_remaining_seconds(record),
        device_count=len(devices),
        max_devices=getattr(record, "max_devices", 1) or 1,
        active_device_name=(active.name or None) if active else None,
    )


def list_codes(
    session: Session,
    *,
    query: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> CodePage:
    """码列表，新的在前。

    ``query`` 同时匹配 **码本身**和**备注**：运维找码时记得的往往是\"发给谁\"，
    而不是那串字符。
    """
    page = max(1, page)
    page_size = max(1, min(100, page_size))

    statement = select(ActivationCode)
    if query:
        needle = query.strip()
        if needle:
            pattern = f"%{needle}%"
            statement = statement.where(
                or_(
                    # 码一律存成大写，所以搜小写也要能命中
                    ActivationCode.code.like(f"%{needle.upper()}%"),
                    ActivationCode.note.like(pattern),
                )
            )

    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = session.scalars(
        statement.order_by(ActivationCode.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return CodePage(
        items=[to_code_item(row) for row in rows],
        total=int(total),
        page=page,
        page_size=page_size,
    )


def get_code(session: Session, code_id: int) -> ActivationCode:
    record = session.get(ActivationCode, code_id)
    if record is None:
        raise AppError(ErrorCode.NOT_FOUND, "没有这个激活码")
    return record


def list_devices(session: Session, code_id: int) -> tuple[ActivationCode, list[DeviceItem]]:
    """某个码用过的设备。**按最近出现排序** —— 运维想看的通常是\"最后在用的那台\"。"""
    record = get_code(session, code_id)
    devices = sorted(record.devices or [], key=lambda d: d.last_seen_at or d.created_at, reverse=True)
    return record, [
        DeviceItem(
            id=device.id,
            name=device.name or "",
            token_prefix=device.token[:TOKEN_PREFIX_LEN],
            created_at=as_aware(device.created_at),
            last_seen_at=as_aware(device.last_seen_at),
            is_active=device.id == record.active_device_id,
        )
        for device in devices
    ]


# ------------------------------------------------------------------ 写


def issue_codes(
    session: Session,
    *,
    duration_hours: int,
    count: int,
    note: str,
    max_devices: int = 1,
) -> list[str]:
    """批量发码。支持指定最大可用设备数。"""
    codes: list[str] = []
    for _ in range(max(1, min(50, count))):
        record = activation_service.issue_code(
            session,
            duration_hours=duration_hours,
            note=note,
            max_devices=max_devices,
        )
        codes.append(record.code)
    return codes


def set_disabled(session: Session, code_id: int, *, disabled: bool) -> ActivationCode:
    """停用 / 解封。

    停用是**立即生效**的：客户端的下一次请求（内容或心跳）就会拿到 ``FORBIDDEN``。
    不需要额外通知 —— 活跃位和令牌都不用动，``_ensure_usable()`` 那道检查会拦住它。
    """
    record = get_code(session, code_id)
    if disabled and record.disabled_at is None:
        record.disabled_at = utcnow()
    elif not disabled:
        record.disabled_at = None
    session.flush()
    return record


def extend(session: Session, code_id: int, *, hours: int) -> ActivationCode:
    """把时长往后挪 ``hours`` 小时。

    **两条分支是这个函数存在的全部理由**（见文件头第 1 条）：

    ==================  =========================  ==========================
    码的状态            改哪个字段                  为什么
    ==================  =========================  ==========================
    已激活（有到期时间）  ``expires_at += hours``     计时起点已经钉死，改 duration 无效
    未激活（没有到期）    ``duration_hours += hours`` 还没有到期时间，只能改\"将来给多久\"
    ==================  =========================  ==========================
    """
    record = get_code(session, code_id)
    if record.expires_at is None:
        record.duration_hours += hours
    else:
        record.expires_at = record.expires_at + timedelta(hours=hours)

    # 到期时间被挪到未来了 → 这个码应当重新可用。
    # 但**停用是运维的明确决定**，延长不该顺手解封它（那是两件事）。
    session.flush()
    return record


def kick_device(session: Session, device_id: int) -> ActivationCode:
    """把那台设备从活跃位上拿下来。

    做法是 ``active_device_id = None``，于是：

    * 那台设备的下一次请求拿到 ``SESSION_KICKED``（守卫里的比较不等）；
    * 它的心跳返回 ``is_active: false``，客户端会停播并提示；
    * **它还能自己抢回来** —— 这是刻意的：踢是\"请下线\"，不是\"封设备\"。
      真要让它彻底用不了，应该停用整个码。
    """
    device = session.get(Device, device_id)
    if device is None:
        raise AppError(ErrorCode.NOT_FOUND, "没有这台设备")

    record = device.activation
    if record is None:  # pragma: no cover - 外键保证不会发生
        raise AppError(ErrorCode.INTERNAL, "设备没有关联的激活码")

    if record.active_device_id == device.id:
        record.active_device_id = None
        session.flush()

    return record


def unbind_device(session: Session, device_id: int) -> ActivationCode:
    """彻底解绑该设备，释放绑定名额供新设备使用。"""
    device = session.get(Device, device_id)
    if device is None:
        raise AppError(ErrorCode.NOT_FOUND, "没有这台设备")

    record = device.activation
    if record is None:
        raise AppError(ErrorCode.INTERNAL, "设备没有关联的激活码")

    if record.active_device_id == device.id:
        record.active_device_id = None
    session.delete(device)
    session.flush()
    return record


def delete_code(session: Session, code_id: int) -> str:
    """彻底删除激活码及其绑定的设备历史。"""
    record = get_code(session, code_id)
    masked = mask_code(record.code)
    # 先删从表设备
    session.query(Device).filter_by(activation_id=code_id).delete()
    # 再删主表激活码
    session.delete(record)
    session.flush()
    return masked


def cleanup_expired_codes(session: Session, days: int = 7) -> int:
    """批量清理过期超过指定天数的失效激活码。"""
    cutoff = utcnow() - timedelta(days=max(0, days))
    expired_rows = session.query(ActivationCode).filter(
        ActivationCode.expires_at.is_not(None),
        ActivationCode.expires_at < cutoff,
    ).all()
    count = len(expired_rows)
    for r in expired_rows:
        session.query(Device).filter_by(activation_id=r.id).delete()
        session.delete(r)
    session.flush()
    return count


# ------------------------------------------------------------------ 内部


def _remaining_seconds(record: ActivationCode) -> int:
    if record.expires_at is None:
        return 0
    return max(0, int((record.expires_at - utcnow()).total_seconds()))


def mask_code(code: str) -> str:
    """日志里用的掩码。

    **激活码也是凭证** —— 一张能开门的纸。日志是会被贴出来求助的东西
    （\"帮我看看这段报错\"），所以日志里不该出现完整码；但审计又需要能认出\"是哪一个\"，
    所以留头留尾。
    """
    if len(code) <= 12:
        return f"{code[:4]}…"
    return f"{code[:8]}…{code[-4:]}"
