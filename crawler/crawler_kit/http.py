"""HTTP 客户端：超时、重试、Cookie 注入、代理、非标准状态码。

设计要点（都是被真实站点逼出来的）：

1. **非 2xx 不抛异常**，原样把 ``Response`` 交给上层。ncat21.com 连
   反爬闸门都是自定义状态码 ``850``，抛异常反而拿不到响应体。
2. **Cookie 用简单的字典管理**，不走 ``http.cookiejar``。站点常见
   ``xxx_js_cookie`` 这类由 JS 算出来的值，行为要完全可预测。
3. **只有网络错误和 5xx 才重试**；4xx / 非标准码立即返回，避免把
   一个明确的"被拦了"重试成"超时了"。
"""

from __future__ import annotations

import json as _json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

from . import log
from .errors import PARSE_ERROR, CrawlerError, TIMEOUT

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

MAX_BYTES = 8 * 1024 * 1024


def _normalize(headers):
    """把 header 名统一成 ``Title-Case``，避免出现重复的 User-Agent。"""
    out = {}
    for key, value in (headers or {}).items():
        if value is None:
            continue
        out[str(key).title()] = str(value)
    return out


class Response:
    """一次请求的结果，无论状态码是多少都返回这个对象。"""

    __slots__ = ("status", "headers", "body", "url")

    def __init__(self, status: int, headers: dict, body: bytes, url: str):
        self.status = status
        self.headers = headers
        self.body = body
        self.url = url

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    @property
    def text(self) -> str:
        ctype = self.headers.get("content-type", "")
        charset = "utf-8"
        if "charset=" in ctype:
            charset = ctype.split("charset=", 1)[1].split(";")[0].strip() or "utf-8"
        try:
            return self.body.decode(charset, errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")

    def json(self):
        try:
            return _json.loads(self.text)
        except ValueError as exc:
            raise CrawlerError(PARSE_ERROR, f"响应不是合法 JSON: {exc}") from exc


class Client:
    def __init__(
        self,
        base_url: str = "",
        headers=None,
        timeout: float = 10.0,
        retries: int = 2,
        backoff: float = 0.6,
        cookies=None,
        proxy: str | None = None,
        min_interval: float = 0.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.default_headers = _normalize(headers)
        self.timeout = float(timeout)
        self.retries = max(0, int(retries))
        self.backoff = float(backoff)
        self.cookies = {str(k): str(v) for k, v in (cookies or {}).items()}
        self.proxy = proxy
        #: 两次请求之间的最小间隔（秒）。
        #: 防范的场景：请求被打得太快时源站会在 TLS 层直接丢包，客户端只能看到
        #: "handshake operation timed out"，完全看不出原因。具体阈值各站不同，
        #: 所以默认不限速（0），对脆弱的源由站点自己设一个保守值。
        self.min_interval = max(0.0, float(min_interval))
        self._last_request_at = 0.0

        handlers = []
        effective_proxy = proxy
        if not effective_proxy:
            import os
            effective_proxy = (
                os.environ.get("HTTPS_PROXY")
                or os.environ.get("HTTP_PROXY")
                or os.environ.get("https_proxy")
                or os.environ.get("http_proxy")
                or os.environ.get("ALL_PROXY")
                or os.environ.get("all_proxy")
            )
        if effective_proxy:
            handlers.append(
                urllib.request.ProxyHandler({"http": effective_proxy, "https": effective_proxy})
            )
        self._opener = urllib.request.build_opener(*handlers)

    # ---------------------------------------------------------------- cookie

    def set_cookies(self, cookies) -> None:
        for key, value in (cookies or {}).items():
            self.cookies[str(key)] = str(value)

    def _absorb_cookies(self, headers) -> None:
        for raw in headers.get_all("Set-Cookie", []) or []:
            pair = raw.split(";", 1)[0].strip()
            if "=" in pair:
                name, value = pair.split("=", 1)
                self.cookies[name.strip()] = value.strip()

    # ---------------------------------------------------------------- request

    def _build_url(self, url: str, params=None) -> str:
        if not url.startswith(("http://", "https://")):
            url = self.base_url + (url if url.startswith("/") else "/" + url)
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            if clean:
                sep = "&" if "?" in url else "?"
                url = url + sep + urllib.parse.urlencode(clean)
        return url

    def _throttle(self) -> None:
        if self.min_interval <= 0:
            return
        waited = time.monotonic() - self._last_request_at
        remaining = self.min_interval - waited
        if self._last_request_at and remaining > 0:
            time.sleep(remaining)
        self._last_request_at = time.monotonic()

    def _headers(self, extra=None) -> dict:
        merged = dict(self.default_headers)
        merged.update(_normalize(extra))
        if self.cookies:
            merged["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        merged.setdefault("User-Agent", DEFAULT_UA)
        return merged

    def request(
        self,
        method: str,
        url: str,
        params=None,
        headers=None,
        data=None,
        json_body=None,
    ) -> Response:
        full = self._build_url(url, params)

        body = None
        extra_headers = dict(headers or {})
        if json_body is not None:
            body = _json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            extra_headers.setdefault("Content-Type", "application/json")
        elif data is not None:
            if isinstance(data, (bytes, bytearray)):
                body = bytes(data)
            else:
                body = urllib.parse.urlencode(data).encode("utf-8")
                extra_headers.setdefault(
                    "Content-Type", "application/x-www-form-urlencoded"
                )

        attempt = 0
        while attempt <= self.retries:
            attempt += 1
            self._throttle()
            request = urllib.request.Request(full, data=body, method=method.upper())
            for key, value in self._headers(extra_headers).items():
                request.add_header(key, value)

            try:
                with self._opener.open(request, timeout=self.timeout) as response:
                    payload = response.read(MAX_BYTES)
                    self._absorb_cookies(response.headers)
                    return Response(
                        response.status,
                        {k.lower(): v for k, v in response.headers.items()},
                        payload,
                        full,
                    )
            except urllib.error.HTTPError as exc:
                payload = exc.read(MAX_BYTES)
                self._absorb_cookies(exc.headers)
                exc.close()  # HTTPError 既是异常也是文件对象，不关会漏 socket
                response = Response(
                    exc.code,
                    {k.lower(): v for k, v in exc.headers.items()},
                    payload,
                    full,
                )
                if 500 <= exc.code < 600 and attempt <= self.retries:
                    log.warn(f"HTTP {exc.code}，第 {attempt} 次重试: {full}")
                    time.sleep(self.backoff * attempt)
                    continue
                # 4xx 与自定义状态码（850 等）原样返回，交给上层判断
                return response
            except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as exc:
                if attempt <= self.retries:
                    log.warn(f"网络错误，第 {attempt} 次重试: {full} ({exc})")
                    time.sleep(self.backoff * attempt)
                    continue
                raise CrawlerError(TIMEOUT, f"请求失败: {full} ({exc})") from exc

        raise CrawlerError(TIMEOUT, f"请求失败: {full}")  # pragma: no cover

    def get(self, url: str, params=None, headers=None) -> Response:
        return self.request("GET", url, params=params, headers=headers)

    def post(self, url: str, data=None, json_body=None, headers=None) -> Response:
        return self.request(
            "POST", url, data=data, json_body=json_body, headers=headers
        )

    # ----------------------------------------------------------- 便捷封装

    def get_json(self, url: str, params=None, headers=None):
        response = self.get(url, params=params, headers=headers)
        if not response.ok:
            raise CrawlerError(
                "HTTP_ERROR", f"{url} 返回 HTTP {response.status}"
            )
        return response.json()

    def get_text(self, url: str, params=None, headers=None) -> str:
        response = self.get(url, params=params, headers=headers)
        if not response.ok:
            raise CrawlerError(
                "HTTP_ERROR", f"{url} 返回 HTTP {response.status}"
            )
        return response.text
