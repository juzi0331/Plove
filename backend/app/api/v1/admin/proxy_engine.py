"""后台 — Xray 核心引擎自动管理与状态托管。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.admin._audit import audit
from app.core.logging import get_logger
from app.core.middleware import get_request_id
from app.schemas.admin_site_control import (
    ProxyEngineActionResponse,
    ProxyEngineStatusPayload,
)
from app.schemas.envelope import Envelope, ok
from app.services.proxy_node import proxy_node_service, xray_engine

logger = get_logger(__name__)

router = APIRouter(tags=["后台-代理引擎"])


@router.get("/proxy-engine/status", response_model=Envelope[ProxyEngineStatusPayload], summary="获取 Xray 核心引擎状态")
def get_proxy_engine_status(
    request_id: str = Depends(get_request_id),
) -> Envelope[ProxyEngineStatusPayload]:
    status = xray_engine.get_status(proxy_node_service.get_nodes())
    return ok(ProxyEngineStatusPayload(**status), request_id)


@router.post("/proxy-engine/install", response_model=Envelope[ProxyEngineActionResponse], summary="一键下载并安装 Xray 核心引擎")
async def install_proxy_engine(
    request_id: str = Depends(get_request_id),
) -> Envelope[ProxyEngineActionResponse]:
    try:
        await xray_engine.install_binary()
        start_res = xray_engine.start_engine(proxy_node_service.get_nodes())
        status = xray_engine.get_status(proxy_node_service.get_nodes())
        if not status.get("running"):
            err_detail = start_res.get("error") or "Xray 核心已成功安装，但启动失败"
            audit("install_proxy_engine", request_id, success=False, error=err_detail)
            return ok(
                ProxyEngineActionResponse(
                    success=False,
                    message=f"Xray 核心已成功安装，但启动失败: {err_detail}",
                    status=ProxyEngineStatusPayload(**status),
                ),
                request_id,
            )
        audit("install_proxy_engine", request_id, success=True)
        return ok(
            ProxyEngineActionResponse(
                success=True,
                message="Xray 核心已成功安装并启动托管",
                status=ProxyEngineStatusPayload(**status),
            ),
            request_id,
        )
    except Exception as exc:
        logger.error("安装 Xray 引擎失败: %s", exc)
        status = xray_engine.get_status(proxy_node_service.get_nodes())
        return ok(
            ProxyEngineActionResponse(
                success=False,
                message=f"安装失败: {exc}",
                status=ProxyEngineStatusPayload(**status),
            ),
            request_id,
        )


@router.post("/proxy-engine/start", response_model=Envelope[ProxyEngineActionResponse], summary="启动 Xray 核心引擎")
def start_proxy_engine(
    request_id: str = Depends(get_request_id),
) -> Envelope[ProxyEngineActionResponse]:
    res = xray_engine.start_engine(proxy_node_service.get_nodes())
    status = xray_engine.get_status(proxy_node_service.get_nodes())
    audit("start_proxy_engine", request_id, running=status["running"])
    err_detail = res.get("error") or res.get("message") or "未知错误"
    return ok(
        ProxyEngineActionResponse(
            success=bool(status["running"]),
            message="Xray 引擎已启动" if status["running"] else f"启动失败: {err_detail}",
            status=ProxyEngineStatusPayload(**status),
        ),
        request_id,
    )


@router.post("/proxy-engine/restart", response_model=Envelope[ProxyEngineActionResponse], summary="重启 Xray 核心引擎")
def restart_proxy_engine(
    request_id: str = Depends(get_request_id),
) -> Envelope[ProxyEngineActionResponse]:
    res = xray_engine.start_engine(proxy_node_service.get_nodes())
    status = xray_engine.get_status(proxy_node_service.get_nodes())
    audit("restart_proxy_engine", request_id, running=status["running"])
    err_detail = res.get("error") or res.get("message") or "未知错误"
    return ok(
        ProxyEngineActionResponse(
            success=bool(status["running"]),
            message="Xray 引擎已重启" if status["running"] else f"重启失败: {err_detail}",
            status=ProxyEngineStatusPayload(**status),
        ),
        request_id,
    )


@router.post("/proxy-engine/stop", response_model=Envelope[ProxyEngineActionResponse], summary="停止 Xray 核心引擎")
def stop_proxy_engine(
    request_id: str = Depends(get_request_id),
) -> Envelope[ProxyEngineActionResponse]:
    xray_engine.stop_engine()
    status = xray_engine.get_status(proxy_node_service.get_nodes())
    audit("stop_proxy_engine", request_id)
    return ok(
        ProxyEngineActionResponse(
            success=True,
            message="Xray 引擎已停止",
            status=ProxyEngineStatusPayload(**status),
        ),
        request_id,
    )
