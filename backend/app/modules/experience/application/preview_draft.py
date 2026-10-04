"""草稿隔离预览用例。

在隔离上下文中生成视图模型供后台安全预览，不污染线上发布与公开缓存。
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.modules.experience.application.build_page import _extract_vod_to_section_item
from app.modules.experience.infrastructure.sqlalchemy_experience_repository import (
    SqlAlchemyExperienceRepository,
)
from app.modules.experience.schemas.bootstrap import ClientBootstrapPayload, NavigationItem
from app.modules.experience.schemas.components import SectionDefinition
from app.modules.experience.schemas.page import PageViewModel
from app.modules.experience.schemas.theme import BrandConfig, PlayerDefaults, ThemeConfig


def preview_draft_bootstrap(session: Session, draft_id: str = "default") -> ClientBootstrapPayload:
    """读取指定草稿的客户端启动预览配置。"""
    repo = SqlAlchemyExperienceRepository(session)
    draft = repo.get_or_create_draft(draft_id)

    brand_data = json.loads(draft.brand_json or "{}")
    theme_data = json.loads(draft.theme_json or "{}")
    nav_data = json.loads(draft.navigation_json or "[]")
    player_data = json.loads(draft.player_defaults_json or "{}")

    return ClientBootstrapPayload(
        schema_version="1.0",
        release_id=f"preview_{draft.id}_rev{draft.revision}",
        revision=draft.revision,
        refresh_after_seconds=30,
        offline_display_ttl_seconds=86400,
        brand=BrandConfig(**brand_data),
        theme=ThemeConfig(**theme_data),
        text={"home.title": "首页预览"},
        navigation=[NavigationItem(**item) for item in nav_data],
        player_defaults=PlayerDefaults(**player_data),
    )


def preview_draft_page(
    session: Session,
    draft_id: str = "default",
    page_id: str = "home_default",
) -> PageViewModel:
    """读取草稿中指定页面的预览 ViewModel。"""
    repo = SqlAlchemyExperienceRepository(session)
    draft = repo.get_or_create_draft(draft_id)

    pages_map = json.loads(draft.pages_json or "{}")
    actual_pid = "home_default" if page_id in ("home", "home_default") else page_id
    page_cfg = pages_map.get(actual_pid, {"id": actual_pid, "title": "页面预览", "sections": []})

    resolved_sections: list[SectionDefinition] = []
    for s in page_cfg.get("sections", []):
        resolved_sections.append(SectionDefinition(**s))

    return PageViewModel(
        schema_version="1.0",
        release_id=f"preview_{draft.id}_rev{draft.revision}",
        page_id=actual_pid,
        title=page_cfg.get("title", "页面预览"),
        content_revision=str(draft.revision),
        sections=resolved_sections,
    )
