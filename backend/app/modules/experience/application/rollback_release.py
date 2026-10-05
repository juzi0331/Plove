"""体验配置回滚用例。

实现蓝图关键要求：
回滚是重新发布旧内容并生成更大 revision，而不是让版本号倒退，
防止客户端把回滚当旧缓存忽略。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.modules.experience.infrastructure.sqlalchemy_experience_repository import (
    SqlAlchemyExperienceRepository,
)
from app.modules.experience.schemas.release import ReleasePublishResult


def rollback_experience_release(
    session: Session,
    target_release_id: str,
    note: str = "",
    rolled_back_by: str = "admin",
) -> ReleasePublishResult:
    """安全回滚至指定历史快照，创建自增版本的新发布并同步草稿。"""
    repo = SqlAlchemyExperienceRepository(session)
    target_release = repo.get_release(target_release_id)
    if target_release is None:
        raise AppError(ErrorCode.NOT_FOUND, f"目标历史版本未找到: {target_release_id}")

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    rand_suffix = uuid.uuid4().hex[:6]
    new_release_id = f"exp_rollback_{timestamp_str}_{rand_suffix}"
    effective_note = note or f"回滚至历史版本 {target_release_id} (原 r{target_release.revision})"

    # 1. 以历史快照为载荷，创建新发布并推进指针（获得更大的 revision）
    new_release, pointer = repo.create_release_and_activate(
        release_id=new_release_id,
        brand_json=target_release.brand_json,
        theme_json=target_release.theme_json,
        navigation_json=target_release.navigation_json,
        pages_json=target_release.pages_json,
        player_defaults_json=target_release.player_defaults_json,
        published_by=rolled_back_by,
        note=effective_note,
    )

    # 2. 将工作草稿同步至回滚后的状态，防止后续编辑继续基于被放弃的草稿
    draft = repo.get_or_create_draft("default")
    repo.save_draft(
        draft_id="default",
        current_revision=draft.revision,
        brand_json=target_release.brand_json,
        theme_json=target_release.theme_json,
        navigation_json=target_release.navigation_json,
        pages_json=target_release.pages_json,
        player_defaults_json=target_release.player_defaults_json,
        updated_by=f"rollback_sync({rolled_back_by})",
    )

    return ReleasePublishResult(
        release_id=new_release.id,
        revision=new_release.revision,
        message=f"已成功回滚至版本 {target_release_id}。已生成最新发布快照 {new_release.id} (修订号 r{new_release.revision})",
    )
