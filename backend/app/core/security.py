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


_FAKE_IP_NETWORKS = (
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("127.128.0.0/9"),
    ipaddress.ip_network("28.0.0.0/8"),
    ipaddress.ip_network("fd00:696e::/32"),
)


def _is_safe_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address, is_from_dns: bool = False) -> bool:
    """判定单个 IP 地址是否属于合法的外部公网地址。"""
    # 处理 IPv4-mapped IPv6 地址 (如 ::ffff:127.0.0.1)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped

    # 兼容透明代理/TUN 模式与 DNS 污染下由 DNS 虚拟分配的 Fake-IP 公网段
    if is_from_dns:
        if any(ip in net for net in _FAKE_IP_NETWORKS):
            return True
        # 兼容 TUN/Mihomo/Sing-box 与 DNS 污染分配的 127.x.x.x 虚拟段（排除真实主机环回 127.0.0.1）
        if isinstance(ip, ipaddress.IPv4Address) and ip in ipaddress.ip_network("127.0.0.0/8") and str(ip) != "127.0.0.1":
            return True

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


def is_safe_public_url(url: str, resolve_dns: bool = True) -> bool:
    """严格校验 URL 是否为安全的外部公网目标，抵御 SSRF。"""
    if not url or not isinstance(url, str):
        return False

    url_str = url.strip().strip("'\"`")
    if url_str.startswith("//"):
        url_str = "https:" + url_str
    elif not url_str.startswith(("http://", "https://")) and "://" not in url_str:
        url_str = "https://" + url_str

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

    try:
        port = parsed.port
        if port and port in _DANGEROUS_PORTS:
            return False
    except (ValueError, TypeError):
        return False

    # 检查是否为直接填写的 IP 字符串
    try:
        direct_ip = ipaddress.ip_address(hostname)
        return _is_safe_ip(direct_ip, is_from_dns=False)
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
            if not _is_safe_ip(ip_obj, is_from_dns=True):
                return False
        return True
    except (socket.gaierror, socket.herror, OSError, ValueError):
        return False
