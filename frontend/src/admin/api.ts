/**
 * 后台接口。**复用用户端那个 `http.ts`** —— 拆信封、超时、错误码翻译都是同一套，
 * 两边行为一致，也少一份要维护的东西。
 *
 * 唯一的差别：这里每个请求都带上 `X-Admin-Token`，而且**令牌没配就直接抛**，
 * 不去发一个注定 401 的请求。
 *
 * 注意：它和用户端用的是**两套凭证**：
 * `X-Device-Token` 管\"谁能看内容\"，`X-Admin-Token` 管\"谁能管这台机器\"。
 * 所以后台不需要先给自己发个激活码。
 */

import { ApiError, request, type RequestOptions } from '@/api/http'
import type {
  AdminSiteActionResult,
  AdminSiteListPayload,
  AdminStatusPayload,
  CodeActionResult,
  CodeListPayload,
  CrawlerCodePayload,
  CrawlerUploadRequest,
  CrawlerUploadResult,
  CrawlerValidateRequest,
  CrawlerValidateResult,
  DeviceListPayload,
  IssueCodesRequest,
  IssueCodesResult,
  KickResult,
  ProxyEngineActionResponse,
  ProxyEngineStatusPayload,
  ProxyNodeBindRequest,
  ProxyNodeCreateRequest,
  ProxyNodeItem,
  ProxyNodeListPayload,
  ProxyTestRequest,
  ProxyTestResult,
  RefreshResult,
  SiteAdvancedSettingPayload,
  SiteAdvancedSettingUpdateRequest,
  SiteCategoryRulePayload,
  SiteCategoryRuleUpdateRequest,
  SiteDetailPolicyPayload,
  SiteDetailPolicyUpdateRequest,
} from '@/api/types'

import { getAdminToken } from './token'
import { assertWritable } from './ui'

async function admin<T>(path: string, options: Omit<RequestOptions, 'adminToken'> = {}): Promise<T> {
  const token = getAdminToken()
  if (!token) {
    throw new ApiError({ code: 'UNAUTHORIZED', message: '还没有输入后台令牌' })
  }
  return request<T>(path, { ...options, adminToken: token })
}

// ------------------------------------------------------------------ 看一眼

export function status(): Promise<AdminStatusPayload> {
  return admin('/admin/status')
}

export function refreshCache(wait = false): Promise<RefreshResult> {
  assertWritable()
  return admin('/admin/cache/refresh', { method: 'POST', query: { wait: wait ? 'true' : undefined } })
}

// ------------------------------------------------------------------ 站点（内容源）

/** 后台的源列表：**包含被停用的**（运维要能看到自己关掉了什么）。 */
export function listSites(): Promise<AdminSiteListPayload> {
  return admin('/admin/sites')
}

/**
 * 停用：用户端列表里不再出现它，内容接口直接回 `SITE_DISABLED`。
 *
 * **连爬虫都不会被 fork** —— 停用是运维的决定，不该在守护里被记成"源站又失败了一次"。
 */
export function disableSite(key: string): Promise<AdminSiteActionResult> {
  assertWritable()
  return admin(`/admin/sites/${key}/disable`, { method: 'POST' })
}

/** 启用。守护状态刻意不动 —— 它停用期间没被调用过，旧状态不代表现在。 */
export function enableSite(key: string): Promise<AdminSiteActionResult> {
  assertWritable()
  return admin(`/admin/sites/${key}/enable`, { method: 'POST' })
}

/** 重排：提交的是**完整顺序**（不是单条改动），所以不会出现"改到一半"的中间态。 */
export function orderSites(keys: string[]): Promise<AdminSiteListPayload> {
  assertWritable()
  return admin('/admin/sites/order', { method: 'POST', body: { keys } })
}

// ------------------------------------------------------------------ 采集器上传与管理

export function validateCrawler(payload: CrawlerValidateRequest): Promise<CrawlerValidateResult> {
  return admin('/admin/crawlers/validate', { method: 'POST', body: payload })
}

