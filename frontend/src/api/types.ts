// ┌─────────────────────────────────────────────────────────────────┐
// │  这个文件是生成物，**不要手改** —— 手改的部分下次生成就没了。    │
// └─────────────────────────────────────────────────────────────────┘
//
// 来源：contracts/schemas/*.json（后端 Pydantic 模型的生成物）
// 重新生成：cd frontend && npm run gen:types
// 检查是否过期：npm run check:types（退出码非 0 = 契约改过但没重新生成）
//
// 契约指纹：fe3b18fcab73
/** 激活成功后的状态。 */
export interface ActivationResult {
  device_token: string
  device_name: string
  expires_at: string
  remaining_seconds: number
  heartbeat_interval_seconds: number
}

/** 启用 / 停用 / 重排之后的回执：说一句 + 回带上这一行。 */
export interface AdminSiteActionResult {
  message: string
  site: AdminSiteItem
}

/** 后台「站点管理」里的一行。 它比用户端的 ``SiteMeta`` 多三样东西：**开关、顺序、健康** —— 这三样正好是"要不要动它、动完对不对"的全部依据。 */
export interface AdminSiteItem {
  key: string
  name: string
  enabled: boolean
  sort_order: number
  note?: string
  version?: string
  mode?: string
  capabilities?: string[]
  meta_error?: string | null
  health: SiteHealth
  proxy_enabled?: boolean
  proxy_url?: string
}

/** 站点管理页的全部数据：**包括被停用的源**（运维要能看到自己关掉了什么）。 */
export interface AdminSiteListPayload {
  sites?: AdminSiteItem[]
}

/** 重排用户端的站点顺序。 给的是**完整顺序**，不是单条改动：这样一次提交就是一个一致的最终状态， 不会出现"改到一半"的中间态（单条改动最怕的就是中途失败）。 */
export interface AdminSiteOrderRequest {
  keys: string[]
}

/** 后台一眼看全：缓存、预热、每个源的健康。 */
export interface AdminStatusPayload {
  env: string
  sites?: SiteHealth[]
  cache: CacheStats
  warmup: WarmupStatus
}

/** 跨源聚合搜索比对总览。 */
export interface AggregateSearchPayload {
  kw: string
  total_sites: number
  total_count: number
  results?: AggregateSearchSiteResult[]
}

/** 单站搜索聚合结果。 */
export interface AggregateSearchSiteResult {
  site: string
  site_name: string
  supported: boolean
  count: number
  elapsed_ms: number
  error?: string | null
  items?: unknown[]
}

/** 清除缓存请求。 */
export interface CacheClearRequest {
  site?: string | null
  key?: string | null
}

/** 清除缓存执行结果。 */
export interface CacheClearResult {
  cleared_count: number
  message: string
}

/** 单条缓存的具体数据透视。 */
export interface CacheEntryDetail {
  key: string
  site: string
  namespace: string
  ident: string
  remaining_seconds: number
  data?: unknown
}

/** 当前内存缓存里的单个 Key 条目。 */
export interface CacheKeyEntry {
  key: string
  site: string
  namespace: string
  ident: string
  remaining_seconds: number
  is_disk?: boolean
}

/** 主动预热缓存请求。 */
export interface CachePreheatRequest {
  site?: string | null
}

/** 缓存预热结果。 */
export interface CachePreheatResult {
  success: boolean
  preheated_sites?: string[]
  elapsed_ms: number
  details?: SitePreheatDetail[]
}

/** 缓存现状。``hits`` / ``misses`` 是进程启动以来的累计值。 */
export interface CacheStats {
  size: number
  maxsize: number
  hits: number
  misses: number
  inflight: number
  ttl: CacheTtl
  disk?: Record<string, unknown> | null
}

/** 缓存全局命中率与容量看板数据。 */
export interface CacheStatsPayload {
  size: number
  maxsize: number
  hits: number
  misses: number
  hit_ratio_percent: number
  inflight?: number
  ttl?: Record<string, number>
  disk?: Record<string, unknown> | null
  enabled?: boolean
  warmup_enabled?: boolean
}

/** 三类内容的缓存时长（秒）。0 表示该类缓存已关闭。 */
export interface CacheTtl {
  home: number
  category: number
  detail: number
}

/** 单个分类的控制规则。 */
export interface CategoryRuleItem {
  tid: string
  name: string
  custom_name?: string
  hidden?: boolean
  sort_order?: number
  show_on_home?: boolean
  subcategories?: SubCategoryItem[]
}

