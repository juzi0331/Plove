#!/usr/bin/env python
"""xiaoyakankan.com（小鸭看看）单文件采集器适配器。

站点特征：
1. 页面为现代服务端渲染 HTML 模板；
2. 导航与二级子分类丰富：/cat/10.html（电影）、/cat/1001.html（动作片）等；
3. 视频卡片统一为 /post/<id>.html；
4. 详情页直接将播放器全部线路与全集直链内嵌在 `var pp = {...}` 变量中，
   包含真实 m3u8 直链，无需解密无需跳转即可秒播！
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler_kit import Client, CrawlerError, clean, cli, log, parse  # noqa: E402

KEY = "xiaoyakankan"
NAME = "小鸭看看"
BASE_URL = "https://xiaoyakankan.com"

# 静态内置主要分类（包含电影及其热门子分类、电视剧、动漫、综艺等）
CATEGORIES = [
    {"tid": "10", "name": "全部电影"},
    {"tid": "1001", "name": "动作片"},
    {"tid": "1002", "name": "喜剧片"},
    {"tid": "1003", "name": "爱情片"},
    {"tid": "1004", "name": "科幻片"},
    {"tid": "1005", "name": "恐怖片"},
    {"tid": "1006", "name": "剧情片"},
    {"tid": "1007", "name": "战争片"},
    {"tid": "1008", "name": "纪录片"},
    {"tid": "1009", "name": "微电影"},
    {"tid": "1010", "name": "动漫电影"},
    {"tid": "1011", "name": "奇幻片"},
    {"tid": "1012", "name": "动画片"},
    {"tid": "1013", "name": "犯罪片"},
    {"tid": "1014", "name": "悬疑片"},
    {"tid": "1015", "name": "欧美片"},
    {"tid": "1016", "name": "邵氏电影"},
    {"tid": "1017", "name": "同性片"},
    {"tid": "1018", "name": "家庭片"},
    {"tid": "1019", "name": "古装片"},
    {"tid": "1020", "name": "历史片"},
    {"tid": "1021", "name": "4K电影"},
    {"tid": "20", "name": "连续剧"},
    {"tid": "30", "name": "动漫"},
    {"tid": "40", "name": "综艺"},
    {"tid": "50", "name": "短剧"},
]


class Xiaoyakankan:
    key = KEY
    name = NAME
    version = "1.0.0"
    base_url = BASE_URL
    mode = "direct"

    def __init__(self) -> None:
        self.http = Client(
            base_url=self.base_url,
            timeout=15.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": self.base_url,
            },
        )

    def meta(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "version": self.version,
            "base_url": self.base_url,
            "mode": self.mode,
            "capabilities": ["meta", "home", "category", "detail", "play", "search"],
        }

    def home(self) -> dict[str, Any]:
        resp = self.http.get("/")
        if not resp.ok:
            raise CrawlerError("NETWORK_ERROR", f"请求首页失败: HTTP {resp.status}")

        root = parse.parse_html(resp.text)
        recommend = self._parse_card_list(root)

        return {
            "categories": CATEGORIES,
            "recommend": recommend[:30],
        }

    def category(self, tid: str, page: int = 1) -> dict[str, Any]:
        clean_tid = str(tid).strip()
        page_num = max(1, int(page))
        if page_num == 1:
            path = f"/cat/{clean_tid}.html"
        else:
            path = f"/cat/{clean_tid}/page/{page_num}.html"

        resp = self.http.get(path)
        if not resp.ok:
            raise CrawlerError("NETWORK_ERROR", f"获取分类 {tid} 第 {page} 页失败: HTTP {resp.status}")

        root = parse.parse_html(resp.text)
        videos = self._parse_card_list(root)
        has_more = len(videos) >= 12

        return {
            "videos": videos,
            "page": page_num,
            "has_more": has_more,
        }

    def detail(self, id: str) -> dict[str, Any]:
        clean_id = str(id).strip()
        if clean_id.startswith("http"):
            path = clean_id
        elif clean_id.startswith("/"):
            path = clean_id
        else:
            path = f"/post/{clean_id}.html"

        resp = self.http.get(path)
        if not resp.ok:
            raise CrawlerError("NETWORK_ERROR", f"获取详情页失败: {path} HTTP {resp.status}")

        html = resp.text
        root = parse.parse_html(html)

        # 1. 标题
        title = ""
        title_node = root.select_first("h1, .page-title, .title")
        if title_node:
            title = clean.clean_title(title_node.text)
        if not title:
            raw_title = root.select_first("title")
            if raw_title:
                title = clean.clean_title(raw_title.text.split("在线观看")[0].split("-")[0].strip())

        # 2. 封面图
        pic = ""
        img_node = root.select_first(".module-item-pic img, .detail-pic img, .cover img, img")
        if img_node:
            pic = img_node.attr("data-original") or img_node.attr("data-src") or img_node.attr("src") or ""
            pic = urllib.parse.urljoin(self.base_url, pic)

        # 3. 简介
        desc = ""
        desc_node = root.select_first(".video-info-content, .desc, .content, p.detail")
        if desc_node:
            desc = clean.clean_text(desc_node.text)

        # 4. 解析播放器线路与全集直链（从 var pp = {...} 提取）
        lines = []
        episodes = []
        pp_match = re.search(r"var\s+pp\s*=\s*(\{.*?\});", html)
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

        if not lines:
            lines = [{"line": "1", "name": "默认线路", "count": len(episodes)}]

        # 提炼实际 ID
        m_id = re.search(r"/post/([a-zA-Z0-9_-]+)\.html", path)
        final_id = m_id.group(1) if m_id else clean_id

        return {
            "video": {
                "vod_id": final_id,
                "vod_name": title or "未知影片",
                "vod_pic": pic,
                "vod_remarks": f"共{len(episodes)}集" if episodes else "",
            },
            "desc": desc,
            "episodes": episodes,
            "lines": lines,
        }

    def play(
        self,
        id: str | None = None,
        ep: int | str = 1,
        play_id: str | None = None,
        line: str | None = None,
    ) -> dict[str, Any]:
        # 如果 play_id 本身已经是 m3u8 直链，直接返回秒播
        if play_id and (".m3u8" in play_id or ".mp4" in play_id):
            return {
                "url": play_id,
                "format": "m3u8" if ".m3u8" in play_id else "mp4",
                "headers": {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Referer": self.base_url,
                },
            }

        # 否则通过 id 回溯详情页中的 var pp
        target_id = id or play_id
        if not target_id:
            raise CrawlerError("PARSE_ERROR", "play 缺少必要参数 id 或 play_id")

        det = self.detail(str(target_id))
        eps = det.get("episodes", [])
        if not eps:
            raise CrawlerError("PARSE_ERROR", f"未能从影片 {target_id} 中解析到播放直链")

        ep_idx = int(ep) - 1
        if 0 <= ep_idx < len(eps):
            stream_url = eps[ep_idx].get("play_id")
        else:
            stream_url = eps[0].get("play_id")

        return {
            "url": stream_url,
            "format": "m3u8",
            "headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": self.base_url,
            },
        }

    def search(self, keyword: str, page: int = 1) -> dict[str, Any]:
        resp = self.http.get(f"/search.html?wd={keyword}")
        if not resp.ok:
            return {"videos": [], "page": 1, "has_more": False}
        root = parse.parse_html(resp.text)
        videos = self._parse_card_list(root)
        return {"videos": videos, "page": 1, "has_more": False}

    def _parse_card_list(self, root: parse.HtmlNode) -> list[dict[str, Any]]:
        results = []
        seen = set()

        for a in root.select("a"):
            href = a.attr("href")
            if not href or not href.startswith("/post/"):
                continue

            m = re.search(r"/post/([a-zA-Z0-9_-]+)\.html", href)
            if not m:
                continue
            vod_id = m.group(1)
            if vod_id in seen:
                continue

            # 寻找标题与图片
            img = a.select_first("img")
            pic = ""
            if img:
                pic = img.attr("data-original") or img.attr("data-src") or img.attr("src") or ""
                pic = urllib.parse.urljoin(self.base_url, pic)

            title = clean.clean_title(a.attr("title") or (img.attr("alt") if img else "") or a.text)
            if not title:
                continue

            remarks = ""
            remarks_node = a.select_first(".module-item-text, .remarks, .badge, .pic-text")
            if remarks_node:
                remarks = clean.clean_text(remarks_node.text)

            seen.add(vod_id)
            results.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks,
            })
            if len(results) >= 36:
                break

        return results


if __name__ == "__main__":
    cli.main(Xiaoyakankan())
