import type {
  AdminSiteActionResult,
  AdminSiteListPayload,
  SiteAdvancedSettingPayload,
  SiteAdvancedSettingUpdateRequest,
} from '@/api/types'
import { assertWritable } from '../ui'
import { admin } from './client'

/** 后台的源列表：包含被停用的（运维要能看到自己关掉了什么）。 */
export function listSites(): Promise<AdminSiteListPayload> {
  return admin('/admin/sites')
}

/** 停用：用户端列表里不再出现它，内容接口直接回 SITE_DISABLED。 */
export function disableSite(key: string): Promise<AdminSiteActionResult> {
  assertWritable()
  return admin(`/admin/sites/${key}/disable`, { method: 'POST' })
}

/** 启用。守护状态刻意不动 —— 它停用期间没被调用过，旧状态不代表现在。 */
export function enableSite(key: string): Promise<AdminSiteActionResult> {
  assertWritable()
  return admin(`/admin/sites/${key}/enable`, { method: 'POST' })
}

/** 重排：提交的是完整顺序（不是单条改动），所以不会出现"改到一半"的中间态。 */
export function orderSites(keys: string[]): Promise<AdminSiteListPayload> {
  assertWritable()
  return admin('/admin/sites/order', { method: 'POST', body: { keys } })
}

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
