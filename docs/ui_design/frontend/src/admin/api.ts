/**
 * 后台接口。**复用用户端那个 `http.ts`** —— 拆信封、超时、错误码翻译都是同一套，
 * 两边行为一致，也少一份要维护的东西。
 *
 * 唯一的差别：这里每个请求都带上 `X-Admin-Token`，而且**令牌没配就直接抛**，
 * 不去发一个注定 401 的请求。
 *
 * ⚠️ 它和用户端用的是**两套凭证**：
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
  DeviceListPayload,
  IssueCodesRequest,
  IssueCodesResult,
  KickResult,
  RefreshResult,
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

/** 踢下线。**它还能自己抢回来** —— 踢是\"请下线\"，不是\"封设备\"。 */
export function kickDevice(deviceId: number): Promise<KickResult> {
  assertWritable()
  return admin(`/admin/devices/${deviceId}/kick`, { method: 'POST' })
}
