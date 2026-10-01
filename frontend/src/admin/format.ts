/**
 * 后台的展示口径。
 *
 * 抽出来的原因：同一个东西在列表、详情、导出里显示得不一样，
 * 是最容易让人误判的地方 —— 尤其\"还剩多久\"和\"这个码现在算什么状态\"。
 */

import type { CodeListItem } from '@/api/types'

/** UTC 时间戳 → 本地可读时间。后端一律给带时区的 ISO，这里只负责换成本地人看得懂的。 */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`
}

/** 还剩多久。用\"天\"而不是秒，因为这个数字是给人看的，不是给机器看的。 */
export function humanRemaining(seconds: number): string {
  if (seconds <= 0) return '—'
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  if (days > 0) return `${days} 天 ${hours} 小时`
  const minutes = Math.floor((seconds % 3600) / 60)
  return hours > 0 ? `${hours} 小时 ${minutes} 分` : `${minutes} 分`
}

export type TagType = 'success' | 'warning' | 'danger' | 'info'

export interface CodeState {
  label: string
  tag: TagType
}

/**
 * 一个码现在到底算什么状态。
 *
 * **注意 `remaining_seconds === 0` 有两种含义**（契约里写明了）：
 * 还没激活、或者已经到期。只看 0 会得出错误结论，所以这里必须结合
 * `activated_at` 一起判断。
 */
export function codeState(item: CodeListItem): CodeState {
  if (item.disabled_at) return { label: '已停用', tag: 'danger' }
  if (!item.activated_at) return { label: '未激活', tag: 'info' }
  // 生成的类型里带默认值的字段是可选的（JSON Schema 的 required 才是硬约定），
  // 所以这里统一兜一个 0，而不是在每个调用点写 `?? 0`。
  if ((item.remaining_seconds ?? 0) <= 0) return { label: '已到期', tag: 'warning' }
  return { label: '使用中', tag: 'success' }
}

/** 命中率（%）：命中 / (命中 + 未命中)。没有请求时给 0 而不是 NaN。 */
export function hitRate(hits: number, misses: number): number {
  const total = hits + misses
  if (total === 0) return 0
  return Math.round((hits / total) * 1000) / 10
}
