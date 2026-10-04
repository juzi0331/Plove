/**
 * 主题适配器 (Theme Adapter)。
 *
 * 职责：
 * 将服务端下发的 ThemeConfig 语义 Token 安全映射为前端根文档 CSS 变量。
 * 阻止任何不受控的任意样式字符串注入。
 */

import type { BrandConfig, ThemeConfig } from '@/api/types'

const HEX_COLOR_REGEX = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/

function isSafeHexColor(val?: string | null): val is string {
  if (!val || typeof val !== 'string') return false
  return HEX_COLOR_REGEX.test(val.trim())
}

/**
 * 将十六进制颜色转化为稍暗或稍亮的操作辅助色
 */
function adjustHexBrightness(hex: string, percent: number): string {
  if (!isSafeHexColor(hex)) return hex
  let clean = hex.replace('#', '')
  if (clean.length === 3) {
    clean = clean.split('').map(c => c + c).join('')
  }
  const num = parseInt(clean, 16)
  let r = (num >> 16) + percent
  let g = ((num >> 8) & 0x00ff) + percent
  let b = (num & 0x0000ff) + percent

  r = Math.min(255, Math.max(0, r))
  g = Math.min(255, Math.max(0, g))
  b = Math.min(255, Math.max(0, b))

  return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`
}

export function applyThemeTokens(theme?: ThemeConfig | null, brand?: BrandConfig | null): void {
  if (typeof document === 'undefined') return
  const root = document.documentElement

  if (theme) {
    // 1. 色彩映射
    if (theme.color) {
      if (isSafeHexColor(theme.color.background)) {
        root.style.setProperty('--plove-bg', theme.color.background)
      }
      if (isSafeHexColor(theme.color.surface)) {
        root.style.setProperty('--plove-surface', theme.color.surface)
        root.style.setProperty('--plove-surface-2', adjustHexBrightness(theme.color.surface, 15))
      }
      if (isSafeHexColor(theme.color.primary)) {
        root.style.setProperty('--plove-accent', theme.color.primary)
        root.style.setProperty('--plove-accent-press', adjustHexBrightness(theme.color.primary, -25))
        root.style.setProperty('--plove-accent-deep', adjustHexBrightness(theme.color.primary, -40))
      }
      if (isSafeHexColor(theme.color.text)) {
        root.style.setProperty('--plove-text', theme.color.text)
      }
      if (isSafeHexColor(theme.color.muted)) {
        root.style.setProperty('--plove-muted', theme.color.muted)
        root.style.setProperty('--plove-text-dim', adjustHexBrightness(theme.color.muted, 30))
      }
      if (isSafeHexColor(theme.color.border)) {
        root.style.setProperty('--plove-line', theme.color.border)
      }
      if (isSafeHexColor(theme.color.danger)) {
        root.style.setProperty('--plove-danger', theme.color.danger)
      }
    }

    // 2. 卡片与圆角
    if (theme.card) {
      if (typeof theme.card.radius_px === 'number') {
        const rad = Math.min(32, Math.max(0, theme.card.radius_px))
        root.style.setProperty('--plove-radius', `${rad}px`)
        root.style.setProperty('--plove-radius-sm', `${Math.max(2, Math.round(rad * 0.7))}px`)
      }
    }

    // 3. 布局与间距
    if (theme.layout) {
      if (typeof theme.layout.page_padding_px === 'number') {
        const pad = Math.min(64, Math.max(0, theme.layout.page_padding_px))
        root.style.setProperty('--plove-pad', `${pad}px`)
      }
      if (typeof theme.layout.gap_px === 'number') {
        const gap = Math.min(48, Math.max(0, theme.layout.gap_px))
        root.style.setProperty('--plove-gap', `${gap}px`)
      }
      if (typeof theme.layout.max_width_px === 'number') {
        const maxW = Math.min(2560, Math.max(960, theme.layout.max_width_px))
        root.style.setProperty('--plove-page-max-width', `${maxW}px`)
      }
    }

    // 4. 排版
    if (theme.typography) {
      if (typeof theme.typography.body_px === 'number') {
        const bodyPx = Math.min(24, Math.max(12, theme.typography.body_px))
        root.style.setProperty('--plove-font-body', `${bodyPx}px`)
      }
      if (typeof theme.typography.title_px === 'number') {
        const titlePx = Math.min(48, Math.max(18, theme.typography.title_px))
        root.style.setProperty('--plove-font-title', `${titlePx}px`)
      }
    }

    // 5. 动效
    if (theme.motion) {
      if (typeof theme.motion.duration_ms === 'number') {
        const dur = Math.min(1000, Math.max(0, theme.motion.duration_ms))
        root.style.setProperty('--plove-motion-duration', `${dur}ms`)
      }
    }
  }

  // 6. 品牌名称同步
  if (brand?.name) {
    if (typeof document !== 'undefined' && brand.name.trim()) {
      document.title = brand.name.trim()
    }
  }
}
