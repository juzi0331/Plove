"""站点详情页展示策略（广告过滤、线路映射、集数清洗、智能优选）。"""

from __future__ import annotations

import concurrent.futures
import json
import re
import time
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.security import is_safe_public_url

from app.crawler.registry import SiteRegistry
from app.schemas.admin_site_control import (
    SiteDetailPolicyPayload,
    SiteDetailPolicyUpdateRequest,
)
from app.schemas.catalog import DetailPayload
from app.services import site_settings
from app.services.site_settings import SiteSettingsStore


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
        ts, line_id = cached
        if time.time() - ts < 600:
            return line_id
    return None


def set_cached_fastest_line(key: str, vod_id: str, line_id: int) -> None:
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
            if not is_safe_public_url(url):
                return line_id, 999.0

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Range": "bytes=0-1024",
            }
            if playback_obj.headers:
                headers.update(playback_obj.headers)

            t0 = time.perf_counter()
            with httpx.Client(timeout=1.5, follow_redirects=False) as client:
                current_url = url
                resp = None
                for _ in range(3):
                    if not is_safe_public_url(current_url):
                        return line_id, 999.0
                    resp = client.get(current_url, headers=headers)
                    if resp.is_redirect:
                        loc = resp.headers.get("Location")
                        if not loc:
                            break
                        next_url = str(resp.url.join(loc))
                        if not is_safe_public_url(next_url):
                            return line_id, 999.0
                        current_url = next_url
                        continue
                    break

                if resp is None:
                    return line_id, 999.0
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

    desc = "" if "desc" in hide_fields else clean_text_with_patterns(detail.desc, patterns)

    clean_lines = []
    for line in detail.lines:
        orig_name = line.name or f"线路 {line.line}"
        mapped_name = line_overrides.get(orig_name, orig_name)
        clean_lines.append(line.model_copy(update={"name": mapped_name}))

    clean_episodes = []
    for ep in detail.episodes:
        ep_name = ep.ep_name or f"第 {ep.ep_index} 集"
        if naming_rule == "standard":
            ep_name = f"第 {ep.ep_index} 集"
        elif naming_rule == "auto":
            if vod_name and vod_name in ep_name:
                ep_name = ep_name.replace(vod_name, "").strip(" -_")
            ep_name = clean_text_with_patterns(ep_name, patterns)
            if not ep_name:
                ep_name = f"第 {ep.ep_index} 集"
        else:
            ep_name = clean_text_with_patterns(ep_name, patterns)

        clean_episodes.append(ep.model_copy(update={"ep_name": ep_name}))

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
