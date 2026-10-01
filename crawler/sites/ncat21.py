#!/usr/bin/env python
"""ncat21.com（网飞猫）适配器。

站点特征（实测）：

* maccms 衍生模板，**列表/详情/播放页全是服务端渲染**，纯 HTTP 就能拿；
* 前面有一道 ``cdndefend`` 闸门：不带 cookie 请求返回 **HTTP 850** 和挑战页，
  页面里的 JS 算出 ``cdndefend_js_cookie``。算法见 :func:`solve_cdndefend`
  —— 本质是暴力找一个让 SHA-1 摘要特定两字节命中的计数器，实测约 5 万次、
  30 毫秒就能出结果，**完全不需要浏览器**；
* 详情页有 **多条线路**（``.episode-list`` 一组一条），每组的 ``data-index``
  都从 1 重新开始 —— 所以 ``play_id`` 必须用完整路径，不能用集号；
* 播放页 HTML 里直接写着带签名、带时间戳的 m3u8，**不需要解密**。

用法::

    python sites/ncat21.py meta
    python sites/ncat21.py home
    python sites/ncat21.py category --tid 1 --page 1
    python sites/ncat21.py detail --id 318185
    python sites/ncat21.py play --id 318185 --line 1 --ep 1
    # 带上详情里给的 play_id 可以省掉一次详情页抓取（实测快 3.5 秒）
    python sites/ncat21.py play --play-id /play/318185-41-2946527.html
    python sites/ncat21.py selftest
"""

from __future__ import annotations

import hashlib
import os
import re
import sys

if __package__ in (None, ""):  # 允许直接 `python sites/ncat21.py` 运行
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler_kit import CookieGate, Client, CrawlerError, clean, cli, log, parse  # noqa: E402

KEY = "ncat21"
NAME = "网飞猫"
BASE_URL = "https://www.ncat21.com"

CHALLENGE_COOKIE = "cdndefend_js_cookie"
CHALLENGE_STATUS = 850
#: 两次请求的最小间隔（秒）。防的是"被拦了却完全看不出来"，阈值保守
MIN_REQUEST_INTERVAL = 1.0
#: 闸门期望命中概率是 1/65536，实测约 5 万次；上限放到 200 万次兜底
SOLVE_MAX_ITERATIONS = 2_000_000

_SECRET_RE = re.compile(r"['\"]([0-9A-Fa-f]{40})['\"]")
_DETAIL_HREF_RE = re.compile(r"/detail/(\d+)\.html")
_CHANNEL_HREF_RE = re.compile(r"/channel/(\d+)\.html")


# ------------------------------------------------------------------ 闸门求解


def solve_cdndefend(challenge_html: str) -> str:
    """复刻 ``cdndefend`` 前端算法，返回 cookie 的值（不含 cookie 名）。

    挑战页里的逻辑可以瘦成这几行：

    ```js
    let c = '<40 位十六进制 secret>';        // 硬编码在页面里
    let n1 = parseInt('0x' + c[0]);          // 取首字符当十六进制数
    for (let i = 0; ; i++) {
      let s = sha1(c + i).array();           // 20 字节摘要
      if (s[n1] === 0xb0 && s[n1 + 1] === 0x0b) {
        document.cookie = 'cdndefend_js_cookie=' + c + i;
        break;
      }
    }
    ```

    所以只要找到让摘要第 ``n1``、``n1+1`` 字节等于 ``0xB0 0x0B`` 的计数器即可。
    **secret 每页都可能轮换，必须从挑战页现解析，不能写死。**
    """
    match = _SECRET_RE.search(challenge_html or "")
    if not match:
        raise CrawlerError("BLOCKED", "挑战页里找不到 secret（结构可能已变）")

    secret = match.group(1).upper()
    offset = int(secret[0], 16)
    for counter in range(SOLVE_MAX_ITERATIONS):
        digest = hashlib.sha1(f"{secret}{counter}".encode()).digest()
        if digest[offset] == 0xB0 and digest[offset + 1] == 0x0B:
            log.debug(f"闸门命中: secret={secret[:8]}… counter={counter}")
            return secret + str(counter)
    raise CrawlerError("BLOCKED", f"闸门求解超过 {SOLVE_MAX_ITERATIONS} 次迭代")


# --------------------------------------------------------------------- 站点


