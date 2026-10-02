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

let _globalImageProxy = false

export function setGlobalImageProxy(enabled: boolean): void {
  _globalImageProxy = enabled
}

export function isGlobalImageProxy(): boolean {
  return _globalImageProxy
}

/**
 * 智能包装影视海报封面地址：
 * 开启全局代理后，第三方 http/https 图片自动转由 /api/v1/proxy/image 中继
 */
export function formatPosterUrl(rawUrl: string | undefined | null, siteKey?: string | null): string {
  if (!rawUrl) return ''
  const trimmed = rawUrl.trim()
  if (!trimmed) return ''
  if (trimmed.startsWith('/api/v1/proxy/image')) return trimmed
  if (_globalImageProxy && (trimmed.startsWith('http://') || trimmed.startsWith('https://'))) {
    const siteParam = siteKey ? `&site=${encodeURIComponent(siteKey)}` : ''
    return `/api/v1/proxy/image?url=${encodeURIComponent(trimmed)}${siteParam}`
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

