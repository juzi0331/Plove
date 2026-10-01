/**
 * 后台的界面状态：主题 / 只读模式 / 自动刷新 / 发码表单记忆。
 *
 * 为什么单独一个模块（不是 pinia store）：
 * 和 `token.ts` 同一个理由 —— `api.ts` 要读「只读模式」，
 * 而 store 会让依赖变成 `http → store → client → http` 的环。
 * 这里只有 `vue` 的响应式原语，谁都能 import。
 *
 * ### 只存"界面偏好"，不存凭证
 * 主题、自动刷新间隔、只读开关、发码表单的上次参数 —— 这些放 `localStorage` 没问题；
 * 后台令牌**不在这里**（它在 `token.ts`，存 `sessionStorage`，关标签页即失效）。
 *
 * ### 暗色模式怎么生效
 * Element Plus 的暗色变量挂在 `html.dark` 下，所以进入后台时由这里挂上/摘掉
 * （计数式，登录页切到主壳时不会闪一下）。「跟随系统」用 matchMedia 实时跟随。
 */

import { reactive, readonly } from 'vue'

export type AdminTheme = 'system' | 'light' | 'dark'

const UI_KEY = 'plove.admin.ui'
const ISSUE_KEY = 'plove.admin.issue'

interface Persisted {
  theme: AdminTheme
  readOnly: boolean
  autoRefreshEnabled: boolean
  autoRefreshSeconds: number
}

function readStorage<T>(key: string): Partial<T> {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as Partial<T>) : {}
  } catch {
    return {} // 隐私模式 / 坏数据：用默认值，不炸
  }
}

function writeStorage(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* 见上 */
  }
}

const persisted = readStorage<Persisted>(UI_KEY)

const state = reactive<Persisted>({
  theme: persisted.theme ?? 'system',
  readOnly: persisted.readOnly ?? false,
  autoRefreshEnabled: persisted.autoRefreshEnabled ?? true,
  autoRefreshSeconds: persisted.autoRefreshSeconds ?? 5,
})

/** 只读，但里面是响应式的 —— 组件的 computed / 模板都能直接跟 */
export const ui = readonly(state)

function save(): void {
  writeStorage(UI_KEY, { ...state })
}

// ------------------------------------------------------------------ 主题

const media = typeof window !== 'undefined' ? window.matchMedia('(prefers-color-scheme: dark)') : null

function systemPrefersDark(): boolean {
  return media?.matches ?? false
}

function applyTheme(): void {
  const dark = state.theme === 'dark' || (state.theme === 'system' && systemPrefersDark())
  document.documentElement.classList.toggle('dark', dark)
}

function onSystemThemeChange(): void {
  if (state.theme === 'system') applyTheme()
}

export function setTheme(theme: AdminTheme): void {
  state.theme = theme
  save()
  applyTheme()
}

/** 顶栏那个按钮：亮 → 暗 → 跟随系统 → 亮 … */
export function cycleTheme(): AdminTheme {
  const next: AdminTheme = state.theme === 'light' ? 'dark' : state.theme === 'dark' ? 'system' : 'light'
  setTheme(next)
  return next
}

export function themeLabel(theme: AdminTheme = state.theme): string {
  if (theme === 'light') return '浅色'
  if (theme === 'dark') return '深色'
  return '跟随系统'
}

/**
 * 进入 / 离开后台。**计数式**：登录页切主壳的同一刻两边都会调，
 * 直接 toggle 会闪一下（先摘后挂）。
 */
let mounted = 0

export function enterAdminUi(): void {
  mounted += 1
  if (mounted !== 1) return
  applyTheme()
  media?.addEventListener('change', onSystemThemeChange)
}

export function leaveAdminUi(): void {
  mounted = Math.max(0, mounted - 1)
  if (mounted !== 0) return
  media?.removeEventListener('change', onSystemThemeChange)
  // 离开后台就把暗色摘掉 —— 用户端（Vant）不受 Element 的暗色变量影响，
  // 但"后台留下的全局 class"本身就是一种脏状态，不留。
  document.documentElement.classList.remove('dark')
}

// ------------------------------------------------------------------ 只读模式

export function setReadOnly(value: boolean): void {
  state.readOnly = value
  save()
}

export function toggleReadOnly(): boolean {
  setReadOnly(!state.readOnly)
  return state.readOnly
}

/** 写操作前调它。**双保险**：按钮也会禁用，但万一有漏网的入口，这里兜底。 */
export function assertWritable(): void {
  if (state.readOnly) {
    throw new Error('只读模式已开启：所有写操作都被禁用（顶栏可以关掉它）')
  }
}

// ------------------------------------------------------------------ 自动刷新

export function setAutoRefresh(enabled: boolean): void {
  state.autoRefreshEnabled = enabled
  save()
}

export function setAutoRefreshSeconds(seconds: number): void {
  state.autoRefreshSeconds = seconds
  save()
}

// ------------------------------------------------------------------ 发码表单记忆

export interface IssueMemory {
  unit: 'days' | 'hours'
  amount: number
  count: number
  note: string
}

const DEFAULT_ISSUE: IssueMemory = { unit: 'days', amount: 30, count: 1, note: '' }

export function loadIssueMemory(): IssueMemory {
  const saved = readStorage<IssueMemory>(ISSUE_KEY)
  return {
    unit: saved.unit === 'hours' ? 'hours' : DEFAULT_ISSUE.unit,
    amount: typeof saved.amount === 'number' && saved.amount > 0 ? saved.amount : DEFAULT_ISSUE.amount,
    count: typeof saved.count === 'number' && saved.count > 0 ? saved.count : DEFAULT_ISSUE.count,
    note: '',
  }
}

export function saveIssueMemory(memory: Omit<IssueMemory, 'note'>): void {
  writeStorage(ISSUE_KEY, memory)
}
