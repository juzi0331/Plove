<script setup lang="ts">
import {
  ElButton,
  ElCard,
  ElIcon,
  ElSwitch,
  ElTag,
} from 'element-plus'
import {
  CircleCheck,
  CircleClose,
  Promotion,
  Setting,
} from '@element-plus/icons-vue'
import type { WebhookConfigPayload, WebhookDeliveryLogItem } from '@/api/types'

const props = defineProps<{
  telegram: Required<WebhookConfigPayload>['telegram']
  lastLog: WebhookDeliveryLogItem | null
  testing: boolean
  readOnly: boolean
}>()

const emit = defineEmits<{
  openConfig: []
  save: []
  test: []
}>()
</script>

<template>
  <div class="bot-card-container">
    <ElCard shadow="hover" class="bot-hero-card" @click="emit('openConfig')">
      <div class="bot-card-inner">
        <div class="bot-brand-col">
          <div class="bot-avatar-box">
            <ElIcon :size="28" class="bot-plane-icon"><Promotion /></ElIcon>
          </div>
          <div class="bot-meta-info">
            <div class="bot-title-row">
              <span class="bot-name">
                {{ props.telegram.bot_name || 'Telegram 告警机器人' }}
              </span>
              <ElTag
                v-if="props.telegram.bot_username"
                size="small"
                type="primary"
                effect="plain"
                class="bot-uname-tag"
              >
                @{{ props.telegram.bot_username }}
              </ElTag>
              <ElTag
                size="small"
                :type="props.telegram.enabled ? 'success' : 'info'"
                effect="dark"
              >
                {{ props.telegram.enabled ? '运行中' : '未开启' }}
              </ElTag>
            </div>
            <div class="bot-sub-row">
              <span class="bot-param-pill">
                <strong>目标 Chat ID:</strong>
                <code>{{ props.telegram.chat_id || '未配置' }}</code>
              </span>
              <span class="bot-param-pill">
                <strong>网络代理:</strong>
                <code>{{ props.telegram.proxy_url || '继承代理池 (127.0.0.1:10809)' }}</code>
              </span>
            </div>
          </div>
        </div>

        <div class="bot-actions-col" @click.stop>
          <div class="switch-wrap">
            <span class="switch-label">启用推送</span>
            <ElSwitch
              v-model="props.telegram.enabled"
              :disabled="props.readOnly"
              inline-prompt
              active-text="开启"
              inactive-text="关闭"
              @change="emit('save')"
            />
          </div>
          <ElButton
            type="primary"
            :icon="Setting"
            plain
            @click="emit('openConfig')"
          >
            配置参数
          </ElButton>
          <ElButton
            type="success"
            :icon="Promotion"
            plain
            :loading="props.testing"
            :disabled="!props.telegram.bot_token || !props.telegram.chat_id"
            @click="emit('test')"
          >
            发送测试消息
          </ElButton>
        </div>
      </div>

      <!-- 连通性提示条 -->
      <div v-if="props.lastLog" class="bot-card-banner">
        <ElIcon :size="14" :color="props.lastLog.status === 'success' ? '#166534' : '#dc2626'">
          <CircleCheck v-if="props.lastLog.status === 'success'" />
          <CircleClose v-else />
        </ElIcon>
        <span class="banner-text">
          最近投递状态：{{ props.lastLog.status === 'success' ? '正常投递成功' : '投递失败' }}
          （耗时 {{ props.lastLog.duration_ms }}ms，{{ props.lastLog.sent_at }}）
        </span>
        <span v-if="props.lastLog.error" class="banner-err">{{ props.lastLog.error }}</span>
      </div>
    </ElCard>
  </div>
</template>
