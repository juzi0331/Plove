#!/usr/bin/env python
"""xiaoyakankan.com（小鸭看看）适配器。

站点特征（2026-10-01 实测）：

* **服务端渲染、无反爬闸门**：裸 GET 直接 200（text/html; charset=UTF-8），
  纯 HTTP 就能拿全部数据，不需要解挑战；
* 路由形态：首页 ``/``，分类 ``/cat/{tid}.html``（第 2 页起 ``/cat/{tid}-{page}.html``，
  每页 36 个），详情 ``/post/{10位hex}.html``；
* **所有线路所有集的 m3u8 直链都内嵌在详情页**，形状是::

      var pp={"no":"bc8df8d8c2","lines":[["147_165746","线路147",1,
              ["https://v.gsuus.com/play/e9r15mxa/index.m3u8"]], ...], ...}

  即 ``lines[i] = [线路id, 线路名, 集数, [m3u8, ...]]``。播放入口（``.m4-source``
  里的集数按钮）不带 href，点击后由前端脚本从这个 JSON 取地址 —— 所以
  detail 一次抓齐，play 无需二次探索；
* 线路条目大量重复（电影 98 条里只有 29 组 URL 不同），必须按
  ``(线路名, URL列表)`` 去重后编号，否则"线路 2"永远指不到正确的地址；
* m3u8 实测**不带 Referer 也返回 200**，但仍然回传 Referer 头以防 CDN
  日后加防盗链；
* 站内搜索是 ``<form action="https://www.google.com/search">``（Google 站内
  表单），没有站内搜索接口 —— search 明确报 UNSUPPORTED。

play_id 设计（与 ncat21 的"完整路径"不同）：这里是 **不透明定位符**
``{影片no}|{线路id}|{集号}``，例如 ``bc8df8d8c2|147_165746|1``。它**不是
URL**：解析回结构化字段后，线路 id 必须在详情页 pp JSON 里精确命中、影片
no 必须与详情一致，集号必须在合法区间 —— 播放地址永远只从站点自己的
pp JSON 里取，不存在"拿上层传来的地址直接 fetch"的 SSRF 面。

用法（crawler_kit 在脚本同目录 / 脚本父目录 / 当前目录 / ``CRAWLER_KIT_PATH``
任一处即可直接跑；都找不到时也会按协议吐 ``ok:false`` 信封并退出码 0）::

    python xiaoyakankan.py meta
    python xiaoyakankan.py home
    python xiaoyakankan.py category --tid 10 --page 1
    python xiaoyakankan.py detail --id bc8df8d8c2
    python xiaoyakankan.py play --id bc8df8d8c2 --line 1 --ep 1
    # 带上详情里给的 play_id（shell 里要给管道符加引号）
    python xiaoyakankan.py play --play-id 'bc8df8d8c2|147_165746|1'
"""

from __future__ import annotations

import json
import os
import re
import sys


def _boot_fail(message: str):
    """连 crawler_kit 都拿不到时也要守住协议：stdout 一行 ok:false + 退出码 0。

    用 ``ensure_ascii=True``：此时还没走到 cli 的 UTF-8 强制，Windows 控制台
    可能是 GBK，纯 ASCII 的 JSON 在任何编码下都是合法的一行信封。
    """
    print(
        json.dumps(
            {"ok": False, "data": None, "error": {"code": "UNKNOWN", "message": message}},
            ensure_ascii=True,
        )
    )
    raise SystemExit(0)


