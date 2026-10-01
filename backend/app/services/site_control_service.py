"""站点分类控制与详情页清洗展示策略服务。

负责：
1. 站点分类与子分类的控制规则合并、保存与运行时过滤应用；
2. 详情页广告清洗、线路名称别名、集数格式化、海报兜底的策略应用。
"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.crawler.registry import SiteRegistry
from app.schemas.admin_site_control import (
    CategoryRuleItem,
    SiteCategoryRulePayload,
    SiteCategoryRuleUpdateRequest,
    SiteDetailPolicyPayload,
    SiteDetailPolicyUpdateRequest,
    SubCategoryItem,
)
from app.schemas.catalog import DetailPayload
from app.schemas.vod import SubCategory, VodCategory
from app.services import site_settings
from app.services.site_settings import SiteSettingsStore


# ------------------------------------------------------------------ 分类控制

def _load_cat_rules_json(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


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

    rules: list[CategoryRuleItem] = []
    # 优先使用真实拉到的分类
    seen_tids = set()
    for cat in real_categories:
        tid = str(cat.tid)
        seen_tids.add(tid)
        saved_item = saved_rules_map.get(tid, {})
        subcats = [
            SubCategoryItem(tid=str(s.get("tid")), name=str(s.get("name")))
            for s in saved_item.get("subcategories", [])
            if isinstance(s, dict) and "tid" in s
        ]
        if not subcats and cat.subcategories:
            subcats = [
                SubCategoryItem(tid=str(s.tid), name=str(s.name))
                for s in cat.subcategories
            ]
        rules.append(
            CategoryRuleItem(
                tid=tid,
                name=cat.name or tid,
                custom_name=str(saved_item.get("custom_name", "")),
                hidden=bool(saved_item.get("hidden", False)),
                sort_order=int(saved_item.get("sort_order", 0)),
                subcategories=subcats,
            )
        )

    # 补齐只在 saved 里的 tid（例如源站偶尔下架或不同页面抓到的）
    for tid, saved_item in saved_rules_map.items():
        if tid not in seen_tids:
            subcats = [
                SubCategoryItem(tid=str(s.get("tid")), name=str(s.get("name")))
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
                    subcategories=subcats,
                )
            )

    return SiteCategoryRulePayload(
        site_key=key,
        rules=rules,
        default_tid=saved.get("default_tid"),
    )


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
            # 隐藏该分类
            continue

        name = cat.name
        sort_order = 0
        subcategories: list[SubCategory] = list(cat.subcategories)

        if rule:
            custom_name = rule.get("custom_name", "").strip()
            if custom_name:
                name = custom_name
            sort_order = int(rule.get("sort_order", 0))
            subcats_raw = rule.get("subcategories")
            if isinstance(subcats_raw, list) and subcats_raw:
                subcategories = [
                    SubCategory(tid=str(s.get("tid")), name=str(s.get("name")))
                    for s in subcats_raw
                    if isinstance(s, dict) and s.get("tid")
                ]

        new_cat = VodCategory(tid=tid, name=name, subcategories=subcategories)
        result.append((sort_order, new_cat))

    # 追加后台手动配置且未隐藏的分类（支持新增自定义专区）
    for item in saved_rules_list:
        tid = str(item.get("tid", ""))
        if tid and tid not in seen_tids and not item.get("hidden"):
            subcategories = [
                SubCategory(tid=str(s.get("tid")), name=str(s.get("name")))
                for s in item.get("subcategories", [])
                if isinstance(s, dict) and s.get("tid")
            ]
            name = item.get("custom_name", "").strip() or item.get("name", tid)
            new_cat = VodCategory(tid=tid, name=name, subcategories=subcategories)
            result.append((int(item.get("sort_order", 0)), new_cat))

    # 按 sort_order 升序排序
    result.sort(key=lambda x: x[0])
    return [item[1] for item in result]


def check_category_allowed(key: str, tid: str | None, store: SiteSettingsStore) -> None:
    """若指定分类被后台禁用，直接拒绝访问。"""
    if not tid:
        return
    config = store.config(key)
    saved = _load_cat_rules_json(config.category_rules_json)
    rules_map = {
        str(item.get("tid")): item
        for item in saved.get("rules", [])
        if isinstance(item, dict) and item.get("tid")
    }
    rule = rules_map.get(str(tid))
    if rule and rule.get("hidden"):
        raise AppError(ErrorCode.FORBIDDEN, f"该分类已被停用: {tid}")


# ------------------------------------------------------------------ 详情页显示与清洗策略

def _load_detail_policy_json(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get_detail_policy_payload(store: SiteSettingsStore, key: str) -> SiteDetailPolicyPayload:
    """获取站点的详情页清洗策略。"""
    config = store.config(key)
    saved = _load_detail_policy_json(config.detail_policy_json)
    return SiteDetailPolicyPayload(
        site_key=key,
        ad_patterns=saved.get("ad_patterns", []),
        line_name_overrides=saved.get("line_name_overrides", {}),
        ep_naming_rule=saved.get("ep_naming_rule", "auto"),
        default_poster=saved.get("default_poster", ""),
        hide_fields=saved.get("hide_fields", []),
    )


def save_detail_policy_payload(
    session: Session,
    key: str,
    payload: SiteDetailPolicyUpdateRequest,
) -> SiteDetailPolicyPayload:
    """更新站点的详情页清洗策略。"""
    # 读现有合并
    current = site_settings.get_or_create(session, key)
    saved = _load_detail_policy_json(current.detail_policy_json)

    if payload.ad_patterns is not None:
        saved["ad_patterns"] = [p.strip() for p in payload.ad_patterns if p.strip()]
    if payload.line_name_overrides is not None:
        saved["line_name_overrides"] = payload.line_name_overrides
    if payload.ep_naming_rule is not None:
        saved["ep_naming_rule"] = payload.ep_naming_rule
    if payload.default_poster is not None:
        saved["default_poster"] = payload.default_poster.strip()
    if payload.hide_fields is not None:
        saved["hide_fields"] = payload.hide_fields

    current.detail_policy_json = json.dumps(saved, ensure_ascii=False)
    session.flush()

    return SiteDetailPolicyPayload(
        site_key=key,
        ad_patterns=saved.get("ad_patterns", []),
        line_name_overrides=saved.get("line_name_overrides", {}),
        ep_naming_rule=saved.get("ep_naming_rule", "auto"),
        default_poster=saved.get("default_poster", ""),
        hide_fields=saved.get("hide_fields", []),
    )


def clean_text_with_patterns(text: str, patterns: list[str]) -> str:
    """根据广告词/正则模式过滤文本。"""
    if not text or not patterns:
        return text
    result = text
    for pattern in patterns:
        if not pattern:
            continue
        try:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)
        except re.error:
            result = result.replace(pattern, "")
    return result.strip()


def apply_detail_policy(
    key: str,
    detail: DetailPayload,
    store: SiteSettingsStore,
) -> DetailPayload:
    """清洗与格式化详情页数据。"""
    config = store.config(key)
    saved = _load_detail_policy_json(config.detail_policy_json)
    if not saved:
        return detail

    patterns: list[str] = saved.get("ad_patterns", [])
    line_overrides: dict[str, str] = saved.get("line_name_overrides", {})
    naming_rule: str = saved.get("ep_naming_rule", "auto")
    default_poster: str = saved.get("default_poster", "")
    hide_fields: set[str] = set(saved.get("hide_fields", []))

    # 1. 清洗影片卡片基本信息
    v = detail.video
    vod_name = clean_text_with_patterns(v.vod_name, patterns)
    vod_remarks = clean_text_with_patterns(v.vod_remarks, patterns)
    vod_pic = v.vod_pic
    if default_poster and (not vod_pic or "placeholder" in vod_pic):
        vod_pic = default_poster

    vod_actor = None if "vod_actor" in hide_fields else clean_text_with_patterns(v.vod_actor or "", patterns) or None
    vod_director = (
        None if "vod_director" in hide_fields else clean_text_with_patterns(getattr(v, "vod_director", "") or "", patterns) or None
    )

    clean_video = v.model_copy(
        update={
            "vod_name": vod_name,
            "vod_remarks": vod_remarks,
            "vod_pic": vod_pic,
            "vod_actor": vod_actor,
        }
    )

    # 2. 清洗简介
    desc = "" if "desc" in hide_fields else clean_text_with_patterns(detail.desc, patterns)

    # 3. 清洗线路名称与映射
    clean_lines = []
    for line in detail.lines:
        orig_name = line.name or f"线路 {line.line}"
        mapped_name = line_overrides.get(orig_name, orig_name)
        clean_lines.append(line.model_copy(update={"name": mapped_name}))

    # 4. 清洗集数列表
    clean_episodes = []
    for ep in detail.episodes:
        ep_name = ep.ep_name or f"第 {ep.ep_index} 集"
        if naming_rule == "standard":
            ep_name = f"第 {ep.ep_index} 集"
        elif naming_rule == "auto":
            # 如果 ep_name 包含了完整剧名或过长，自动清洗
            if vod_name and vod_name in ep_name:
                ep_name = ep_name.replace(vod_name, "").strip(" -_")
            ep_name = clean_text_with_patterns(ep_name, patterns)
            if not ep_name:
                ep_name = f"第 {ep.ep_index} 集"
        else:
            ep_name = clean_text_with_patterns(ep_name, patterns)

        clean_episodes.append(ep.model_copy(update={"ep_name": ep_name}))

    return detail.model_copy(
        update={
            "video": clean_video,
            "desc": desc,
            "lines": clean_lines,
            "episodes": clean_episodes,
        }
    )


# ------------------------------------------------------------------ 单站缓存控制策略

from app.schemas.admin_extended import SiteCachePolicy


def get_site_cache_policy(store: SiteSettingsStore, key: str) -> SiteCachePolicy:
    """读取某站点的独立缓存策略。"""
    config = store.config(key)
    raw = getattr(config, "cache_policy_json", "{}")
    try:
        data = json.loads(raw or "{}")
        return SiteCachePolicy(**data)
    except Exception:
        return SiteCachePolicy()


def save_site_cache_policy(
    db: Session,
    key: str,
    policy: SiteCachePolicy,
) -> SiteCachePolicy:
    """持久化保存某站点的独立缓存策略。"""
    from app.db.session import commit_now
    from app.models.site_setting import SiteSetting

    setting = db.query(SiteSetting).filter_by(key=key).first()
    if not setting:
        setting = SiteSetting(key=key)
        db.add(setting)

    setting.cache_policy_json = policy.model_dump_json()
    commit_now(db)
    return policy

