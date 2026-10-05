/**
 * 时间与数据格式化通用工具库
 */

/**
 * 格式化时间戳或时间字符串为 YYYY-MM-DD HH:mm:ss 格式
 * @param time 秒级 Unix 时间戳或 ISO 时间字符串
 * @returns 格式化后的时间字符串或友好提示
 */
export function formatExpiry(time: number | string | null | undefined): string {
  if (!time) return '同步中...'
  try {
    const d = typeof time === 'number' ? new Date(time * 1000) : new Date(time)
    if (isNaN(d.getTime())) return String(time)
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    const h = String(d.getHours()).padStart(2, '0')
    const min = String(d.getMinutes()).padStart(2, '0')
    const s = String(d.getSeconds()).padStart(2, '0')
    return `${y}-${m}-${day} ${h}:${min}:${s}`
  } catch {
    return String(time)
  }
}

import { getDeviceToken } from '@/api/session'
import { getAdminToken } from '@/admin/token'
import type { ImageCdnPrefixRule } from '@/api/types'

let _globalImageProxy = false
let _decryptDomains: string[] = []
let _cdnPrefixRules: ImageCdnPrefixRule[] = [
  // 预置默认兜底规则：网飞猫海外图床自动通过 wsrv.nl 边缘加速
  {
    id: 'default_ncat21',
    name: '网飞猫图床加速',
    site_key: 'www_ncat21_com',
    match_domain: 'vres.cyscyy.com',
    prefix: 'https://wsrv.nl/?url=',
    enabled: true,
  },
]

export function setGlobalImageProxy(enabled: boolean): void {
  _globalImageProxy = enabled
}

export function setDecryptDomains(domains: string[]): void {
  _decryptDomains = (domains || []).filter(Boolean)
}

export function setCdnPrefixRules(rules: ImageCdnPrefixRule[]): void {
  if (rules && rules.length > 0) {
    _cdnPrefixRules = rules.filter(r => r && r.enabled && r.prefix)
  }
}

/**
 * 智能包装影视海报封面地址：
 * 1. 命中外部 CDN 加速前缀（如 wsrv.nl 等）时，自动组装为全球边缘加速地址
 * 2. 开启全局代理后，第三方 http/https 图片自动转由 /api/v1/proxy/image 中继
 * 3. 属于后台配置启用的解密图床域名特征时，自动通过中继代理流式解密（纯动态感知，无需修改代码）
 */
export function formatPosterUrl(rawUrl: string | undefined | null, siteKey?: string | null): string {
  if (!rawUrl) return ''
  const trimmed = rawUrl.trim()
  if (!trimmed) return ''
  if (trimmed.startsWith('/api/v1/proxy/image')) return trimmed

  // 1. 优先匹配外部 CDN 加速前缀规则（如 wsrv.nl）
  const curSite = (siteKey || '').trim().toLowerCase()
  for (const rule of _cdnPrefixRules) {
    if (!rule.enabled || !rule.prefix) continue
    const rSite = (rule.site_key || '').trim().toLowerCase()
    const rDomain = (rule.match_domain || '').trim().toLowerCase()

    if (rSite && curSite && rSite !== curSite) continue
    if (rDomain && !trimmed.toLowerCase().includes(rDomain)) continue

    if (!trimmed.startsWith(rule.prefix)) {
      return `${rule.prefix}${encodeURIComponent(trimmed)}`
    }
    return trimmed
  }

  // 2. 检查内置图片防盗链代理 / 解密中继
  const isEncryptedHost = _decryptDomains.some(d => d && trimmed.toLowerCase().includes(d.toLowerCase()))

  if ((_globalImageProxy || isEncryptedHost) && (trimmed.startsWith('http://') || trimmed.startsWith('https://'))) {
    const siteParam = siteKey ? `&site=${encodeURIComponent(siteKey)}` : ''
    const devToken = getDeviceToken() || getAdminToken() || ''
    const tokenParam = devToken ? `&token=${encodeURIComponent(devToken)}` : ''
    return `/api/v1/proxy/image?url=${encodeURIComponent(trimmed)}${siteParam}${tokenParam}`
  }
  return trimmed
}

/**
 * 分类与标签展示名归一化（带管理员自定义别名后缀）
 */
export function formatCatDisplay(name?: string, custom?: string): string {
  if (!name) return ''
  if (!custom || !custom.trim()) return name
  let c = custom.trim()
  if ((c.startsWith('(') && c.endsWith(')')) || (c.startsWith('（') && c.endsWith('）'))) {
    c = c.slice(1, -1).trim()
  }
  if (!c) return name
  const suffix = `（${c}）`
  if (name.endsWith(suffix)) return name
  return `${name}${suffix}`
}