def _load_crawler_kit():
    """定位 crawler_kit 工具箱。

    生产环境（受保护子进程）本来就 import 得到，这里只管本地直跑：
    依次找 ``CRAWLER_KIT_PATH``、脚本同目录、脚本父目录（crawler/sites/ 布局）、
    当前目录（以及当前目录下的 ``crawler/``）。
    """
    try:
        import crawler_kit  # noqa: F401
        return
    except ImportError:
        pass

    here = os.path.dirname(os.path.abspath(__file__))
    bases = (
        os.environ.get("CRAWLER_KIT_PATH") or "",
        here,
        os.path.dirname(here),
        os.getcwd(),
        os.path.join(os.getcwd(), "crawler"),
    )
    for base in bases:
        if base and os.path.isdir(os.path.join(base, "crawler_kit")):
            sys.path.insert(0, base)
            return
    _boot_fail(
        "找不到 crawler_kit 工具箱：把本文件放进 crawler/sites/ 运行，"
        "或在 crawler_kit 所在目录旁运行，或设环境变量 CRAWLER_KIT_PATH 指向它"
    )


_load_crawler_kit()

from crawler_kit import Client, CrawlerError, clean, cli, log, parse  # noqa: E402

KEY = "xiaoyakankan"
NAME = "小鸭看看"
BASE_URL = "https://xiaoyakankan.com"

#: 分类页每页条数（实测 36，仅用于文档/对账，不参与逻辑）
PAGE_SIZE = 36
#: 主动限速：单命令内多次请求时的最小间隔（秒）
MIN_REQUEST_INTERVAL = 0.4

_POST_HREF_RE = re.compile(r"/post/([0-9a-f]{6,})\.html", re.I)
_PAGE_HREF_RE = re.compile(r"/cat/(\d+)-(\d+)\.html")
#: 详情页影片 id 是 10 位左右的十六进制 hash
_VOD_ID_RE = re.compile(r"^[0-9a-fA-F]{6,}$")
#: pp JSON 里的线路 id，形如 ``147_165746``
_LINE_ID_RE = re.compile(r"^[0-9A-Za-z]{1,32}(?:_[0-9A-Za-z]{1,32})?$")
_PP_MARKER_RE = re.compile(r"var\s+pp\s*=")

#: 卡片图片的属性优先级（懒加载：src 是 base64 占位图，真图在 data-src）
_IMAGE_ATTRS = ("data-original", "data-src", "data-lazy-src", "data-echo", "src")


# ------------------------------------------------------------------ 映射层


def _card(node):
    """首页/分类页的 ``.item`` 卡片 -> VodItem。缺 id 或名字的丢弃。"""
    link = node.select_first("a.link")
    match = _POST_HREF_RE.search(link.attr("href") or "") if link is not None else None
    if not match:
        return None

    title = node.select_first(".info .title")
    image = node.select_first("img")
    name = clean.strip_promo(title.text) if title is not None else ""
    if not name and image is not None:
        name = clean.strip_promo(image.attr("alt") or "")
    if not name:
        return None

    video = {
        "vod_id": match.group(1),
        "vod_name": name,
        "vod_pic": _img_url(image),
        "vod_remarks": _card_remarks(node),
    }
    tag2 = node.select_first(".tag2")
    kind, year = _split_tag2(tag2.text if tag2 is not None else "")
    if kind:
        video["vod_type"] = kind
    if year:
        video["vod_year"] = year
    desc = node.select_first(".info .desc")
    if desc is not None and desc.text:
        video["vod_actor"] = desc.text
    return video


def _cards(nodes):
    out = []
    for node in nodes:
        video = _card(node)
        if video is not None:
            out.append(video)
    return clean.dedupe(out, key=lambda item: item["vod_id"])


def _img_url(image):
    """懒加载卡片：``src`` 是 base64 占位 gif，真图在 ``data-src`` 等属性里。"""
    if image is None:
        return ""
    for name in _IMAGE_ATTRS:
        url = (image.attr(name) or "").strip()
        if not url or url.startswith("data:"):
            continue
        if clean.is_placeholder_image(url):
            continue
        return clean.absolute(url, BASE_URL)
    return ""


def _card_remarks(node):
    """列表卡片角标：``.tag1`` 是清晰度（1080p/720p）。"""
    tag1 = node.select_first(".tag1")
    return clean.collapse(tag1.text) if tag1 is not None else ""


