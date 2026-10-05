import pytest
from app.services.stream_proxy_service import rewrite_m3u8_content, _decode_media_content

def test_rewrite_m3u8_content_media_playlist():
    raw_m3u8 = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:10
#EXT-X-MEDIA-SEQUENCE:1
#EXT-X-KEY:METHOD=AES-128,URI="crypt.key?token=123",IV=0x1234
#EXTINF:10.0,
seg1.png?exp=999
#EXTINF:10.0,
https://cdn.example.com/hls/seg2.ts
#EXT-X-ENDLIST
"""
    base_url = "https://source.example.com/hls/master/index.m3u8"
    rewritten = rewrite_m3u8_content(raw_m3u8, base_url=base_url, site="rou")

    lines = rewritten.splitlines()
    assert lines[0] == "#EXTM3U"
    # Check key rewrite
    key_line = [l for l in lines if l.startswith("#EXT-X-KEY")][0]
    assert '/api/v1/proxy/stream/key?url=' in key_line
    assert 'site=rou' in key_line
    assert 'https%3A//source.example.com/hls/master/crypt.key' in key_line

    # Check relative segment rewrite
    seg1_line = lines[6]
    assert seg1_line.startswith("/api/v1/proxy/stream/segment?url=")
    assert "https%3A//source.example.com/hls/master/seg1.png" in seg1_line
    assert "site=rou" in seg1_line

    # Check absolute segment rewrite
    seg2_line = lines[8]
    assert seg2_line.startswith("/api/v1/proxy/stream/segment?url=")
    assert "https%3A//cdn.example.com/hls/seg2.ts" in seg2_line

def test_rewrite_m3u8_content_variant_stream():
    master_m3u8 = """#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=1280000,RESOLUTION=720x480
720p/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=2560000,RESOLUTION=1920x1080
1080p/index.m3u8
"""
    base_url = "https://source.example.com/video/master.m3u8"
    rewritten = rewrite_m3u8_content(master_m3u8, base_url=base_url, site="rou")

    lines = rewritten.splitlines()
    assert lines[2].startswith("/api/v1/proxy/stream/m3u8?url=")
    assert "https%3A//source.example.com/video/720p/index.m3u8" in lines[2]
    assert lines[4].startswith("/api/v1/proxy/stream/m3u8?url=")
    assert "https%3A//source.example.com/video/1080p/index.m3u8" in lines[4]


def test_rewrite_m3u8_media_and_iframe_tags():
    m3u8 = """#EXTM3U
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",NAME="English",DEFAULT=YES,URI="audio/index.m3u8"
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",NAME="Chinese",URI="subs/zh.m3u8"
#EXT-X-I-FRAME-STREAM-INF:BANDWIDTH=86000,URI="iframe/index.m3u8"
#EXT-X-STREAM-INF:BANDWIDTH=1280000
video/index.m3u8
"""
    base_url = "https://source.example.com/video/master.m3u8"
    rewritten = rewrite_m3u8_content(m3u8, base_url=base_url, site="rou")
    assert '/api/v1/proxy/stream/m3u8?url=https%3A//source.example.com/video/audio/index.m3u8' in rewritten
    assert '/api/v1/proxy/stream/m3u8?url=https%3A//source.example.com/video/subs/zh.m3u8' in rewritten
    assert '/api/v1/proxy/stream/m3u8?url=https%3A//source.example.com/video/iframe/index.m3u8' in rewritten


def test_fetch_and_decode_segment_upstream_206_passthrough(monkeypatch):
    import httpx
    from unittest.mock import MagicMock
    from app.services.stream_proxy_service import fetch_and_decode_segment

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 206
    mock_resp.content = b"56789"
    mock_resp.is_redirect = False
    mock_resp.headers = {
        "content-type": "video/mp2t",
        "content-range": "bytes 5-9/10",
    }

    monkeypatch.setattr("app.services.stream_proxy_service.is_safe_public_url", lambda *args, **kwargs: True)
    monkeypatch.setattr("app.services.stream_proxy_service._create_http_client", lambda *args, **kwargs: MagicMock(__enter__=lambda s: MagicMock(get=lambda *a, **kw: mock_resp), __exit__=lambda *a: None))

    data, media_type, status, headers = fetch_and_decode_segment(
        "https://example.com/seg.ts",
        range_header="bytes=5-9",
    )
    assert status == 206
    assert data == b"56789"
    assert headers.get("Content-Range") == "bytes 5-9/10"