/** 停用 / 启用 / 延长之后的回执：说明 + 变更后的那一行。 回带整行而不是只回一个 ``ok``：界面可以直接用它刷新那一行， 不用再多发一次列表请求（也就不会出现"操作成功了但列表还是旧值"）。 */
export interface CodeActionResult {
  message: string
  code: CodeListItem
}

/** 批量清理失效激活码结果。 */
export interface CodeCleanupResult {
  deleted_count: number
  message: string
}

/** 后台列表里的一行激活码。 */
export interface CodeListItem {
  id: number
  code: string
  note?: string
  duration_hours: number
  created_at: string
  activated_at?: string | null
  expires_at?: string | null
  disabled_at?: string | null
  remaining_seconds?: number
  device_count?: number
  max_devices?: number
  active_device_name?: string | null
}

/** 激活码列表（分页）。 */
export interface CodeListPayload {
  codes?: CodeListItem[]
  total?: number
  page?: number
  page_size?: number
}

/** 查看采集器脚本源码。 */
export interface CrawlerCodePayload {
  key: string
  code: string
  updated_at?: string
}

/** 上传采集器脚本。 */
export interface CrawlerUploadRequest {
  key: string
  code: string
  overwrite?: boolean
  auto_bump_version?: boolean
}

/** 上传采集器结果。 */
export interface CrawlerUploadResult {
  success: boolean
  message: string
  meta: SiteMeta
}

/** 请求验证采集器脚本代码。 */
export interface CrawlerValidateRequest {
  code: string
  key?: string | null
}

/** 采集器校验结果。 */
export interface CrawlerValidateResult {
  valid: boolean
  key: string
  meta?: SiteMeta | null
  error?: string | null
  checks?: string[]
}

export interface DetailPayload {
  video: VodItem
  desc?: string
  episodes?: Episode[]
  lines?: LineInfo[]
}

/** 一台设备。**没有 token 字段，只有掩码前缀**（见文件头）。 */
export interface DeviceItem {
  id: number
  name?: string
  token_prefix: string
  created_at: string
  last_seen_at: string
  is_active: boolean
}

/** 某个码用过的所有设备。 */
export interface DeviceListPayload {
  devices?: DeviceItem[]
  active_device_id?: number | null
}

/** 统一响应信封。**每个**接口都是这个形状，包括错误。 */
export interface ApiEnvelope<T = unknown> {
  ok: boolean
  data?: T | null
  error?: ErrorInfo | null
  /** 请求 id，排查问题时拿它串日志 */
  request_id: string
}

/** 单集。 ``ep_index`` 是 **1 起算的集号**，不是数组下标。 ``play_id`` 的含义由爬虫定义：后端拿到它去调 ``play``，自行不作解释。 多线路源的集号会重复，必须靠 ``line`` 区分——所以 ``play_id`` 建议用完整路径 （见 crawler-plan.md 的"最容易踩的坑"）。 */
export interface Episode {
  ep_index: number
  ep_name?: string
  play_id: string
  line?: number | null
  duration_sec?: number | null
}

/** 对外暴露的全部错误码。加新码时记得补 :data:`HTTP_STATUS`。 */
export type ErrorCode = "UPSTREAM_TIMEOUT" | "UPSTREAM_HTTP_ERROR" | "UPSTREAM_PARSE_ERROR" | "UPSTREAM_BLOCKED" | "UPSTREAM_UNKNOWN" | "UPSTREAM_BUSY" | "UPSTREAM_CIRCUIT_OPEN" | "NOT_FOUND" | "UNSUPPORTED" | "SITE_DISABLED" | "BAD_REQUEST" | "VALIDATION_ERROR" | "UNAUTHORIZED" | "FORBIDDEN" | "RATE_LIMITED" | "ACTIVATION_INVALID" | "ACTIVATION_EXPIRED" | "SESSION_KICKED" | "NOT_IMPLEMENTED" | "INTERNAL"

/** 错误对象。``code`` / ``message`` 与爬虫那侧完全一致，多一个可选 ``detail``。 */
export interface ErrorInfo {
  code: ErrorCode
  message: string
  detail?: unknown | null
}

/** 延长时长。**只能加时间，不能减** —— 减时间应该用停用。 */
export interface ExtendRequest {
  hours: number
}

/** 健康检查。故意只回最少的字段：它要能在数据库、爬虫全挂时照样返回。 */
export interface HealthPayload {
  status?: "ok"
  env: string
  version: string
}

export interface HomePayload {
  categories?: VodCategory[]
  recommend?: VodItem[]
  sections?: HomeSection[]
}

