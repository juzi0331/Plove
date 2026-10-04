"""站点分类与子分类规则控制逻辑。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.crawler.registry import SiteRegistry
from app.schemas.admin_site_control import (
    CategoryRuleItem,
    SiteCategoryRulePayload,
    SiteCategoryRuleUpdateRequest,
    SubCategoryItem,
)
from app.schemas.vod import SubCategory, VodCategory
from app.services import site_settings
from app.services.site_settings import SiteSettingsStore


def _load_cat_rules_json(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def format_category_display_name(raw_name: str, custom_name: str) -> str:
    """分类重命名规则：
    若填写了重命名（如"你好"），前端显示格式为"原名（你好）"；
    若未重命名则直接显示原名。
    """
    raw = (raw_name or "").strip()
    custom = (custom_name or "").strip()
    if not custom:
        return raw
    clean_custom = custom.strip("()（）")
    if not clean_custom:
        return raw
    return f"{raw}（{clean_custom}）"


def get_category_rules_payload(
    registry: SiteRegistry,
    store: SiteSettingsStore,
    key: str,
) -> SiteCategoryRulePayload:
    """获取某站点的分类控制配置。若库中未配置，则自动基于源站分类生成默认全开启规则。"""
    config = store.config(key)
    saved = _load_cat_rules_json(config.category_rules_json)
    saved_rules_map: dict[str, dict] = {
        item.get("tid"): item for item in saved.get("rules", []) if isinstance(item, dict) and item.get("tid")
    }

    # 尝试从源站拉一次分类作为基准
    real_categories: list[VodCategory] = []
    try:
        home_data = registry.run(key, "home")
        if isinstance(home_data, dict) and "categories" in home_data:
            real_categories = [
                VodCategory(**cat) for cat in home_data["categories"] if isinstance(cat, dict) and "tid" in cat
            ]
    except Exception:
        pass

    is_new_config = not saved.get("rules")
    rules: list[CategoryRuleItem] = []
    seen_tids = set()
    for idx, cat in enumerate(real_categories):
        tid = str(cat.tid)
        seen_tids.add(tid)
        saved_item = saved_rules_map.get(tid, {})
        subcats = [
            SubCategoryItem(
                tid=str(s.get("tid")),
                name=str(s.get("name")),
                custom_name=str(s.get("custom_name", "")),
                hidden=bool(s.get("hidden", False)),
            )
            for s in saved_item.get("subcategories", [])
            if isinstance(s, dict) and "tid" in s
        ]
        if not subcats and cat.subcategories:
            subcats = [
                SubCategoryItem(
                    tid=str(s.tid),
                    name=str(s.name),
                    custom_name="",
                    hidden=False,
                )
                for s in cat.subcategories
            ]

        if is_new_config:
            show_home = idx < 3
        else:
            show_home = bool(saved_item.get("show_on_home", False))

        rules.append(
            CategoryRuleItem(
                tid=tid,
                name=cat.name or tid,
                custom_name=str(saved_item.get("custom_name", "")),
                hidden=bool(saved_item.get("hidden", False)),
                sort_order=int(saved_item.get("sort_order", 0)),
                show_on_home=show_home,
                subcategories=subcats,
            )
        )

    # 补齐只在 saved 里的 tid（例如源站偶尔下架或不同页面抓到的）
    for tid, saved_item in saved_rules_map.items():
        if tid not in seen_tids:
            subcats = [
                SubCategoryItem(
                    tid=str(s.get("tid")),
                    name=str(s.get("name")),
                    custom_name=str(s.get("custom_name", "")),
                    hidden=bool(s.get("hidden", False)),
                )
                for s in saved_item.get("subcategories", [])
                if isinstance(s, dict) and "tid" in s
            ]
            rules.append(
                CategoryRuleItem(
                    tid=tid,
                    name=str(saved_item.get("name", tid)),
                    custom_name=str(saved_item.get("custom_name", "")),
                    hidden=bool(saved_item.get("hidden", False)),
                    sort_order=int(saved_item.get("sort_order", 0)),
                    show_on_home=bool(saved_item.get("show_on_home", False)),
                    subcategories=subcats,
                )
            )

    return SiteCategoryRulePayload(
        site_key=key,
        rules=rules,
        default_tid=saved.get("default_tid"),
    )


def get_home_display_category_plans(
    key: str,
    categories: list[VodCategory],
    store: SiteSettingsStore,
) -> list[dict[str, Any]]:
    """计算应在首页以横幅展示的分类计划列表。"""
    config = store.config(key)
    saved = _load_cat_rules_json(config.category_rules_json)
    saved_rules_list = saved.get("rules", [])

    plans: list[dict[str, Any]] = []

    if saved_rules_list:
        rules_map = {
            str(item.get("tid")): item
            for item in saved_rules_list
            if isinstance(item, dict) and item.get("tid")
        }
        for cat in categories:
            tid = str(cat.tid)
            rule = rules_map.get(tid)
            if not rule or rule.get("hidden"):
                continue
            if rule.get("show_on_home"):
                custom = str(rule.get("custom_name", "")).strip()
                title = format_category_display_name(cat.name or tid, custom)
                order = int(rule.get("sort_order", 0))
                plans.append({"tid": tid, "title": title, "order": order})
        plans.sort(key=lambda x: x["order"])
    else:
        for cat in categories[:3]:
            plans.append({
                "tid": str(cat.tid),
                "title": cat.name or str(cat.tid),
                "order": 0,
            })

    return plans


def save_category_rules_payload(
    session: Session,
    store: SiteSettingsStore,
    key: str,
    payload: SiteCategoryRuleUpdateRequest,
) -> SiteCategoryRulePayload:
    """保存分类控制规则。"""
    raw_dict = {
        "default_tid": payload.default_tid,
        "rules": [rule.model_dump() for rule in payload.rules],
    }
    rules_json = json.dumps(raw_dict, ensure_ascii=False)
    site_settings.update_category_rules(session, key, rules_json)
    return SiteCategoryRulePayload(
        site_key=key,
        rules=payload.rules,
        default_tid=payload.default_tid,
    )


def apply_category_rules(
    key: str,
    categories: list[VodCategory],
    store: SiteSettingsStore,
) -> list[VodCategory]:
    """在运行时过滤、重命名和重排序分类，并注入子分类。"""
    config = store.config(key)
    saved = _load_cat_rules_json(config.category_rules_json)
    saved_rules_list = saved.get("rules", [])
    if not saved_rules_list:
        return categories

    rules_map: dict[str, dict] = {
        str(item.get("tid")): item for item in saved_rules_list if isinstance(item, dict) and item.get("tid")
    }

    result: list[tuple[int, VodCategory]] = []
    seen_tids = set()
    for cat in categories:
        tid = str(cat.tid)
        seen_tids.add(tid)
        rule = rules_map.get(tid)
        if rule and rule.get("hidden"):
            continue

        raw_name = cat.name or tid
        name = raw_name
        sort_order = 0
        subcategories: list[SubCategory] = []

        if rule:
            custom_name = rule.get("custom_name", "")
            name = format_category_display_name(raw_name, custom_name)
            sort_order = int(rule.get("sort_order", 0))
            subcats_raw = rule.get("subcategories")
            if isinstance(subcats_raw, list) and subcats_raw:
                for s in subcats_raw:
                    if not isinstance(s, dict) or not s.get("tid"):
                        continue
                    if s.get("hidden"):
                        continue
                    s_raw_name = str(s.get("name", s.get("tid")))
                    s_custom = str(s.get("custom_name", ""))
                    subcategories.append(
                        SubCategory(
                            tid=str(s.get("tid")),
                            name=format_category_display_name(s_raw_name, s_custom),
                        )
                    )
            else:
                subcategories = list(cat.subcategories)
        else:
            subcategories = list(cat.subcategories)

        new_cat = VodCategory(tid=tid, name=name, subcategories=subcategories)
        result.append((sort_order, new_cat))

    for item in saved_rules_list:
        tid = str(item.get("tid", ""))
        if tid and tid not in seen_tids and not item.get("hidden"):
            subcategories = []
            for s in item.get("subcategories", []):
                if isinstance(s, dict) and s.get("tid") and not s.get("hidden"):
                    s_raw_name = str(s.get("name", s.get("tid")))
                    s_custom = str(s.get("custom_name", ""))
                    subcategories.append(
                        SubCategory(
                            tid=str(s.get("tid")),
                            name=format_category_display_name(s_raw_name, s_custom),
                        )
                    )
            cat_raw_name = str(item.get("name", tid))
            cat_custom = str(item.get("custom_name", ""))
            name = format_category_display_name(cat_raw_name, cat_custom)
            new_cat = VodCategory(tid=tid, name=name, subcategories=subcategories)
            result.append((int(item.get("sort_order", 0)), new_cat))

    result.sort(key=lambda x: x[0])
    return [item[1] for item in result]


def check_category_allowed(key: str, tid: str | None, store: SiteSettingsStore) -> None:
    """若指定分类或二级分类被后台禁用，直接拒绝访问。"""
    if not tid:
        return
    config = store.config(key)
    saved = _load_cat_rules_json(config.category_rules_json)
    target_tid = str(tid)
    for rule in saved.get("rules", []):
        if not isinstance(rule, dict):
            continue
        if str(rule.get("tid")) == target_tid and rule.get("hidden"):
            raise AppError(ErrorCode.FORBIDDEN, f"该分类已被停用: {tid}")
        for s in rule.get("subcategories", []):
            if isinstance(s, dict) and str(s.get("tid")) == target_tid and s.get("hidden"):
                raise AppError(ErrorCode.FORBIDDEN, f"该二级分类已被停用: {tid}")
