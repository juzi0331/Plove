"""后台 — 激活码管理。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import commit_now, get_db
from app.api.v1.admin._audit import audit
from app.core.middleware import get_request_id
from app.schemas.admin import (
    CodeActionResult,
    CodeListPayload,
    ExtendRequest,
    IssueCodesRequest,
    IssueCodesResult,
)
from app.schemas.admin_extended import CodeCleanupResult
from app.schemas.envelope import Envelope, ok
from app.services import admin_service

router = APIRouter(tags=["后台-激活码"])


@router.get("/codes", response_model=Envelope[CodeListPayload], summary="激活码列表")
def list_codes(
    query: str | None = Query(
        None,
        description="搜索词，同时匹配码本身和备注 —— 运维常记得的是发给谁",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[CodeListPayload]:
    """新的在前。``total`` 是满足搜索条件的总数，不是本页条数。"""
    result = admin_service.list_codes(db, query=query, page=page, page_size=page_size)
    return ok(
        CodeListPayload(
            codes=result.items,
            total=result.total,
            page=result.page,
            page_size=result.page_size,
        ),
        request_id,
    )


@router.post("/codes", response_model=Envelope[IssueCodesResult], summary="发码")
def issue_codes(
    payload: IssueCodesRequest,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[IssueCodesResult]:
    """一次可以发多个（count，上限 50）。"""
    codes = admin_service.issue_codes(
        db,
        duration_hours=payload.total_hours,
        count=payload.count,
        note=payload.note,
        max_devices=payload.max_devices,
    )
    commit_now(db)
    audit(
        "issue_codes",
        request_id,
        count=len(codes),
        hours=payload.total_hours,
        note=payload.note or "",
        codes=",".join(admin_service.mask_code(code) for code in codes),
    )
    return ok(
        IssueCodesResult(
            codes=codes,
            duration_hours=payload.total_hours,
            note=payload.note,
        ),
        request_id,
    )


@router.post("/codes/{code_id}/disable", response_model=Envelope[CodeActionResult], summary="停用激活码")
def disable_code(
    code_id: int,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[CodeActionResult]:
    """立即生效：那台设备的下一次请求（内容或心跳）就会拿到 FORBIDDEN。"""
    record = admin_service.set_disabled(db, code_id, disabled=True)
    commit_now(db)
    audit("disable_code", request_id, id=record.id, code=admin_service.mask_code(record.code))
    return ok(
        CodeActionResult(message="已停用", code=admin_service.to_code_item(record)),
        request_id,
    )


@router.post("/codes/{code_id}/enable", response_model=Envelope[CodeActionResult], summary="解封激活码")
def enable_code(
    code_id: int,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[CodeActionResult]:
    """只有清 disabled_at。已经到期的码不会因为解封而恢复。"""
    record = admin_service.set_disabled(db, code_id, disabled=False)
    commit_now(db)
    audit("enable_code", request_id, id=record.id, code=admin_service.mask_code(record.code))
    return ok(
        CodeActionResult(message="已解封", code=admin_service.to_code_item(record)),
        request_id,
    )


@router.post("/codes/{code_id}/extend", response_model=Envelope[CodeActionResult], summary="延长时长")
def extend_code(
    payload: ExtendRequest,
    code_id: int,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[CodeActionResult]:
    """往后加时间。只能加不能减，要减用停用。"""
    before = admin_service.get_code(db, code_id)
    was_started = before.expires_at is not None
    record = admin_service.extend(db, code_id, hours=payload.hours)
    commit_now(db)
    audit(
        "extend_code",
        request_id,
        id=record.id,
        code=admin_service.mask_code(record.code),
        hours=payload.hours,
        target="expires_at" if was_started else "duration_hours",
    )
    message = (
        f"已延长 {payload.hours} 小时（到期时间往后挪）"
        if was_started
        else f"已延长 {payload.hours} 小时（这个码还没激活，加在时长上）"
    )
    return ok(CodeActionResult(message=message, code=admin_service.to_code_item(record)), request_id)


@router.delete("/codes/{code_id}", response_model=Envelope[dict], summary="删除激活码")
def delete_code(
    code_id: int,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[dict]:
    """彻底删除激活码及其绑定的设备记录。"""
    masked = admin_service.delete_code(db, code_id)
    commit_now(db)
    audit("delete_code", request_id, id=code_id, code=masked)
    return ok({"message": f"激活码已彻底删除（{masked}）", "id": code_id}, request_id)


@router.post("/codes/cleanup-expired", response_model=Envelope[CodeCleanupResult], summary="批量清理失效激活码")
def cleanup_expired_codes(
    days: int = Query(7, ge=0, description="清理过期超过天数的码，默认为 7 天前到期的码"),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[CodeCleanupResult]:
    """清理已过期超过指定天数的失效激活码，释放数据库存储。"""
    count = admin_service.cleanup_expired_codes(db, days=days)
    commit_now(db)
    audit("cleanup_expired_codes", request_id, days=days, count=count)
    return ok(
        CodeCleanupResult(
            deleted_count=count,
            message=f"已成功清理 {count} 个到期超过 {days} 天的失效激活码",
        ),
        request_id,
    )