export function uploadCrawler(payload: CrawlerUploadRequest): Promise<CrawlerUploadResult> {
  assertWritable()
  return admin('/admin/crawlers/upload', { method: 'POST', body: payload })
}

export function getCrawlerCode(key: string): Promise<CrawlerCodePayload> {
  return admin(`/admin/crawlers/${encodeURIComponent(key)}/code`)
}

export function deleteCrawler(key: string): Promise<void> {
  assertWritable()
  return admin(`/admin/crawlers/${encodeURIComponent(key)}`, { method: 'DELETE' })
}

// ------------------------------------------------------------------ 单站高级控制

export function getSiteAdvanced(key: string): Promise<SiteAdvancedSettingPayload> {
  return admin(`/admin/sites/${encodeURIComponent(key)}/advanced`)
}

export function updateSiteAdvanced(
  key: string,
  payload: SiteAdvancedSettingUpdateRequest,
): Promise<SiteAdvancedSettingPayload> {
  assertWritable()
  return admin(`/admin/sites/${encodeURIComponent(key)}/advanced`, { method: 'PUT', body: payload })
}

// ------------------------------------------------------------------ 站点分类与子分类控制

export function getSiteCategories(key: string): Promise<SiteCategoryRulePayload> {
  return admin(`/admin/sites/${encodeURIComponent(key)}/categories`)
}

export function updateSiteCategories(
  key: string,
  payload: SiteCategoryRuleUpdateRequest,
): Promise<SiteCategoryRulePayload> {
  assertWritable()
  return admin(`/admin/sites/${encodeURIComponent(key)}/categories`, { method: 'PUT', body: payload })
}

// ------------------------------------------------------------------ 详情页清洗与展示策略

export function getSiteDetailPolicy(key: string): Promise<SiteDetailPolicyPayload> {
  return admin(`/admin/sites/${encodeURIComponent(key)}/detail-policy`)
}

export function updateSiteDetailPolicy(
  key: string,
  payload: SiteDetailPolicyUpdateRequest,
): Promise<SiteDetailPolicyPayload> {
  assertWritable()
  return admin(`/admin/sites/${encodeURIComponent(key)}/detail-policy`, { method: 'PUT', body: payload })
}

// ------------------------------------------------------------------ 激活码

export interface CodeQuery {
  query?: string
  page?: number
  pageSize?: number
}

export function listCodes(input: CodeQuery = {}): Promise<CodeListPayload> {
  return admin('/admin/codes', {
    query: { query: input.query, page: input.page ?? 1, page_size: input.pageSize ?? 20 },
  })
}

export function issueCodes(payload: IssueCodesRequest): Promise<IssueCodesResult> {
  assertWritable()
  return admin('/admin/codes', { method: 'POST', body: payload })
}

/** 停用。立即生效：那台设备的下一次请求就会拿到 403。 */
export function disableCode(codeId: number): Promise<CodeActionResult> {
  assertWritable()
  return admin(`/admin/codes/${codeId}/disable`, { method: 'POST' })
}

export function enableCode(codeId: number): Promise<CodeActionResult> {
  assertWritable()
  return admin(`/admin/codes/${codeId}/enable`, { method: 'POST' })
}

/**
 * 延长时长。
 *
 * 后端会自己判断该改哪个字段（还没激活的码加 `duration_hours`、
 * 激活过的码加 `expires_at`），并说明它做的是哪一种 —— 前端不用也不该复刻这个判断。
 */
export function extendCode(codeId: number, hours: number): Promise<CodeActionResult> {
  assertWritable()
  return admin(`/admin/codes/${codeId}/extend`, { method: 'POST', body: { hours } })
}

// ------------------------------------------------------------------ 设备

export function listDevices(codeId: number): Promise<DeviceListPayload> {
  return admin(`/admin/codes/${codeId}/devices`)
}