def _split_tag2(text):
    """``剧情片 / 2026年`` -> ``("剧情片", 2026)``。"""
    parts = [clean.collapse(part) for part in clean.collapse(text).split("/")]
    kind = parts[0] if parts else ""
    year = clean.to_int(parts[1]) if len(parts) > 1 else None
    return kind, year


def _nav_categories(root):
    """首页分类：顶部导航（10 电影 / 11 连续剧 / 12 综艺 / 13 动漫 / 15 福利）
    加上各板块的子分类（1001 动作片…）。``全部xx`` 与导航 tid 重叠，去重丢弃。"""
    out = []
    head = root.select_first(".m4-head") or root
    for anchor in head.select('a[href^="/cat/"]'):
        match = re.search(r"/cat/(\d+)\.html", anchor.attr("href") or "")
        if not match:
            continue
        span = anchor.select_first("span")
        name = clean.collapse(span.text if span is not None else anchor.text)
        if name:
            out.append({"tid": match.group(1), "name": name})
    for meta in root.select(".m4-meta"):
        for anchor in meta.select('a[href^="/cat/"]'):
            match = re.search(r"/cat/(\d+)\.html", anchor.attr("href") or "")
            if not match:
                continue
            name = clean.collapse(anchor.text)
            if name:
                out.append({"tid": match.group(1), "name": name})
    return clean.dedupe(out, key=lambda item: item["tid"])


def _max_page(root, tid):
    """分页条 ``.m4-page`` 里链接到的最大页码；没有带页码的链接就是末页。"""
    best = 1
    for anchor in root.select(".m4-page a"):
        match = _PAGE_HREF_RE.search(anchor.attr("href") or "")
        if match and match.group(1) == str(tid):
            best = max(best, clean.to_int(match.group(2), 1) or 1)
    return best


def _meta_kv(root):
    """详情页 ``.info`` 行（``地区：印度``）拆成字典。相关推荐的 .info 没有
    冒号前缀，拆不出来自然被忽略。"""
    out = {}
    for info in root.select(".info"):
        text = clean.collapse(info.text)
        if "：" not in text:
            continue
        key, value = text.split("：", 1)
        if key and value and key not in out:
            out[key] = clean.strip_promo(value)
    return out


def _poster(root):
    """封面：``.m4-player`` 的 ``data-poster`` 属性，退回第一张真图。"""
    player = root.select_first(".m4-player")
    url = (player.attr("data-poster") or "").strip() if player is not None else ""
    if url and not url.startswith("data:"):
        return clean.absolute(url, BASE_URL)
    return _img_url(root.select_first("img"))


def _detail_genre(root):
    """面包屑末级（``首页 / 连续剧 / 韩国剧 / 我们家``）里的类型名。"""
    for li in reversed(root.select(".m4-bread li")):
        if "on" in li.class_list:
            continue
        text = clean.collapse(li.text)
        if text and text != "首页":
            return text
    return ""


def _detail_remarks(root):
    """详情页角标取第一条线路的清晰度（``.res`` 的 720p/1080p）。"""
    res = root.select_first(".m4-source .res")
    return clean.collapse(res.text) if res is not None else ""


def _h1_text(root):
    node = root.select_one("h1")
    return clean.strip_promo(node.text) if node is not None else ""


def _extract_pp(html):
    """抠出 ``var pp={...}`` 的 JSON 段并解析。

    为什么不用正则圈到行尾：JSON 与后面的脚本挤在同一个 ``<script>`` 里，
    花括号嵌套深度不可假设，只能做一次**感知字符串的花括号配平**。
    """
    match = _PP_MARKER_RE.search(html or "")
    if not match:
        return None
    start = html.find("{", match.end())
    if start < 0:
        return None
    depth = 0
    in_str = False
    escaped = False
    for index in range(start, len(html)):
        char = html[index]
        if in_str:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_str = False
            continue
        if char == '"':
            in_str = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start:index + 1])
                except ValueError:
                    return None
    return None


