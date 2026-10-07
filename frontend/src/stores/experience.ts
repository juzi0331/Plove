/**
 * 前台体验与自动发布感知 Store (experience.ts)。
 *
 * 核心能力：
 * 1. 启动时拉取 Bootstrap 基础配置并注入主题 Token
 * 2. 在线活跃客户端每 30 秒进行条件版本查询 (ETag)
 * 3. 页面切回前台 (focus / visibilitychange) 立即核查版本
 * 4. 当后台发布新配置或回滚时，已打开页面自动无感热更新主题与内容！
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ClientBootstrapPayload, PageViewModel, ReleaseCurrentPayload } from '@/api/types'
import { getDeviceToken } from '@/api/session'
import { applyThemeTokens } from '@/theme/adapter'

export const useExperienceStore = defineStore('experience', () => {
  const bootstrap = ref<ClientBootstrapPayload | null>(null)
  const currentPage = ref<PageViewModel | null>(null)
  const currentRevision = ref<number>(1)
  const currentReleaseId = ref<string>('')
  const lastEtag = ref<string>('')
  const isPollingActive = ref<boolean>(false)
  const contentRevisionTrigger = ref<number>(0)

  let pollTimer: number | null = null

  /**
   * 拉取全站启动配置并应用主题
   */
  async function loadBootstrap(): Promise<ClientBootstrapPayload | null> {
    try {
      const resp = await fetch('/api/v2/client/bootstrap', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
      if (!resp.ok) return null
      const json = await resp.json()
      if (json.ok && json.data) {
        bootstrap.value = json.data
        currentRevision.value = json.data.revision
        currentReleaseId.value = json.data.release_id
        applyThemeTokens(json.data.theme, json.data.brand)
        return json.data
      }
    } catch (e) {
      console.warn('Bootstrap fetch failed:', e)
    }
    return null
  }

  /**
   * 拉取受控页面渲染模型 (如 'home')
   */
  async function loadPage(pageId = 'home', _force = false): Promise<PageViewModel | null> {
    try {
      const headers: Record<string, string> = {}
      const token = getDeviceToken()
      if (token) {
        headers['X-Device-Token'] = token
      }
      const resp = await fetch(`/api/v2/client/pages/${encodeURIComponent(pageId)}`, { headers })
      if (!resp.ok) return null
      const json = await resp.json()
      if (json.ok && json.data) {
        currentPage.value = json.data as PageViewModel
        return json.data
      }
    } catch (e) {
      console.warn('Page fetch failed:', e)
    }
    return null
  }

  /**
   * 检查发布版本，若后端有新发布或回滚则自动同步
   */
  async function checkForUpdates(): Promise<boolean> {
    try {
      const headers: Record<string, string> = {}
      if (lastEtag.value) {
        headers['If-None-Match'] = lastEtag.value
      }

      const resp = await fetch('/api/v2/client/releases/current', { headers })
      if (resp.status === 304) {
        // 未变动，节省带宽
        return false
      }

      const newEtag = resp.headers.get('etag')
      if (newEtag) {
        lastEtag.value = newEtag
      }

      if (resp.ok) {
        const json = await resp.json()
        if (json.ok && json.data) {
          const info = json.data as ReleaseCurrentPayload
          if (info.revision !== currentRevision.value || info.release_id !== currentReleaseId.value) {
            console.log(`检测到后台新发布/回滚 (r${info.revision})，正在自动无感应用...`)
            await loadBootstrap()
            contentRevisionTrigger.value++
            return true
          }
        }
      }
    } catch (e) {
      // 离线或网络波动保持旧配置
    }
    return false
  }

  /**
   * 启动前台版本自动检测循环
   */
  function startVersionPolling(): void {
    if (isPollingActive.value || typeof window === 'undefined') return
    isPollingActive.value = true

    // 1. 定时心跳轮询（默认 120 秒，结合切回前台即时核查）
    const intervalSec = Math.max(60, bootstrap.value?.refresh_after_seconds || 120)
    pollTimer = window.setInterval(() => {
      checkForUpdates()
    }, intervalSec * 1000)

    // 2. 切回前台或获得焦点时立即复核
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        checkForUpdates()
      }
    })
    window.addEventListener('focus', () => {
      checkForUpdates()
    })
  }

  function stopVersionPolling(): void {
    if (pollTimer !== null) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    isPollingActive.value = false
  }

  return {
    bootstrap,
    currentPage,
    currentRevision,
    currentReleaseId,
    contentRevisionTrigger,
    loadBootstrap,
    loadPage,
    checkForUpdates,
    startVersionPolling,
    stopVersionPolling,
  }
})
