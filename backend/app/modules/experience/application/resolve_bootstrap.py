"""解析并组装客户端启动基础配置 (Bootstrap) 用例。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.modules.experience.infrastructure.sqlalchemy_experience_repository import (
    SqlAlchemyExperienceRepository,
    get_default_experience_data,
)
from app.modules.experience.schemas.bootstrap import (
    ClientBootstrapPayload,
    NavigationItem,
    ReleaseCurrentPayload,
)
from app.modules.experience.schemas.theme import BrandConfig, PlayerDefaults, ThemeConfig


def _ensure_active_release(repo: SqlAlchemyExperienceRepository) -> Any:
    """确保至少存在一个激活的发布快照。若没有则从默认数据直接发布首版。"""
    release, pointer = repo.get_active_release()
    if release is not None and pointer is not None:
        return release

    defaults = get_default_experience_data()
    rel_id = f"exp_init_{int(datetime.now().timestamp())}"
    release, _ = repo.create_release_and_activate(
        release_id=rel_id,
        brand_json=json.dumps(defaults["brand"], ensure_ascii=False),
        theme_json=json.dumps(defaults["theme"], ensure_ascii=False),
        navigation_json=json.dumps(defaults["navigation"], ensure_ascii=False),
        pages_json=json.dumps(defaults["pages"], ensure_ascii=False),
        player_defaults_json=json.dumps(defaults["player_defaults"], ensure_ascii=False),
        published_by="system",
        note="系统初始化出厂配置",
    )
    return release


def resolve_client_bootstrap(session: Session) -> ClientBootstrapPayload:
    """读取当前全站发布的品牌、主题 Token、导航与播放偏好。"""
    repo = SqlAlchemyExperienceRepository(session)
    release = _ensure_active_release(repo)

    brand_data = json.loads(release.brand_json or "{}")
    theme_data = json.loads(release.theme_json or "{}")
    nav_data = json.loads(release.navigation_json or "[]")
    player_data = json.loads(release.player_defaults_json or "{}")

    # 全局文案提取
    defaults = get_default_experience_data()
    text_data = defaults.get("text", {})

    return ClientBootstrapPayload(
        schema_version="1.0",
        release_id=release.id,
        revision=release.revision,
        refresh_after_seconds=30,
        offline_display_ttl_seconds=86400,
        brand=BrandConfig(**brand_data),
        theme=ThemeConfig(**theme_data),
        text=text_data,
        navigation=[NavigationItem(**item) for item in nav_data],
        player_defaults=PlayerDefaults(**player_data),
    )


def resolve_current_release_info(session: Session) -> ReleaseCurrentPayload:
    """查询当前发布版本状态，用于高频条件轮询。"""
    repo = SqlAlchemyExperienceRepository(session)
    release = _ensure_active_release(repo)

    return ReleaseCurrentPayload(
        release_id=release.id,
        revision=release.revision,
        published_at=release.published_at.isoformat(),
    )
