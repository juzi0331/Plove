"""后台 — 代理节点池管理与 Xray 引擎托管。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    commit_now,
    get_db,
    get_site_settings,
)
from app.api.v1.admin._audit import audit
from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger
from app.core.middleware import get_request_id
from app.models.site_setting import SiteSetting
from app.schemas.admin_site_control import (
    ProxyNodeBindRequest,
    ProxyNodeCreateRequest,
    ProxyNodeItem,
    ProxyNodeListPayload,
    ProxyTestRequest,
    ProxyTestResult,
)
from app.schemas.envelope import Envelope, ok
from app.services import site_settings
from app.services.proxy_node import proxy_node_service
from app.services.site_settings import SiteSettingsStore

logger = get_logger(__name__)

router = APIRouter(tags=["后台-代理节点池"])


@router.get("/proxy-nodes", response_model=Envelope[ProxyNodeListPayload], summary="获取代理节点池与采集器绑定清单")
def list_proxy_nodes(
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[ProxyNodeListPayload]:
    data = proxy_node_service.get_data()
    bindings = dict(data.get("bindings", {}))

    # 动态与数据库 site_settings 进行权威同步，确保已设置直连的适配器绝对不会残留旧节点绑定
    try:
        rows = db.query(SiteSetting).all()
        for row in rows:
            site_k = (row.key or "").strip().lower()
            if not row.proxy_enabled or not row.proxy_node_id or row.proxy_node_id in ("direct", "none"):
                if site_k in bindings:
                    bindings.pop(site_k, None)
                    proxy_node_service.bind_site(site_k, "direct")
            else:
                bindings[site_k] = row.proxy_node_id
    except Exception as exc:
        logger.warning("同步采集器代理绑定状态失败: %s", exc)

    items = [
        ProxyNodeItem(
            id=n.get("id", ""),
            name=n.get("name", ""),
            protocol=n.get("protocol", "http"),
            proxy_url=n.get("proxy_url", ""),
            raw_url=n.get("raw_url", ""),
            server=n.get("server", ""),
            port=int(n.get("port", 0) or 0),
            security=n.get("security", "none"),
            network_type=n.get("network_type", "tcp"),
            local_port=int(n.get("local_port", 10809) or 10809),
            created_at=n.get("created_at", ""),
        )
        for n in data.get("nodes", [])
    ]
    return ok(ProxyNodeListPayload(nodes=items, bindings=bindings), request_id)


@router.post("/proxy-nodes", response_model=Envelope[ProxyNodeItem], summary="添加或解析代理节点")
def add_proxy_node(
    payload: ProxyNodeCreateRequest,
    request_id: str = Depends(get_request_id),
) -> Envelope[ProxyNodeItem]:
    try:
        n = proxy_node_service.add_node(
            raw_input=payload.raw_url,
            custom_name=payload.name,
            local_port=payload.local_port,
        )
        audit("add_proxy_node", request_id, name=n.get("name"), protocol=n.get("protocol"))
        return ok(
            ProxyNodeItem(
                id=n.get("id", ""),
                name=n.get("name", ""),
                protocol=n.get("protocol", "http"),
                proxy_url=n.get("proxy_url", ""),
                raw_url=n.get("raw_url", ""),
                server=n.get("server", ""),
                port=int(n.get("port", 0) or 0),
                security=n.get("security", "none"),
                network_type=n.get("network_type", "tcp"),
                local_port=int(n.get("local_port", 10809) or 10809),
                created_at=n.get("created_at", ""),
            ),
            request_id,
        )
    except Exception as exc:
        raise AppError(ErrorCode.BAD_REQUEST, f"解析或添加节点失败: {exc}")


@router.delete("/proxy-nodes/{node_id}", response_model=Envelope[dict], summary="删除指定的代理节点")
def delete_proxy_node(
    node_id: str,
    request_id: str = Depends(get_request_id),
) -> Envelope[dict]:
    ok_deleted = proxy_node_service.delete_node(node_id)
    audit("delete_proxy_node", request_id, node_id=node_id, success=ok_deleted)
    return ok({"message": f"节点 {node_id} 已移除", "deleted": ok_deleted}, request_id)


@router.post("/proxy-nodes/test", response_model=Envelope[ProxyTestResult], summary="测试节点或代理连通性")
async def test_proxy_node(
    payload: ProxyTestRequest,
    request_id: str = Depends(get_request_id),
) -> Envelope[ProxyTestResult]:
    res = await proxy_node_service.test_node_connection(
        node_id=payload.node_id,
        custom_proxy=payload.proxy_url,
        target_url=payload.target_url or "https://www.google.com",
    )
    return ok(
        ProxyTestResult(
            ok=res["ok"],
            duration_ms=res["duration_ms"],
            status_code=res["status_code"],
            proxy_used=res["proxy_used"],
            message=res["message"],
        ),
        request_id,
    )


@router.get("/proxy-nodes/{node_id}/xray", response_model=Envelope[dict], summary="导出 VLESS 节点的 Xray config.json")
def export_node_xray_config(
    node_id: str,
    http_port: int = Query(10809, ge=1024, le=65535, description="本地 HTTP 监听端口"),
    socks_port: int = Query(10808, ge=1024, le=65535, description="本地 SOCKS5 监听端口"),
    request_id: str = Depends(get_request_id),
) -> Envelope[dict]:
    try:
        cfg = proxy_node_service.export_xray(node_id, http_port=http_port, socks_port=socks_port)
        return ok(cfg, request_id)
    except Exception as exc:
        raise AppError(ErrorCode.BAD_REQUEST, f"导出 Xray 配置失败: {exc}")


@router.post("/proxy-nodes/bind", response_model=Envelope[dict], summary="指派采集器绑定代理节点")
def bind_proxy_node(
    payload: ProxyNodeBindRequest,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
    store: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[dict]:
    clean_target = (payload.node_id or "").strip()
    if not clean_target or clean_target in ("direct", "none", "default"):
        proxy_node_service.bind_site(payload.site_key, "direct")
        site_settings.update_advanced(db, payload.site_key, proxy_enabled=False, proxy_node_id="", proxy_url="")
        commit_now(db)
        store.refresh(db, force=True)
        audit("bind_proxy_node", request_id, site_key=payload.site_key, node_id="direct")
        return ok({"message": f"采集器 {payload.site_key} 已成功切换为直连模式"}, request_id)

    proxy_node_service.bind_site(payload.site_key, clean_target)
    node = proxy_node_service.get_node(clean_target)
    if node:
        proxy_url = node.get("proxy_url") or node.get("local_http_proxy")
        site_settings.update_advanced(
            db, payload.site_key, proxy_enabled=True, proxy_url=proxy_url, proxy_node_id=clean_target
        )
    commit_now(db)
    store.refresh(db, force=True)
    audit("bind_proxy_node", request_id, site_key=payload.site_key, node_id=clean_target)
    return ok({"message": f"采集器 {payload.site_key} 已成功绑定节点 {clean_target}"}, request_id)

