import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import type {
  TelegramVerifyResult,
  WebhookConfigPayload,
  WebhookDeliveryLogItem,
} from '@/api/types'
import {
  clearWebhookLogs,
  getWebhookConfig,
  getWebhookLogs,
  saveWebhookConfig,
  testWebhookChannel,
  verifyTelegramBot,
} from '@/admin/api/webhooks'

export function useWebhooks() {
  const loading = ref(false)
  const saving = ref(false)
  const testing = ref(false)
  const verifying = ref(false)
  const clearingLogs = ref(false)
  const configDialogVisible = ref(false)

  const config = ref<Required<WebhookConfigPayload>>({
    telegram: {
      enabled: false,
      bot_token: '',
      chat_id: '',
      proxy_url: '',
      bot_username: '',
      bot_name: '',
    },
    wechat_work: { enabled: false, webhook_url: '' },
    feishu: { enabled: false, webhook_url: '', secret: '' },
    custom_http: { enabled: false, url: '', secret_token: '' },
    events: {
      circuit_break: true,
      code_activated: true,
      proxy_offline: true,
      daily_report: false,
      fail_threshold: 3,
    },
  })

  // 弹窗内的编辑草稿
  const editDraft = ref({
    bot_token: '',
    chat_id: '',
    proxy_url: '',
    enabled: false,
  })

  const verifyResult = ref<TelegramVerifyResult | null>(null)
  const logs = ref<WebhookDeliveryLogItem[]>([])

  // 统计指标
  const activeEventsCount = computed(() => {
    let count = 0
    const ev = config.value.events
    if (ev.circuit_break) count++
    if (ev.code_activated) count++
    if (ev.proxy_offline) count++
    if (ev.daily_report) count++
    return count
  })

  const lastLog = computed(() => (logs.value.length > 0 ? logs.value[0] : null))

  // ------------------------------------------------------------------ 数据交互

  async function loadData(): Promise<void> {
    loading.value = true
    try {
      const [cfgRes, logsRes] = await Promise.all([
        getWebhookConfig(),
        getWebhookLogs(30),
      ])
      if (cfgRes) {
        config.value = {
          telegram: { ...config.value.telegram, ...(cfgRes.telegram || {}) },
          wechat_work: { ...config.value.wechat_work, ...(cfgRes.wechat_work || {}) },
          feishu: { ...config.value.feishu, ...(cfgRes.feishu || {}) },
          custom_http: { ...config.value.custom_http, ...(cfgRes.custom_http || {}) },
          events: { ...config.value.events, ...(cfgRes.events || {}) },
        }
      }
      logs.value = logsRes.logs || []
    } catch (err: unknown) {
      ElMessage.error(err instanceof Error ? err.message : '加载配置失败')
    } finally {
      loading.value = false
    }
  }

  async function handleSave(): Promise<void> {
    saving.value = true
    try {
      const res = await saveWebhookConfig(config.value)
      if (res) {
        config.value = {
          telegram: { ...config.value.telegram, ...(res.telegram || {}) },
          wechat_work: { ...config.value.wechat_work, ...(res.wechat_work || {}) },
          feishu: { ...config.value.feishu, ...(res.feishu || {}) },
          custom_http: { ...config.value.custom_http, ...(res.custom_http || {}) },
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
    editDraft.value = {
      bot_token: config.value.telegram.bot_token || '',
      chat_id: config.value.telegram.chat_id || '',
      proxy_url: config.value.telegram.proxy_url || '',
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

  onMounted(() => {
    void loadData()
  })

  return {
    loading,
    saving,
    testing,
    verifying,
    clearingLogs,
    configDialogVisible,
    config,
    editDraft,
    verifyResult,
    logs,
    activeEventsCount,
    lastLog,
    loadData,
    handleSave,
    openConfigDialog,
    handleVerifyToken,
    saveDialogConfig,
    handleTest,
    handleClearLogs,
  }
}
