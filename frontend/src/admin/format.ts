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

export type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'

export interface CodeState {
  label: string
  tag: TagType
  isPlaying?: boolean
  currentPlayback?: string | null
}

/**
 * 一个码现在到底算什么状态。
 *
 * 状态口径说明：
 * - 已停用：管理员手动封禁
 * - 未激活：发放后尚未在任何设备上兑换
 * - 已到期：有效期已过
 * - 使用中：当前有设备正在播放视频（实时心跳活跃）
 * - 空闲中：码正常有效，但当前无设备在播放
 */
export function codeState(item: CodeListItem): CodeState {
  if (item.disabled_at) return { label: '已停用', tag: 'danger' }
  if (!item.activated_at) return { label: '未激活', tag: 'info' }
  if ((item.remaining_seconds ?? 0) <= 0) return { label: '已到期', tag: 'warning' }
  if (item.is_playing) {
    return {
      label: '使用中',
      tag: 'success',
      isPlaying: true,
      currentPlayback: item.current_playback,
    }
  }
  return { label: '空闲中', tag: 'info', isPlaying: false }
}

/** 命中率（%）：命中 / (命中 + 未命中)。没有请求时给 0 而不是 NaN。 */
export function hitRate(hits: number, misses: number): number {
  const total = hits + misses
  if (total === 0) return 0
  return Math.round((hits / total) * 1000) / 10
}