# --------------------------------------------------------------------- 站点


class Xiaoyakankan:
    key = KEY
    name = NAME
    version = "1.0.0"
    base_url = BASE_URL
    #: 播放直连源站 CDN（实测无 Referer 校验），不需要后端做流代理
    mode = "direct"
    capabilities = ("meta", "home", "category", "detail", "play")

    def __init__(self, client=None):
        self.http = client or Client(
            base_url=BASE_URL,
            timeout=15.0,
            retries=1,
            headers={
                "Referer": BASE_URL + "/",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            min_interval=MIN_REQUEST_INTERVAL,
        )

    # ---------------------------------------------------------------- 基础

    def _fetch(self, path: str) -> str:
        response = self.http.get(path)
        if response.status == 404:
            raise CrawlerError("NOT_FOUND", f"页面不存在: {path}")
        if not response.ok:
            raise CrawlerError("HTTP_ERROR", f"{path} 返回 HTTP {response.status}")
        return response.text

    @staticmethod
    def _check_vod_id(id):
        """影片 id 必须是站点的 hex hash 形态；不是就当查无此片。"""
        text = str(id or "").strip()
        return text if _VOD_ID_RE.match(text) else None

    # ---------------------------------------------------------------- pp 解析

    @staticmethod
    def _raw_lines(pp):
        """pp JSON 的 ``lines`` 摊平成 ``[{id, name, urls}]``，剔除坏条目。"""
        raws = []
        for entry in pp.get("lines") or []:
            if not isinstance(entry, list) or len(entry) < 4:
                continue
            line_id = str(entry[0] or "").strip()
            name = clean.clean_text(entry[1]) or "线路"
            urls = []
            for url in entry[3] if isinstance(entry[3], list) else []:
                if isinstance(url, str) and url.strip():
                    urls.append(clean.absolute(url.strip(), BASE_URL))
            if line_id and _LINE_ID_RE.match(line_id) and urls:
                raws.append({"id": line_id, "name": name, "urls": urls})
        if not raws:
            raise CrawlerError("PARSE_ERROR", "pp.lines 里没有可用线路（结构可能已变）")
        return raws

    @staticmethod
    def _source_labels(root):
        """HTML 里每个 ``.source`` 块的展示信息：线路标签 + 集数按钮文案。

        pp JSON 只有地址，"第01集 / 番外1 / 正片" 这些名字只存在于 HTML 里，
        用 ``data-vod``（= 线路 id）对上。
        """
        labels = {}
        names = {}
        for source in root.select(".m4-source .source"):
            vod = (source.attr("data-vod") or "").strip()
            if not vod:
                continue
            if vod not in labels:
                name_node = source.select_first(".title .name")
                labels[vod] = clean.collapse(name_node.text) if name_node is not None else ""
            if vod not in names:
                names[vod] = [clean.collapse(a.text) for a in source.select(".list a")]
        return labels, names

    @staticmethod
    def _display_lines(raws, labels, names):
        """按 ``(线路名, URL列表)`` 去重后的展示线路（保持站点顺序）。

        实测同一部电影的 pp.lines 有 98 条、去重后只剩 29 组 —— 不去重的话
        "线路 2" 在界面上永远翻不到真正不同的源。
        """
        groups = {}
        order = []
        for raw in raws:
            key = (raw["name"], tuple(raw["urls"]))
            group = groups.get(key)
            if group is None:
                group = {
                    "id": raw["id"],
                    "name": raw["name"],
                    "urls": list(raw["urls"]),
                    "ep_names": [],
                    "label": "",
                }
                groups[key] = group
                order.append(group)
            if not group["ep_names"]:
                group["ep_names"] = names.get(raw["id"], [])
            if not group["label"]:
                group["label"] = labels.get(raw["id"], "")
        return order

    @staticmethod
    def _ep_name(group, index):
        """集名优先取 HTML 按钮（``第01集``/``番外1``/``正片``），缺了再合成。"""
        if 0 < index <= len(group["ep_names"]) and group["ep_names"][index - 1]:
            return group["ep_names"][index - 1]
        return "正片" if len(group["urls"]) == 1 else f"第{index:02d}集"

    # ---------------------------------------------------------------- 命令

    def meta(self):
        return {
            "key": self.key,
            "name": self.name,
            "version": self.version,
            "base_url": self.base_url,
            "mode": self.mode,
            "capabilities": list(self.capabilities),
            "play_format": ["m3u8"],
            "note": "无反爬闸门；全部播放直链内嵌详情页 var pp JSON；无站内搜索（站点用 Google 站内表单）",
        }

    def home(self):
        root = parse.parse_html(self._fetch("/"))
        return {
            "categories": _nav_categories(root),
            "recommend": _cards(root.select(".item")),
        }

    def category(self, tid=None, page=1):
        page = clean.to_int(page, 1) or 1
        if page < 1:
            page = 1
        if tid is None or str(tid).strip() == "" or not str(tid).strip().isdigit():
            raise CrawlerError("NOT_FOUND", f"无效的分类 id: {tid}")
        tid = str(tid).strip()

        # 站点分页形态：第 1 页 /cat/10.html，第 2 页起 /cat/10-2.html
        path = f"/cat/{tid}.html" if page == 1 else f"/cat/{tid}-{page}.html"
        root = parse.parse_html(self._fetch(path))
        return {
            "videos": _cards(root.select(".item")),
            "page": page,
            # 请求超过末页时站点会把最后一页原样吐回来，分页条里没有更大页码
            "has_more": _max_page(root, tid) > page,
        }

    def detail(self, id):
        vod_id = self._check_vod_id(id)
        if vod_id is None:
            raise CrawlerError("NOT_FOUND", f"无效的影片 id: {id}")

        html = self._fetch(f"/post/{vod_id}.html")
        root = parse.parse_html(html)

        pp = _extract_pp(html)
        if not isinstance(pp, dict) or not pp.get("no"):
            raise CrawlerError("PARSE_ERROR", f"详情页里找不到 var pp JSON: {vod_id}")

        name = _h1_text(root)
        if not name:
            raise CrawlerError("PARSE_ERROR", f"详情页里找不到标题: {vod_id}")

        video = {
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": _poster(root),
            "vod_remarks": _detail_remarks(root),
        }
        kv = _meta_kv(root)
        genre = _detail_genre(root)
        if genre:
            video["vod_type"] = genre
        if kv.get("地区"):
            video["vod_area"] = kv["地区"]
        year = clean.to_int(kv.get("年份"))
        if year:
            video["vod_year"] = year
        if kv.get("演员"):
            video["vod_actor"] = kv["演员"]
        if kv.get("导演"):
            video["vod_director"] = kv["导演"]

        raws = self._raw_lines(pp)
        labels, names = self._source_labels(root)
        groups = self._display_lines(raws, labels, names)
        no = str(pp["no"])

        episodes = []
        lines = []
        for line_no, group in enumerate(groups, start=1):
            lines.append(
                {
                    "line": line_no,
                    "name": group["label"] or group["name"],
                    "count": len(group["urls"]),
                }
            )
            for index in range(1, len(group["urls"]) + 1):
                episodes.append(
                    {
                        "ep_index": index,
                        "ep_name": self._ep_name(group, index),
                        # 不透明定位符：play 阶段回详情页解析，绝不直接当 URL 用
                        "play_id": f"{no}|{group['id']}|{index}",
                        "line": line_no,
                    }
                )

        return {
            "video": video,
            "desc": kv.get("简介", ""),
            "episodes": episodes,
            "lines": lines,
        }

    def play(self, id=None, ep=1, line=1, play_id=None):
        """取某一集的 m3u8。

        两条等价路径，都只需一次详情页请求（直链都在 pp JSON 里）：

        * 带 ``play_id``（``no|线路id|集号``）：按定位符精确解析，影片号与
          详情页不一致时直接报 NOT_FOUND，绝不静默回退到别的集；
        * 只带 ``id``：按线路号 + 集号在去重后的展示线路里取。
        """
        ep_no = clean.to_int(ep, 1) or 1
        line_no = clean.to_int(line, 1) or 1

        token_vod = token_line = token_ep = None
        if play_id:
            token_vod, token_line, token_ep = self._parse_play_id(play_id)

        vod_id = self._check_vod_id(id if id is not None else token_vod)
        if vod_id is None:
            raise CrawlerError("NOT_FOUND", "play 需要 --id；或者传一个合法的 --play-id")

        html = self._fetch(f"/post/{vod_id}.html")
        pp = _extract_pp(html)
        if not isinstance(pp, dict) or not pp.get("no"):
            raise CrawlerError("PARSE_ERROR", f"详情页里找不到 var pp JSON: {vod_id}")
        no = str(pp["no"])

        url = ""
        if token_vod is not None:
            if token_vod != no:
                raise CrawlerError(
                    "NOT_FOUND", f"play_id 与影片不匹配: {token_vod} != {no}"
                )
            raw = next((r for r in self._raw_lines(pp) if r["id"] == token_line), None)
            if raw is None:
                raise CrawlerError("NOT_FOUND", f"play_id 指向的线路不存在: {token_line}")
            if not 1 <= token_ep <= len(raw["urls"]):
                raise CrawlerError(
                    "NOT_FOUND", f"play_id 指向的集数不存在: {token_ep}/{len(raw['urls'])}"
                )
            url = raw["urls"][token_ep - 1]
        else:
            root = parse.parse_html(html)
            raws = self._raw_lines(pp)
            labels, names = self._source_labels(root)
            groups = self._display_lines(raws, labels, names)
            if not 1 <= line_no <= len(groups):
                raise CrawlerError(
                    "NOT_FOUND", f"线路 {line_no} 不存在（共 {len(groups)} 条线路）"
                )
            group = groups[line_no - 1]
            if not 1 <= ep_no <= len(group["urls"]):
                raise CrawlerError(
                    "NOT_FOUND",
                    f"线路 {line_no} 第 {ep_no} 集不存在（共 {len(group['urls'])} 集）",
                )
            url = group["urls"][ep_no - 1]

        if not url:
            raise CrawlerError("PARSE_ERROR", "没有解析到可播放的地址")
        return {
            "url": clean.absolute(url, BASE_URL),
            "format": "m3u8",
            # 实测无 Referer 也能取到清单；带上以防 CDN 日后加防盗链
            "headers": {"Referer": BASE_URL + "/"},
        }

    @staticmethod
    def _parse_play_id(play_id):
        """``no|线路id|集号`` -> (no, line_id, ep)；形态不对返回 None 并只记日志。

        这里只做**形态校验**；值是否真实存在由 play 阶段在 pp JSON 里核对。
        """
        parts = str(play_id or "").strip().split("|")
        if len(parts) == 3 and _VOD_ID_RE.match(parts[0]) and _LINE_ID_RE.match(parts[1]) and parts[2].isdigit():
            return parts[0], parts[1], int(parts[2])
        log.warn(f"忽略不可信的 play_id: {str(play_id)[:80]!r}")
        return None, None, None

    def search(self, kw=None, page=1):
        # 能力清单里没有 search：站内搜索是 Google 表单，宁可明确报错
        raise CrawlerError("UNSUPPORTED", "该源无站内搜索接口（站点搜索为 Google 站内表单），能力清单中已标注")


if __name__ == "__main__":
    cli.main(Xiaoyakankan())
