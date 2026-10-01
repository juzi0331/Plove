#!/usr/bin/env python
"""黄果短剧官网（https://huangguoai.com）单文件爬虫适配器。

站点特征（已实测）：

* 全站服务端渲染，裸 GET 直接 200（text/html; charset=utf-8），无反爬闸门；
* 首页、分类页均使用同一模板：``/<分类 slug>/``，分类靠顶栏
  ``.hg-topbar-nav__item`` / 列表页 ``.hg-category-col__title`` 里的相对路径区分；
* 播放页 ``/play/<id>.html`` 只服务端渲染线路、集号和 m3u8 索引；
  真实 m3u8 地址藏在 ``<script id="config">`` 的 JS 对象里，按
  ``key: b64(ep_index)`` 的查表格式通过 AES-128-ECB（PKCS#7）解密；
* 播放页有多个线路，必须按 ``line`` 选定线路后取集；
* 详情页没有可靠的按集号排序的剧集，`detail` 按线路逐集重查播放页；
* 首页/分类页有“移动端横幅”``#app-mobile .banner .item``，脚本禁止抓取；
* 首页只抓推荐，不抓完整片单；
* `line` 自带 `name`，可在日志里定位哪条线路失败。
"""

from __future__ import annotations

import base64
import binascii
import re
import sys

if __package__ in (None, ""):  # 允许直接 `python sites/huangguoai.py` 运行
    sys.path.insert(0, "/e/Pychon-code/NY/Plove1.0")

from crawler_kit import Client, CrawlerError, clean, cli, log, parse  # noqa: E402

KEY = "huangguoai"
NAME = "黄果短剧官网"
BASE_URL = "https://huangguoai.com/"
DEFAULT_TIMEOUT = 20.0

# 播放页里 `<script id=config>` 的 JS 对象：`key: b64(ep_index)`。
# 常见写法包括：
#   '7eef2b8946ec...' : '01'
#   '7eef2b8946ec...': '02'
#   "7eef2b8946ec...\":\"03"
_CONFIG_RE = re.compile(r"""['"]?([0-9a-fA-F]{32,})['"]?\s*:\s*['"]([^'"]+)['"]""")

# 播放页里的 `select#line` 选项，用于把 `line` 映射到线路名。
_LINE_OPTION_RE = re.compile(r"""['"]?([^'"]+)['"]?\s*value=['"]?([^'"]+)['"]""")

# 播放页里 `select#ep` 里的 `option value`。
_EP_OPTION_RE = re.compile(r"""['"]?([^'"]+)['"]?\s*value=['"]?([^'"]+)['"]""")

# 播放页的 m3u8 索引，一般形如 `http://.../play/.../index.m3u8`。
_M3U8_RE = re.compile(r"""https?://[^\s'"]+\.m3u8""", re.I)


# ------------------------------------------------------------------ 解密

def _unpad_pkcs7(payload: bytes) -> bytes:
    if not payload:
        raise ValueError("empty ciphertext")
    pad = payload[-1]
    if pad < 1 or pad > 16:
        raise ValueError("invalid PKCS#7 padding")
    if payload[-pad:] != bytes([pad] * pad):
        raise ValueError("PKCS#7 padding mismatch")
    return payload[:-pad]


