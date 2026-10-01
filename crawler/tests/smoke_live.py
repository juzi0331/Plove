#!/usr/bin/env python
"""联网冒烟测试 —— **不在离线测试套件里**，需要手动跑。

离线测试用 fixtures 保证"不联网也能测"，这个脚本则负责回答唯一一个
fixtures 回答不了的问题：**play 吐出来的地址，真的能播吗？**

它跑一遍 crawler-plan 第七节的验收流程：

    meta -> home -> category -> detail -> play -> 实际请求 m3u8

用法::

    python tests/smoke_live.py            # 默认站点
    python tests/smoke_live.py ai2048     # 指定站点 key

退出码 0 表示全部通过。
"""

from __future__ import annotations

import os
import sys
from urllib.parse import urljoin

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler_kit import cli, log  # noqa: E402
from crawler_kit.errors import CrawlerError  # noqa: E402
from crawler_kit.http import Client  # noqa: E402

SITES = {}


def _register():
    from sites.ai2048 import Ai2048
    from sites.ncat21 import Ncat21

    SITES[Ai2048.key] = Ai2048
    SITES[Ncat21.key] = Ncat21


class Smoke:
    def __init__(self, site):
        self.site = site
        self.failures = []

    def check(self, label, condition, detail=""):
        mark = "PASS" if condition else "FAIL"
        line = f"[{mark}] {label}"
        if detail:
            line += f" — {detail}"
        print(line, file=sys.stderr, flush=True)
        if not condition:
            self.failures.append(label)
        return condition

    def run(self):
        site = self.site

        meta = site.meta()
        self.check("meta", bool(meta.get("base_url")) and bool(meta.get("capabilities")),
                   f"{meta.get('name')} mode={meta.get('mode')}")

        home = site.home()
        self.check("home.recommend", len(home["recommend"]) > 0,
                   f"{len(home['recommend'])} 条 / {len(home['categories'])} 个分类")
        self.check("home.required_fields",
                   all(all(k in v for k in ("vod_id", "vod_name", "vod_pic", "vod_remarks"))
                       for v in home["recommend"]))

        tid = home["categories"][0]["tid"] if home["categories"] else None
        listing = site.category(tid=tid, page=1)
        self.check("category.videos", len(listing["videos"]) > 0,
                   f"tid={tid} 共 {len(listing['videos'])} 条, has_more={listing['has_more']}")
        if not listing["videos"]:
            return

        vod = listing["videos"][0]
        detail = site.detail(id=vod["vod_id"])
        self.check("detail.episodes", len(detail["episodes"]) > 0,
                   f"{detail['video']['vod_name']} 共 {len(detail['episodes'])} 集")
        if not detail["episodes"]:
            return

        episode = detail["episodes"][0]
        play = site.play(id=vod["vod_id"], ep=episode["ep_index"])
        self.check("play.format", play["format"] == "m3u8", play["url"][:110])
        self.check("play.url_is_absolute", play["url"].startswith("http"))

        # 真正的验收：地址能不能播
        client = Client(timeout=15.0, retries=1,
                        headers={"Referer": meta["base_url"] + "/"})
        response = client.get(play["url"])
        body = response.text
        self.check("play.fetch", response.ok, f"HTTP {response.status}")
        self.check("play.is_hls_manifest", body.lstrip().startswith("#EXTM3U"),
                   f"{len(body)} 字节")

        # 清单可能是媒体清单（有分片），也可能是主清单（要再跟一层到变体）。
        # 两种都合法，不能只认一种 —— 否则会把正常的 HLS 误判成失败。
        is_master = "#EXT-X-STREAM-INF" in body
        self.check("play.has_content", is_master or "#EXTINF" in body,
                   f"master={is_master} 分片条目={body.count('#EXTINF')}")
        if is_master:
            variant = next(
                (line.strip() for line in body.splitlines()
                 if line.strip() and not line.lstrip().startswith("#")),
                "",
            )
            self.check("play.variant_uri", bool(variant), variant[:80])
            if variant:
                variant_url = urljoin(play["url"], variant)
                nested = client.get(variant_url)
                nested_body = nested.text
                self.check("play.variant_is_manifest",
                           nested.ok and nested_body.lstrip().startswith("#EXTM3U"),
                           f"HTTP {nested.status}, {nested_body.count('#EXTINF')} 个分片条目")


def main(argv):
    cli.force_utf8()
    _register()
    key = argv[1] if len(argv) > 1 else next(iter(SITES))
    if key not in SITES:
        print(f"未知站点: {key}（可选: {', '.join(SITES)}）", file=sys.stderr)
        return 1

    print(f"=== 冒烟测试: {key} ===", file=sys.stderr)
    smoke = Smoke(SITES[key]())
    try:
        smoke.run()
    except CrawlerError as exc:
        print(f"\n中断 [{exc.code}] {exc.message}", file=sys.stderr)
        smoke.failures.append(exc.code)

    if smoke.failures:
        print(f"\n失败 {len(smoke.failures)} 项: {', '.join(smoke.failures)}", file=sys.stderr)
        return 1
    print("\n全部通过", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
