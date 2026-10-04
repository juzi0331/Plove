"""体验层 SQLAlchemy 仓储实现。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.errors import AppError, ErrorCode
from app.models.experience import ExperienceActivePointer, ExperienceDraft, ExperienceRelease


def get_default_experience_data() -> dict[str, Any]:
    """生成系统内置出厂默认配置快照。"""
    return {
        "brand": {"name": "Plove", "logo_url": ""},
        "theme": {
            "color": {
                "background": "#141414",
                "surface": "#202020",
                "primary": "#E50914",
                "text": "#FFFFFF",
                "muted": "#B8B8B8",
                "border": "#2A2A2A",
                "danger": "#E50914",
            },
            "typography": {
                "family": "system",
                "body_px": 15,
                "title_px": 26,
            },
            "layout": {
                "max_width_px": 1440,
                "page_padding_px": 16,
                "gap_px": 14,
            },
            "card": {
                "aspect_ratio": "16:9",
                "radius_px": 6,
                "image_fit": "cover",
            },
            "motion": {
                "preset": "subtle",
                "duration_ms": 200,
            },
        },
        "navigation": [
            {
                "id": "home",
                "label_key": "home.title",
                "label": "首页",
                "action": {"type": "open_home"},
            }
        ],
        "pages": {
            "home_default": {
                "id": "home_default",
                "title": "首页",
                "sections": [
                    {
                        "id": "hero_main",
                        "component": "hero",
                        "component_version": 1,
                        "style": {"variant": "cinematic"},
                        "props": {
                            "title": "精选影视",
                            "subtitle": "后台动态布局与推荐",
                            "poster_url": "",
                            "action": {"type": "open_home"},
                        },
                    },
                    {
                        "id": "editorial_recommendations",
                        "component": "video_rail",
                        "component_version": 1,
                        "style": {"card_variant": "landscape", "density": "comfortable"},
                        "props": {
                            "title": "热播推荐",
                            "items": [],
                        },
                    },
                    {
                        "id": "latest_releases",
                        "component": "video_grid",
                        "component_version": 1,
                        "style": {"card_variant": "landscape"},
                        "props": {
                            "title": "最新上线",
                            "items": [],
                        },
                    },
                ],
            }
        },
        "player_defaults": {
            "auto_next": True,
            "auto_next_delay_seconds": 5,
            "default_rate": 1.0,
            "allowed_rates": [0.75, 1.0, 1.25, 1.5, 2.0],
            "hud_hide_after_ms": 3500,
        },
        "text": {
            "home.title": "首页",
            "catalog.search_placeholder": "搜索影片或演员",
            "player.loading": "正在连接播放资源",
        },
    }


class SqlAlchemyExperienceRepository:
    """SQLAlchemy 实现的体验仓储。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create_draft(self, draft_id: str = "default") -> ExperienceDraft:
        stmt = select(ExperienceDraft).where(ExperienceDraft.id == draft_id)
        draft = self.session.scalar(stmt)
        if draft is not None:
            return draft

        defaults = get_default_experience_data()
        draft = ExperienceDraft(
            id=draft_id,
            revision=1,
            brand_json=json.dumps(defaults["brand"], ensure_ascii=False),
            theme_json=json.dumps(defaults["theme"], ensure_ascii=False),
            navigation_json=json.dumps(defaults["navigation"], ensure_ascii=False),
            pages_json=json.dumps(defaults["pages"], ensure_ascii=False),
            player_defaults_json=json.dumps(defaults["player_defaults"], ensure_ascii=False),
            updated_at=utcnow(),
            updated_by="system",
        )
        self.session.add(draft)
        self.session.flush()
        return draft

    def save_draft(
        self,
        draft_id: str,
        current_revision: int,
        brand_json: str,
        theme_json: str,
        navigation_json: str,
        pages_json: str,
        player_defaults_json: str,
        updated_by: str = "admin",
    ) -> ExperienceDraft:
        draft = self.get_or_create_draft(draft_id)
        if draft.revision != current_revision:
            raise AppError(
                ErrorCode.BAD_REQUEST,
                f"配置已被其他人修改（您的版本号: {current_revision}，当前数据库最新: {draft.revision}），请刷新草稿后再试以防覆盖",
            )

        draft.brand_json = brand_json
        draft.theme_json = theme_json
        draft.navigation_json = navigation_json
        draft.pages_json = pages_json
        draft.player_defaults_json = player_defaults_json
        draft.revision += 1
        draft.updated_at = utcnow()
        draft.updated_by = updated_by
        self.session.flush()
        return draft

    def get_active_release(
        self, channel: str = "default"
    ) -> tuple[ExperienceRelease | None, ExperienceActivePointer | None]:
        pointer = self.session.scalar(
            select(ExperienceActivePointer).where(ExperienceActivePointer.channel == channel)
        )
        if pointer is None:
            return None, None

        release = self.session.scalar(
            select(ExperienceRelease).where(ExperienceRelease.id == pointer.release_id)
        )
        return release, pointer

    def get_release(self, release_id: str) -> ExperienceRelease | None:
        return self.session.scalar(
            select(ExperienceRelease).where(ExperienceRelease.id == release_id)
        )

    def list_releases(self, limit: int = 50) -> list[ExperienceRelease]:
        stmt = (
            select(ExperienceRelease)
            .order_by(desc(ExperienceRelease.revision))
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())

    def _get_next_release_revision(self) -> int:
        stmt = select(func.max(ExperienceRelease.revision))
        max_rev = self.session.scalar(stmt)
        return (max_rev or 0) + 1

    def create_release_and_activate(
        self,
        release_id: str,
        brand_json: str,
        theme_json: str,
        navigation_json: str,
        pages_json: str,
        player_defaults_json: str,
        published_by: str = "admin",
        note: str = "",
        channel: str = "default",
    ) -> tuple[ExperienceRelease, ExperienceActivePointer]:
        next_rev = self._get_next_release_revision()

        release = ExperienceRelease(
            id=release_id,
            revision=next_rev,
            brand_json=brand_json,
            theme_json=theme_json,
            navigation_json=navigation_json,
            pages_json=pages_json,
            player_defaults_json=player_defaults_json,
            published_at=utcnow(),
            published_by=published_by,
            note=note,
        )
        self.session.add(release)
        self.session.flush()

        # 更新或创建激活指针
        pointer = self.session.scalar(
            select(ExperienceActivePointer).where(ExperienceActivePointer.channel == channel)
        )
        if pointer is None:
            pointer = ExperienceActivePointer(
                channel=channel,
                release_id=release.id,
                revision=release.revision,
                updated_at=utcnow(),
            )
            self.session.add(pointer)
        else:
            pointer.release_id = release.id
            pointer.revision = release.revision
            pointer.updated_at = utcnow()

        self.session.flush()
        return release, pointer
