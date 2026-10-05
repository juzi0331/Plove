"""发布体验配置快照用例。

将草稿冻结为不可变发布快照并原子推进全站当前指针。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.errors import AppError, ErrorCode
from app.modules.experience.domain.page_rules import validate_page_sections
from app.modules.experience.domain.theme_rules import validate_theme_tokens
from app.modules.experience.infrastructure.sqlalchemy_experience_repository import (
    SqlAlchemyExperienceRepository,
)
from app.modules.experience.schemas.release import ReleasePublishResult


def publish_experience_release(
    session: Session,
    draft_id: str = "default",
    note: str = "",
    published_by: str = "admin",
) -> ReleasePublishResult:
    """从草稿创建不可变发布快照并原子切换当前活跃指针。"""
    repo = SqlAlchemyExperienceRepository(session)
    draft = repo.get_or_create_draft(draft_id)

    # 1. 完整性与规则校验
    theme_dict = json.loads(draft.theme_json or "{}")
    theme_errs = validate_theme_tokens(theme_dict)
    if theme_errs:
        raise AppError(ErrorCode.BAD_REQUEST, f"发布被拒绝：草稿主题 Token 未通过校验: {'; '.join(theme_errs)}")

    pages_dict = json.loads(draft.pages_json or "{}")
    for pid, pdata in pages_dict.items():
        errs = validate_page_sections(pdata.get("sections", []))
        if errs:
            raise AppError(ErrorCode.BAD_REQUEST, f"发布被拒绝：页面 '{pid}' 未通过校验: {'; '.join(errs)}")

    # 2. 生成发布快照 ID 并原子发布（增加随机后缀防止同秒发布主键冲突）
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    rand_suffix = uuid.uuid4().hex[:6]
    release_id = f"exp_{timestamp_str}_{rand_suffix}"
    effective_note = note or f"由管理员 {published_by} 发布"

    release, pointer = repo.create_release_and_activate(
        release_id=release_id,
        brand_json=draft.brand_json,
        theme_json=draft.theme_json,
        navigation_json=draft.navigation_json,
        pages_json=draft.pages_json,
        player_defaults_json=draft.player_defaults_json,
        published_by=published_by,
        note=effective_note,
    )

    return ReleasePublishResult(
        release_id=release.id,
        revision=release.revision,
        message=f"已成功发布版本 {release.id} (修订号 r{release.revision})，全站客户端将在 30-60 秒内无感生效",
    )
