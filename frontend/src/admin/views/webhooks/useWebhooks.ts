import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import type {
  EventSubscriptions,
  ProxyNodeItem,
  TelegramConfig,
  TelegramVerifyResult,
  WebhookDeliveryLogItem,
} from '@/api/types'
import {
  clearWebhookLogs,
  detectTelegramChat,
  getWebhookConfig,
  getWebhookLogs,
  saveWebhookConfig,
  sendWebhookEvent,
  testWebhookChannel,
  verifyTelegramBot,
} from '@/admin/api/webhooks'
import { listProxyNodes } from '@/admin/api/proxy-nodes'

export interface WebhookAdminConfig {
  telegram: Required<TelegramConfig>
  events: Required<EventSubscriptions>
  wechat_work?: unknown | null
  feishu?: unknown | null
  custom_http?: unknown | null
}

export function useWebhooks() {
  const loading = ref(false)
  const saving = ref(false)
  const testing = ref(false)
  const verifying = ref(false)
  const detectingChat = ref(false)
  const clearingLogs = ref(false)
  const configDialogVisible = ref(false)
  const rulesDialogVisible = ref(false)
  const customNoticeDialogVisible = ref(false)

  // 代理节点池列表
  const proxyNodes = ref<ProxyNodeItem[]>([])

  const config = ref<WebhookAdminConfig>({
    telegram: {
      enabled: false,
      bot_token: '',
      chat_id: '',
      proxy_url: '',
      bot_username: '',
      bot_name: '',
      console_url: '',
    },
    events: {
      circuit_break: true,
      circuit_recover: true,
      site_health_report: true,
      code_activated: true,
      device_conflict: true,
      security_alert: true,
      proxy_offline: true,
      daily_report: false,
      system_startup: false,
      fail_threshold: 3,
    },
  })

  // 弹窗内的编辑草稿
  const editDraft = ref({
    bot_token: '',
    chat_id: '',
    proxy_url: '',
    console_url: '',
    enabled: false,
  })

  const verifyResult = ref<TelegramVerifyResult | null>(null)
  const logs = ref<WebhookDeliveryLogItem[]>([])

  // 统计指标（9 项运维与运营核心事件）
  const activeEventsCount = computed(() => {
    let count = 0
    const ev = config.value.events
    if (ev.circuit_break) count++
    if (ev.circuit_recover) count++
    if (ev.site_health_report) count++
    if (ev.code_activated) count++
    if (ev.device_conflict) count++
    if (ev.security_alert) count++
    if (ev.proxy_offline) count++
    if (ev.daily_report) count++
    if (ev.system_startup) count++
    return count
  })

  const lastLog = computed(() => (logs.value.length > 0 ? logs.value[0] : null))

  // ------------------------------------------------------------------ 数据交互

  async function loadData(): Promise<void> {
    loading.value = true
    try {
      const [cfgRes, logsRes, nodesRes] = await Promise.all([
        getWebhookConfig(),
        getWebhookLogs(30),
        listProxyNodes().catch(() => ({ nodes: [] })),
      ])
      if (cfgRes) {
        config.value = {
          telegram: { ...config.value.telegram, ...(cfgRes.telegram || {}) },
          events: { ...config.value.events, ...(cfgRes.events || {}) },
        }
      }
      logs.value = logsRes.logs || []
      proxyNodes.value = nodesRes?.nodes || []
    } catch (err: unknown) {
      ElMessage.error(err instanceof Error ? err.message : '加载配置失败')
    } finally {
      loading.value = false
    }
  }

  async function loadProxyNodes(): Promise<void> {
    try {
      const res = await listProxyNodes()
      proxyNodes.value = res?.nodes || []
    } catch {
      // 保持静默
    }
  }

  async function handleSave(): Promise<void> {
    saving.value = true
    try {
      const res = await saveWebhookConfig(config.value)
      if (res) {
        config.value = {
          telegram: { ...config.value.telegram, ...(res.telegram || {}) },
          events: { ...config.value.events, ...(res.events || {}) },
        }
      }
      ElMessage.success('Telegram 机器人配置已成功保存')
    } catch (err: unknown) {
      ElMessage.error(err instanceof Error ? err.message : '保存配置失败')
    } finally {
      saving.value = false
    }
  }

  function openConfigDialog(): void {
    void loadProxyNodes()
    editDraft.value = {
      bot_token: config.value.telegram.bot_token || '',
      chat_id: config.value.telegram.chat_id || '',
      proxy_url: config.value.telegram.proxy_url || '',
      console_url: config.value.telegram.console_url || '',
      enabled: config.value.telegram.enabled || false,
    }
    verifyResult.value = config.value.telegram.bot_username
      ? {
          ok: true,
          username: config.value.telegram.bot_username,
          first_name: config.value.telegram.bot_name,
        }
      : null
    configDialogVisible.value = true
  }

  async function handleVerifyToken(): Promise<void> {
    if (!editDraft.value.bot_token.trim()) {
      ElMessage.warning('请先输入 Telegram Bot Token')
      return
    }
    verifying.value = true
    try {
      const res = await verifyTelegramBot(
        editDraft.value.bot_token.trim(),
        editDraft.value.proxy_url.trim() || undefined,
      )
      verifyResult.value = res
      if (res.ok) {
        ElMessage.success(`Token 校验通过！识别到机器人: @${res.username || '未知'}`)
        config.value.telegram.bot_username = res.username || ''
        config.value.telegram.bot_name = res.first_name || ''
      } else {
        ElMessage.error(res.error || 'Token 验证失败，请检查 Token 与网络代理')
      }
    } catch (err: unknown) {
      ElMessage.error(err instanceof Error ? err.message : '请求验证异常')
    } finally {
      verifying.value = false
    }
  }

  async function saveDialogConfig(): Promise<void> {
    config.value.telegram.bot_token = editDraft.value.bot_token.trim()
    config.value.telegram.chat_id = editDraft.value.chat_id.trim()
    config.value.telegram.proxy_url = editDraft.value.proxy_url.trim()
    config.value.telegram.console_url = editDraft.value.console_url.trim()
    config.value.telegram.enabled = editDraft.value.enabled

    if (verifyResult.value?.ok) {
      config.value.telegram.bot_username = verifyResult.value.username || ''
      config.value.telegram.bot_name = verifyResult.value.first_name || ''
    }

    await handleSave()
    configDialogVisible.value = false
  }

  async function handleTest(): Promise<void> {
    testing.value = true
    try {
      const res = await testWebhookChannel({ channel: 'telegram' })
      if (res.ok) {
        ElMessage.success(`Telegram 测试消息投递成功（耗时 ${res.duration_ms}ms）`)
      } else {
        ElMessage.error(`投递失败: ${res.message || res.error || '请检查 Bot Token 与代理设置'}`)
      }
      const logsRes = await getWebhookLogs(30)
      logs.value = logsRes.logs || []
    } catch (err: unknown) {
      ElMessage.error(err instanceof Error ? err.message : '测试请求异常')
    } finally {
      testing.value = false
    }
  }

  async function handleClearLogs(): Promise<void> {
    clearingLogs.value = true
    try {
      await clearWebhookLogs()
      logs.value = []
      ElMessage.success('Telegram 投递历史记录已清空')
    } catch (err: unknown) {
      ElMessage.error(err instanceof Error ? err.message : '清空日志失败')
    } finally {
      clearingLogs.value = false
    }
  }

  async function handleDetectChat(): Promise<void> {
    if (!editDraft.value.bot_token.trim()) {
      ElMessage.warning('请先输入 Telegram Bot Token')
      return
    }
    detectingChat.value = true
    try {
      const res = await detectTelegramChat(
        editDraft.value.bot_token.trim(),
        editDraft.value.proxy_url.trim() || undefined,
      )
      if (res.ok && res.chat_id) {
        editDraft.value.chat_id = res.chat_id
        const typeDesc = res.chat_type === 'private' ? '个人管理员 ID' : '群组 / 频道 ID'
        ElMessage.success(`成功识别到 ${typeDesc}: ${res.chat_id} (${res.chat_title || '未命名'})`)
      } else {
        ElMessage.warning(res.error || '未获取到近期互动，请先在 Telegram 向机器人发送一条消息')
      }
    } catch (err: unknown) {
      ElMessage.error(err instanceof Error ? err.message : '自动获取 Chat ID 异常')
    } finally {
      detectingChat.value = false
    }
  }

  const sendingEvent = ref<string | null>(null)
  const sendingCustomNotice = ref(false)

  const customNoticeDraft = ref({
    title: '',
    category: '📢 系统公告',
    content: '',
    extraNote: '',
    rawHtml: true,
  })

  const EVENT_NAMES: Record<string, string> = {
    site_health_report: '站点清单与连通性自检报告',
    circuit_break: '内容源熔断告警',
    circuit_recover: '内容源自愈恢复',
    proxy_offline: '代理节点离线预警',
    code_activated: '激活码绑定提醒',
    device_conflict: '多设备抢线冲突',
    security_alert: '接口防刷限流告警',
    daily_report: '每日运行大盘简报',
    system_startup: '集群就绪重启通知',
    custom: '自定义全网广播',
  }

  async function handleSendEvent(eventType: string): Promise<void> {
    sendingEvent.value = eventType
    try {
      const res = await sendWebhookEvent({ event_type: eventType })
      const label = EVENT_NAMES[eventType] || eventType
      if (res.ok) {
        ElMessage.success(`「${label}」已即时推送到 Telegram（耗时 ${res.duration_ms}ms）`)
      } else {
        ElMessage.error(`推送失败: ${res.message || res.error || '请检查 Bot Token 与代理'}`)
      }
      const logsRes = await getWebhookLogs(30)
      logs.value = logsRes.logs || []
    } catch (err: unknown) {
      ElMessage.error(err instanceof Error ? err.message : '发送事件异常')
    } finally {
      sendingEvent.value = null
    }
  }

  async function handleSendCustomNotice(): Promise<void> {
    if (!customNoticeDraft.value.content.trim()) {
      ElMessage.warning('请输入要广播的通知正文')
      return
    }
    sendingCustomNotice.value = true
    try {
      const title = customNoticeDraft.value.title.trim() || '系统公告与运维通知'
      const isRaw = customNoticeDraft.value.rawHtml
      const res = await sendWebhookEvent({
        event_type: 'custom',
        title,
        content: customNoticeDraft.value.content.trim(),
        raw_html: isRaw,
        fields: isRaw
          ? undefined
          : {
              '公告类型': customNoticeDraft.value.category || '📢 系统公告',
              '发报人': '系统管理员 (Console)',
              ...(customNoticeDraft.value.extraNote.trim() ? { '处理建议': customNoticeDraft.value.extraNote.trim() } : {}),
            },
      })
      if (res.ok) {
        ElMessage.success(`自定义通知已成功发布并推送至 Telegram（耗时 ${res.duration_ms}ms）`)
        customNoticeDraft.value.content = ''
        customNoticeDraft.value.extraNote = ''
      } else {
        ElMessage.error(`推送失败: ${res.message || res.error || '请检查配置与 HTML 标签闭合'}`)
      }
      const logsRes = await getWebhookLogs(30)
      logs.value = logsRes.logs || []
    } catch (err: unknown) {
      ElMessage.error(err instanceof Error ? err.message : '发送通知异常')
    } finally {
      sendingCustomNotice.value = false
    }
  }

  onMounted(() => {
    void loadData()
  })

  return {
    loading,
    saving,
    testing,
    verifying,
    detectingChat,
    clearingLogs,
    configDialogVisible,
    rulesDialogVisible,
    customNoticeDialogVisible,
    proxyNodes,
    config,
    editDraft,
    verifyResult,
    logs,
    activeEventsCount,
    lastLog,
    sendingEvent,
    sendingCustomNotice,
    customNoticeDraft,
    loadData,
    loadProxyNodes,
    handleSave,
    openConfigDialog,
    handleVerifyToken,
    handleDetectChat,
    saveDialogConfig,
    handleTest,
    handleClearLogs,
    handleSendEvent,
    handleSendCustomNotice,
  }
}