class Ncat21:
    key = KEY
    name = NAME
    version = "1.0.0"
    base_url = BASE_URL
    mode = "direct"
    capabilities = ("meta", "home", "category", "detail", "play", "selftest")

    def __init__(self, client=None, gate=None):
        self.http = client or Client(
            base_url=BASE_URL,
            timeout=15.0,
            retries=1,
            headers={
                "Referer": BASE_URL + "/",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            # 主动限速：请求打太快时源站会在 TLS 层直接丢包，客户端只看到
            # "handshake timed out"，看不出原因。具体阈值未实测，先保守取 1s。
            min_interval=MIN_REQUEST_INTERVAL,
        )
        self.gate = gate or CookieGate(
            solve_cdndefend, CHALLENGE_COOKIE, challenge_status=CHALLENGE_STATUS
        )

    # ---------------------------------------------------------------- 基础

    def _page(self, path: str) -> str:
        response = self.gate.fetch(self.http, path)
        if response.status == CHALLENGE_STATUS:
            raise CrawlerError("BLOCKED", f"被 cdndefend 拦截: {path}")
        if response.status == 404:
            raise CrawlerError("NOT_FOUND", f"页面不存在: {path}")
        if not response.ok:
            raise CrawlerError("HTTP_ERROR", f"{path} 返回 HTTP {response.status}")
        return response.text

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
            "note": f"存在 {CHALLENGE_COOKIE} 反爬闸门（HTTP {CHALLENGE_STATUS}），已内置求解",
        }

    def home(self):
        root = parse.parse_html(self._page("/"))
        return {
            "categories": _nav_categories(root),
            "recommend": _cards(root.select(".v-item")),
        }

    def category(self, tid=None, page=1):
        page = clean.to_int(page, 1) or 1
        if tid is None or str(tid).strip() == "":
            path = "/label/new.html"
        else:
            number = clean.to_int(tid)
            if number is None:
                raise CrawlerError("NOT_FOUND", f"无效的分类 id: {tid}")
            path = f"/channel/{number}.html"
        if page > 1:
            path += f"?page={page}"

        root = parse.parse_html(self._page(path))
        return {
            "videos": _cards(root.select(".v-item")),
            "page": page,
            "has_more": _has_more(root, page),
        }

    def search(self, kw=None, page=1):
        # 站点搜索要带 t=<token> 参数，第一版不做，明确报错而不是返回空列表
        raise CrawlerError("UNSUPPORTED", "该源搜索需要额外 token，能力清单中已标注")

    def detail(self, id):
        vod_id = clean.to_int(id)
        if vod_id is None:
            raise CrawlerError("NOT_FOUND", f"无效的影片 id: {id}")

        html = self._page(f"/detail/{vod_id}.html")
        root = parse.parse_html(html)

        name = _detail_title(root, html)
        video = {
            "vod_id": str(vod_id),
            "vod_name": name,
            "vod_pic": clean.absolute(_detail_cover(root, html), BASE_URL),
            "vod_remarks": _detail_remarks(root),
        }
        episodes, lines = _episodes(root)

        return {
            "video": video,
            "desc": _detail_desc(root, html),
            "episodes": episodes,
            # 扩展字段：线路清单。多线路源必须让上层知道有几条线
            "lines": lines,
        }

    def play(self, id=None, ep=1, line=1, play_id=None):
        """取播放地址。

        ``--play-id`` 是**加速通道**，也是这个源上最值钱的一处优化：
        原来每次都要先抓一遍详情页（只为找到"线路 N 第 M 集"对应的路径），
        而那一次详情实测要 **3.5 秒**。详情里每集本来就带着 ``play_id``
        （完整路径），上层把它原样传回来，这里就能直捣播放页。

        没传或不可信就退回老路径：**行为不变，只是慢一点**。
        """
        index = clean.to_int(ep, 1) or 1
        line_no = clean.to_int(line, 1) or 1

        path = clean.safe_relative_path(play_id)
        if not path:
            if play_id:
                # 不报错、只记一笔：一个奇怪的值不该让用户看不了片
                log.warn(f"忽略不可信的 play_id（不是站内相对路径）: {str(play_id)[:80]!r}")
            if id is None:
                raise CrawlerError("NOT_FOUND", "play 需要 --id；或者传一个合法的 --play-id")

            detail = self.detail(id)
            target = next(
                (
                    item
                    for item in detail["episodes"]
                    if item["line"] == line_no and item["ep_index"] == index
                ),
                None,
            )
            if target is None:
                raise CrawlerError(
                    "NOT_FOUND",
                    f"线路 {line_no} 第 {index} 集不存在（共 {len(detail['lines'])} 条线路）",
                )
            path = target["play_id"]

        html = self._page(path)
        candidates = parse.find_m3u8(html)
        if not candidates:
            raise CrawlerError("PARSE_ERROR", f"播放页里找不到 m3u8: {path}")

        url = clean.absolute(_best_media(candidates), BASE_URL)
        return {
            "url": url,
            "format": "m3u8",
            # 源站有防盗链，带上 Referer
            "headers": {"Referer": BASE_URL + "/"},
        }

    def selftest(self):
        """结构指纹：任一计数骤降就说明站点改版了，应触发熔断。"""
        home_root = parse.parse_html(self._page("/"))
        cards = home_root.select(".v-item")
        fingerprint = {
            "home.card": len(cards),
            "home.channel": len(home_root.select('a[href^="/channel/"]')),
            "home.cover_img": len(home_root.select(".v-item-cover img")),
            "home.title_node": len(home_root.select(".v-item-title")),
        }
        href = cards[0].attr("href") if cards else ""
        if href:
            detail_root = parse.parse_html(self._page(href))
            fingerprint["detail.episode_group"] = len(detail_root.select(".episode-list"))
            fingerprint["detail.episode_item"] = len(detail_root.select("a.episode-item"))
        return {"selectors": fingerprint}


