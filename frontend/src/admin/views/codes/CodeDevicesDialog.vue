<script setup lang="ts">
import {
  ElButton,
  ElDialog,
  ElLoading,
  ElTag,
} from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import type { CodeListItem, DeviceItem } from '@/api/types'
import EmptyState from '@/admin/components/EmptyState.vue'
import TimeAgo from '@/admin/components/TimeAgo.vue'
import { humanRemaining, type TagType } from '@/admin/format'
import { ui } from '@/admin/ui'

const vLoading = ElLoading.directive

const props = defineProps<{
  modelValue: boolean
  currentDeviceCode: CodeListItem | null
  devicesList: DeviceItem[]
  loadingDevices: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'refresh'): void
  (e: 'kickDevice', device: DeviceItem): void
  (e: 'unbindDevice', device: DeviceItem): void
}>()

const RECENT_MS = 5 * 60 * 1000
function getDeviceOnlineState(device: DeviceItem): { label: string; tag: TagType } {
  if (device.is_active) return { label: '活跃播放中', tag: 'success' }
  const seen = new Date(device.last_seen_at).getTime()
  if (!Number.isNaN(seen) && Date.now() - seen < RECENT_MS) return { label: '最近活跃', tag: 'info' }
  return { label: '离线', tag: 'info' }
}
</script>

<template>
  <ElDialog
    :model-value="props.modelValue"
    :title="`绑定设备管控 · ${props.currentDeviceCode?.code || ''}`"
    width="720px"
    destroy-on-close
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div v-loading="props.loadingDevices" class="device-modal-content">
      <!-- 激活码摘要条 -->
      <div class="device-code-summary">
        <div class="summary-item">
          <span class="summary-label">激活码</span>
          <strong class="code-mono">{{ props.currentDeviceCode?.code }}</strong>
        </div>
        <div class="summary-item">
          <span class="summary-label">设备占用</span>
          <ElTag
            :type="(props.devicesList.length || 0) >= (props.currentDeviceCode?.max_devices || 1) ? 'danger' : 'info'"
            size="small"
          >
            {{ props.devicesList.length }} / {{ props.currentDeviceCode?.max_devices || 1 }} 台
          </ElTag>
        </div>
        <div class="summary-item">
          <span class="summary-label">授权时长</span>
          <span>{{ props.currentDeviceCode?.duration_hours }} 小时</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">剩余时间</span>
          <span>{{ humanRemaining(props.currentDeviceCode?.remaining_seconds ?? 0) }}</span>
        </div>
      </div>

      <div v-if="props.devicesList.length === 0" class="device-empty-box">
        <EmptyState
          title="该激活码暂无任何绑定设备"
          hint="用户在客户端输入此激活码激活成功后，设备信息将实时在此呈现（设备令牌前 6 位脱敏展示）"
        />
      </div>

      <div v-else class="devices-list-cards">
        <div v-for="dev in props.devicesList" :key="dev.id" class="device-card-item">
          <div class="device-card-main">
            <div class="device-header-row">
              <span class="device-name">{{ dev.name || '未命名设备' }}</span>
              <ElTag :type="getDeviceOnlineState(dev).tag" size="small" effect="dark">
                {{ getDeviceOnlineState(dev).label }}
              </ElTag>
            </div>

            <div class="device-meta-row">
              <span class="device-token">
                凭证令牌：<code>{{ dev.token_prefix }}******</code>
              </span>
              <span class="device-seen">
                最近活跃：<TimeAgo :value="dev.last_seen_at" />
              </span>
            </div>
          </div>

          <div class="device-card-actions">
            <ElButton
              size="small"
              type="warning"
              plain
              :disabled="ui.readOnly"
              @click="emit('kickDevice', dev)"
            >
              踢下线
            </ElButton>
            <ElButton
              size="small"
              type="danger"
              plain
              :disabled="ui.readOnly"
              @click="emit('unbindDevice', dev)"
            >
              解绑释放名额
            </ElButton>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <ElButton
          size="small"
          :icon="Refresh"
          :loading="props.loadingDevices"
          @click="emit('refresh')"
        >
          刷新设备
        </ElButton>
        <ElButton size="small" type="primary" @click="emit('update:modelValue', false)">
          关闭
        </ElButton>
      </div>
    </template>
  </ElDialog>
</template>
