from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sites.xiaoyakankan import Xiaoyakankan

HOME = """
<html><body><div class="m4-main">
  <div class="m4-meta"><h2>电影</h2><a href="/cat/10.html">全部电影</a></div>
  <div class="m4-list">
    <div class="item">
      <a class="link" href="/post/abcdef12.html"><img data-src="https://img/a.jpg" alt="电影A"></a>
      <div class="info"><div class="title">电影A</div><div class="desc">演员A</div></div>
      <span class="tag1">1080p</span><span class="tag2">剧情片 / 2026年</span>
    </div>
  </div>
  <div class="m4-meta"><h2>连续剧</h2><a href="/cat/11.html">全部连续剧</a></div>
  <div class="m4-list">
    <div class="item">
      <a class="link" href="/post/1234abcd.html"><img data-src="https://img/b.jpg" alt="剧集B"></a>
      <div class="info"><div class="title">剧集B</div><div class="desc">演员B</div></div>
      <span class="tag1">720p</span><span class="tag2">国产剧 / 2025年</span>
    </div>
  </div>
</div></body></html>
"""

DETAIL = """
<html><body>
<h1>电影A</h1>
<script>
var pp={"no":"abcdef12","lines":[["1","线路1",1,["https://v.example/index.m3u8"]]]};
</script>
</body></html>
"""
class FakeResponse:
    def __init__(self, text, status=200):
        self.status = status
        self.body = text.encode("utf-8")
        self.headers = {"content-type": "text/html; charset=utf-8"}

    @property
    def ok(self):
        return 200 <= self.status < 300

    @property
    def text(self):
        return self.body.decode("utf-8")


class FakeClient:
    def get(self, path, params=None, headers=None):
        if path == "/":
            return FakeResponse(HOME)
        if path == "/post/abcdef12.html":
            return FakeResponse(DETAIL)
        return FakeResponse("<html>not found</html>", 404)


class XiaoyaHomeTests(unittest.TestCase):
    def test_home_preserves_real_source_sections(self):
        data = Xiaoyakankan(client=FakeClient()).home()
        self.assertEqual([s["title"] for s in data["sections"]], ["电影", "连续剧"])
        self.assertEqual([len(s["videos"]) for s in data["sections"]], [1, 1])
        self.assertEqual([v["vod_id"] for v in data["recommend"]], ["abcdef12", "1234abcd"])


class XiaoyaPlaybackTests(unittest.TestCase):
    def test_playback_does_not_emit_forbidden_referer_header(self):
        data = Xiaoyakankan(client=FakeClient()).play(id="abcdef12", ep=1, line=1)
        self.assertEqual(data["url"], "https://v.example/index.m3u8")
        self.assertEqual(data["format"], "m3u8")
        self.assertEqual(data["headers"], {})


if __name__ == "__main__":
    unittest.main()
