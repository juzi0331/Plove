"""异步高性能 HTTP 客户端。

具备能力：
1. 连接池复用与长连接；
2. 自动检测并破解反爬闸门（cdndefend 等）；
3. 文本编码自动探测（UTF-8, GBK, GB2312 等）；
4. 超时、网络故障统一翻译为规范异常。
"""

from __future__ import annotations

from typing import Any, Optional
import httpx

from .errors import CrawlerServiceError, ErrorCode
from .gates import solve_cdndefend_cookie
from .log import get_logger
from ..config import settings

import time
import urllib.parse

logger = get_logger("http_client")

# 全局 Host 级别闸门 Cookie 缓存池：复用已解出的 Cookie (如 cdndefend_js_cookie)，避免跨页面跳转重复拦截
_GATE_COOKIE_CACHE: dict[str, tuple[dict[str, str], float]] = {}


def _get_cached_gate_cookies(host: str) -> dict[str, str]:
    if not host:
        return {}
    clean_host = host.split(":")[0].lower()
    entry = _GATE_COOKIE_CACHE.get(clean_host)
    if entry:
        cookies, expires_at = entry
        if time.monotonic() < expires_at:
            return cookies
        _GATE_COOKIE_CACHE.pop(clean_host, None)
    return {}


def _save_cached_gate_cookies(host: str, cookies: dict[str, str], ttl: float = 1800.0) -> None:
    if not host or not cookies:
        return
    clean_host = host.split(":")[0].lower()
    _GATE_COOKIE_CACHE[clean_host] = (dict(cookies), time.monotonic() + ttl)


class HttpClient:
    """通用的异步 HTTP 抓取客户端。"""

    def __init__(
        self,
        base_url: str = "",
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
        cookies: Optional[dict[str, str]] = None,
    ) -> None:
        self.base_url = base_url
        req_headers = {
            "User-Agent": settings.DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        if headers:
            req_headers.update(headers)

        from ..engine.proxy_manager import proxy_manager

        effective_proxy = proxy_manager.get_proxy_url()
        client_cookies = dict(cookies or {})

        # 尝试注入宿主机已缓存的放行 Cookie
        if self.base_url.startswith("http"):
            try:
                host = urllib.parse.urlparse(self.base_url).netloc
                cached = _get_cached_gate_cookies(host)
                if cached:
                    client_cookies.update(cached)
            except Exception:
                pass

        self._timeout = timeout or settings.DEFAULT_TIMEOUT
        self._client = httpx.AsyncClient(
            base_url=self.base_url if self.base_url.startswith("http") else "",
            headers=req_headers,
            cookies=client_cookies,
            proxy=effective_proxy,
            trust_env=bool(effective_proxy),  # 未显式配置代理时强制直连，不受 Windows 系统全局代理劫持
            timeout=httpx.Timeout(self._timeout, connect=5.0),
            follow_redirects=True,
            verify=False,  # 目标源站经常有证书过期或自签情况，避免因 SSL 阻断抓取
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "HttpClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def request(
        self,
        method: str,
        url: str,
        params: Optional[dict[str, Any]] = None,
        data: Optional[Any] = None,
        json_body: Optional[Any] = None,
        headers: Optional[dict[str, str]] = None,
        custom_timeout: Optional[float] = None,
        enable_gate_solving: bool = True,
    ) -> httpx.Response:
        """发起异步 HTTP 请求并自动拦截处理闸门。"""
        timeout = custom_timeout or self._timeout
        # 发送请求前，尝试预注入 Host 缓存的 Cookie
        try:
            req_host = urllib.parse.urlparse(url).netloc or urllib.parse.urlparse(self.base_url).netloc
            cached_cookies = _get_cached_gate_cookies(req_host)
            if cached_cookies:
                self._client.cookies.update(cached_cookies)
        except Exception:
            pass

        try:
            resp = await self._client.request(
                method=method,
                url=url,
                params=params,
                data=data,
                json=json_body,
                headers=headers,
                timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            logger.warning("请求超时: method=%s url=%s timeout=%ss", method, url, timeout)
            raise CrawlerServiceError(
                ErrorCode.TIMEOUT,
                f"请求目标源站超时（{timeout}s）: {url}",
            ) from exc
        except httpx.RequestError as exc:
            logger.error("网络请求失败: %s", exc)
            raise CrawlerServiceError(
                ErrorCode.HTTP_ERROR,
                f"网络连接错误: {exc}",
            ) from exc

        # 检查是否命中了反爬闸门 (支持 850, 403, 503, 200 以及任何带 cdndefend 的挑战页)
        if enable_gate_solving and (resp.status_code in (200, 403, 503, 850) or "cdndefend" in resp.text[:10000]):
            resp_text = resp.text
            if "cdndefend" in resp_text:
                logger.info("检测到反爬闸门拦截 (HTTP %d)，启动破解机制...", resp.status_code)
                gate_cookies = solve_cdndefend_cookie(resp_text)
                if gate_cookies:
                    # 缓存已破解的 Cookie，方便后续页面跳转直接放行
                    try:
                        req_host = urllib.parse.urlparse(url).netloc or urllib.parse.urlparse(self.base_url).netloc
                        _save_cached_gate_cookies(req_host, gate_cookies)
                    except Exception:
                        pass
                    # 将求解出来的 Cookie 写入客户端实例并重试一次请求
                    self._client.cookies.update(gate_cookies)
                    logger.info("携带闸门 Cookie (%s) 重试请求...", gate_cookies)
                    return await self.request(
                        method=method,
                        url=url,
                        params=params,
                        data=data,
                        json_body=json_body,
                        headers=headers,
                        custom_timeout=timeout,
                        enable_gate_solving=False,  # 避免递归死循环
                    )

        if resp.status_code >= 400:
            if resp.status_code == 404:
                raise CrawlerServiceError(ErrorCode.NOT_FOUND, f"目标资源不存在 (404): {url}")
            if resp.status_code in (403, 401):
                raise CrawlerServiceError(ErrorCode.BLOCKED, f"源站拒绝访问 ({resp.status_code}): {url}")
            raise CrawlerServiceError(
                ErrorCode.HTTP_ERROR,
                f"源站返回非正常状态码 ({resp.status_code}): {url}",
            )

        return resp

    async def get_text(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        encoding: Optional[str] = None,
    ) -> str:
        """获取纯文本/HTML 内容。"""
        resp = await self.request("GET", url, params=params, headers=headers)
        if encoding:
            resp.encoding = encoding
        elif resp.encoding is None or resp.encoding.lower() == "iso-8859-1":
            # 自动优先用 utf-8
            resp.encoding = "utf-8"
        return resp.text

    async def get_json(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> Any:
        """获取解析后的 JSON 对象。"""
        resp = await self.request("GET", url, params=params, headers=headers)
        try:
            return resp.json()
        except Exception as exc:
            raise CrawlerServiceError(
                ErrorCode.PARSE_ERROR,
                f"目标接口返回非合法 JSON 内容: {exc}",
            ) from exc
