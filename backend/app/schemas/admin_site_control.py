"""后台站点高级控制、分类/子分类规则、详情清洗策略与采集器管理契约。

严格遵循契约规范：全部字段有 description，带默认值的字段在前端 TS 生成时为可选。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.site import SiteMeta


# ------------------------------------------------------------------ 采集器上传与校验

class CrawlerValidateRequest(BaseModel):
    """请求验证采集器脚本代码。"""

    code: str = Field(min_length=10, description="Python 采集器源码")
    key: str | None = Field(default=None, description="可选的站点 key（若不提供则从代码中探测）")


class CrawlerValidateResult(BaseModel):
    """采集器校验结果。"""

    valid: bool = Field(description="是否通过全部安全检查与冒烟协议测试")
    key: str = Field(description="探测到的站点 key")
    meta: SiteMeta | None = Field(default=None, description="如果协议测试通过，返回的站点元信息")
    error: str | None = Field(default=None, description="未通过时的具体错误原因")
    checks: list[str] = Field(default_factory=list, description="通过的检查项目列表")


class CrawlerUploadRequest(BaseModel):
    """上传采集器脚本。"""

    key: str = Field(pattern=r"^[a-z_][a-z0-9_]{1,63}$", description="站点 key，如 custom_site")
    code: str = Field(min_length=10, description="Python 源码")
    overwrite: bool = Field(default=False, description="若站点已存在是否允许覆盖")
    auto_bump_version: bool = Field(default=True, description="若覆盖已存在脚本且版本号未变动，是否自动自增修订号(如 1.0.0 -> 1.0.1)")


class CrawlerUploadResult(BaseModel):
    """上传采集器结果。"""

    success: bool = Field(description="是否成功落盘并激活")
    message: str = Field(description="提示信息")
    meta: SiteMeta = Field(description="站点元信息")


class CrawlerCodePayload(BaseModel):
    """查看采集器脚本源码。"""

    key: str = Field(description="站点 key")
    code: str = Field(description="源码内容")
    updated_at: str = Field(default="", description="文件最后修改时间")


# ------------------------------------------------------------------ 单站高级控制

class SiteAdvancedSettingPayload(BaseModel):
    """单站的高级配置载荷。"""

    key: str = Field(description="站点 key")
    custom_name: str = Field(default="", description="前台自定义别名（空则显示源站原名）")
    badge: str = Field(default="", description="前台站点角标（如 4K, 极速, 独家）")
    timeout_seconds: float = Field(default=0.0, description="单站自定义超时时间秒数，0 为跟随全局")
    note: str = Field(default="", description="运维备注")
    proxy_enabled: bool = Field(default=False, description="是否为该站点开启独立代理")
    proxy_url: str = Field(default="", description="该站点使用的代理地址，如 http://192.168.31.5:10809")
    proxy_node_id: str = Field(default="", description="绑定的代理节点 ID（留空为自定地址）")


class SiteAdvancedSettingUpdateRequest(BaseModel):
    """修改单站高级设置请求。"""

    custom_name: str | None = Field(default=None, description="前台自定义别名")
    badge: str | None = Field(default=None, description="前台站点角标")
    timeout_seconds: float | None = Field(default=None, ge=0.0, le=120.0, description="超时秒数")
    note: str | None = Field(default=None, description="运维备注")
    proxy_enabled: bool | None = Field(default=None, description="是否为该站点开启独立代理")
    proxy_url: str | None = Field(default=None, description="该站点使用的代理地址")
    proxy_node_id: str | None = Field(default=None, description="绑定的代理节点 ID")


# ------------------------------------------------------------------ 代理节点池管理

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
    bindings: dict[str, str] = Field(default_factory=dict, description="采集器与节点绑定映射 {site_key: node_id}")


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


# ------------------------------------------------------------------ Xray 代理引擎状态与控制

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


# ------------------------------------------------------------------ 站点分类与子分类控制

class SubCategoryItem(BaseModel):
    """子分类/二级筛选标签。"""

    tid: str = Field(description="子分类唯一标识")
    name: str = Field(description="子分类名称")
    custom_name: str = Field(default="", description="前台展示重命名（空则保持原名）")
    hidden: bool = Field(default=False, description="是否在前台隐藏/屏蔽该二级分类")


class CategoryRuleItem(BaseModel):
    """单个分类的控制规则。"""

    tid: str = Field(description="源站分类 tid")
    name: str = Field(description="源站原始名称")
    custom_name: str = Field(default="", description="前台展示重命名（空则保持原名）")
    hidden: bool = Field(default=False, description="是否在前台隐藏/屏蔽该分类")
    sort_order: int = Field(default=0, description="排序权重，小的在前")
    show_on_home: bool = Field(default=False, description="是否在首页横幅中展示该分类")
    subcategories: list[SubCategoryItem] = Field(default_factory=list, description="该分类下的子分类列表")


class SiteCategoryRulePayload(BaseModel):
    """站点的全部动态分类控制状态与规则。"""

    site_key: str = Field(description="站点 key")
    rules: list[CategoryRuleItem] = Field(default_factory=list, description="分类规则列表")
    default_tid: str | None = Field(default=None, description="默认推荐分类 tid")


class SiteCategoryRuleUpdateRequest(BaseModel):
    """更新站点分类与子分类控制规则。"""

    rules: list[CategoryRuleItem] = Field(default_factory=list, description="完整的分类规则清单")
    default_tid: str | None = Field(default=None, description="默认推荐分类 tid")


# ------------------------------------------------------------------ 详情页显示与清洗策略

class SiteDetailPolicyPayload(BaseModel):
    """详情页显示与清洗策略。"""

    site_key: str = Field(description="站点 key")
    ad_patterns: list[str] = Field(
        default_factory=list,
        description="广告清理词汇/正则列表，命中将从标题、备注、简介和集数中清洗",
    )
    line_name_overrides: dict[str, str] = Field(
        default_factory=dict,
        description="线路名称别名映射表，如 {'lzm3u8': '超清极速专线'}",
    )
    ep_naming_rule: Literal["auto", "standard", "raw"] = Field(
        default="auto",
        description="剧集名称显示规则：auto (智能清洗剧名重复), standard (统一第N集), raw (源站原样)",
    )
    default_poster: str = Field(default="", description="兜底海报 URL（海报为空或源站防盗链失效时兜底）")
    hide_fields: list[str] = Field(
        default_factory=list,
        description="隐藏字段列表，例如 ['vod_actor', 'vod_director']",
    )
    auto_select_fastest_line: bool = Field(
        default=True,
        description="后端测速优选单线路模式：多线路时由后端并发测速默认选用最快线路，不让前端显示多线路",
    )


class SiteDetailPolicyUpdateRequest(BaseModel):
    """更新详情页策略。"""

    ad_patterns: list[str] | None = Field(default=None, description="广告清理词汇列表")
    line_name_overrides: dict[str, str] | None = Field(default=None, description="线路别名映射")
    ep_naming_rule: Literal["auto", "standard", "raw"] | None = Field(default=None, description="剧集命名规则")
    default_poster: str | None = Field(default=None, description="兜底海报 URL")
    hide_fields: list[str] | None = Field(default=None, description="隐藏字段列表")
    auto_select_fastest_line: bool | None = Field(default=None, description="是否开启后端测速优选单线路")
