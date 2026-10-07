"""构建页面 ViewModel 用例。

将服务端已解析的内容与后台配置的有序区块组合为 ViewModel。
前端按 sections[] 顺序直接渲染，不再自行裁剪或合成第二套规则。
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.cache.content import ContentCache
from app.core.errors import AppError, ErrorCode
from app.crawler.registry import SiteRegistry
from app.modules.experience.application.resolve_bootstrap import _ensure_active_release
from app.modules.experience.infrastructure.sqlalchemy_experience_repository import (
    SqlAlchemyExperienceRepository,
)
from app.modules.experience.schemas.components import (
    ActionPayload,
    SectionBadge,
    SectionDefinition,
    SectionItem,
)
from app.modules.experience.schemas.page import PageViewModel
from app.services import catalog_service


def _extract_vod_to_section_item(vod: Any) -> SectionItem:
    """将 Catalog VodItem 或字典转换为前台 SectionItem。"""
    if hasattr(vod, "vod_id"):
        vod_id = str(vod.vod_id)
        title = getattr(vod, "vod_name", "无标题")
        subtitle = getattr(vod, "vod_remarks", "")
        pic = getattr(vod, "vod_pic", "")
    elif isinstance(vod, dict):
        vod_id = str(vod.get("vod_id", ""))
        title = vod.get("vod_name", "无标题")
        subtitle = vod.get("vod_remarks", "")
        pic = vod.get("vod_pic", "")
    else:
        vod_id = "0"
        title = "示例影片"
        subtitle = ""
        pic = ""

    return SectionItem(
        content_id=vod_id,
        title=title,
        subtitle=subtitle,
        poster_url=pic,
        fallback_asset_id="poster_default",
        badge=SectionBadge(text=subtitle, tone="primary") if subtitle else None,
        action=ActionPayload(type="open_detail", content_id=vod_id),
    )


def build_page_view_model(
    session: Session,
    page_id: str = "home_default",
    release_id: str | None = None,
    registry: SiteRegistry | None = None,
    cache: ContentCache | None = None,
) -> PageViewModel:
    """根据指定发布快照与内容源组装完整的 PageViewModel。"""
    repo = SqlAlchemyExperienceRepository(session)

    if release_id:
        release = repo.get_release(release_id)
        if release is None:
            raise AppError(ErrorCode.NOT_FOUND, f"发布版本未找到: {release_id}")
    else:
        release = _ensure_active_release(repo)

    pages_map = json.loads(release.pages_json or "{}")
    # 兼容别名映射
    actual_page_id = "home_default" if page_id in ("home", "home_default") else page_id
    page_cfg = pages_map.get(actual_page_id)
    if not page_cfg:
        # 回退内置默认配置
        from app.modules.experience.infrastructure.sqlalchemy_experience_repository import (
            get_default_experience_data,
        )
        defaults = get_default_experience_data()
        page_cfg = defaults["pages"].get("home_default", {"id": actual_page_id, "title": "页面", "sections": []})

    title = page_cfg.get("title", "页面")
    raw_sections = page_cfg.get("sections", [])

    # 尝试从 Catalog 获取真实数据供页面绑定
    catalog_items: list[Any] = []
    if registry is not None and cache is not None:
        try:
            enabled_sites = registry.list_enabled()
            if enabled_sites:
                primary_site = enabled_sites[0].key
                home_data = catalog_service.home(registry, cache, primary_site)
                if home_data and home_data.sections:
                    for sec in home_data.sections:
                        catalog_items.extend(sec.items)
        except Exception:
            pass

    resolved_sections: list[SectionDefinition] = []
    for sec_data in raw_sections:
        sec_id = sec_data.get("id", "sec")
        component = sec_data.get("component", "empty_state")
        comp_ver = sec_data.get("component_version", 1)
        style = sec_data.get("style", {})
        props = dict(sec_data.get("props", {}))

        # 为 hero 和 video_rail 补充真实或示例数据
        if component == "hero":
            # 如果 props 中没有指定 poster，用 catalog 头部数据
            if not props.get("poster_url") and catalog_items:
                top_item = catalog_items[0]
                item_obj = _extract_vod_to_section_item(top_item)
                props["content_id"] = item_obj.content_id
                props["title"] = props.get("title") or item_obj.title
                props["subtitle"] = props.get("subtitle") or item_obj.subtitle
                props["poster_url"] = item_obj.poster_url
                props["action"] = item_obj.action.model_dump() if item_obj.action else {"type": "open_home"}
        elif component in ("video_rail", "video_grid"):
            existing_items = props.get("items", [])
            if not existing_items and catalog_items:
                # 绑定 catalog 数据
                slice_items = catalog_items[:12] if component == "video_rail" else catalog_items[12:28]
                if not slice_items:
                    slice_items = catalog_items[:10]
                props["items"] = [_extract_vod_to_section_item(v).model_dump() for v in slice_items]

        resolved_sections.append(
            SectionDefinition(
                id=sec_id,
                component=component,
                component_version=comp_ver,
                style=style,
                props=props,
            )
        )

    return PageViewModel(
        schema_version="1.0",
        release_id=release.id,
        page_id=actual_page_id,
        title=title,
        content_revision=str(release.revision),
        sections=resolved_sections,
    )
