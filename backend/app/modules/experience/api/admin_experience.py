"""管理后台前台体验与发布中心接口 (/api/v2/admin/experience)。

全部受管理员凭证保护。
"""

from __future__ import annotations

import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.core.middleware import get_request_id
from app.modules.experience.application.preview_draft import (
    preview_draft_bootstrap,
    preview_draft_page,
)
from app.modules.experience.application.publish_release import publish_experience_release
from app.modules.experience.application.rollback_release import rollback_experience_release
from app.modules.experience.application.save_draft import save_experience_draft
from app.modules.experience.infrastructure.sqlalchemy_experience_repository import (
    SqlAlchemyExperienceRepository,
)
from app.modules.experience.schemas.bootstrap import ClientBootstrapPayload, NavigationItem
from app.modules.experience.schemas.draft import (
    DraftSaveResult,
    ExperienceDraftPayload,
    ExperienceDraftUpdateRequest,
)
from app.modules.experience.schemas.page import PageDefinition, PageViewModel
from app.modules.experience.schemas.release import (
    ExperienceReleaseItem,
    ReleasePublishRequest,
    ReleasePublishResult,
    ReleaseRollbackRequest,
)
from app.modules.experience.schemas.theme import BrandConfig, PlayerDefaults, ThemeConfig
from app.schemas.envelope import Envelope, ok

router = APIRouter(
    prefix="/admin/experience",
    tags=["管理后台体验与发布"],
    dependencies=[Depends(require_admin)],
)


@router.get("/drafts/{draft_id}", response_model=Envelope[ExperienceDraftPayload], summary="读取指定体验草稿")
def get_draft(
    draft_id: str = "default",
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[ExperienceDraftPayload]:
    repo = SqlAlchemyExperienceRepository(db)
    draft = repo.get_or_create_draft(draft_id)

    brand_data = json.loads(draft.brand_json or "{}")
    theme_data = json.loads(draft.theme_json or "{}")
    nav_data = json.loads(draft.navigation_json or "[]")
    pages_data = json.loads(draft.pages_json or "{}")
    player_data = json.loads(draft.player_defaults_json or "{}")

    parsed_pages = {pid: PageDefinition(**pdef) for pid, pdef in pages_data.items()}

    payload = ExperienceDraftPayload(
        draft_id=draft.id,
        revision=draft.revision,
        brand=BrandConfig(**brand_data),
        theme=ThemeConfig(**theme_data),
        text={"home.title": "首页"},
        navigation=[NavigationItem(**item) for item in nav_data],
        pages=parsed_pages,
        player_defaults=PlayerDefaults(**player_data),
        updated_at=draft.updated_at.isoformat(),
        updated_by=draft.updated_by,
    )
    return ok(payload, request_id)


@router.put("/drafts/{draft_id}", response_model=Envelope[DraftSaveResult], summary="保存或更新体验草稿")
def update_draft(
    draft_id: str,
    body: ExperienceDraftUpdateRequest,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[DraftSaveResult]:
    result = save_experience_draft(session=db, draft_id=draft_id, req=body)
    return ok(result, request_id)


@router.get(
    "/drafts/{draft_id}/preview/bootstrap",
    response_model=Envelope[ClientBootstrapPayload],
    summary="预览草稿对应的客户端 Bootstrap 配置",
)
def get_preview_bootstrap(
    draft_id: str = "default",
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[ClientBootstrapPayload]:
    payload = preview_draft_bootstrap(db, draft_id)
    return ok(payload, request_id)


@router.get(
    "/drafts/{draft_id}/preview/pages/{page_id}",
    response_model=Envelope[PageViewModel],
    summary="预览草稿对应的页面视图模型",
)
def get_preview_page(
    draft_id: str = "default",
    page_id: str = "home_default",
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[PageViewModel]:
    payload = preview_draft_page(db, draft_id, page_id)
    return ok(payload, request_id)


@router.post(
    "/drafts/{draft_id}/publish",
    response_model=Envelope[ReleasePublishResult],
    summary="从草稿创建不可变发布快照并原子切换生效指针",
)
def publish_draft(
    draft_id: str = "default",
    body: ReleasePublishRequest | None = None,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[ReleasePublishResult]:
    note = body.note if body else ""
    result = publish_experience_release(session=db, draft_id=draft_id, note=note)
    return ok(result, request_id)


@router.get(
    "/releases",
    response_model=Envelope[list[ExperienceReleaseItem]],
    summary="获取历史发布快照列表与当前指针状态",
)
def list_releases(
    limit: int = Query(50, ge=1, le=100),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[list[ExperienceReleaseItem]]:
    repo = SqlAlchemyExperienceRepository(db)
    active_rel, pointer = repo.get_active_release()
    active_id = active_rel.id if active_rel else ""

    records = repo.list_releases(limit=limit)
    items = [
        ExperienceReleaseItem(
            release_id=r.id,
            revision=r.revision,
            published_at=r.published_at.isoformat(),
            published_by=r.published_by,
            note=r.note,
            is_active=(r.id == active_id),
        )
        for r in records
    ]
    return ok(items, request_id)


@router.post(
    "/releases/{release_id}/rollback",
    response_model=Envelope[ReleasePublishResult],
    summary="从指定历史发布快照安全回滚（生成更大 revision 的新发布）",
)
def rollback_release(
    release_id: str,
    body: ReleaseRollbackRequest | None = None,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[ReleasePublishResult]:
    note = body.note if body else ""
    target_id = (body.target_release_id if body and body.target_release_id else release_id)
    result = rollback_experience_release(session=db, target_release_id=target_id, note=note)
    return ok(result, request_id)
