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
