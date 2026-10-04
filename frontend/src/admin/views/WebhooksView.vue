<script setup lang="ts">
/**
 * WebhooksView - Telegram 告警与通知机器人管理中心
 *
 * 专注于 Telegram 官方 Bot 自动化推送：
 * 1. Bot Token 校验与机器人信息拉取 (getMe)
 * 2. 目标 Chat ID / 频道群组配置
 * 3. HTTP / SOCKS5 代理穿透支持 (适应国内环境)
 * 4. 弹出式参数配置卡片 (Dialog 模态设计)
 * 5. 核心告警规则订阅矩阵 (源站熔断、代理离线、激活码使用、每日简报)
 * 6. 一键连通性测试与投递日志审计
 */
import {
  Check,
  CircleCheck,
  CircleClose,
  Delete,
  Document,
  Notification,
  Promotion,
  Refresh,
  Setting,
  WarningFilled,
} from '@element-plus/icons-vue'
import {
  ElButton,
  ElCard,
  ElDialog,
  ElDivider,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElSkeleton,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus'
import { computed, onMounted, ref } from 'vue'

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
} from '../api/webhooks'
import PageHeader from '../components/PageHeader.vue'
import { ui } from '../ui'

// ------------------------------------------------------------------ 状态管理

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
</script>

