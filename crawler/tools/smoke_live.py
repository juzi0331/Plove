#!/usr/bin/env python
"""联网冒烟测试 —— 负责真实请求各方法链路，验证 play 吐出的真实流地址是否可播。

用法::

    python crawler/tools/smoke_live.py            # 测试默认站点
    python crawler/tools/smoke_live.py <site_key> # 指定站点 key

退出码 0 表示全部通过。
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path
import sys
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crawler_kit.http import Client

SITES = {}


def _register():
    sites_dir = Path(__file__).resolve().parents[1] / "sites"
    if str(Path(__file__).resolve().parents[1]) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    for py_file in sites_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
        mod_name = f"sites.{py_file.stem}"
        try:
            mod = importlib.import_module(mod_name)
            for attr in dir(mod):
                cls = getattr(mod, attr)
                if isinstance(cls, type) and hasattr(cls, "key") and hasattr(cls, "meta"):
                    SITES[cls.key] = cls
        except Exception:
            pass


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
                   f"id={vod['vod_id']} 共 {len(detail['episodes'])} 集 / {len(detail['lines'])} 条线路")
        if not detail["episodes"]:
            return

        ep = detail["episodes"][0]
        kwargs = {"id": vod["vod_id"], "ep": ep["ep_index"], "line": ep["line"]}
        if "play_id" in ep:
            kwargs["play_id"] = ep["play_id"]
        play = site.play(**kwargs)
        url = play.get("url")
        self.check("play.url", bool(url) and url.startswith("http"),
                   f"format={play.get('format')} url={url[:60]}...")
        if not url:
            return

        self._check_stream(url, play.get("headers") or {})

    def _check_stream(self, url: str, headers: dict[str, str]):
        client = Client(timeout=10, retries=1)
        try:
            head = client.get(url, headers={"Range": "bytes=0-1024", **headers})
            self.check("stream.probe", head.status in (200, 206),
                       f"status={head.status} content_type={head.headers.get('content-type')}")
        except Exception as exc:
            self.check("stream.probe", False, f"请求失败: {exc}")
            return

        if not url.endswith(".m3u8"):
            return
        m3u8 = head.text
        self.check("stream.is_m3u8", "#EXTM3U" in m3u8, "首包包含 #EXTM3U")

        first_ts = None
        for line in m3u8.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                first_ts = urljoin(url, line)
                break

        if first_ts:
            try:
                ts_resp = client.get(first_ts, headers={"Range": "bytes=0-1024", **headers})
                self.check("stream.first_ts", ts_resp.status in (200, 206),
                           f"分片可读 status={ts_resp.status} len={len(ts_resp.body)}")
            except Exception as exc:
                self.check("stream.first_ts", False, f"分片请求失败: {exc}")


def main():
    _register()
    if not SITES:
        print("未找到任何可用站点", file=sys.stderr)
        return 1

    target = sys.argv[1] if len(sys.argv) > 1 else next(iter(SITES))
    if target not in SITES:
        print(f"站点 {target!r} 未注册，可选: {list(SITES)}", file=sys.stderr)
        return 1

    site_cls = SITES[target]
    smoke = Smoke(site_cls())
    smoke.run()

    if smoke.failures:
        print(f"\n[FAIL] 冒烟测试失败，失败项: {smoke.failures}", file=sys.stderr)
        return 1

    print("\n[OK] 冒烟测试全部通过", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
