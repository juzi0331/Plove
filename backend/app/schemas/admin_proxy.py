"""后台代理节点池与内核引擎管理契约。

包含代理节点管理、连通性测速、采集器绑定及 Xray 引擎状态监控控制载荷。
对应契约: admin-proxy-*.json
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProxyNodeItem(BaseModel):
    """单个代理节点信息。"""

    id: str = Field(description="节点唯一 ID")
    name: str = Field(description="节点名称备注")
    protocol: str = Field(description="协议类型: vless / http / socks5")
    proxy_url: str = Field(description="供爬虫访问的本地或目标 HTTP 代理地址")
    raw_url: str = Field(default="", description="原始配置链接或地址")
    server: str = Field(default="", description="远端节点服务器地址/域名")
    port: int = Field(default=0, description="远端服务端口")
    security: str = Field(default="none", description="加密/安全协议 (reality, tls, none)")
    network_type: str = Field(default="tcp", description="传输层协议 (tcp, ws, grpc)")
    local_port: int = Field(default=10809, description="本地监听端口")
    sni: str | None = Field(default="", description="SNI 伪装域名")
    ping_ms: float | None = Field(default=None, description="上一次测速延迟 (ms)")
    last_tested_at: str | None = Field(default=None, description="上一次测速时间")
    created_at: str = Field(default="", description="添加时间")


class ProxyNodeListPayload(BaseModel):
    """代理节点池列表与采集器绑定关系。"""

    nodes: list[ProxyNodeItem] = Field(default_factory=list, description="全部节点列表")
    bindings: dict[str, str] = Field(
        default_factory=dict,
        description="采集器与节点绑定映射 {site_key: node_id}",
    )


class ProxyNodeCreateRequest(BaseModel):
    """添加或解析代理节点请求。"""

    raw_url: str = Field(min_length=5, description="vless:// 链接或 http/socks 代理地址")
    name: str = Field(default="", description="自定义节点备注名称")
    local_port: int = Field(default=10809, ge=1024, le=65535, description="本地代理映射端口")


class ProxyTestRequest(BaseModel):
    """连通性测速请求。"""

    node_id: str | None = Field(default=None, description="指定测试的节点 ID")
    proxy_url: str | None = Field(default=None, description="或直接指定代理地址")
    target_url: str = Field(default="https://www.google.com", description="测速目标地址")


class ProxyTestResult(BaseModel):
    """连通性测速结果。"""

    ok: bool = Field(description="是否测试通过")
    duration_ms: float = Field(description="响应耗时毫秒数")
    status_code: int = Field(description="HTTP 状态码")
    proxy_used: str = Field(description="使用的代理地址")
    message: str = Field(description="测试结果说明")


class ProxyNodeBindRequest(BaseModel):
    """将采集器绑定到节点。"""

    site_key: str = Field(description="站点 key")
    node_id: str = Field(description="节点 ID，'direct' 表示直连，'default' 表示跟随全局")


class ProxyEngineStatusPayload(BaseModel):
    """Xray 引擎当前运行状态。"""

    installed: bool = Field(description="核心程序是否已安装")
    running: bool = Field(description="内核守护进程是否正在运行")
    pid: int | None = Field(default=None, description="守护进程 PID")
    version: str | None = Field(default=None, description="内核版本号")
    bin_path: str | None = Field(default=None, description="核心程序所在绝对路径")
    managed_ports: list[int] = Field(default_factory=list, description="当前在监听的本地代理端口")
    managed_nodes: list[str] = Field(default_factory=list, description="正在接管的 VLESS 节点列表")
    error: str | None = Field(default=None, description="错误日志或异常提示")


class ProxyEngineActionResponse(BaseModel):
    """Xray 引擎控制操作结果。"""

    success: bool = Field(description="操作是否成功")
    message: str = Field(description="反馈提示信息")
    status: ProxyEngineStatusPayload = Field(description="操作后的引擎状态")
