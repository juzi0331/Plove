from __future__ import annotations

import json
import re
from typing import Any

from ..extractor_html import HtmlNode
from ...core.cleaner import clean_title, collapse_whitespace, safe_resolve_url


def default_detail_fields() -> list[dict[str, Any]]:
    """返回详情页标准采集字段模板。"""
    return [
        {"field": "vod_name", "field_key": "vod_name", "label": "影片名称 (vod_name)", "field_label": "影片名称 (vod_name)", "found": False, "sample": "", "detected_sample": "", "required": True, "selected": True, "tip": "片名，大厅展示与播放器核心显示（必须采集）"},
        {"field": "vod_pic", "field_key": "vod_pic", "label": "海报封面 (vod_pic)", "field_label": "海报封面 (vod_pic)", "found": False, "sample": "", "detected_sample": "", "required": True, "selected": True, "tip": "封面图片 URL（必须采集）"},
        {"field": "vod_remarks", "field_key": "vod_remarks", "label": "集数状态 (vod_remarks)", "field_label": "集数状态 (vod_remarks)", "found": False, "sample": "", "detected_sample": "", "required": False, "selected": True, "tip": "如'全12集'、'更新至第8集'、'1080P中字'"},
        {"field": "vod_year", "field_key": "vod_year", "label": "上映年份 (vod_year)", "field_label": "上映年份 (vod_year)", "found": False, "sample": "", "detected_sample": "", "required": False, "selected": False, "tip": "如 2026"},
        {"field": "vod_area", "field_key": "vod_area", "label": "制片地区 (vod_area)", "field_label": "制片地区 (vod_area)", "found": False, "sample": "", "detected_sample": "", "required": False, "selected": False, "tip": "如'中国大陆'、'日本'、'韩国'"},
        {"field": "vod_actor", "field_key": "vod_actor", "label": "主演演员 (vod_actor)", "field_label": "主演演员 (vod_actor)", "found": False, "sample": "", "detected_sample": "", "required": False, "selected": False, "tip": "主演名单字符串"},
        {"field": "vod_director", "field_key": "vod_director", "label": "导演主创 (vod_director)", "field_label": "导演主创 (vod_director)", "found": False, "sample": "", "detected_sample": "", "required": False, "selected": False, "tip": "导演名单字符串"},
        {"field": "vod_tag", "field_key": "vod_tag", "label": "分类题材 (vod_tag)", "field_label": "分类题材 (vod_tag)", "found": False, "sample": "", "detected_sample": "", "required": False, "selected": True, "tip": "类型标签，如'都市,爱情,科幻'"},
        {"field": "vod_content", "field_key": "vod_content", "label": "剧情简介 (vod_content)", "field_label": "剧情简介 (vod_content)", "found": False, "sample": "", "detected_sample": "", "required": False, "selected": True, "tip": "影片详细剧情描述"},
        {"field": "episodes", "field_key": "episodes", "label": "选集列表 (episodes)", "field_label": "选集列表 (episodes)", "found": False, "sample": "", "detected_sample": "", "required": True, "selected": True, "tip": "逐集定位符，包含集号与 play_id（必须采集）"},
        {"field": "lines", "field_key": "lines", "label": "播放线路 (lines)", "field_label": "播放线路 (lines)", "found": False, "sample": "", "detected_sample": "", "required": False, "selected": True, "tip": "多条播放源线路列表"},
    ]


