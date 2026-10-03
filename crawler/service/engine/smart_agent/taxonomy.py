from __future__ import annotations

import re
import urllib.parse
from typing import Any

from ..extractor_html import HtmlNode, parse_html
from ...core.cleaner import collapse_whitespace, safe_resolve_url
from ...core.http_client import HttpClient


async def discover_taxonomy_tree(
    client: HttpClient, base_url: str, root: HtmlNode, html: str
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """智能探索站点的一级分类与二级子标签。"""
    anchors = root.select(
        "nav a, header a, .menu a, .navbar a, [class*='nav'] a, [class*='menu'] a, a"
    )
    discovered_primaries: list[dict[str, Any]] = []
    all_tags: list[dict[str, str]] = []
    seen_tids: set[str] = set()
    seen_tags: set[str] = set()

    cat_page_url = ""

    for a in anchors:
        href = (a.attr("href") or "").strip()
        text = collapse_whitespace(a.text)
        if not href or href == "#" or href.startswith("javascript:") or not text:
            continue
        if len(text) > 15:
            continue

        lower_t = text.lower()
        lower_h = href.lower()
        if any(
            x in lower_t or x in lower_h
            for x in [
                "app", "download", "login", "register", "vip", "pay", "order", "help",
                "telegram", "group", "feedback", "dizhi", "follows", "history", "search",
            ]
        ):
            continue

        if not cat_page_url and any(c in lower_h for c in ["/cat", "/tags", "/categories", "/category"]):
            cat_page_url = safe_resolve_url(base_url, href)

        if "/t/" in href or "/tag/" in href:
            tag_name = text.lstrip("#")
            m_tag = re.search(r"/(?:t|tag)/([^/?#]+)", href)
            if m_tag:
                try:
                    tag_name = urllib.parse.unquote(m_tag.group(1))
                except Exception:
                    pass
            if tag_name and tag_name not in seen_tags:
                seen_tags.add(tag_name)
                all_tags.append({
                    "tid": f"t/{tag_name}",
                    "type_id": f"t/{tag_name}",
                    "name": tag_name,
                    "type_name": tag_name,
                    "tag_name": tag_name,
                    "raw_href": href,
                })
            continue

        tid = ""
        m_type = re.search(r"/(?:type|vod/type/id|category|show|channel)/(\d+)", href)
        if m_type:
            tid = m_type.group(1)
        elif any(
            p == href or href.endswith(p)
            for p in ["/v", "/series", "/movie", "/tv", "/drama", "/dongman", "/zongyi"]
        ):
            tid = href.strip("/").split("/")[-1]
        elif text in (
            "影片", "视频", "劇集", "短剧", "电影", "电视剧", "动漫", "综艺",
            "國產AV", "探花", "自拍流出", "麻豆傳媒", "OnlyFans", "日本",
        ):
            tid = href.strip("/").replace("/", "_") or "1"

        if tid and tid not in seen_tids:
            seen_tids.add(tid)
            discovered_primaries.append({
                "tid": tid,
                "type_id": tid,
                "name": text,
                "type_name": text,
                "raw_href": href,
                "selected": True,
                "subcategories": [
                    {
                        "tid": tid,
                        "type_id": tid,
                        "name": f"全部{text}",
                        "type_name": f"全部{text}",
                        "selected": True,
                    }
                ],
            })

    if cat_page_url:
        try:
            cat_resp = await client.request("GET", cat_page_url)
            if cat_resp.status_code == 200:
                cat_root = parse_html(cat_resp.text)
                for a in cat_root.select('a[href*="/t/"], a[href*="/tag/"]'):
                    h = a.attr("href") or ""
                    t = collapse_whitespace(a.text)
                    m_t = re.search(r"/(?:t|tag)/([^/?#]+)", h)
                    name = urllib.parse.unquote(m_t.group(1)) if m_t else t.lstrip("#")
                    if name and name not in seen_tags and len(name) <= 12:
                        seen_tags.add(name)
                        all_tags.append({
                            "tid": f"t/{name}",
                            "type_id": f"t/{name}",
                            "name": name,
                            "type_name": name,
                            "raw_href": h,
                        })
        except Exception:
            pass

    unassigned_tags: list[dict[str, str]] = []
    assigned_tag_names: set[str] = set()

    for prim in discovered_primaries:
        p_name = prim["name"]
        for tag in all_tags:
            t_name = tag["name"]
            if t_name in assigned_tag_names:
                continue
            if (p_name in t_name or t_name in p_name) and t_name != p_name:
                prim["subcategories"].append({
                    "tid": tag["tid"],
                    "type_id": tag.get("type_id", tag["tid"]),
                    "name": t_name,
                    "type_name": t_name,
                    "selected": True,
                })
                assigned_tag_names.add(t_name)

    for tag in all_tags:
        if tag["name"] not in assigned_tag_names:
            unassigned_tags.append({
                "tid": tag.get("tid", ""),
                "type_id": tag.get("type_id", tag.get("tid", "")),
                "name": tag.get("name", ""),
                "type_name": tag.get("name", ""),
                "tag_name": tag.get("name", ""),
                "url_hint": tag.get("raw_href", ""),
            })

    return discovered_primaries, unassigned_tags[:80]


def extract_categories_heuristic(root: HtmlNode) -> list[dict[str, str]]:
    """启发式提取分类导航条目。"""
    categories = []
    seen_tids = set()

    patterns = [
        r"/type/(\d+)",
        r"/vod/type/id/(\d+)",
        r"/category/(\d+)",
        r"/show/(\d+)",
        r"tid=(\d+)",
    ]

    candidates = root.select("nav a, .nav a, .menu a, header a, .navbar a, a")
    for a in candidates:
        href = a.attr("href")
        text = collapse_whitespace(a.text)
        if not href or not text or len(text) > 8:
            continue
        if text in ("首页", "留言", "APP", "求片", "公告", "排行榜", "资讯"):
            continue

        for pat in patterns:
            m = re.search(pat, href)
            if m:
                tid = m.group(1)
                if tid not in seen_tids:
                    seen_tids.add(tid)
                    categories.append({"tid": tid, "name": text})
                break

        if len(categories) >= 8:
            break

    if not categories:
        categories = [
            {"tid": "1", "name": "电影"},
            {"tid": "2", "name": "连续剧"},
            {"tid": "3", "name": "综艺"},
            {"tid": "4", "name": "动漫"},
        ]
    return categories
