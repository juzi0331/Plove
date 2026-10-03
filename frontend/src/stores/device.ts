/**
 * 设备（激活）状态。**整个应用的门就在这里。**
 *
 * 三条规则来自后端的设计，前端必须照做，否则会出现\"用户看不懂的踢来踢去\"：
 *
 * 1. **服务端不做离线超时释放**：活跃位只在有人主动抢时才变。
 *    所以这里**不**在切后台/锁屏时清任何状态，也没有本地超时。
 * 2. 心跳返回 `is_active: false` = 活跃位被别的设备拿走了。
 *    客户端应当**立即停播并提示**，而不是自己抢回来 ——
 *    否则两台设备会互相无限踢。
 * 3. 抢回来是**用户动作**（界面上的\"在此设备继续\"），不是自动的。
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import * as api from '@/api/client'
import { ApiError, describeError } from '@/api/http'
import { getDeviceToken, onSessionKicked, setDeviceToken } from '@/api/session'

const NAME_KEY = 'plove.device_name'
const EXPIRES_KEY = 'plove.device_expires_at'
const SECONDS_KEY = 'plove.device_remaining_seconds'

export const useDeviceStore = defineStore('device', () => {
  const token = ref<string | null>(getDeviceToken())
  const deviceName = ref<string>(readSavedName())
  const remainingSeconds = ref<number>(readSavedSeconds())
  const expiresAt = ref<string | null>(readSavedExpiresAt())
  const kicked = ref(false)
  const busy = ref(false)
  const lastError = ref<string | null>(null)
  /**
   * "刚刚把活跃位抢回来了"的信号，每成功抢回一次就变一次。
   *
   * 为什么需要它：被踢的时候，当前那个页面上的请求会拿到 `SESSION_KICKED`
   * 而**当场变成一个错误态**（首页/播放页都不例外）。用户点完"在此设备继续"，
   * 会话是好了，但那个错误还挂在屏幕上 —— 他得自己发现"重试"按钮。
   * 视图监听这个信号自己重新加载，用户感觉就是"点了一下，画面回来了"。
   */
  const restoredAt = ref(0)

  let timer: number | null = null
  let intervalSeconds = 30

  const activated = computed(() => token.value !== null)
  const daysLeft = computed(() => Math.max(0, Math.floor(remainingSeconds.value / 86400)))

  const formattedRemainingTime = computed(() => {
    const sec = remainingSeconds.value
    if (sec <= 0) return '已過期'
    const days = Math.floor(sec / 86400)
    const hours = Math.floor((sec % 86400) / 3600)
    if (days > 0) {
      return hours > 0 ? `${days} 天 ${hours} 小時` : `${days} 天`
    }
    const mins = Math.max(1, Math.floor((sec % 3600) / 60))
    return `${hours} 小時 ${mins} 分鐘`
  })

  function readSavedName(): string {
    try {
      return localStorage.getItem(NAME_KEY) ?? ''
    } catch {
      return ''
    }
  }

  function readSavedExpiresAt(): string | null {
    try {
      return localStorage.getItem(EXPIRES_KEY)
    } catch {
      return null
    }
  }

  function readSavedSeconds(): number {
    try {
      const v = localStorage.getItem(SECONDS_KEY)
      return v ? Number(v) : 0
    } catch {
      return 0
    }
  }

  function saveName(value: string): void {
    deviceName.value = value
    try {
      localStorage.setItem(NAME_KEY, value)
    } catch {
      /* 存不进就算了 */
    }
  }

  function applyResult(result: { remaining_seconds: number; expires_at: string; heartbeat_interval_seconds: number }): void {
    remainingSeconds.value = result.remaining_seconds
    expiresAt.value = result.expires_at
    intervalSeconds = result.heartbeat_interval_seconds
    try {
      localStorage.setItem(EXPIRES_KEY, String(result.expires_at))
      localStorage.setItem(SECONDS_KEY, String(result.remaining_seconds))
    } catch {
      /* 忽略存储异常 */
    }
  }

  /** 首次激活 */
  async function activate(code: string, name: string): Promise<boolean> {
    busy.value = true
    lastError.value = null
    try {
      const result = await api.redeem({ code: code.trim(), deviceName: name.trim() })
      setDeviceToken(result.device_token)
      token.value = result.device_token
      saveName(result.device_name || name.trim())
      applyResult(result)
      kicked.value = false
      startHeartbeat()
      return true
    } catch (error) {
      lastError.value = describeError(error)
      return false
    } finally {
      busy.value = false
    }
  }

  /**
   * 被踢之后\"在此设备继续\"。给的是**已存的令牌**，不需要用户再输一次码。
   * 这是用户主动的动作，所以不会造成无限互踢。
   */
  async function resume(): Promise<boolean> {
    if (!token.value) return false
    busy.value = true
    lastError.value = null
    try {
      const result = await api.redeem({ deviceToken: token.value, deviceName: deviceName.value })
      setDeviceToken(result.device_token)
      token.value = result.device_token
      applyResult(result)
      kicked.value = false
      startHeartbeat()
      // 通知还在屏幕上的那个视图：可以把刚才失败的请求重做一遍了
      restoredAt.value = Date.now()
      return true
    } catch (error) {
      lastError.value = describeError(error)
      return false
    } finally {
      busy.value = false
    }
  }

  async function heartbeatOnce(): Promise<void> {
    if (!token.value) return
    try {
      const state = await api.heartbeat()
      applyResult(state)
      if (!state.is_active) {
        // 停播 + 提示由界面来做；这里只把状态立起来，并停掉心跳
        // （继续心跳没有意义：活跃位不会因为我们问就回来）。
        kicked.value = true
        stopHeartbeat()
      }
    } catch (error) {
      // 心跳失败**不踢人**：网络抖一下不该让用户丢掉会话。
      // 只有明确的\"被踢\"才处理，其余交给下一次心跳。
      if (error instanceof ApiError && error.code === 'UNAUTHORIZED') {
        forget()
      }
    }
  }

  function startHeartbeat(): void {
    stopHeartbeat()
    if (!token.value) return
    // 立即向后端拉取一次最新状态，秒级同步真实到期时间和剩余秒数
    void heartbeatOnce()
    timer = window.setInterval(() => void heartbeatOnce(), Math.max(10, intervalSeconds) * 1000)
  }

  function stopHeartbeat(): void {
    if (timer !== null) {
      window.clearInterval(timer)
      timer = null
    }
  }

  /** 令牌作废：清干净并回激活页 */
  function forget(): void {
    stopHeartbeat()
    setDeviceToken(null)
    token.value = null
    remainingSeconds.value = 0
    expiresAt.value = null
    kicked.value = false
    try {
      localStorage.removeItem(EXPIRES_KEY)
      localStorage.removeItem(SECONDS_KEY)
    } catch {
      /* 忽略 */
    }
  }

  function dismissKicked(): void {
    kicked.value = false
  }

  // HTTP 层看到 SESSION_KICKED 时会喊一声，这里接住。
  // 这样\"任何接口发现被踢\"都能统一走同一套处理，而不用每个页面写一遍。
  onSessionKicked(() => {
    kicked.value = true
    stopHeartbeat()
  })

  return {
    token,
    deviceName,
    remainingSeconds,
    expiresAt,
    kicked,
    restoredAt,
    busy,
    lastError,
    activated,
    daysLeft,
    formattedRemainingTime,
    activate,
    resume,
    heartbeatOnce,
    startHeartbeat,
    stopHeartbeat,
    forget,
    dismissKicked,
    saveName,
  }
})