/** 首页板块。源站自己的分组结构或后台自定义首页分类楼层。 */
export interface HomeSection {
  title: string
  tid?: string | null
  videos?: VodItem[]
}

/** 图片缓存清理结果。 */
export interface ImageProxyClearResult {
  cleared_files: number
  freed_mb: number
}

/** 全局图片防盗链代理总控配置。 */
export interface ImageProxyConfig {
  global_proxy_enabled?: boolean
  disk_cache_enabled?: boolean
  auto_strip_referer?: boolean
  custom_referer?: string
  cache_max_mb?: number
  updated_at?: string
}

/** 图片代理缓存看板数据。 */
export interface ImageProxyStats {
  cached_files: number
  total_size_mb: number
  cache_dir: string
}

/** 发码。``hours`` / ``days`` 二选一。 */
export interface IssueCodesRequest {
  hours?: number | null
  days?: number | null
  count?: number
  max_devices?: number
  note?: string
}

/** 发码的回执。**码本身一定要回给调用方** —— 它是唯一的交付物。 */
export interface IssueCodesResult {
  codes?: string[]
  duration_hours: number
  note?: string
}

/** 踢设备的回执。 */
export interface KickResult {
  message: string
  code: CodeListItem
}

/** 一条播放线路。多线路源必须让上层知道有几条线、各有多少集。 */
export interface LineInfo {
  line: number
  name?: string
  count?: number
}

/** 分类与搜索共用。 */
export interface ListPayload {
  videos?: VodItem[]
  page?: number
  has_more?: boolean
}

/** 一次调用的播放结果。 */
export interface Playback {
  url: string
  format?: "m3u8" | "mp4"
  headers?: Record<string, string>
}

/** 发起探针测试请求。 */
export interface PlaygroundProbeRequest {
  site: string
  command: "home" | "category" | "detail" | "play"
  tid?: string | null
  page?: number
  vod_id?: string | null
  ep?: number
  bypass_cache?: boolean
}

/** 探针执行响应：包含清洗前后的数据差分、耗时与视频流。 */
export interface PlaygroundProbeResult {
  site: string
  command: string
  elapsed_ms: number
  cache_hit: boolean
  status: "OK" | "ERROR"
  raw_data?: unknown | null
  cleaned_data?: unknown | null
  playback_url?: string | null
  error_detail?: string | null
}

/** 激活请求。两种用法： * **首次激活**：只给 ``code``； * **被踢后抢回**（"在此设备继续"）：给 ``device_token``，``code`` 可省。 为什么把这两件事合成一个动作？因为它们本质是同一件事： **"把活跃位指到这台上"**。分开做会多一套状态和一堆边界情况。 */
export interface RedeemRequest {
  code?: string | null
  device_token?: string | null
  device_name?: string
}

/** ``POST /admin/cache/refresh`` 的回执。 ``started=False`` 不是错误：可能只是**已经有一轮在跑**， 这时应该去看 ``GET /admin/status`` 里的 ``warmup.running``。 */
export interface RefreshResult {
  started: boolean
  message: string
  warmup?: WarmupStatus | null
}

/** 抽样的真实源站海报。 */
export interface SamplePosterItem {
  title: string
  url: string
  site: string
}

/** 自动从内容源提取的海报图库。 */
export interface SamplePostersPayload {
  items?: SamplePosterItem[]
}

/** 心跳返回的会话状态。 ``is_active`` 是**单会话模型的抓手**：为 false 就说明活跃位已经被别的设备拿走了， 客户端应当立即停止播放并提示用户，而不是自己抢回来。 */
export interface SessionState {
  is_active: boolean
  expires_at: string
  remaining_seconds: number
  server_time: string
  heartbeat_interval_seconds: number
}

/** 单站的高级配置载荷。 */
export interface SiteAdvancedSettingPayload {
  key: string
  custom_name?: string
  badge?: string
  timeout_seconds?: number
  note?: string
  proxy_enabled?: boolean
  proxy_url?: string
}

/** 修改单站高级设置请求。 */
export interface SiteAdvancedSettingUpdateRequest {
  custom_name?: string | null
  badge?: string | null
  timeout_seconds?: number | null
  note?: string | null
  proxy_enabled?: boolean | null
  proxy_url?: string | null
}

/** 单站点独立定制的缓存 TTL 策略。 */
export interface SiteCachePolicy {
  home_ttl?: number | null
  category_ttl?: number | null
  detail_ttl?: number | null
  long_term_static_ttl?: number | null
}

