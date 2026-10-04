<script setup lang="ts">
import {
  ElButton,
  ElCard,
  ElIcon,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus'
import { Delete, Document } from '@element-plus/icons-vue'
import type { WebhookDeliveryLogItem } from '@/api/types'

const props = defineProps<{
  logs: WebhookDeliveryLogItem[]
  clearing: boolean
  readOnly: boolean
}>()

const emit = defineEmits<{
  clear: []
}>()
</script>

<template>
  <div>
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
          :loading="props.clearing"
          :disabled="props.logs.length === 0 || props.readOnly"
          @click="emit('clear')"
        >
          清空历史日志
        </ElButton>
      </div>
    </div>

    <ElCard shadow="hover" class="logs-card">
      <ElTable
        :data="props.logs"
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
            <span
              class="a-mono"
              :class="row.status_code >= 200 && row.status_code < 300 ? 'status-ok' : 'status-fail'"
            >
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
  </div>
</template>
