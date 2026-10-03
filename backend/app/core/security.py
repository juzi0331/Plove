"""安全工具与 SSRF 防护模块。"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "instance-data",
}

_DANGEROUS_PORTS = {
    21, 22, 23, 25, 110, 143, 3306, 5432, 6379, 9200, 11211, 27017,
}


def is_safe_public_url(url: str, resolve_dns: bool = True) -> bool:
    """严格校验 URL 是否为安全的外部公网目标，抵御 SSRF。
    
    1. 限制为 HTTP/HTTPS 协议；
    2. 禁止包含 user:pass 用户凭证信息；
    3. 校验端口范围并拦截敏感服务端口；
    4. 对目标主机名进行 DNS 解析，严格拦截回环、私有内网、链路本地、组播及云元数据地址；
    5. 正确放行合法的公网 IP（包括 Cloudflare 172.64.0.0/13 等公网段）。
    """
    if not url or not isinstance(url, str):
        return False

    url_str = url.strip()
    try:
        parsed = urlparse(url_str)
    except Exception:
        return False

    if parsed.scheme.lower() not in ("http", "https"):
        return False

    if parsed.username or parsed.password:
        return False

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        return False

    if hostname in _BLOCKED_HOSTNAMES or hostname.endswith(".local") or hostname.endswith(".internal"):
        return False

    if parsed.port and parsed.port in _DANGEROUS_PORTS:
        return False

    # 检查是否为直接填写的 IP 字符串
    try:
        direct_ip = ipaddress.ip_address(hostname)
        return _is_safe_ip(direct_ip)
    except ValueError:
        # 目标是域名
        pass

    if not resolve_dns:
        return True

    try:
        addr_infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
        if not addr_infos:
            return False
        for family, _, _, _, sockaddr in addr_infos:
            ip_str = sockaddr[0]
            ip_obj = ipaddress.ip_address(ip_str)
            if not _is_safe_ip(ip_obj):
                return False
        return True
    except (socket.gaierror, socket.herror, OSError, ValueError):
        return False


def _is_safe_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """判定单个 IP 地址是否属于合法的外部公网地址。"""
    # 处理 IPv4-mapped IPv6 地址 (如 ::ffff:127.0.0.1)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped

    if ip.is_loopback:
        return False
    if ip.is_private:
        return False
    if ip.is_link_local:
        return False
    if ip.is_multicast:
        return False
    if ip.is_reserved:
        return False
    if ip.is_unspecified:
        return False

    # 针对云服务厂商元数据特定地址防御
    str_ip = str(ip)
    if str_ip in ("169.254.169.254", "fd00:ec2::254"):
        return False

    return True