/** 站点的全部动态分类控制状态与规则。 */
export interface SiteCategoryRulePayload {
  site_key: string
  rules?: CategoryRuleItem[]
  default_tid?: string | null
}

/** 更新站点分类与子分类控制规则。 */
export interface SiteCategoryRuleUpdateRequest {
  rules?: CategoryRuleItem[]
  default_tid?: string | null
}

/** 详情页显示与清洗策略。 */
export interface SiteDetailPolicyPayload {
  site_key: string
  ad_patterns?: string[]
  line_name_overrides?: Record<string, string>
  ep_naming_rule?: "auto" | "standard" | "raw"
  default_poster?: string
  hide_fields?: string[]
  auto_select_fastest_line?: boolean
}

/** 更新详情页策略。 */
export interface SiteDetailPolicyUpdateRequest {
  ad_patterns?: string[] | null
  line_name_overrides?: Record<string, string> | null
  ep_naming_rule?: "auto" | "standard" | "raw" | null
  default_poster?: string | null
  hide_fields?: string[] | null
  auto_select_fastest_line?: boolean | null
}

/** 单个源的守护状态。 */
export interface SiteHealth {
  site: string
  state: string
  failures: number
  fail_threshold: number
  retry_after?: number | null
  probing: boolean
  max_concurrency: number
  reset_seconds: number
  global_limit?: number
  probed?: boolean
}

/** 站点清单。只有 meta 能拿到（即爬虫文件真的能跑起来）的源才会出现在这里。 */
export interface SiteListPayload {
  sites?: SiteMeta[]
}

export interface SiteMeta {
  key: string
  name: string
  version?: string
  base_url?: string
  mode?: "direct" | "proxy"
  capabilities?: string[]
  play_format?: string[]
  note?: string | null
  badge?: string
  custom_name?: string
}

/** 单站首页预热成果明细报表。 */
export interface SitePreheatDetail {
  site: string
  site_name: string
  categories_count: number
  categories?: string[]
  recommend_count: number
  recommend_titles?: string[]
  sample_posters?: string[]
  elapsed_ms: number
}

/** 子分类或过滤标签。 */
export interface SubCategory {
  tid: string
  name?: string
  custom_name?: string
  hidden?: boolean
}

/** 子分类/二级筛选标签。 */
export interface SubCategoryItem {
  tid: string
  name: string
  custom_name?: string
  hidden?: boolean
}

/** 紧急停服维护模式。 */
export interface SystemMaintenancePayload {
  enabled?: boolean
  message?: string
  allow_admin?: boolean
  updated_at?: string
}

/** 全站公告内容与弹窗策略。 */
export interface SystemNoticePayload {
  enabled?: boolean
  title?: string
  content?: string
  level?: "info" | "warning" | "danger"
  display_type?: "banner" | "modal" | "both"
  dismissible?: boolean
  updated_at?: string
}

/** 公共系统状态（客户端 App / Web 启动时调用的公开接口）。 */
export interface SystemStatusPayload {
  maintenance?: boolean
  maintenance_message?: string
  notice?: SystemNoticePayload | null
  image_proxy_enabled?: boolean
}

/** 站级动态分类，由爬虫的 ``home`` 返回，前端不写死。 */
export interface VodCategory {
  tid: string
  name?: string
  custom_name?: string
  hidden?: boolean
  subcategories?: SubCategory[]
}

/** 统一的影片卡片。 必填四项是硬约定（见 crawler-plan.md 2.4）——缺了就该在爬虫那侧被丢掉， 不允许"凑合入库"。 源站可能带扩展字段，一律忽略而不是报错：扩展字段是给上游自己玩的， 不进契约。 */
export interface VodItem {
  vod_id: string
  vod_name: string
  vod_pic: string
  vod_remarks: string
  vod_year?: number | null
  vod_area?: string | null
  vod_type?: string | null
  vod_actor?: string | null
  vod_score?: number | null
}

/** 一次预热里某个源的结果。 */
export interface WarmupSiteResult {
  site: string
  ok: boolean
  home_items?: number
  categories?: number
  seconds?: number
  error?: string | null
}

/** 主动预热的状态。``last_*`` 为空表示这个进程还从没跑过。 */
export interface WarmupStatus {
  enabled: boolean
  running: boolean
  interval_seconds: number
  last_reason?: string | null
  last_started_at?: string | null
  last_finished_at?: string | null
  last_seconds?: number | null
  sites?: WarmupSiteResult[]
}