<template>
  <div class="a-page webhooks-page">
    <PageHeader
      title="Telegram 机器人"
      desc="配置 Telegram 官方告警机器人通道。当源站采集熔断、代理离线或激活码兑换时，实时向 Telegram 频道或运维群组推送告警。"
    >
      <template #actions>
        <ElButton
          :icon="Refresh"
          :loading="loading"
          @click="loadData"
        >
          刷新
        </ElButton>
        <ElButton
          type="primary"
          :icon="Check"
          :loading="saving"
          :disabled="ui.readOnly"
          @click="handleSave"
        >
          保存全部配置
        </ElButton>
      </template>
    </PageHeader>

    <!-- 骨架屏加载状态 -->
    <div v-if="loading && !config.telegram.chat_id && logs.length === 0" class="a-card skeleton">
      <ElSkeleton :rows="6" animated />
    </div>

    <template v-else>
      <!-- 顶部核心指标看板 -->
      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-title">机器人运行状态</div>
          <div class="kpi-main">
            <span
              class="kpi-status-dot"
              :class="config.telegram.enabled ? 'dot-active' : 'dot-inactive'"
            />
            <span class="kpi-num-text">
              {{ config.telegram.enabled ? '已启用推送' : '未开启' }}
            </span>
          </div>
          <div class="kpi-desc">
            {{ config.telegram.enabled ? '全天候监听并推送关键告警' : '启用后将自动下发群消息' }}
          </div>
        </div>

        <div class="kpi-card">
          <div class="kpi-title">目标接收群组 / 频道</div>
          <div class="kpi-main">
            <span class="kpi-mono-val">
              {{ config.telegram.chat_id || '未绑定 Chat ID' }}
            </span>
          </div>
          <div class="kpi-desc">管理员个人或超级群组 ID</div>
        </div>

        <div class="kpi-card">
          <div class="kpi-title">网络连接代理</div>
          <div class="kpi-main">
            <span class="kpi-mono-val">
              {{ config.telegram.proxy_url || '自动继承本地代理池' }}
            </span>
          </div>
          <div class="kpi-desc">确保国内网络环境下 API 正常连通</div>
        </div>

        <div class="kpi-card">
          <div class="kpi-title">已订阅告警事件</div>
          <div class="kpi-main">
            <span class="kpi-num">{{ activeEventsCount }}</span>
            <span class="kpi-unit">/ 4 项</span>
          </div>
          <div class="kpi-desc">熔断报警、节点离线、激活发码</div>
        </div>
      </div>

      <!-- Telegram 核心卡片展示 -->
      <div class="section-title-bar">
        <div class="title-with-icon">
          <ElIcon :size="16"><Promotion /></ElIcon>
          <span>Telegram 机器人核心通道</span>
        </div>
      </div>

    <div class="bot-card-container">
      <ElCard shadow="hover" class="bot-hero-card" @click="openConfigDialog">
        <div class="bot-card-inner">
          <div class="bot-brand-col">
            <div class="bot-avatar-box">
              <ElIcon :size="28" class="bot-plane-icon"><Promotion /></ElIcon>
            </div>
            <div class="bot-meta-info">
              <div class="bot-title-row">
                <span class="bot-name">
                  {{ config.telegram.bot_name || 'Telegram 告警机器人' }}
                </span>
                <ElTag
                  v-if="config.telegram.bot_username"
                  size="small"
                  type="primary"
                  effect="plain"
                  class="bot-uname-tag"
                >
                  @{{ config.telegram.bot_username }}
                </ElTag>
                <ElTag
                  size="small"
                  :type="config.telegram.enabled ? 'success' : 'info'"
                  effect="dark"
                >
                  {{ config.telegram.enabled ? '运行中' : '未开启' }}
                </ElTag>
              </div>
              <div class="bot-sub-row">
                <span class="bot-param-pill">
                  <strong>目标 Chat ID:</strong>
                  <code>{{ config.telegram.chat_id || '未配置' }}</code>
                </span>
                <span class="bot-param-pill">
                  <strong>网络代理:</strong>
                  <code>{{ config.telegram.proxy_url || '继承代理池 (127.0.0.1:10809)' }}</code>
                </span>
              </div>
            </div>
          </div>

          <div class="bot-actions-col" @click.stop>
            <div class="switch-wrap">
              <span class="switch-label">启用推送</span>
              <ElSwitch
                v-model="config.telegram.enabled"
                :disabled="ui.readOnly"
                inline-prompt
                active-text="开启"
                inactive-text="关闭"
                @change="handleSave"
              />
            </div>
            <ElButton
              type="primary"
              :icon="Setting"
              plain
              @click="openConfigDialog"
            >
              配置参数
            </ElButton>
            <ElButton
              type="success"
              :icon="Promotion"
              plain
              :loading="testing"
              :disabled="!config.telegram.bot_token || !config.telegram.chat_id"
              @click="handleTest"
            >
              发送测试消息
            </ElButton>
          </div>
        </div>

        <!-- 连通性提示条 -->
        <div v-if="lastLog" class="bot-card-banner">
          <ElIcon :size="14" :color="lastLog.status === 'success' ? '#166534' : '#dc2626'">
            <CircleCheck v-if="lastLog.status === 'success'" />
            <CircleClose v-else />
          </ElIcon>
          <span class="banner-text">
            最近投递状态：{{ lastLog.status === 'success' ? '正常投递成功' : '投递失败' }}
            （耗时 {{ lastLog.duration_ms }}ms，{{ lastLog.sent_at }}）
          </span>
          <span v-if="lastLog.error" class="banner-err">{{ lastLog.error }}</span>
        </div>
      </ElCard>
    </div>

    <!-- 告警订阅事件规则设置 -->
    <div class="section-title-bar" style="margin-top: 24px;">
      <div class="title-with-icon">
        <ElIcon :size="16"><Notification /></ElIcon>
        <span>系统事件与告警触发订阅规则</span>
      </div>
    </div>

    <ElCard shadow="hover" class="events-card">
      <div class="event-rows-list">
        <div class="event-item-row">
          <div class="event-meta">
            <div class="event-name">内容源抓取连续异常与熔断警报</div>
            <div class="event-sub">当某个内容源在上游请求、DOM 解析中连续失败达到阈值，或触发自动熔断保护时立即向群内告警</div>
          </div>
          <div class="event-controls">
            <span class="threshold-label">连续失败阈值:</span>
            <ElInputNumber
              v-model="config.events.fail_threshold"
              :min="1"
              :max="10"
              size="small"
              :disabled="ui.readOnly"
              style="width: 100px; margin-right: 16px;"
            />
            <ElSwitch
              v-model="config.events.circuit_break"
              :disabled="ui.readOnly"
              inline-prompt
              active-text="开启"
              inactive-text="关闭"
            />
          </div>
        </div>

        <ElDivider style="margin: 12px 0;" />

        <div class="event-item-row">
          <div class="event-meta">
            <div class="event-name">代理节点离线与高延迟警报</div>
            <div class="event-sub">当绑定的 VLESS / HTTP 代理节点无法建立 TLS 握手或持续连接超时，自动推送运维提示</div>
          </div>
          <div class="event-controls">
            <ElSwitch
              v-model="config.events.proxy_offline"
              :disabled="ui.readOnly"
              inline-prompt
              active-text="开启"
              inactive-text="关闭"
            />
          </div>
        </div>

        <ElDivider style="margin: 12px 0;" />

        <div class="event-item-row">
          <div class="event-meta">
            <div class="event-name">用户端激活码激活与绑定提醒</div>
            <div class="event-sub">当有新激活码首次在客户端激活并绑定设备时，推送设备型号、激活码前缀与有效时长信息</div>
          </div>
          <div class="event-controls">
            <ElSwitch
              v-model="config.events.code_activated"
              :disabled="ui.readOnly"
              inline-prompt
              active-text="开启"
              inactive-text="关闭"
            />
          </div>
        </div>

        <ElDivider style="margin: 12px 0;" />

        <div class="event-item-row">
          <div class="event-meta">
            <div class="event-name">每日系统运行简报推送</div>
            <div class="event-sub">每日固定时间分发全站活跃设备数、今日总请求量与缓存截留率综合大盘简报</div>
          </div>
          <div class="event-controls">
            <ElSwitch
              v-model="config.events.daily_report"
              :disabled="ui.readOnly"
              inline-prompt
              active-text="开启"
              inactive-text="关闭"
            />
          </div>
        </div>
      </div>
    </ElCard>

    <!-- 投递审计日志 -->
    <div class="section-title-bar" style="margin-top: 24px;">
      <div class="title-with-icon">
        <ElIcon :size="16"><Document /></ElIcon>
        <span>Telegram 消息推送审计历史</span>
      </div>
      <div class="title-actions">
        <ElButton
          size="small"
          type="danger"
          plain
          :icon="Delete"
          :loading="clearingLogs"
          :disabled="logs.length === 0 || ui.readOnly"
          @click="handleClearLogs"
        >
          清空历史日志
        </ElButton>
      </div>
    </div>

    <ElCard shadow="hover" class="logs-card">
      <ElTable
        :data="logs"
        style="width: 100%"
        empty-text="暂无 Telegram 推送历史记录，可通过上方「发送测试消息」验证"
      >
        <ElTableColumn prop="sent_at" label="触发时间" width="170">
          <template #default="{ row }">
            <span class="a-mono" style="font-size: 12.5px;">{{ row.sent_at }}</span>
          </template>
        </ElTableColumn>

        <ElTableColumn prop="event_type" label="事件类型" width="140">
          <template #default="{ row }">
            <span class="event-badge">{{ row.event_type }}</span>
          </template>
        </ElTableColumn>

        <ElTableColumn prop="status" label="投递结果" width="120">
          <template #default="{ row }">
            <ElTag
              size="small"
              :type="row.status === 'success' ? 'success' : 'danger'"
              effect="dark"
            >
              {{ row.status === 'success' ? '成功' : '失败' }}
            </ElTag>
          </template>
        </ElTableColumn>

        <ElTableColumn prop="status_code" label="响应代码" width="100">
          <template #default="{ row }">
            <span class="a-mono" :class="row.status_code >= 200 && row.status_code < 300 ? 'status-ok' : 'status-fail'">
              {{ row.status_code || '—' }}
            </span>
          </template>
        </ElTableColumn>

        <ElTableColumn prop="duration_ms" label="网络耗时" width="110">
          <template #default="{ row }">
            <span class="a-mono" style="font-size: 12px;">{{ row.duration_ms }}ms</span>
          </template>
        </ElTableColumn>

        <ElTableColumn prop="payload_summary" label="消息摘要 / 异常详情">
          <template #default="{ row }">
            <div class="log-summary" :title="row.error || row.payload_summary">
              <span v-if="row.error" class="log-error-text">{{ row.error }}</span>
              <span v-else>{{ row.payload_summary }}</span>
            </div>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElCard>
  </template>

    <!-- ---------------------------------------------------------- 弹出式参数配置卡片 -->
    <ElDialog
      v-model="configDialogVisible"
      title="Telegram 机器人参数配置"
      width="560px"
      append-to-body
      destroy-on-close
      class="bot-config-dialog"
    >
      <div class="dialog-body-wrap">
        <ElForm label-position="top" class="config-modal-form">
          <!-- 1. Bot Token -->
          <ElFormItem label="Telegram Bot Token">
            <div class="token-input-row">
              <ElInput
                v-model="editDraft.bot_token"
                placeholder="例如：123456789:AAFxz_SAMPLE_TOKEN"
                type="password"
                show-password
                :disabled="ui.readOnly"
              />
              <ElButton
                type="primary"
                plain
                :loading="verifying"
                :disabled="!editDraft.bot_token || ui.readOnly"
                @click="handleVerifyToken"
              >
                验证 Token
              </ElButton>
            </div>
            <div class="form-hint">
              向 Telegram 中的 <strong>@BotFather</strong> 发起 <code>/newbot</code> 即可免费获取 API Token
            </div>

            <!-- Token 校验回显卡片 -->
            <div v-if="verifyResult" class="verify-feedback-box" :class="verifyResult.ok ? 'verify-ok' : 'verify-fail'">
              <ElIcon :size="15">
                <CircleCheck v-if="verifyResult.ok" />
                <WarningFilled v-else />
              </ElIcon>
              <div v-if="verifyResult.ok" class="feedback-text">
                机器人验证成功：<strong>{{ verifyResult.first_name }}</strong>
                <span v-if="verifyResult.username"> (@{{ verifyResult.username }})</span>
              </div>
              <div v-else class="feedback-text">
                {{ verifyResult.error }}
              </div>
            </div>
          </ElFormItem>

          <!-- 2. Chat ID -->
          <ElFormItem label="目标 Chat ID / Group ID">
            <ElInput
              v-model="editDraft.chat_id"
              placeholder="例如：-1001234567890 或管理员个人 ID"
              :disabled="ui.readOnly"
            />
            <div class="form-hint">
              接收告警的管理员个人 ID 或 Telegram 群组的负数 ID（需先将机器人拉入群中并设为管理员）
            </div>
          </ElFormItem>

          <!-- 3. 网络代理 -->
          <ElFormItem label="网络连接代理 (Proxy URL，可选)">
            <ElInput
              v-model="editDraft.proxy_url"
              placeholder="例如：http://127.0.0.1:10809 或留空自动继承代理池"
              :disabled="ui.readOnly"
            />
            <div class="form-hint">
              在国内服务器环境下必须通过 HTTP / SOCKS5 代理方可访问 Telegram。留空将自动继承本地代理节点池。
            </div>
          </ElFormItem>

          <!-- 4. 启用开关 -->
          <ElFormItem label="启用状态">
            <div class="switch-line">
              <span class="switch-hint">开启后当系统事件发生时将自动向此 Telegram 发送告警</span>
              <ElSwitch
                v-model="editDraft.enabled"
                :disabled="ui.readOnly"
                inline-prompt
                active-text="开启"
                inactive-text="关闭"
              />
            </div>
          </ElFormItem>
        </ElForm>
      </div>

      <template #footer>
        <div class="dialog-footer-actions">
          <ElButton @click="configDialogVisible = false">取消</ElButton>
          <ElButton
            type="success"
            plain
            :loading="testing"
            :disabled="!editDraft.bot_token || !editDraft.chat_id"
            @click="handleTest"
          >
            即时发送测试
          </ElButton>
          <ElButton
            type="primary"
            :loading="saving"
            :disabled="ui.readOnly"
            @click="saveDialogConfig"
          >
            保存配置
          </ElButton>
        </div>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.webhooks-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.skeleton {
  padding: 24px;
  background: var(--a-card, #ffffff);
  border-radius: 12px;
  border: 1px solid var(--a-border, #e2e8f0);
}

/* 顶部指标卡片 */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-bottom: 24px;
}

@media (max-width: 900px) {
  .kpi-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 520px) {
  .kpi-grid {
    grid-template-columns: 1fr;
  }
}

.kpi-card {
  background: var(--a-card, #ffffff);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: 12px;
  padding: 16px 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.kpi-title {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--a-text-2, #64748b);
  margin-bottom: 6px;
}

.kpi-main {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.kpi-status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-active {
  background: #16a34a;
  box-shadow: 0 0 0 3px rgba(22, 163, 74, 0.2);
}

.dot-inactive {
  background: #94a3b8;
}

.kpi-num-text {
  font-size: 18px;
  font-weight: 700;
  color: var(--a-text, #0f172a);
}

.kpi-mono-val {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 14px;
  font-weight: 700;
  color: var(--a-text, #0f172a);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.kpi-num {
  font-size: 26px;
  font-weight: 800;
  color: var(--a-text, #0f172a);
  font-family: 'JetBrains Mono', Consolas, monospace;
}

.kpi-unit {
  font-size: 13px;
  color: var(--a-text-3, #94a3b8);
}

.kpi-desc {
  font-size: 12px;
  color: var(--a-text-3, #94a3b8);
}

/* 区域分块标题 */
.section-title-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 8px;
}

.title-with-icon {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 700;
  color: var(--a-text, #0f172a);
}

/* Telegram 机器人主体大卡片 */
.bot-card-container {
  margin-bottom: 24px;
}

.bot-hero-card {
  border-radius: 12px;
  border: 1px solid var(--a-border, #e2e8f0);
  background: var(--a-card, #ffffff);
  cursor: pointer;
  transition: all 0.2s ease;
}

.bot-hero-card:hover {
  border-color: #38bdf8;
  box-shadow: 0 4px 14px rgba(56, 189, 248, 0.12);
}

.bot-card-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;
}

.bot-brand-col {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
  min-width: 280px;
}

.bot-avatar-box {
  width: 52px;
  height: 52px;
  border-radius: 12px;
  background: linear-gradient(135deg, #0088cc 0%, #229ed9 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  flex-shrink: 0;
  box-shadow: 0 4px 10px rgba(34, 158, 217, 0.25);
}

.bot-meta-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.bot-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.bot-name {
  font-size: 16px;
  font-weight: 700;
  color: var(--a-text, #0f172a);
}

.bot-uname-tag {
  font-family: 'JetBrains Mono', Consolas, monospace;
}

.bot-sub-row {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.bot-param-pill {
  font-size: 12.5px;
  color: var(--a-text-2, #64748b);
  display: flex;
  align-items: center;
  gap: 6px;
}

.bot-param-pill code {
  background: var(--a-bg-subtle, #f1f5f9);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 12px;
  color: var(--a-text, #0f172a);
}

.bot-actions-col {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.switch-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-right: 8px;
}

.switch-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--a-text-2, #64748b);
}

.bot-card-banner {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed var(--a-border, #e2e8f0);
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  color: var(--a-text-2, #64748b);
}

.banner-text {
  font-weight: 500;
}

.banner-err {
  color: #dc2626;
  font-family: 'JetBrains Mono', Consolas, monospace;
}

/* 订阅事件设置 */
.events-card {
  border-radius: 12px;
  border: 1px solid var(--a-border, #e2e8f0);
}

.event-rows-list {
  padding: 4px 0;
}

.event-item-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.event-meta {
  flex: 1;
  min-width: 240px;
}

.event-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--a-text, #0f172a);
  margin-bottom: 4px;
}

.event-sub {
  font-size: 12.5px;
  color: var(--a-text-2, #64748b);
  line-height: 1.4;
}

.event-controls {
  display: flex;
  align-items: center;
}

.threshold-label {
  font-size: 12.5px;
  color: var(--a-text-2, #64748b);
  margin-right: 8px;
}

/* 历史日志 */
.logs-card {
  border-radius: 12px;
  border: 1px solid var(--a-border, #e2e8f0);
}

.event-badge {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 12px;
  color: var(--a-text-2, #475569);
  background: var(--a-bg-subtle, #f1f5f9);
  padding: 2px 6px;
  border-radius: 4px;
}

.status-ok {
  color: #166534;
  font-weight: 700;
}

.status-fail {
  color: #dc2626;
  font-weight: 700;
}

.log-summary {
  font-size: 12.5px;
  color: var(--a-text-2, #475569);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 480px;
}

.log-error-text {
  color: #dc2626;
  font-weight: 600;
}

/* 弹窗样式 */
:deep(.bot-config-dialog) {
  border-radius: 14px;
}

:deep(.bot-config-dialog .el-dialog__header) {
  padding: 20px 24px 12px;
  margin-right: 0;
  border-bottom: 1px solid var(--a-border, #e2e8f0);
}

:deep(.bot-config-dialog .el-dialog__title) {
  font-size: 17px;
  font-weight: 800;
  color: var(--a-text, #0f172a);
}

:deep(.bot-config-dialog .el-dialog__body) {
  padding: 20px 24px;
}

:deep(.bot-config-dialog .el-dialog__footer) {
  padding: 14px 24px 20px;
  border-top: 1px solid var(--a-border, #e2e8f0);
}

.dialog-body-wrap {
  display: flex;
  flex-direction: column;
}

:deep(.config-modal-form .el-form-item__label) {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--a-text, #0f172a) !important;
  margin-bottom: 4px;
}

.token-input-row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}

.form-hint {
  font-size: 12px;
  color: var(--a-text-2, #64748b);
  margin-top: 4px;
  line-height: 1.4;
}

.form-hint code {
  background: var(--a-bg-subtle, #f1f5f9);
  padding: 1px 4px;
  border-radius: 3px;
  color: #0284c7;
}

.verify-feedback-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  margin-top: 8px;
  font-size: 12.5px;
}

.verify-ok {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  color: #166534;
}

.verify-fail {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
}

.feedback-text {
  flex: 1;
}

.switch-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 8px 12px;
  background: var(--a-bg-subtle, #f8fafc);
  border-radius: 8px;
  border: 1px solid var(--a-border, #e2e8f0);
}

.switch-hint {
  font-size: 12.5px;
  color: var(--a-text-2, #64748b);
}

.dialog-footer-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}
</style>
