"""反爬闸门：**自定义状态码 + 前端算出来的 cookie**。

ncat21.com 用 ``cdndefend``：不带 cookie 请求，服务端返回 HTTP **850** 和一个
6.5KB 的挑战页，页面里的 JS 算出一个 cookie 写进去，然后刷新。这类闸门的
共同形状是固定的，所以这里把"检测 → 求解 → 注入 → 缓存有效期"这段流程
抽成一份，站点只需要提供 ``solve(challenge_html) -> cookie_value``。

求解函数由站点提供而不是框架提供 —— **算法是站点私有的，机制才是通用的**。
"""

from __future__ import annotations

import time

from . import log
from .errors import BLOCKED, CrawlerError


class CookieGate:
    def __init__(
        self,
        solve,
        cookie_name: str,
        challenge_status: int = 850,
        ttl: float = 1800.0,
        probe_url: str = "/",
    ):
        self.solve = solve
        self.cookie_name = cookie_name
        self.challenge_status = int(challenge_status)
        self.ttl = float(ttl)
        self.probe_url = probe_url
        self._value = None
        self._solved_at = 0.0

    # ------------------------------------------------------------------ 状态

    @property
    def solved(self) -> bool:
        if self._value is None:
            return False
        return (time.monotonic() - self._solved_at) < self.ttl

    @property
    def value(self):
        return self._value

    def reset(self) -> None:
        self._value = None
        self._solved_at = 0.0

    # ------------------------------------------------------------------ 主流程

    def ensure(self, client, probe_url: str | None = None, force: bool = False) -> bool:
        """保证 ``client`` 手上有一个可用的放行 cookie。

        已解且没过期就直接返回；否则探测一次，被拦就解一次。
        """
        if not force and self.solved:
            return True

        url = probe_url or self.probe_url
        response = client.get(url)
        if response.ok:
            # 这次没被拦（可能压根没开闸，也可能上层的 cookie 还有效）
            return True
        if response.status != self.challenge_status:
            raise CrawlerError(
                BLOCKED, f"闸门探测返回意外状态码 {response.status}（{url}）"
            )

        value = self.solve(response.text)
        if not value:
            raise CrawlerError(BLOCKED, f"闸门求解失败（{url}）")

        client.set_cookies({self.cookie_name: value})
        self._value = value
        self._solved_at = time.monotonic()
        log.info(f"闸门已通过: {self.cookie_name}={value[:12]}…（{url}）")
        return True

    def fetch(self, client, url: str):
        """取页面；中途 cookie 失效就重解一次再取。"""
        self.ensure(client)
        response = client.get(url)
        if response.status == self.challenge_status:
            log.warn(f"cookie 失效，重新求解闸门: {url}")
            self.reset()
            self.ensure(client, force=True)
            response = client.get(url)
            if response.status == self.challenge_status:
                raise CrawlerError(BLOCKED, f"重新求解后仍被拦: {url}")
        return response