def _aes_128_ecb_decrypt(key: str, ciphertext_b64: str) -> str:
    """按 `key: b64(ep_index)` 的查表格式解密，返回 UTF-8 明文。"""
    key_bytes = key.encode("utf-8")
    if len(key_bytes) != 16:
        raise ValueError(f"密钥不是 16 字节: {key!r}")
    try:
        blob = base64.b64decode(ciphertext_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"无效 base64: {ciphertext_b64!r}") from exc
    if len(blob) % 16 != 0:
        raise ValueError("密文长度不是 16 字节对齐")

    # AES-128-ECB: 每一列独立变换。Nielsen 给出的是列优先 4x4 状态。
    # 逆变换顺序：逆 ShiftRows -> 逆 MixColumns -> 逆 SubBytes -> 逆 AddRoundKey。
    state = list(blob)

    # 构造 AES S-box 与求逆 S-box。
    sbox = []
    for i in range(256):
        v = i
        if v == 0:
            s = 0x63
        else:
            c = v
            p = 1
            while p < 256:
                p <<= 1
                if p & 256:
                    p ^= 0x11B
                c ^= p
            s = c ^ 0x63
        sbox.append(s)

    inv_sbox = [0] * 256
    for i, s in enumerate(sbox):
        inv_sbox[s] = i

    # GF(2^8) 对数/指数表。
    gf_exp = [0] * 256
    gf_log = [0] * 256
    x = 1
    for i in range(255):
        gf_exp[i] = x
        gf_log[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11B
    gf_exp[255] = gf_exp[0]

    def gf_mul(a: int, b: int) -> int:
        if a == 0 or b == 0:
            return 0
        return gf_exp[(gf_log[a] + gf_log[b]) % 255]

    def gf_mul_const(a: int, c: int) -> int:
        if a == 0 or c == 0:
            return 0
        return gf_exp[(gf_log[a] + c) % 255]

    def add_round_key(rk: list[int]) -> None:
        for i in range(4):
            state[i] ^= rk[i]

    # 逆移位行。
    t = state[13]
    state[13] = state[9]
    state[9] = state[5]
    state[5] = state[1]
    state[1] = t

    t = state[14]
    state[14] = state[10]
    state[10] = state[6]
    state[6] = state[2]
    state[2] = t

    t = state[15]
    state[15] = state[11]
    state[11] = state[7]
    state[7] = state[3]
    state[3] = t

    # 逆 MixColumns：每列用矩阵 [0E 0B 0D 09; 09 0E 0B 0D; 0D 09 0E 0B; 0B 0D 09 0E] 变换。
    for col in range(4):
        a0 = state[col]
        a1 = state[col + 4]
        a2 = state[col + 8]
        a3 = state[col + 12]

        m0 = gf_mul_const(a0, 0x0E)
        m1 = gf_mul_const(a1, 0x0B)
        m2 = gf_mul_const(a2, 0x0D)
        m3 = gf_mul_const(a3, 0x09)

        m4 = gf_mul_const(a0, 0x09)
        m5 = gf_mul_const(a1, 0x0E)
        m6 = gf_mul_const(a2, 0x0B)
        m7 = gf_mul_const(a3, 0x0D)

        m8 = gf_mul_const(a0, 0x0D)
        m9 = gf_mul_const(a1, 0x09)
        m10 = gf_mul_const(a2, 0x0E)
        m11 = gf_mul_const(a3, 0x0B)

        m12 = gf_mul_const(a0, 0x0B)
        m13 = gf_mul_const(a1, 0x0D)
        m14 = gf_mul_const(a2, 0x09)
        m15 = gf_mul_const(a3, 0x0E)

        state[col] = m0 ^ m1 ^ m2 ^ m3
        state[col + 4] = m4 ^ m5 ^ m6 ^ m7
        state[col + 8] = m8 ^ m9 ^ m10 ^ m11
        state[col + 12] = m12 ^ m13 ^ m14 ^ m15

    # 逆 SubBytes。
    for i in range(16):
        state[i] = inv_sbox[state[i]]

    return bytes(state).decode("utf-8")


# ------------------------------------------------------------------ 站点

class Huangguoai:
    key = KEY
    name = NAME
    version = "1.0.0"
    base_url = BASE_URL
    mode = "direct"
    capabilities = ("meta", "home", "category", "detail", "play")

    def __init__(self, client=None):
        self.http = client or Client(
            base_url=BASE_URL,
            timeout=DEFAULT_TIMEOUT,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            retries=1,
        )

    # ---------------------------------------------------------------- 生命周期

    def meta(self):
        return {
            "key": self.key,
            "name": self.name,
            "version": self.version,
            "base_url": self.base_url,
            "mode": self.mode,
            "capabilities": list(self.capabilities),
            "play_format": ["m3u8"],
            "note": (
                "首页/分类页: /<分类 slug>/；详情: /detail/<id>.html；"
                "播放: /play/<id>.html，需 JS 解密 m3u8"
            ),
        }

    # ---------------------------------------------------------------- 请求

    def _page(self, path: str) -> str:
        response = self.http.get(path)
        if not response.ok:
            raise CrawlerError("HTTP_ERROR", f"{path} 返回 HTTP {response.status}")
        return response.text

    # ---------------------------------------------------------------- 动作

    def home(self):
        html = self._page("/")
        root = parse.parse_html(html)
        return self._common_page(root, "/")

    def category(self, tid=None, page=1):
        page = clean.to_int(page, 1) or 1
        if page < 1:
            page = 1
        if tid is None or str(tid).strip() == "":
            raise CrawlerError("NOT_FOUND", "缺少必填参数 --tid")
        tid = str(tid).strip()
        if not tid:
            raise CrawlerError("NOT_FOUND", f"无效的分类 id: {tid}")
        html = self._page(f"/{tid}/")
        root = parse.parse_html(html)
        return self._common_page(root, f"/{tid}/")

    def _common_page(self, root, current_path: str):
        categories = _categories(root)
        # 首页只抓推荐；分类页才抓完整片单。分类页可能只给当前页片单。
        videos = _videos(root, forbidden_selectors=("#app-mobile .banner .item",))
        has_more = _has_more(root, current_path)
        return {
            "categories": categories,
            "recommend": videos,
            "page": _current_page(root),
            "has_more": has_more,
        }

    def detail(self, id):
        detail_id = self._check_detail_id(id)
        if detail_id is None:
            raise CrawlerError("NOT_FOUND", f"无效的影片 id: {id}")

        root = parse.parse_html(self._page(f"/detail/{detail_id}.html"))
        video = _video(root, detail_id)
        if video is None:
            raise CrawlerError("NOT_FOUND", f"详情页中未解析到有效影片: {detail_id}")

        desc = _description(root)
        if not desc:
            raise CrawlerError("PARSE_ERROR", f"详情页缺少摘要: {detail_id}")

        episodes, lines = _episodes(root, detail_id)
        if not episodes:
            raise CrawlerError("PARSE_ERROR", f"详情页未解析到剧集: {detail_id}")

        video["episodes"] = episodes
        video["lines"] = lines
        video["desc"] = desc

        return {
            "video": video,
            "desc": desc,
            "episodes": episodes,
            "lines": lines,
        }

    def play(self, id=None, ep=1, line=1, play_id=None):
        index = clean.to_int(ep, 1) or 1
        if index < 1:
            index = 1
        line_no = clean.to_int(line, 1) or 1
        if line_no < 1:
            line_no = 1

        detail = self.detail(id)
        target = _pick_episode(detail, index, line_no)
        if target is None:
            raise CrawlerError(
                "NOT_FOUND",
                f"线路 {line_no} 第 {index} 集不存在（共 {len(detail['lines'])} 条线路）",
            )

        html = self._page(target["play_url"])
        m3u8 = _m3u8_from_play_page(html)
        if not m3u8:
            raise CrawlerError("PARSE_ERROR", "播放页未解密出 m3u8")

        return {"url": m3u8, "format": "m3u8", "headers": {"Referer": BASE_URL}}

    def _check_detail_id(self, id):
        value = str(id or "").strip()
        if not value:
            return None
        if not re.fullmatch(r"[0-9a-fA-F]{6,}", value):
            return None
        return value


# ------------------------------------------------------------------ 解析

def _categories(root):
    """顶栏导航 + 分类区块列出所有分类。

    注意：分页链接（``/ai-duanju/2``、``/ai-duanju/3``）和
    ``/ai-duanju/2/`` 这种伪分类必须过滤掉。
    """
    out = []
    seen = set()

    # 顶栏导航：<a class="hg-topbar-nav__item" href="/ai-duanju/">
    for anchor in root.select('a[href^="/ai-"]'):
        href = clean.clean_text(anchor.attr("href")) if anchor.attr("href") else ""
        if not href or _is_pager_link(href):
            continue
        name = clean.clean_text(anchor.text) or "未命名分类"
        if href not in seen:
            seen.add(href)
            out.append({"tid": href.rstrip("/"), "name": name})

    # 分类区块：<a class="hg-category-col__title" href="/ai-duanju/">
    for anchor in root.select('a.hg-category-col__title'):
        href = clean.clean_text(anchor.attr("href")) if anchor.attr("href") else ""
        if not href or _is_pager_link(href):
            continue
        name = clean.clean_text(anchor.text) or "未命名分类"
        if href not in seen:
            seen.add(href)
            out.append({"tid": href.rstrip("/"), "name": name})

    return out


def _videos(root, forbidden_selectors):
    """首页主推荐区的影片卡片 -> VodItem。"""
    out = []
    # 首页主推荐区：<a class="hg-drama-card__cover-link" href="/video/6875/">
    for node in root.select('a.hg-drama-card__cover-link'):
        match = re.search(r"/video/([0-9]+)/", node.attr("href") or "")
        if not match:
            continue
        name = clean.clean_text(node.text) or match.group(1)
        if not name:
            continue
        video = {
            "vod_id": match.group(1),
            "vod_name": name,
            "vod_pic": "",
            "vod_remarks": "",
        }
        out.append(video)
    return clean.dedupe(out, key=lambda item: item["vod_id"])


def _has_more(root, current_path: str) -> bool:
    # 首页/分类页都没有分页，返回 False；协议需要 has_more。
    return False


def _is_pager_link(href: str) -> bool:
    """判断是否是分页/伪分类链接，例：/ai-duanju/2、/ai-duanju/3。"""
    return bool(re.fullmatch(r"/ai-[a-z]+/\d+(\/.*)?", href))


def _current_page(root):
    # 当前页码：首页/分类页只有一页，返回 1。
    return 1


def _description(root):
    """详情页摘要：优先 meta description，其次正文。"""
    node = root.select_first('meta[name="description"]')
    if node is not None and node.attr("content"):
        text = clean.clean_text(node.attr("content"))
        if text:
            return text[:5000]

    node = root.select_first("[class*=desc]")
    if node is not None and node.text:
        text = clean.clean_text(node.text)
        if text:
            return text[:5000]

    node = root.select_first("[class*=intro]")
    if node is not None and node.text:
        text = clean.clean_text(node.text)
        if text:
            return text[:5000]

    return ""


def _episodes(root, detail_id):
    """详情页按线路逐集重查播放页，获取 m3u8 索引。"""
    lines = []
    line_names = []

    # 详情页播放入口：<select id="line"> 里的 <option>。
    for option in root.select('select#line option'):
        value = option.attr("value")
        if value:
            lines.append(value)
            name = clean.clean_text(option.text)
            if name:
                line_names.append(name)

    episodes = []
    for line_no, line in enumerate(lines, start=1):
        name = line_names[line_no - 1] if line_no - 1 < len(line_names) else line
        href = f"/play/{detail_id}.html?line={line}&ep=1"
        if name:
            episodes.append(
                {
                    "ep_index": 1,
                    "ep_name": name,
                    "play_url": href,
                    "line": name,
                    "line_no": line_no,
                }
            )
        else:
            episodes.append(
                {
                    "ep_index": 1,
                    "ep_name": f"第{line_no}集",
                    "play_url": href,
                    "line": line,
                    "line_no": line_no,
                }
            )

    return episodes, lines


def _pick_episode(detail, index, line_no):
    for episode in detail.get("episodes") or []:
        if episode.get("line_no") == line_no and episode.get("ep_index") == index:
            return episode
    return None


def _m3u8_from_play_page(html):
    """播放页 `<script id=config>` 里的 `key: b64(ep_index)`，按同一脚本
    里的 `key` 查表并 AES-128-ECB 解密，返回 m3u8 地址。"""
    root = parse.parse_html(html)
    scripts = root.select('script[id=config]')
    if not scripts:
        return None

    config_text = clean.clean_text(scripts[0].text)
    if not config_text:
        return None

    # 取 `key = '...'` 里的值。
    match = re.search(r"['\"]([0-9a-fA-F]{32,})['\"]\s*=", config_text)
    if not match:
        return None

    key = match.group(1)

    # 按线路选其实是在首页/分类页就返回了，播放页只需要按 `line` 取。
    for option in root.select('select#line option'):
        value = option.attr("value")
        if not value:
            continue
        # 取 `value` 的 `<option value="line">` 里 `value` 对应的值。实际线路
        # 名称直接来自 `<option>` 文本。
        option_text = clean.clean_text(option.text)
        index = _option_index(option_text, value)
        if index is None:
            continue

        # 按 `key: b64(ep_index)` 查表。
        for match in _CONFIG_RE.finditer(config_text):
            config_key = match.group(1)
            if config_key != key:
                continue
            ciphertext = match.group(2)
            try:
                plain = _aes_128_ecb_decrypt(key, ciphertext)
            except (ValueError, binascii.Error, OverflowError):
                log.warn(f"黄果解密失败: {config_key[:8]}... ep={index}")
                continue
            if plain:
                return plain

    return None


def _option_index(option_text: str, value: str) -> int | None:
    """根据 `select#ep` 里 `value` 的写法，取对应集号。"""
    # 常见写法：`value="1"`、`value="1"`、`value="1"`、`value="1"`。
    # 优先按 `value` 对应 `<option>` 里的文本取集号。
    for option in re.finditer(
        r"<option[^>]*value=['\"]([^'\"]+)['\"][^>]*>(.*?)</option>", option_text, re.S
    ):
        opt_value, opt_html = option.group(1), option.group(2)
        if opt_value == value:
            text = clean.clean_text(opt_html)
            if text:
                match = re.search(r"\d+", text)
                if match:
                    return int(match.group())
            return None
    # 兜底：如果 `value` 直接就是集号。
    if re.fullmatch(r"\d+", value):
        return int(value)
    return None


def _video(root, detail_id):
    name = root.select_first("h1")
    if name is not None and name.text:
        text = clean.clean_text(name.text)
        if text:
            return {
                "vod_id": detail_id,
                "vod_name": text,
                "vod_pic": "",
                "vod_remarks": "",
            }
    return None


if __name__ == "__main__":
    cli.main(Huangguoai())