# ------------------------------------------------------------------ 映射层


def _cards(nodes):
    out = []
    for node in nodes:
        video = _card(node)
        if video is not None:
            out.append(video)
    return clean.dedupe(out, key=lambda item: item["vod_id"])


def _card(node):
    match = _DETAIL_HREF_RE.search(node.attr("href") or "")
    if not match:
        return None
    name = _card_name(node)
    if not name:
        return None

    video = {
        "vod_id": match.group(1),
        "vod_name": name,
        "vod_pic": clean.absolute(parse.first_image(node), BASE_URL),
        "vod_remarks": _card_remarks(node),
    }
    kind = _card_kind(node)
    if kind:
        video["vod_type"] = kind
    return video


def _card_name(node) -> str:
    """卡片里有多个同名标题，只有一个是可见的，其余是隐藏的广告水印。"""
    titles = [
        clean.strip_promo(item.text)
        for item in parse.visible(node.select(".v-item-title"))
    ]
    titles = [text for text in titles if text]
    return titles[0] if titles else ""


def _card_kind(node) -> str:
    span = parse.select_one(node, ".v-item-bottom span")
    return clean.collapse(span.text) if span else ""


def _card_remarks(node) -> str:
    for selector in (".v-item-top-right", ".v-item-top-left", "[class*=remark]", ".v-item-bottom"):
        found = parse.select_visible(node, selector, limit=1)
        if found and found[0].text:
            return found[0].text
    return ""


def _nav_categories(root):
    out = []
    for anchor in root.select('a[href^="/channel/"]'):
        match = _CHANNEL_HREF_RE.search(anchor.attr("href") or "")
        name = clean.collapse(anchor.text)
        if match and name:
            out.append({"tid": match.group(1), "name": name})
    return clean.dedupe(out, key=lambda item: item["tid"])


def _episodes(root):
    """把多线路剧集列表摊平成 episodes + lines。"""
    episodes = []
    lines = []
    for line_no, group in enumerate(root.select(".episode-list"), start=1):
        anchors = parse.visible(group.select("a.episode-item")) or group.select("a.episode-item")
        if not anchors:
            continue
        lines.append({"line": line_no, "name": _line_label(root, line_no), "count": len(anchors)})
        for order, anchor in enumerate(anchors, start=1):
            href = anchor.attr("href") or ""
            if not href:
                continue
            index = clean.to_int(anchor.attr("data-index"), order) or order
            quality = anchor.select_one("span")
            episodes.append(
                {
                    "ep_index": index,
                    "line": line_no,
                    "ep_name": clean.normalize_quality(quality.text) if quality else "",
                    # 完整路径当 id：多线路时 data-index 会重复，只有路径是唯一的
                    "play_id": href,
                }
            )
    return episodes, lines


def _line_label(root, line_no) -> str:
    labels = parse.select_visible(root, ".source-item-label")
    if 0 < line_no <= len(labels):
        return clean.collapse(labels[line_no - 1].text)
    return f"线路{line_no}"


def _detail_title(root, html) -> str:
    for selector in ("h1", ".detail-title", ".vod-title", "[class*=detail-head] h1"):
        for node in parse.select_visible(root, selector):
            text = clean.strip_promo(node.text)
            if text:
                return text
    raw = parse.re_first(r"<title>([^<]*)</title>", html, default="")
    return clean.strip_promo(raw.split("-")[0]) if raw else ""


def _detail_cover(root, html) -> str:
    for selector in (".detail-cover", ".detail-pic", "[class*=detail-cover]", "[class*=detail-pic]"):
        node = parse.select_one(root, selector)
        if node is not None:
            url = parse.first_image(node)
            if url:
                return url
    return parse.re_first(
        r"""<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)""", html, default=""
    )


def _detail_desc(root, html) -> str:
    for selector in ("[class*=detail-desc]", "[class*=vod-desc]", "[class*=intro]", "[class*=desc]"):
        node = parse.select_one(root, selector)
        if node is not None:
            text = clean.strip_promo(node.text)
            if text:
                return text
    for pattern in (
        r"""<meta[^>]+property=["']og:description["'][^>]+content=["']([^"']+)""",
        r"""<meta[^>]+name=["']description["'][^>]+content=["']([^"']+)""",
    ):
        text = parse.re_first(pattern, html, default="")
        text = clean.strip_promo(text)
        if text:
            return text
    return ""


def _detail_remarks(root) -> str:
    for selector in ("[class*=remark]", "[class*=detail-status]", "[class*=status]"):
        found = parse.select_visible(root, selector, limit=1)
        if found and found[0].text:
            return found[0].text
    return ""


def _has_more(root, page) -> bool:
    hrefs = [anchor.attr("href") or "" for anchor in root.select("a")]
    return any(f"page={page + 1}" in href for href in hrefs)


def _best_media(urls):
    """一个播放页里可能有多条 m3u8，优先挑高码率的。"""
    for marker in ("/1920/", "/1080/", "sign="):
        for url in urls:
            if marker in url:
                return url
    return urls[0]


if __name__ == "__main__":
    cli.main(Ncat21())
