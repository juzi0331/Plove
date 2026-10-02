"""智能自适应采集器（Smart Auto-Discovery Scraper）。

核心理念：
用户只需输入一个目标站点的主页 URL，剩下的全部自动化：
1. 自动连接探测（自动探测编码、自动破解反爬闸门）；
2. 自动识别站点名称、提取导航分类；
3. 启发式聚类挖掘首页推荐视频卡片（图片、标题、ID、状态）；
4. 自动深入采集样本影片详情（剧情、选集列表）；
5. 自动嗅探第一集播放页面，正则提取真实 m3u8/mp4 视频流；
6. 自动推导并生成可长久复用的 SiteRule 配置。
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional
from pydantic import BaseModel, Field

from .code_generator import generate_crawler_python_code
from .extractor_html import HtmlNode, parse_html
from .models import SiteRule
from ..core.cleaner import clean_title, collapse_whitespace, is_placeholder_image, safe_resolve_url
from ..core.http_client import HttpClient
from ..core.log import get_logger

logger = get_logger("smart_agent")

_M3U8_REGEX = re.compile(r"""(?:["']|\b)(https?://[^\s"'<>]+\.m3u8[^\s"'<>]*)(?:["']|\b)""", re.IGNORECASE)
_MP4_REGEX = re.compile(r"""(?:["']|\b)(https?://[^\s"'<>]+\.mp4[^\s"'<>]*)(?:["']|\b)""", re.IGNORECASE)


class SmartExploreResult(BaseModel):
    base_url: str
    site_name: str
    suggested_key: str
    data_type: str
    categories: list[dict[str, Any]]
    recommend: list[dict[str, Any]]
    sample_detail: Optional[dict[str, Any]] = None
    sample_stream: Optional[dict[str, Any]] = None
    generated_rule: dict[str, Any]
    generated_python_code: str = ""
    steps_log: list[str]


class StructureInspectionResult(BaseModel):
    base_url: str
    site_name: str
    suggested_key: str
    categories_tree: list[dict[str, Any]]
    unassigned_tags: list[dict[str, str]]
    unassigned_tags_pool: list[dict[str, str]] = Field(default_factory=list)
    detail_fields: list[dict[str, Any]]
    sample_video: Optional[dict[str, Any]] = None
    html_preview: str = ""
    steps_log: list[str] = Field(default_factory=list)




class SmartAgent:
    """自动探测引擎。"""

    def __init__(self, target_url: str) -> None:
        self.target_url = target_url.strip()
        parsed = urllib.parse.urlparse(self.target_url)
        if not parsed.scheme:
            self.target_url = f"https://{self.target_url}"
            parsed = urllib.parse.urlparse(self.target_url)
        self.base_url = f"{parsed.scheme}://{parsed.netloc}"
        # 生成简易 key，例如 kkys01.com -> kkys01
        domain_parts = parsed.netloc.split(":")[0].split(".")
        clean_key = domain_parts[-2] if len(domain_parts) >= 2 else domain_parts[0]
        self.suggested_key = re.sub(r"[^a-zA-Z0-9_]", "", clean_key).lower()
        if not self.suggested_key or not self.suggested_key[0].isalpha():
            self.suggested_key = f"site_{self.suggested_key}"
        self.logs: list[str] = []

    def log(self, msg: str) -> None:
        self.logs.append(msg)
        logger.info("[SmartAgent] %s", msg)

    async def _resolve_entry_page(self, client: HttpClient, target_url: str) -> tuple[str, HtmlNode]:
        """请求目标页面，若遇到门禁页/过渡页/欢迎页（如未成年警告、仅有几个引导链接），自动跟踪进入主入口。"""
        resp = await client.request("GET", target_url)
        self.log(f"源站响应状态码: {resp.status_code}")
        html = resp.text
        root = parse_html(html)

        anchors = root.select("a")
        # 若页面超链接极少 (<= 6 个)，检测是否为门禁/过渡页
        if len(anchors) <= 6:
            for a in anchors:
                h = (a.attr("href") or "").strip()
                t = collapse_whitespace(a.text)
                if not h or h == "#" or h.startswith("javascript:"):
                    continue
                if any(w in t for w in ["进入", "進入", "18", "滿", "满", "成年", "agree", "enter", "continue", "首页", "首頁"]) or h in ("/home", "/index.html", "/main"):
                    if not h.startswith("http") or any(dom in h for dom in (self.base_url, self.suggested_key)):
                        next_url = safe_resolve_url(self.base_url, h)
                        self.log(f"检测到网站引导/准入过渡页，自动跟踪至主入口: {next_url}")
                        try:
                            next_resp = await client.request("GET", next_url)
                            if next_resp.status_code == 200 and len(next_resp.text) > len(html):
                                return next_resp.text, parse_html(next_resp.text)
                        except Exception as exc:
                            self.log(f"跟踪主入口异常: {exc}")
                        break
        return html, root

    async def explore(self) -> SmartExploreResult:
        self.log(f"开始连接目标站点: {self.target_url}")
        async with HttpClient(base_url=self.base_url) as client:
            html, root = await self._resolve_entry_page(client, self.target_url)

            # 探测是 JSON 还是 HTML
            text_body = html
            if text_body.strip().startswith("{") and text_body.strip().endswith("}"):
                self.log("检测到目标站为纯 JSON API 接口")
                return await self._explore_json(json.loads(text_body))
            else:
                self.log("检测到目标站为 HTML 网页形态，启动智能 DOM 聚类分析")
                return await self._explore_html(client, text_body)

    async def inspect_structure(self) -> StructureInspectionResult:
        """对目标站点进行可视化探测勘探：
        1. 探测站点名称与推荐主页卡片
        2. 扫描并归纳一级分类与二级子标签树
        3. 深入样本详情页，探测各项关键字段（片名、海报、状态、年份、地区、演员、导演、标签、简介、选集、线路）
        4. 返回供前端可视化展示与勾选的完整结构
        """
        self.log(f"启动可视化结构勘探: {self.target_url}")
        async with HttpClient(base_url=self.base_url) as client:
            html, root = await self._resolve_entry_page(client, self.target_url)

            # 1. 站点名称
            og_site = root.select_first("meta[property='og:site_name'], meta[name='og:site_name']")
            if og_site and og_site.attr("content"):
                site_name = clean_title(og_site.attr("content").split(",")[0].split("-")[0].split("_")[0]) or self.suggested_key
            else:
                title_node = root.select_first("title")
                raw_title = title_node.text if title_node else self.suggested_key
                site_name = clean_title(raw_title.split("-")[0].split("_")[0].split("|")[0]) or self.suggested_key

            # 2. 深度导航与标签树勘探
            categories_tree, unassigned_tags = await self._discover_taxonomy_tree(client, root, html)
            self.log(f"识别出 {len(categories_tree)} 个候选一级分类，{len(unassigned_tags)} 个标签候选项")

            # 3. 采样详情页字段探测
            recommend = self._extract_vod_list_heuristic(root, categories=categories_tree)
            sample_video = recommend[0] if recommend else None
            detail_fields = self._default_detail_fields()

            if sample_video and sample_video.get("raw_href"):
                detail_url = safe_resolve_url(self.base_url, sample_video["raw_href"])
                self.log(f"采样详情页深入探测: {detail_url}")
                try:
                    detail_resp = await client.request("GET", detail_url)
                    detail_html = detail_resp.text
                    detail_root = parse_html(detail_html)
                    detail_fields = self._probe_detail_fields(sample_video, detail_root, detail_url, detail_html)
                except Exception as exc:
                    self.log(f"采样详情页探测异常: {exc}")

            return StructureInspectionResult(
                base_url=self.base_url,
                site_name=site_name,
                suggested_key=self.suggested_key,
                categories_tree=categories_tree,
                unassigned_tags=unassigned_tags,
                unassigned_tags_pool=unassigned_tags,
                detail_fields=detail_fields,
                sample_video=sample_video,
                html_preview=html[:3000],
                steps_log=self.logs,
            )

    async def _discover_taxonomy_tree(
        self, client: HttpClient, root: HtmlNode, html: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        """智能探索站点的一级分类与二级子标签。"""
        anchors = root.select("nav a, header a, .menu a, .navbar a, [class*='nav'] a, [class*='menu'] a, a")
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
            if any(x in lower_t or x in lower_h for x in [
                "app", "download", "login", "register", "vip", "pay", "order", "help",
                "telegram", "group", "feedback", "dizhi", "follows", "history", "search"
            ]):
                continue

            if not cat_page_url and any(c in lower_h for c in ["/cat", "/tags", "/categories", "/category"]):
                cat_page_url = safe_resolve_url(self.base_url, href)

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
            elif any(p == href or href.endswith(p) for p in ["/v", "/series", "/movie", "/tv", "/drama", "/dongman", "/zongyi"]):
                tid = href.strip("/").split("/")[-1]
            elif text in ("影片", "视频", "劇集", "短剧", "电影", "电视剧", "动漫", "综艺", "國產AV", "探花", "自拍流出", "麻豆傳媒", "OnlyFans", "日本"):
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
                    "subcategories": [{"tid": tid, "type_id": tid, "name": f"全部{text}", "type_name": f"全部{text}", "selected": True}],
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
                                "raw_href": h
                            })
            except Exception:
                pass

        if not discovered_primaries:
            discovered_primaries = [
                {
                    "tid": "1", "type_id": "1", "name": "电影", "type_name": "电影", "raw_href": "/type/1.html", "selected": True,
                    "subcategories": [
                        {"tid": "1", "type_id": "1", "name": "全部电影", "type_name": "全部电影", "selected": True},
                        {"tid": "101", "type_id": "101", "name": "动作片", "type_name": "动作片", "selected": True},
                        {"tid": "102", "type_id": "102", "name": "喜剧片", "type_name": "喜剧片", "selected": True},
                        {"tid": "103", "type_id": "103", "name": "爱情片", "type_name": "爱情片", "selected": True},
                        {"tid": "104", "type_id": "104", "name": "科幻片", "type_name": "科幻片", "selected": True},
                    ]
                },
                {
                    "tid": "2", "type_id": "2", "name": "电视剧", "type_name": "电视剧", "raw_href": "/type/2.html", "selected": True,
                    "subcategories": [
                        {"tid": "2", "type_id": "2", "name": "全部剧集", "type_name": "全部剧集", "selected": True},
                        {"tid": "201", "type_id": "201", "name": "国产剧", "type_name": "国产剧", "selected": True},
                        {"tid": "202", "type_id": "202", "name": "欧美剧", "type_name": "欧美剧", "selected": True},
                        {"tid": "203", "type_id": "203", "name": "日韩剧", "type_name": "日韩剧", "selected": True},
                    ]
                },
                {
                    "tid": "3", "type_id": "3", "name": "动漫", "type_name": "动漫", "raw_href": "/type/3.html", "selected": True,
                    "subcategories": [
                        {"tid": "3", "type_id": "3", "name": "全部动漫", "type_name": "全部动漫", "selected": True},
                        {"tid": "301", "type_id": "301", "name": "国漫", "type_name": "国漫", "selected": True},
                        {"tid": "302", "type_id": "302", "name": "日漫", "type_name": "日漫", "selected": True},
                    ]
                },
                {
                    "tid": "4", "type_id": "4", "name": "综艺", "type_name": "综艺", "raw_href": "/type/4.html", "selected": True,
                    "subcategories": [
                        {"tid": "4", "type_id": "4", "name": "全部综艺", "type_name": "全部综艺", "selected": True},
                        {"tid": "401", "type_id": "401", "name": "大陆综艺", "type_name": "大陆综艺", "selected": True},
                    ]
                },
            ]

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
                        "selected": True
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

    def _default_detail_fields(self) -> list[dict[str, Any]]:
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

    def _probe_detail_fields(
        self, vod_item: dict[str, Any], root: HtmlNode, detail_url: str, html_content: str
    ) -> list[dict[str, Any]]:
        fields = self._default_detail_fields()

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
        pic = safe_resolve_url(self.base_url, pic) if pic else ""
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

    async def _explore_html(self, client: HttpClient, html: str) -> SmartExploreResult:
        root = parse_html(html)

        # 1. 站点名称推测
        og_site = root.select_first("meta[property='og:site_name'], meta[name='og:site_name']")
        if og_site and og_site.attr("content"):
            site_name = clean_title(og_site.attr("content").split(",")[0].split("-")[0].split("_")[0]) or self.suggested_key
        else:
            title_node = root.select_first("title")
            raw_title = title_node.text if title_node else self.suggested_key
            site_name = clean_title(raw_title.split("-")[0].split("_")[0].split("|")[0]) or self.suggested_key
        self.log(f"推断站点名称: {site_name}")

        # 2. 启发式提取分类
        categories = self._extract_categories_heuristic(root)
        self.log(f"自动发现 {len(categories)} 个分类导航条目")

        # 3. 启发式聚类提取首页视频列表
        recommend = self._extract_vod_list_heuristic(root, categories=categories)
        self.log(f"自动发现 {len(recommend)} 部首页推荐视频")

        sample_detail = None
        sample_stream = None

        # 4. 深入第一部影片获取详情与播放地址
        if recommend:
            first_vod = recommend[0]
            vod_href = first_vod.get("raw_href")
            if vod_href:
                detail_url = safe_resolve_url(self.base_url, vod_href)
                self.log(f"深入探索样本详情页: {detail_url}")
                try:
                    detail_html = await client.get_text(detail_url)
                    detail_root = parse_html(detail_html)
                    sample_detail = self._extract_detail_heuristic(first_vod, detail_root, detail_url, html_content=detail_html)
                    self.log(f"成功提取详情: 《{sample_detail['video']['vod_name']}》，共 {len(sample_detail['episodes'])} 集")

                    # 5. 深入第一集探测播放流
                    if sample_detail["episodes"]:
                        first_ep = sample_detail["episodes"][0]
                        play_href = first_ep.get("play_id")
                        if play_href and play_href.startswith("/"):
                            play_url = safe_resolve_url(self.base_url, play_href)
                            self.log(f"深入嗅探第 1 集播放流页面: {play_url}")
                            play_html = await client.get_text(play_url)
                            sample_stream = self._sniff_stream_url(play_html)
                            if sample_stream:
                                self.log(f"嗅探到播放流直链: {sample_stream['url']}")
                            else:
                                self.log("未直接嗅探到 m3u8，尝试在详情页源码中搜索...")
                except Exception as exc:
                    self.log(f"深入详情页发生非致命异常: {exc}")

        # 6. 生成可运行的 SiteRule 与独立 Python 爬虫脚本
        generated_rule = self._generate_rule(site_name, categories, recommend)
        python_code = generate_crawler_python_code(
            key=self.suggested_key,
            name=site_name,
            base_url=self.base_url,
            categories=categories,
        )
        self.log(f"已自动生成合规单文件采集器脚本: sites/{self.suggested_key}.py (共 {len(python_code.splitlines())} 行)")

        return SmartExploreResult(
            base_url=self.base_url,
            site_name=site_name,
            suggested_key=self.suggested_key,
            data_type="html",
            categories=categories,
            recommend=recommend,
            sample_detail=sample_detail,
            sample_stream=sample_stream,
            generated_rule=generated_rule,
            generated_python_code=python_code,
            steps_log=self.logs,
        )


    def _extract_categories_heuristic(self, root: HtmlNode) -> list[dict[str, str]]:
        categories = []
        seen_tids = set()

        # 常见分类链接特征
        patterns = [
            r"/type/(\d+)",
            r"/vod/type/id/(\d+)",
            r"/category/(\d+)",
            r"/show/(\d+)",
            r"tid=(\d+)",
        ]

        # 扫描导航容器或前 100 个带特征链接的 a 标签
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

    def _extract_vod_list_heuristic(self, root: HtmlNode, categories: Optional[list[dict[str, str]]] = None) -> list[dict[str, Any]]:
        results = []
        seen_ids = set()

        # 扫描含有 img 和链接的卡片容器
        card_selectors = [
            ".module-item",
            ".vodlist_item",
            ".v-item",
            ".video-item",
            ".list-item",
            ".card",
            "li",
        ]

        nodes = []
        for sel in card_selectors:
            matched = root.select(sel)
            if len(matched) >= 4:
                nodes = matched
                break

        if not nodes:
            # 兜底寻找包含 img 和 a 的节点
            for a in root.select("a"):
                if a.select_first("img"):
                    nodes.append(a)

        cat_hrefs = set()
        if categories:
            for c in categories:
                raw = c.get("raw_href")
                if raw:
                    cat_hrefs.add(raw)
                tid = c.get("tid")
                if tid:
                    cat_hrefs.add(f"/cat/{tid}.html")
                    cat_hrefs.add(f"/type/{tid}.html")

        for n in nodes:
            # 寻找链接
            a_tag = n if n.tag == "a" else n.select_first("a")
            if not a_tag:
                continue
            href = a_tag.attr("href")
            if not href or href == "#" or "javascript:" in href:
                continue

            # 严格过滤：分类页面绝对不能当作视频
            if href.startswith("/cat/") or "/cat/" in href or href in cat_hrefs:
                continue

            # 提取影片 ID
            vod_id = ""
            m_post = re.search(r"/post/([a-zA-Z0-9_-]+)\.html", href)
            if m_post:
                vod_id = m_post.group(1)
            else:
                m_vod = re.search(r"/(?:detail|vod|v|show)/(\d+)", href)
                if m_vod:
                    vod_id = m_vod.group(1)
                else:
                    m_alt = re.search(r"/(\d+)\.html", href)
                    if m_alt:
                        vod_id = m_alt.group(1)
                    else:
                        clean_href = re.sub(r"[^\w-]", "", href.strip("/"))
                        if clean_href:
                            vod_id = clean_href

            if not vod_id or vod_id in seen_ids:
                continue

            # 寻找标题
            title = ""
            for t_sel in [".title", "h3", "h4", "h2", ".name", "span"]:
                tnode = n.select_first(t_sel)
                if tnode and tnode.text:
                    title = clean_title(tnode.text)
                    if title:
                        break
            if not title:
                title = clean_title(a_tag.attr("title") or a_tag.text)

            if not title or len(title) < 2 or title in ("更多", "换一换", "排行榜"):
                continue

            # 寻找封面图
            pic = ""
            img_tag = n.select_first("img")
            if img_tag:
                pic = img_tag.attr("data-original") or img_tag.attr("data-src") or img_tag.attr("src")
                pic = safe_resolve_url(self.base_url, pic)
                if is_placeholder_image(pic):
                    pic = ""

            # 寻找备注状态
            remarks = ""
            for r_sel in [".module-item-text", ".remarks", ".pic-text", ".badge", ".text-right", ".status"]:
                rnode = n.select_first(r_sel)
                if rnode and rnode.text:
                    remarks = collapse_whitespace(rnode.text)
                    break

            seen_ids.add(vod_id)
            results.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks,
                "raw_href": href,
            })

            if len(results) >= 24:
                break

        return results

    def _extract_detail_heuristic(self, vod_item: dict[str, Any], root: HtmlNode, detail_url: str, html_content: str = "") -> dict[str, Any]:
        # 提取简介
        desc = ""
        for sel in [".video-info-content", ".desc", ".content", ".plot", "#desc", "p.detail"]:
            dnode = root.select_first(sel)
            if dnode and len(dnode.text.strip()) > 10:
                desc = collapse_whitespace(dnode.text)
                break

        episodes = []
        lines = []

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

    def _sniff_stream_url(self, html: str) -> Optional[dict[str, str]]:
        # 1. 优先检查内嵌 var pp 播放器直链
        pp_match = re.search(r"var\s+pp\s*=\s*(\{.*?\});", html)
        if pp_match:
            try:
                pp_data = json.loads(pp_match.group(1))
                for line in pp_data.get("lines", []):
                    if isinstance(line, list) and len(line) >= 4 and isinstance(line[3], list) and line[3]:
                        return {"url": line[3][0], "format": "m3u8"}
            except Exception:
                pass

        # 2. 正则提取 m3u8
        m3u8_match = _M3U8_REGEX.search(html)
        if m3u8_match:
            raw_url = m3u8_match.group(1).replace(r"\/", "/")
            return {"url": raw_url, "format": "m3u8"}

        mp4_match = _MP4_REGEX.search(html)
        if mp4_match:
            raw_url = mp4_match.group(1).replace(r"\/", "/")
            return {"url": raw_url, "format": "mp4"}

        return None


    def _generate_rule(self, site_name: str, categories: list[dict[str, str]], recommend: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "key": self.suggested_key,
            "name": site_name,
            "version": "1.0.0",
            "base_url": self.base_url,
            "mode": "direct",
            "data_type": "html",
            "home": {
                "path": "/",
                "method": "GET",
                "static_categories": categories,
                "recommend_container": ".module-item, .vodlist_item, li",
                "recommend_item": {
                    "vod_id": { "selector": "a", "attribute": "href", "regex": r"/(\d+)\.html" },
                    "vod_name": { "selector": ".title, h3, a" },
                    "vod_pic": { "selector": "img", "attribute": "data-original" },
                    "vod_remarks": { "selector": ".module-item-text, .remarks, span" }
                }
            },
            "detail": {
                "path": "/detail/{id}.html",
                "method": "GET",
                "title_extractor": { "selector": "h1, .page-title" },
                "pic_extractor": { "selector": "img", "attribute": "data-original" },
                "desc_extractor": { "selector": ".video-info-content, .desc, p" },
                "episodes_container": "a[href*='/play/']",
                "episode_item": {
                    "ep_name": { "selector": "" },
                    "play_id": { "attribute": "href" }
                }
            },
            "play": {
                "path": "{play_id}",
                "method": "GET",
                "play_url_extractor": {
                    "type": "regex",
                    "regex": r"""(?:["']|\b)(https?://[^\s"'<>]+\.m3u8[^\s"'<>]*)(?:["']|\b)"""
                },
                "format": "m3u8"
            }
        }

    async def _explore_json(self, data: Any) -> SmartExploreResult:
        # JSON 探测逻辑
        return SmartExploreResult(
            base_url=self.base_url,
            site_name=self.suggested_key,
            suggested_key=self.suggested_key,
            data_type="json",
            categories=[],
            recommend=[],
            generated_rule={"key": self.suggested_key, "base_url": self.base_url, "data_type": "json"},
            steps_log=self.logs,
        )
