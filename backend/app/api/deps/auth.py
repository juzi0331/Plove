"""身份鉴权与安全路由守卫（设备令牌、管理令牌、代理访问守卫）。"""

from __future__ import annotations

import secrets

from fastapi import Depends, Query, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.api.deps.db import get_db
from app.core.config import Settings, get_settings
from app.core.errors import AppError, ErrorCode
from app.models.device import Device
from app.services import activation_service, site_settings

#: 客户端保存这个令牌，之后每次请求都带上它。
#: 注意：设备身份是后端签发的，客户端自报的 device_id 一律不认。
DEVICE_TOKEN_HEADER = "X-Device-Token"

#: 后台管理令牌。它是运维凭证，与激活码完全无关：
#: 激活码管"谁能看内容"，它管"谁能管这台机器"。
ADMIN_TOKEN_HEADER = "X-Admin-Token"

device_token_header = APIKeyHeader(
    name=DEVICE_TOKEN_HEADER,
    scheme_name="DeviceToken",
    auto_error=False,
    description="激活后由 POST /api/v1/activation/redeem 返回的设备令牌",
)

admin_token_header = APIKeyHeader(
    name=ADMIN_TOKEN_HEADER,
    scheme_name="AdminToken",
    auto_error=False,
    description="后台管理令牌（.env 里的 PLOVE_ADMIN_TOKEN）",
)


def require_device(
    db: Session = Depends(get_db),
    token: str | None = Security(device_token_header),
) -> Device:
    """内容接口的守卫：必须是当前活跃设备才放行。

    挂在 router 上（dependencies=[Depends(require_device)]）而不是塞进每个路由，
    这样加接口时不会忘记加鉴权 —— 忘记加鉴权是这类系统最常见的事故。
    """
    device = activation_service.require_active(db, token)
    # 顺手刷新“源开关”的快照（带 5 秒 TTL）。
    # 为什么挂在这里：它守在所有内容接口上（router 级），是唯一
    # 不会漏掉新增路由的刷新点；而且这里手里已经有一个 Session。
    # 漏刷新的后果很具体：后台把源关掉了，内容接口却还在继续供应它。
    site_settings.store().refresh(db)
    return device


def require_admin(
    settings: Settings = Depends(get_settings),
    token: str | None = Security(admin_token_header),
) -> None:
    """后台接口的守卫。同样挂在 router 上。

    两条刻意的处理：
    * 没配令牌就一律拒绝。空令牌必须永远不能通过 —— 否则一个忘了配
      PLOVE_ADMIN_TOKEN 的部署就等于把后台裸奔在公网上。
    * 用 compare_digest 比较。普通 == 会在第一个不同的字符处
      提前返回，从响应时间上能一个字符一个字符地把令牌猜出来。
    """
    expected = settings.admin_token
    if not expected:
        raise AppError(
            ErrorCode.FORBIDDEN,
            "后台接口未启用：请先在 .env 里设置 PLOVE_ADMIN_TOKEN",
        )
    _WEAK_ADMIN_TOKENS = {"admin", "password", "123456", "root", "test", "admin123", "12345678", "qwerty"}
    if expected.strip().lower() in _WEAK_ADMIN_TOKENS:
        raise AppError(
            ErrorCode.FORBIDDEN,
            "管理令牌过于简单，存在严重安全隐患，请在 .env 中更换为高强度安全令牌",
        )
    if not token or not secrets.compare_digest(token, expected):
        raise AppError(ErrorCode.UNAUTHORIZED, "后台令牌不正确")


def require_proxy_access(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    device_token: str | None = Security(device_token_header),
    admin_token: str | None = Security(admin_token_header),
    token: str | None = Query(None, description="设备令牌或管理员凭证"),
) -> None:
    """代理接口守卫（图片防盗链代理、HLS 流媒体代理）。

    防白嫖与防非法代理：必须是「当前活跃设备」或「管理员凭据」方可中继媒体流与图片。
    支持通过 X-Device-Token 标头或 URL 查询参数 token 传入（兼容 HLS 切片与 img 标签）。
    """
    candidate_dev_token = device_token or token
    if candidate_dev_token:
        try:
            activation_service.require_active(db, candidate_dev_token)
            site_settings.store().refresh(db)
            return
        except AppError:
            pass

    candidate_admin_token = admin_token or token
    expected_admin = settings.admin_token
    if candidate_admin_token and expected_admin:
        _WEAK_ADMIN_TOKENS = {"admin", "password", "123456", "root", "test", "admin123", "12345678", "qwerty"}
        if expected_admin.strip().lower() not in _WEAK_ADMIN_TOKENS:
            if secrets.compare_digest(candidate_admin_token, expected_admin):
                return

    raise AppError(ErrorCode.UNAUTHORIZED, "未授权访问代理资源，请先激活设备或提供有效凭据")