def probe_detail_fields(
    base_url: str,
    vod_item: dict[str, Any],
    root: HtmlNode,
    detail_url: str,
    html_content: str,
) -> list[dict[str, Any]]:
    """深入详情页探测各项关键字段。"""
    fields = default_detail_fields()

    h1 = root.select_first("h1, .video-info-header h1, .title, .page-title")
    title = clean_title(h1.text) if h1 and h1.text else vod_item.get("vod_name", "")
    if not title:
        og_t = root.select_first('meta[property="og:title"]')
        if og_t:
            title = clean_title(og_t.attr("content"))
    if title:
        f = next((x for x in fields if x["field"] == "vod_name"), None)
        if f:
            f["found"] = True
            f["sample"] = title

    pic = vod_item.get("vod_pic", "")
    if not pic:
        og_img = root.select_first('meta[property="og:image"]')
        if og_img:
            pic = og_img.attr("content")
    if not pic:
        img = root.select_first(".video-cover img, .poster img, .pic img")
        if img:
            pic = img.attr("data-original") or img.attr("src")
    pic = safe_resolve_url(base_url, pic) if pic else ""
    if pic:
        f = next((x for x in fields if x["field"] == "vod_pic"), None)
        if f:
            f["found"] = True
            f["sample"] = pic

    remarks = vod_item.get("vod_remarks", "")
    if not remarks:
        for r_sel in [".remarks", ".badge", ".module-item-text", ".status"]:
            r_node = root.select_first(r_sel)
            if r_node and r_node.text:
                remarks = collapse_whitespace(r_node.text)
                break
    if remarks:
        f = next((x for x in fields if x["field"] == "vod_remarks"), None)
        if f:
            f["found"] = True
            f["sample"] = remarks
            f["selected"] = True

    year_m = re.search(r"\b(20\d\d|19\d\d)\b", html_content)
    if year_m:
        f = next((x for x in fields if x["field"] == "vod_year"), None)
        if f:
            f["found"] = True
            f["sample"] = year_m.group(1)
            f["selected"] = True

    for area in ["中国大陆", "大陆", "香港", "台湾", "日本", "韩国", "美国", "英国", "泰国"]:
        if area in html_content:
            f = next((x for x in fields if x["field"] == "vod_area"), None)
            if f:
                f["found"] = True
                f["sample"] = area
                f["selected"] = True
            break

    actor_m = re.search(r"(?:主演|演员|cast)[：:\s]+([^\n<]+)", html_content, re.IGNORECASE)
    if actor_m:
        f = next((x for x in fields if x["field"] == "vod_actor"), None)
        if f:
            f["found"] = True
            f["sample"] = collapse_whitespace(actor_m.group(1))[:60]
            f["selected"] = True

    dir_m = re.search(r"(?:导演|director)[：:\s]+([^\n<]+)", html_content, re.IGNORECASE)
    if dir_m:
        f = next((x for x in fields if x["field"] == "vod_director"), None)
        if f:
            f["found"] = True
            f["sample"] = collapse_whitespace(dir_m.group(1))[:40]
            f["selected"] = True

    tag_nodes = root.select('a[href*="/t/"], a[href*="/tag/"], .tag, .genre a')
    tags = [collapse_whitespace(t.text).lstrip("#") for t in tag_nodes if t.text]
    tags = [t for t in tags if t and len(t) <= 10][:8]
    if tags:
        f = next((x for x in fields if x["field"] == "vod_tag"), None)
        if f:
            f["found"] = True
            f["sample"] = ",".join(tags)
            f["selected"] = True

    desc_node = root.select_first(".video-info-content, .desc, .content, details, p.detail")
    if desc_node and desc_node.text:
        desc = collapse_whitespace(desc_node.text)
        if len(desc) > 10:
            f = next((x for x in fields if x["field"] == "vod_content"), None)
            if f:
                f["found"] = True
                f["sample"] = desc[:120] + "..." if len(desc) > 120 else desc
                f["selected"] = True

    ep_links = root.select("a[href*='/play/'], a[href*='/v/'], .module-play-list-link, .playlist a")
    if len(ep_links) >= 1:
        f = next((x for x in fields if x["field"] == "episodes"), None)
        if f:
            f["found"] = True
            f["sample"] = f"成功探测到 {len(ep_links)} 集选集入口"
            f["selected"] = True

    lines_tabs = root.select(".play-source-tab, .source-item, [class*='tab'] button")
    if len(lines_tabs) >= 1:
        f = next((x for x in fields if x["field"] == "lines"), None)
        if f:
            f["found"] = True
            f["sample"] = f"发现 {len(lines_tabs)} 条可选播放线路"
    for f in fields:
        f["detected_sample"] = f.get("sample", "")

    return fields


def extract_detail_heuristic(
    vod_item: dict[str, Any], root: HtmlNode, detail_url: str, html_content: str = ""
) -> dict[str, Any]:
    """启发式提取详情、选集与播放线路。"""
    desc = ""
    for sel in [".video-info-content", ".desc", ".content", ".plot", "#desc", "p.detail"]:
        dnode = root.select_first(sel)
        if dnode and len(dnode.text.strip()) > 10:
            desc = collapse_whitespace(dnode.text)
            break

    episodes: list[dict[str, Any]] = []
    lines: list[dict[str, Any]] = []

    # 检查是否包含内嵌 player 播放数据（如 var pp = {...}）
    if html_content:
        pp_match = re.search(r"var\s+pp\s*=\s*(\{.*?\});", html_content)
        if pp_match:
            try:
                pp_data = json.loads(pp_match.group(1))
                pp_lines = pp_data.get("lines", [])
                for l_idx, line_item in enumerate(pp_lines, start=1):
                    if isinstance(line_item, list) and len(line_item) >= 4:
                        line_id = str(line_item[0])
                        line_name = str(line_item[1])
                        urls = line_item[3] if isinstance(line_item[3], list) else []
                        lines.append({"line": line_id, "name": line_name, "count": len(urls)})
                        if l_idx == 1:
                            for ep_idx, ep_url in enumerate(urls, start=1):
                                episodes.append({
                                    "ep_index": ep_idx,
                                    "ep_name": f"第{ep_idx}集",
                                    "play_id": ep_url,
                                    "line": line_id,
                                })
            except Exception:
                pass

    # 若未从脚本中提取到剧集，从普通链接提取
    if not episodes:
        ep_links = root.select(".module-play-list-link, .playlist a, .urlli a, a[href*='/play/']")
        for idx, ep_a in enumerate(ep_links, start=1):
            ep_href = ep_a.attr("href")
            ep_name = collapse_whitespace(ep_a.text) or f"第{idx}集"
            if ep_href and not ep_href.startswith("javascript"):
                episodes.append({
                    "ep_index": idx,
                    "ep_name": ep_name,
                    "play_id": ep_href,
                    "line": "1",
                })
            if len(episodes) >= 80:
                break

    if not lines:
        lines = [{"line": "1", "name": "默认线路", "count": len(episodes)}]

    return {
        "video": {
            "vod_id": vod_item["vod_id"],
            "vod_name": vod_item["vod_name"],
            "vod_pic": vod_item["vod_pic"],
            "vod_remarks": vod_item["vod_remarks"] or f"共{len(episodes)}集",
        },
        "desc": desc,
        "episodes": episodes,
        "lines": lines,
    }
