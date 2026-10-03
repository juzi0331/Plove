from __future__ import annotations

import json
import re
from typing import Optional

_M3U8_REGEX = re.compile(
    r"""(?:["']|\b)(https?://[^\s"'<>]+\.m3u8[^\s"'<>]*)(?:["']|\b)""",
    re.IGNORECASE,
)
_MP4_REGEX = re.compile(
    r"""(?:["']|\b)(https?://[^\s"'<>]+\.mp4[^\s"'<>]*)(?:["']|\b)""",
    re.IGNORECASE,
)


def sniff_stream_url(html: str) -> Optional[dict[str, str]]:
    """从页面源码中嗅探真实的 m3u8 / mp4 视频播放流地址。"""
    # 1. 优先检查内嵌 var pp 播放器直链
    pp_match = re.search(r"var\s+pp\s*=\s*(\{.*?\});", html)
    if pp_match:
        try:
            pp_data = json.loads(pp_match.group(1))
            for line in pp_data.get("lines", []):
                if (
                    isinstance(line, list)
                    and len(line) >= 4
                    and isinstance(line[3], list)
                    and line[3]
                ):
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
