"""Python 采集器源码生成器。

生成符合 Plove 后端契约与安全审计的独立站点爬虫脚本（sites/<key>.py）。
必须满足：
1. 只能使用 crawler_kit + 标准库；
2. 退出码永远为 0，错误用 CrawlerError / ok:false 表达；
3. 输出纯 JSON 信封；
4. 类实现 meta, home, category, detail, play 规范方法。
"""

from __future__ import annotations

import pprint


def generate_crawler_python_code(
    key: str,
    name: str,
    base_url: str,
    mode: str = "direct",
    categories: list[dict[str, str]] | None = None,
    home_container: str = ".module-item, .v-item, .vodlist_item, li",
    detail_path: str = "/detail/{id}.html",
    play_regex: str = r"""https?://[^\s"'<>]+\.m3u8[^\s"'<>]*""",
) -> str:
    """根据提取的规则自动合成合规的单文件 Python 采集器脚本。"""
    class_name = "".join(part.capitalize() for part in key.split("_"))
    if not class_name:
        class_name = "CustomSite"

    cats_data = categories or [
        {"tid": "1", "name": "电影", "subcategories": [{"tid": "1", "name": "全部电影"}]},
        {"tid": "2", "name": "电视剧", "subcategories": [{"tid": "2", "name": "全部剧集"}]},
        {"tid": "3", "name": "动漫", "subcategories": [{"tid": "3", "name": "全部动漫"}]},
    ]
    cats_repr = pprint.pformat(cats_data, indent=4, width=100)

    raw_detail_path = (detail_path or "/detail/{id}.html").strip()
    if "{id}" not in raw_detail_path:
        raw_detail_path = raw_detail_path.rstrip("/") + "/{id}"
    formatted_detail_path = raw_detail_path.replace("{id}", "{{id}}")

    code_template = f'''#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""自动生成的采集器脚本: {name} ({key})。

由 Plove Spider Generator 自动生成并导出。
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler_kit import Client, CrawlerError, clean, cli, log, parse  # noqa: E402

KEY = "{key}"
NAME = "{name}"
BASE_URL = "{base_url}"
MODE = "{mode}"
CATEGORIES = {cats_repr}


class {class_name}:
    key = KEY
    name = NAME
    version = "1.0.0"
    base_url = BASE_URL
    mode = MODE
    capabilities = ("meta", "home", "category", "detail", "play")

    def __init__(self, client=None):
        self.http = client or Client(
            base_url=BASE_URL,
            timeout=12.0,
            retries=2,
            headers={{
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Referer": BASE_URL + "/",
            }},
        )

    def meta(self):
        return {{
            "key": self.key,
            "name": self.name,
            "version": self.version,
            "base_url": self.base_url,
            "mode": self.mode,
            "capabilities": list(self.capabilities),
        }}

    def home(self):
        resp = self.http.get("/")
        if not resp.ok:
            raise CrawlerError("HTTP_ERROR", f"首页响应异常 HTTP {{resp.status}}")

        root = parse.parse_html(resp.text)
        recommend = self._parse_items(root)
        return {{"categories": CATEGORIES, "recommend": recommend}}

    def category(self, tid, page=1):
        tid_str = str(tid or "").strip().strip("/")
        page_num = max(1, clean.to_int(page, 1) or 1)
        if tid_str.startswith("t/"):
            tag_quote = urllib.parse.quote(tid_str[2:])
            path = f"/t/{{tag_quote}}" + (f"?page={{page_num}}" if page_num > 1 else "")
        elif tid_str.isdigit():
            path = f"/type/{{tid_str}}-{{page_num}}.html"
        else:
            path = f"/{{tid_str}}" + (f"?page={{page_num}}" if page_num > 1 else "")

        resp = self.http.get(path)
        if not resp.ok:
            resp = self.http.get("/", params={{"tid": tid, "page": page_num}})

        root = parse.parse_html(resp.text)
        items = self._parse_items(root)
        return {{"videos": items, "page": page_num, "has_more": len(items) >= 12}}

    def detail(self, id):
        path = f"{formatted_detail_path}"
        resp = self.http.get(path)
        if not resp.ok:
            raise CrawlerError("NOT_FOUND", f"未找到影片详情 id={{id}}")

        root = parse.parse_html(resp.text)
        title_node = root.select_first("h1, .page-title, .title")
        vod_name = clean.clean_title(title_node.text) if title_node else f"影片 {{id}}"

        pic_node = root.select_first("img[src*='upload'], img[data-original], .cover img")
        pic = ""
        if pic_node:
            pic = pic_node.attr("data-original") or pic_node.attr("src") or ""
            if pic.startswith("/"):
                rel = clean.safe_relative_path(pic)
                pic = f"{{self.base_url}}{{rel}}" if rel else pic

        desc_node = root.select_first(".video-info-content, .desc, p.content")
        desc = clean.clean_text(desc_node.text) if desc_node else ""

        episodes = []
        links = root.select(".playlist a, .module-play-list-link, a[href*='/play/']")
        for idx, a in enumerate(links, start=1):
            ep_href = a.attr("href")
            ep_name = clean.clean_text(a.text) or f"第{{idx}}集"
            if ep_href and not ep_href.startswith("javascript"):
                episodes.append({{
                    "ep_index": idx,
                    "ep_name": ep_name,
                    "play_id": ep_href,
                    "line": "1",
                }})
            if len(episodes) >= 80:
                break

        return {{
            "video": {{
                "vod_id": str(id),
                "vod_name": vod_name,
                "vod_pic": pic,
                "vod_remarks": f"共 {{len(episodes)}} 集",
            }},
            "desc": desc,
            "episodes": episodes,
            "lines": [{{"line": "1", "name": "默认线路", "count": len(episodes)}}],
        }}

    def play(self, id=None, ep=1, play_id=None, line=None):
        target_path = play_id or f"/play/{{id}}-1-{{ep}}.html"
        resp = self.http.get(target_path)
        if not resp.ok:
            raise CrawlerError("HTTP_ERROR", f"播放页面响应异常 HTTP {{resp.status}}")

        # 正则提取 m3u8 地址
        m = re.search(r"""{play_regex}""", resp.text)
        if not m:
            raise CrawlerError("PARSE_ERROR", "未能从播放页中提取到有效视频流直链")

        stream_url = m.group(0).replace(r"\\/", "/")
        return {{
            "url": stream_url,
            "format": "m3u8",
            "headers": {{"Referer": self.base_url + "/"}},
        }}

    def _parse_items(self, root):
        items = []
        nodes = root.select("{home_container}")
        for n in nodes[:24]:
            a_tag = n if n.tag == "a" else n.select_first("a")
            if not a_tag:
                continue
            href = a_tag.attr("href")
            m = re.search(r"/(\\d+)\\.html", href)
            vod_id = m.group(1) if m else re.sub(r"[^\\w-]", "", href.strip("/"))
            if not vod_id:
                continue

            t_node = n.select_first(".title, h3, h4, a")
            title = clean.clean_title(t_node.text) if t_node else clean.clean_title(a_tag.attr("title"))
            if not title or len(title) < 2:
                continue

            img_node = n.select_first("img")
            pic = ""
            if img_node:
                pic = img_node.attr("data-original") or img_node.attr("src") or ""
                if pic.startswith("/"):
                    rel = clean.safe_relative_path(pic)
                    pic = f"{{self.base_url}}{{rel}}" if rel else pic

            items.append({{
                "vod_id": str(vod_id),
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "更新中",
            }})
        return items


if __name__ == "__main__":
    cli.main({class_name}())
'''
    return code_template