export function kickDevice(deviceId: number): Promise<KickResult> {
  assertWritable()
  return admin(`/admin/devices/${deviceId}/kick`, { method: 'POST' })
}

export function unbindDevice(deviceId: number): Promise<KickResult> {
  assertWritable()
  return admin(`/admin/devices/${deviceId}/unbind`, { method: 'POST' })
}

export function deleteCode(codeId: number): Promise<{ message: string; id: number }> {
  assertWritable()
  return admin(`/admin/codes/${codeId}`, { method: 'DELETE' })
}

export function cleanupExpiredCodes(days: number = 7): Promise<CodeCleanupResult> {
  assertWritable()
  return admin('/admin/codes/cleanup-expired', {
    method: 'POST',
    query: { days },
  })
}

// ------------------------------------------------------------------ 缓存中心透视与控制

import type {
  AggregateSearchPayload,
  CacheClearResult,
  CacheEntryDetail,
  CacheKeyEntry,
  CachePreheatResult,
  CacheStatsPayload,
  CodeCleanupResult,
  ImageProxyClearResult,
  ImageProxyConfig,
  ImageProxyStats,
  PlaygroundProbeRequest,
  PlaygroundProbeResult,
  SamplePostersPayload,
  SiteCachePolicy,
  SystemMaintenancePayload,
  SystemNoticePayload,
  SystemStatusPayload,
} from '@/api/types'
export type { SitePreheatDetail } from '@/api/types'

export function getCacheStats(): Promise<CacheStatsPayload> {
  return admin('/admin/cache/stats')
}

export function listCacheKeys(site?: string, namespace?: string): Promise<CacheKeyEntry[]> {
  return admin('/admin/cache/keys', {
    query: { site: site || undefined, namespace: namespace || undefined },
  })
}

export function getCacheEntry(key: string): Promise<CacheEntryDetail> {
  return admin('/admin/cache/entry', {
    query: { key },
  })
}

export function clearCache(site?: string, key?: string): Promise<CacheClearResult> {
  assertWritable()
  return admin('/admin/cache/clear', {
    method: 'POST',
    body: { site: site || null, key: key || null },
  })
}

export function preheatCache(site?: string): Promise<CachePreheatResult> {
  assertWritable()
  return admin('/admin/cache/preheat', {
    method: 'POST',
    body: { site: site || null },
  })
}

export interface CacheGlobalConfig {
  cache_enabled: boolean
  warmup_enabled: boolean
  warmup_interval_seconds: number
}

export function getCacheGlobalConfig(): Promise<CacheGlobalConfig> {
  return admin('/admin/cache/config')
}

export function updateCacheGlobalConfig(payload: CacheGlobalConfig): Promise<CacheGlobalConfig> {
  assertWritable()
  return admin('/admin/cache/config', {
    method: 'PUT',
    body: payload,
  })
}

export function getSiteCachePolicy(key: string): Promise<SiteCachePolicy> {
  return admin(`/admin/sites/${key}/cache-policy`)
}

export function updateSiteCachePolicy(key: string, payload: SiteCachePolicy): Promise<SiteCachePolicy> {
  assertWritable()
  return admin(`/admin/sites/${key}/cache-policy`, {
    method: 'PUT',
    body: payload,
  })
}

// ------------------------------------------------------------------ 在线探针与试播台

export function probePlayground(payload: PlaygroundProbeRequest): Promise<PlaygroundProbeResult> {
  return admin('/admin/playground/probe', {
    method: 'POST',
    body: payload,
  })
}

// ------------------------------------------------------------------ 跨源聚合搜索

export function searchAggregate(kw: string): Promise<AggregateSearchPayload> {
  return admin('/admin/search/aggregate', {
    query: { kw },
  })
}

// ------------------------------------------------------------------ 图片防盗链代理

export function getImageProxyStats(): Promise<ImageProxyStats> {
  return admin('/admin/proxy/stats')
}

