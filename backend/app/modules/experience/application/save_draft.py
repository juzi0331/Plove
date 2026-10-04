"""保存体验配置草稿用例。

包含乐观并发版本校验与领域安全规则核对。
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.modules.experience.domain.page_rules import validate_page_sections
from app.modules.experience.domain.theme_rules import validate_theme_tokens
from app.modules.experience.infrastructure.sqlalchemy_experience_repository import (
    SqlAlchemyExperienceRepository,
)
from app.modules.experience.schemas.draft import DraftSaveResult, ExperienceDraftUpdateRequest


def save_experience_draft(
    session: Session,
    draft_id: str,
    req: ExperienceDraftUpdateRequest,
    updated_by: str = "admin",
) -> DraftSaveResult:
    """提交修改草稿配置。"""
    repo = SqlAlchemyExperienceRepository(session)
    draft = repo.get_or_create_draft(draft_id)

    # 1. 乐观并发版本检查
    if draft.revision != req.revision:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            f"草稿已被其他管理员修改（您提交的基础版本: {req.revision}，当前数据库最新: {draft.revision}），请刷新草稿后重新编辑",
        )

    # 2. 准备合并变更
    brand_dict = req.brand.model_dump() if req.brand else json.loads(draft.brand_json or "{}")
    theme_dict = req.theme.model_dump() if req.theme else json.loads(draft.theme_json or "{}")
    nav_list = [item.model_dump() for item in req.navigation] if req.navigation is not None else json.loads(draft.navigation_json or "[]")
    player_dict = req.player_defaults.model_dump() if req.player_defaults else json.loads(draft.player_defaults_json or "{}")

    if req.pages is not None:
        pages_dict = {pid: pdef.model_dump() for pid, pdef in req.pages.items()}
    else:
        pages_dict = json.loads(draft.pages_json or "{}")

    # 3. 领域规则校验
    theme_errs = validate_theme_tokens(theme_dict)
    if theme_errs:
        raise AppError(ErrorCode.BAD_REQUEST, f"主题 Token 校验未通过: {'; '.join(theme_errs)}")

    for pid, pdata in pages_dict.items():
        secs = pdata.get("sections", [])
        page_errs = validate_page_sections(secs)
        if page_errs:
            raise AppError(ErrorCode.BAD_REQUEST, f"页面 '{pid}' 组件布局未通过安全校验: {'; '.join(page_errs)}")

    # 4. 执行更新
    updated = repo.save_draft(
        draft_id=draft_id,
        current_revision=req.revision,
        brand_json=json.dumps(brand_dict, ensure_ascii=False),
        theme_json=json.dumps(theme_dict, ensure_ascii=False),
        navigation_json=json.dumps(nav_list, ensure_ascii=False),
        pages_json=json.dumps(pages_dict, ensure_ascii=False),
        player_defaults_json=json.dumps(player_dict, ensure_ascii=False),
        updated_by=updated_by,
    )

    return DraftSaveResult(
        draft_id=updated.id,
        revision=updated.revision,
        message="草稿保存成功",
    )
