<script setup lang="ts">
import { ref } from 'vue'
import {
  ElButton,
  ElDialog,
  ElDrawer,
  ElLoading,
  ElProgress,
  ElTag,
} from 'element-plus'
import { Refresh, VideoPlay } from '@element-plus/icons-vue'
import type { CodeListItem, DeviceItem, DevicePlaybackHistoryItem } from '@/api/types'
import { getDeviceHistory } from '@/admin/api'
import EmptyState from '@/admin/components/EmptyState.vue'
import TimeAgo from '@/admin/components/TimeAgo.vue'
import { humanRemaining, type TagType } from '@/admin/format'
import { ui } from '@/admin/ui'
import { formatPosterUrl } from '@/utils/format'

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

const historyDrawerVisible = ref(false)
const selectedDevice = ref<DeviceItem | null>(null)
const historyList = ref<DevicePlaybackHistoryItem[]>([])
const loadingHistory = ref(false)

async function openDeviceHistory(dev: DeviceItem): Promise<void> {
  selectedDevice.value = dev
  historyDrawerVisible.value = true
  loadingHistory.value = true
  try {
    const res = await getDeviceHistory(dev.id)
    historyList.value = res.records || []
  } catch {
    historyList.value = []
  } finally {
    loadingHistory.value = false
  }
}

const RECENT_MS = 2 * 60 * 1000
function getDeviceOnlineState(device: DeviceItem): { label: string; tag: TagType; isPlaying?: boolean } {
  if (device.is_playing && device.current_vod_title) {
    return { label: `正在播放：${device.current_vod_title}`, tag: 'success', isPlaying: true }
  }
  const seen = new Date(device.last_seen_at).getTime()
  if (!Number.isNaN(seen) && Date.now() - seen < RECENT_MS) {
    return { label: '在线空闲', tag: 'primary' }
  }
  if (device.is_active) {
    return { label: '空闲中', tag: 'info' }
  }
  return { label: '离线', tag: 'info' }
}

function handlePosterError(event: Event) {
  const target = event.target as HTMLImageElement
  if (target) {
    target.src = 'https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=500&q=80'
  }
}
</script>

<template>
  <ElDialog
    :model-value="props.modelValue"
    :title="`绑定设备管控 · ${props.currentDeviceCode?.code || ''}`"
    width="740px"
    align-center
    append-to-body
    destroy-on-close
    class="submodal-dialog"
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
              <ElTag
                v-if="getDeviceOnlineState(dev).isPlaying"
                type="success"
                size="small"
                effect="dark"
                class="watching-tag"
              >
                <span class="pulse-dot">●</span> {{ getDeviceOnlineState(dev).label }}
              </ElTag>
              <ElTag
                v-else
                :type="getDeviceOnlineState(dev).tag"
                size="small"
                effect="plain"
              >
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
              type="primary"
              plain
              :icon="VideoPlay"
              @click="openDeviceHistory(dev)"
            >
              观看记录
            </ElButton>
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
              解绑
            </ElButton>
          </div>
        </div>
      </div>
    </div>

    <!-- 观看记录足迹抽屉 -->
    <ElDrawer
      v-model="historyDrawerVisible"
      :title="`${selectedDevice?.name || '设备'} · 观看记录 (${historyList.length})`"
      size="460px"
      destroy-on-close
      append-to-body
    >
      <div v-loading="loadingHistory" class="history-drawer-body">
        <div v-if="!historyList.length" class="history-empty">
          <EmptyState
            title="暂无播放足迹"
            hint="用户在此设备上播放影片时，系统将自动记录并实时更新进度"
          />
        </div>
        <div v-else class="history-items-list">
          <div v-for="item in historyList" :key="item.id" class="history-item-card">
            <img
              :src="formatPosterUrl(item.vod_pic, item.site_key) || 'https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=500&q=80'"
              class="history-item-poster"
              loading="lazy"
              @error="handlePosterError"
            />
            <div class="history-item-detail">
              <div class="history-item-title-row">
                <span class="history-item-title" :title="item.vod_name">{{ item.vod_name }}</span>
                <ElTag v-if="item.is_playing" type="success" size="small" class="history-playing-tag">
                  <span class="pulse-dot">●</span> 正在播放
                </ElTag>
              </div>

              <div class="history-item-sub">
                <span class="history-ep-badge">{{ item.ep_name || '正片' }}</span>
                <span v-if="item.site_key" class="history-site-badge">{{ item.site_key }}</span>
              </div>

              <div class="history-item-progress-section">
                <ElProgress
                  :percentage="item.progress_percent || 0"
                  :stroke-width="6"
                  :show-text="false"
                  :status="item.progress_percent === 100 ? 'success' : undefined"
                />
                <div class="history-item-meta">
                  <span class="history-percent-text">已看 {{ item.progress_percent || 0 }}%</span>
                  <span class="history-time-text"><TimeAgo :value="item.updated_at" /></span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </ElDrawer>

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

<style scoped>
.watching-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.pulse-dot {
  font-size: 10px;
  animation: pulse-glow 1.5s infinite ease-in-out;
}
@keyframes pulse-glow {
  0% { opacity: 0.3; }
  50% { opacity: 1; }
  100% { opacity: 0.3; }
}

.history-drawer-body {
  padding: 8px 4px;
  min-height: 200px;
}
.history-empty {
  padding: 40px 0;
}
.history-items-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.history-item-card {
  display: flex;
  gap: 14px;
  padding: 12px;
  background: var(--el-fill-color-light, #f8fafc);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: 8px;
  transition: all 0.2s ease;
}
.history-item-card:hover {
  border-color: #0284c7;
  background: var(--a-card, #ffffff);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}
.history-item-poster {
  width: 72px;
  height: 98px;
  border-radius: 6px;
  object-fit: cover;
  background: #1e293b;
  flex-shrink: 0;
}
.history-item-detail {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  flex: 1;
  min-width: 0;
}
.history-item-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.history-item-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--a-text, #1e293b);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.history-playing-tag {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.history-item-sub {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 4px 0;
}
.history-ep-badge {
  font-size: 12px;
  color: var(--a-primary, #0284c7);
  background: rgba(2, 132, 199, 0.1);
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 500;
}
.history-site-badge {
  font-size: 11px;
  color: var(--a-text-2, #64748b);
  background: rgba(100, 116, 139, 0.1);
  padding: 1px 5px;
  border-radius: 4px;
}
.history-item-progress-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.history-item-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: var(--a-text-2, #64748b);
}
</style>
