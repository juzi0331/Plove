"""反爬挑战与闸门求解器。

包含：
1. cdndefend SHA-1 算力质押快速暴力求解（Python 原生算法 ~30ms，无需任何浏览器驱动）
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional

from .errors import CrawlerServiceError, ErrorCode
from .log import get_logger

logger = get_logger("gates")

# 提取 cdndefend 挑战页中的 secret 常量
_CDNDEFEND_SECRET_RE = re.compile(
    r"""(?:var|let|const)\s+c\s*=\s*['"]([0-9a-fA-F]{32,64})['"]"""
)


def solve_cdndefend_cookie(html: str) -> Optional[dict[str, str]]:
    """从 HTML 挑战页提取 secret，秒算 cdndefend_js_cookie。

    算法原理：
    从挑战页提取 40 位十六进制 secret c，首字符作为十六进制索引 n1 = int(c[0], 16)。
    自增 i，对 c + str(i) 求 SHA-1，当摘要的 digest[n1] == 0xb0 且 digest[n1+1] == 0x0b 时命中。
    最终设置 Cookie: cdndefend_js_cookie = c + str(i)
    """
    match = _CDNDEFEND_SECRET_RE.search(html)
    if not match:
        return None

    secret = match.group(1)
    try:
        n1 = int(secret[0], 16)
    except ValueError:
        return None

    logger.debug("发现 cdndefend 挑战页，开始求解: secret=%s, n1=%d", secret, n1)

    secret_bytes = secret.encode("ascii")
    # 期望 ~65536 次循环，纯 Python 原生字节操作只需 20~40 毫秒
    for i in range(2_000_000):
        candidate = secret_bytes + str(i).encode("ascii")
        digest = hashlib.sha1(candidate).digest()  # noqa: S324 - 目标源站算法即为 sha1
        if digest[n1] == 0xB0 and digest[n1 + 1] == 0x0B:
            cookie_value = secret + str(i)
            logger.info("cdndefend 挑战求解成功！迭代 %d 次，cookie=%s", i, cookie_value)
            return {"cdndefend_js_cookie": cookie_value}

    raise CrawlerServiceError(
        ErrorCode.BLOCKED,
        "cdndefend 求解超时：200万次迭代未命中目标 hash",
    )
