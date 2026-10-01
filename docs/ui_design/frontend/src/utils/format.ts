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
