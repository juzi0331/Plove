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
    # 优先使用真实拉到的分类
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
        
        # 新接入站点未在后台配置过时：默认全开前 3 个
        if is_new_config:
            show_home = (idx < 3)
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
    """计算应在首页以横幅展示的分类计划列表。

    规则：
    1. 若后台配置过规则，则选出所有 show_on_home=True 且未隐藏的分类，按 sort_order 升序排序；
    2. 若未配置过规则，默认兜底展示前 3 个未隐藏分类。
    """
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
        # 新站点兜底：取前 3 个有效未隐藏分类
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
            # 隐藏该分类
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
                    # 二级分类被隐藏，前台不展示
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

    # 追加后台手动配置且未隐藏的分类（支持新增自定义专区）
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

    # 按 sort_order 升序排序
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
        auto_select_fastest_line=bool(saved.get("auto_select_fastest_line", True)),
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
    if payload.auto_select_fastest_line is not None:
        saved["auto_select_fastest_line"] = bool(payload.auto_select_fastest_line)

    current.detail_policy_json = json.dumps(saved, ensure_ascii=False)
    session.flush()

    return SiteDetailPolicyPayload(
        site_key=key,
        ad_patterns=saved.get("ad_patterns", []),
        line_name_overrides=saved.get("line_name_overrides", {}),
        ep_naming_rule=saved.get("ep_naming_rule", "auto"),
        default_poster=saved.get("default_poster", ""),
        hide_fields=saved.get("hide_fields", []),
        auto_select_fastest_line=bool(saved.get("auto_select_fastest_line", True)),
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


_fastest_line_cache: dict[tuple[str, str], tuple[float, int]] = {}


def get_cached_fastest_line(key: str, vod_id: str) -> int | None:
    cached = _fastest_line_cache.get((key, vod_id))
    if cached:
        import time
        ts, line_id = cached
        if time.time() - ts < 600:  # 10 分钟缓存
            return line_id
    return None


def set_cached_fastest_line(key: str, vod_id: str, line_id: int) -> None:
    import time
    _fastest_line_cache[(key, vod_id)] = (time.time(), line_id)


def probe_and_select_fastest_line(
    key: str,
    detail: DetailPayload,
    registry: Any | None = None,
) -> int:
    """并发对影片的所有线路第 1 集进行测速，返回延迟最低的线路号。"""
    vod_id = detail.video.vod_id
    cached_line = get_cached_fastest_line(key, vod_id)
    available_line_ids = {line.line for line in detail.lines}
    if cached_line is not None and cached_line in available_line_ids:
        return cached_line

    fallback = detail.lines[0].line if detail.lines else 1
    if not registry or len(detail.lines) <= 1:
        return fallback

    import concurrent.futures
    import time
    import httpx
    from app.schemas.playback import Playback
    from app.services import catalog_service

    def _probe_line(line_info: Any) -> tuple[int, float]:
        line_id = line_info.line
        ep = next((e for e in detail.episodes if e.line == line_id), None)
        if not ep and detail.episodes:
            ep = detail.episodes[0]
        ep_index = ep.ep_index if ep else 1
        play_id = catalog_service._clean_play_id(ep.play_id) if ep and ep.play_id else None

        options: dict[str, Any] = {"id": vod_id, "ep": ep_index, "line": line_id}
        if play_id:
            options["play_id"] = play_id

        try:
            playback_obj = catalog_service._load(Playback, registry, key, "play", **options)
            url = playback_obj.url
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Range": "bytes=0-1024",
            }
            if playback_obj.headers:
                headers.update(playback_obj.headers)

            t0 = time.perf_counter()
            with httpx.Client(timeout=1.5, verify=False, follow_redirects=True) as client:
                resp = client.get(url, headers=headers)
                latency = time.perf_counter() - t0
                if resp.status_code < 400:
                    return line_id, latency
                return line_id, 900.0 + (resp.status_code / 10.0)
        except Exception:
            return line_id, 999.0

    best_line = fallback
    min_latency = 999.0
    try:
        candidate_lines = detail.lines[:8]
        max_workers = min(len(candidate_lines), 8)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_line = {executor.submit(_probe_line, line): line for line in candidate_lines}
            for future in concurrent.futures.as_completed(future_to_line, timeout=2.0):
                line_id, latency = future.result()
                if latency < min_latency:
                    min_latency = latency
                    best_line = line_id
    except Exception:
        pass

    set_cached_fastest_line(key, vod_id, best_line)
    return best_line


def apply_detail_policy(
    key: str,
    detail: DetailPayload,
    store: SiteSettingsStore,
    registry: SiteRegistry | None = None,
) -> DetailPayload:
    """清洗与格式化详情页数据，并按配置支持测速折叠多线路为单条最快线路。"""
    config = store.config(key)
    saved = _load_detail_policy_json(config.detail_policy_json)

    patterns: list[str] = saved.get("ad_patterns", [])
    line_overrides: dict[str, str] = saved.get("line_name_overrides", {})
    naming_rule: str = saved.get("ep_naming_rule", "auto")
    default_poster: str = saved.get("default_poster", "")
    hide_fields: set[str] = set(saved.get("hide_fields", []))
    auto_select: bool = bool(saved.get("auto_select_fastest_line", True))

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

    # 5. 后端测速优选单线路（如果有多条线路且开启了自动优选，折叠为单一极速线路）
    if auto_select and len(clean_lines) > 1:
        winner_line_id = probe_and_select_fastest_line(key, detail, registry)
        winner_line = next((l for l in clean_lines if l.line == winner_line_id), clean_lines[0])
        clean_lines = [winner_line.model_copy(update={"name": "极速专线"})]
        clean_episodes = [
            ep for ep in clean_episodes
            if ep.line is None or ep.line == winner_line_id
        ]

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
    from app.services import site_settings
    site_settings.store().refresh(db, force=True)
    return policy

