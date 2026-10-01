"""黄果适配器离线回归：不依赖线上站点。"""

from __future__ import annotations

import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sites.huangguoai as hg  # noqa: E402
from sites.huangguoai import Huangguoai  # noqa: E402


class FakeResponse:
    def __init__(self, text: str, status: int = 200):
        self.status = status
        self.body = text.encode("utf-8")
        self.headers = {"content-type": "text/html; charset=utf-8"}
        self.url = "fake://"

    @property
    def ok(self):
        return 200 <= self.status < 300

    @property
    def text(self):
        return self.body.decode("utf-8")

    def json(self):
        return json.loads(self.text)


class FakeClient:
    def __init__(self, routes: dict[str, str]):
        self.routes = routes
        self.calls: list[str] = []

    def get(self, url, params=None, headers=None):
        self.calls.append(url)
        if url not in self.routes:
            return FakeResponse("<html>not found</html>", 404)
        return FakeResponse(self.routes[url])


def detail_page() -> str:
    return """
    <html>
      <head><meta name="description" content="测试简介"></head>
      <body>
        <h1>测试影片</h1>
        <select id="line">
          <option value="fast">高速线</option>
          <option value="backup">备用线</option>
        </select>
      </body>
    </html>
    """


class HuangguoTests(unittest.TestCase):
    def test_category_normalizes_tid_and_extracts_real_cover(self):
        html = """
        <html><body>
          <a class="hg-topbar-nav__item" href="/ai-duanju/">AI短剧</a>
          <a class="hg-drama-card__cover-link" href="/video/7420/" title="测试影片">
            <img src="/static/web/images/cover-placeholder.png"
                 data-src="https://img.example/cover.jpg" alt="测试影片">
          </a>
        </body></html>
        """
        client = FakeClient({"/ai-duanju/": html})
        result = Huangguoai(client).category("ai-duanju", 1)

        self.assertEqual(client.calls, ["/ai-duanju/"])
        self.assertEqual(result["categories"][0]["tid"], "ai-duanju")
        self.assertEqual(result["recommend"][0]["vod_id"], "7420")
        self.assertEqual(result["recommend"][0]["vod_name"], "测试影片")
        self.assertEqual(result["recommend"][0]["vod_pic"], "https://img.example/cover.jpg")

    def test_detail_accepts_numeric_id_and_returns_contract_shape(self):
        client = FakeClient({"/detail/7420.html": detail_page()})
        result = Huangguoai(client).detail("7420")

        self.assertEqual(client.calls, ["/detail/7420.html"])
        self.assertEqual(result["video"]["vod_id"], "7420")
        self.assertEqual(result["video"]["vod_name"], "测试影片")
        self.assertEqual(result["desc"], "测试简介")
        self.assertEqual(
            result["lines"],
            [
                {"line": 1, "name": "高速线", "count": 1},
                {"line": 2, "name": "备用线", "count": 1},
            ],
        )
        self.assertEqual(
            result["episodes"],
            [
                {
                    "ep_index": 1,
                    "ep_name": "第1集",
                    "play_id": "/play/7420.html?line=fast&ep=1",
                    "line": 1,
                },
                {
                    "ep_index": 1,
                    "ep_name": "第1集",
                    "play_id": "/play/7420.html?line=backup&ep=1",
                    "line": 2,
                },
            ],
        )

    def test_invalid_detail_id_is_rejected(self):
        site = Huangguoai(FakeClient({}))
        with self.assertRaises(Exception):
            site.detail("../etc/passwd")

    def test_play_uses_selected_internal_line_and_ignores_external_play_id(self):
        routes = {
            "/detail/7420.html": detail_page(),
            "/play/7420.html?line=backup&ep=1": "<html>play</html>",
        }
        client = FakeClient(routes)
        site = Huangguoai(client)

        with patch.object(hg, "_m3u8_from_play_page", return_value="https://cdn.example/video.m3u8"):
            result = site.play(
                id="7420",
                ep=1,
                line=2,
                play_id="/play/9999.html?line=evil&ep=1",
            )

        self.assertEqual(
            client.calls,
            ["/detail/7420.html", "/play/7420.html?line=backup&ep=1"],
        )
        self.assertEqual(result["url"], "https://cdn.example/video.m3u8")
        self.assertEqual(result["format"], "m3u8")


if __name__ == "__main__":
    unittest.main()