export function getImageProxyConfig(): Promise<ImageProxyConfig> {
  return admin('/admin/proxy/config')
}

export function updateImageProxyConfig(payload: ImageProxyConfig): Promise<ImageProxyConfig> {
  assertWritable()
  return admin('/admin/proxy/config', {
    method: 'PUT',
    body: payload,
  })
}

export function clearImageProxy(): Promise<ImageProxyClearResult> {
  assertWritable()
  return admin('/admin/proxy/clear', { method: 'POST' })
}

export function getSamplePosters(site?: string): Promise<SamplePostersPayload> {
  return admin('/admin/proxy/sample-posters', {
    query: { site: site || undefined },
  })
}

// ------------------------------------------------------------------ 全站公告与维护模式

export function getSystemNotice(): Promise<SystemNoticePayload> {
  return admin('/admin/system/notice')
}

export function updateSystemNotice(payload: SystemNoticePayload): Promise<SystemNoticePayload> {
  assertWritable()
  return admin('/admin/system/notice', {
    method: 'PUT',
    body: payload,
  })
}

export function getSystemMaintenance(): Promise<SystemMaintenancePayload> {
  return admin('/admin/system/maintenance')
}

export function updateSystemMaintenance(payload: SystemMaintenancePayload): Promise<SystemMaintenancePayload> {
  assertWritable()
  return admin('/admin/system/maintenance', {
    method: 'PUT',
    body: payload,
  })
}

export function getPublicSystemStatus(): Promise<SystemStatusPayload> {
  return request<SystemStatusPayload>('/system/status')
}

// ------------------------------------------------------------------ 代理节点池管理

export function listProxyNodes(): Promise<ProxyNodeListPayload> {
  return admin('/admin/proxy-nodes')
}

export function addProxyNode(payload: ProxyNodeCreateRequest): Promise<ProxyNodeItem> {
  assertWritable()
  return admin('/admin/proxy-nodes', {
    method: 'POST',
    body: payload,
  })
}

export function deleteProxyNode(nodeId: string): Promise<{ message: string; deleted: boolean }> {
  assertWritable()
  return admin(`/admin/proxy-nodes/${encodeURIComponent(nodeId)}`, {
    method: 'DELETE',
  })
}

export function testProxyNode(payload: ProxyTestRequest): Promise<ProxyTestResult> {
  return admin('/admin/proxy-nodes/test', {
    method: 'POST',
    body: payload,
  })
}

export function exportNodeXray(nodeId: string, httpPort = 10809, socksPort = 10808): Promise<Record<string, unknown>> {
  return admin(`/admin/proxy-nodes/${encodeURIComponent(nodeId)}/xray?http_port=${httpPort}&socks_port=${socksPort}`)
}

export function bindSiteProxyNode(payload: ProxyNodeBindRequest): Promise<{ message: string }> {
  assertWritable()
  return admin('/admin/proxy-nodes/bind', {
    method: 'POST',
    body: payload,
  })
}

// ------------------------------------------------------------------ Xray 核心引擎自动管理

export function getProxyEngineStatus(): Promise<ProxyEngineStatusPayload> {
  return admin('/admin/proxy-engine/status')
}

export function installProxyEngine(): Promise<ProxyEngineActionResponse> {
  assertWritable()
  return admin('/admin/proxy-engine/install', { method: 'POST' })
}

export function startProxyEngine(): Promise<ProxyEngineActionResponse> {
  assertWritable()
  return admin('/admin/proxy-engine/start', { method: 'POST' })
}

export function restartProxyEngine(): Promise<ProxyEngineActionResponse> {
  assertWritable()
  return admin('/admin/proxy-engine/restart', { method: 'POST' })
}

export function stopProxyEngine(): Promise<ProxyEngineActionResponse> {
  assertWritable()
  return admin('/admin/proxy-engine/stop', { method: 'POST' })
}



