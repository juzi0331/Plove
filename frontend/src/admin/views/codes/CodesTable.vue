<script setup lang="ts">
import { computed } from 'vue'
import {
  ElButton,
  ElCard,
  ElIcon,
  ElPagination,
  ElSkeleton,
  ElTable,
  ElTableColumn,
  ElTag,
  ElTooltip,
} from 'element-plus'
import {
  CopyDocument,
  Monitor,
} from '@element-plus/icons-vue'
import type { CodeListItem, CodeListPayload } from '@/api/types'
import EmptyState from '@/admin/components/EmptyState.vue'
import TimeAgo from '@/admin/components/TimeAgo.vue'
import { codeState, formatDateTime, humanRemaining } from '@/admin/format'
import { ui } from '@/admin/ui'

const props = defineProps<{
  data: CodeListPayload | null
  loading: boolean
  isEmpty: boolean
  page: number
  pageSize: number
  rowClass: (params: { row: CodeListItem }) => string
  widthOf: (key: string, fallback: number) => number
}>()

const codesList = computed<CodeListItem[]>(() => props.data?.codes ?? [])

const emit = defineEmits<{
  headerDragend: [newWidth: number, oldWidth: number, column: any]
  copyText: [text: string, success: string]
  openDevicesCard: [row: CodeListItem]
  openExtend: [row: CodeListItem]
  toggleDisabled: [row: CodeListItem]
  deleteCode: [row: CodeListItem]
  pageChange: [page: number]
  pageSizeChange: [size: number]
  openIssue: []
}>()

function onCopy(code: string): void {
  emit('copyText', code, `已复制激活码: ${code}`)
}

function onOpenDevices(row: any): void {
  emit('openDevicesCard', row as CodeListItem)
}

function onExtend(row: any): void {
  emit('openExtend', row as CodeListItem)
}

function onToggleDisabled(row: any): void {
  emit('toggleDisabled', row as CodeListItem)
}

function onDelete(row: any): void {
  emit('deleteCode', row as CodeListItem)
}

function getCodeState(row: any) {
  return codeState(row as CodeListItem)
}
</script>

<template>
  <ElCard shadow="hover" class="module-card table-card">
    <div v-if="props.loading && !props.data" class="skeleton-pad">
      <ElSkeleton :rows="8" animated />
    </div>

    <EmptyState
      v-else-if="props.isEmpty"
      title="没有找到激活码"
      hint="点击上方「发行新码」按钮生成一批激活码"
      action-text="发行新激活码"
      @action="emit('openIssue')"
    />

    <template v-else>
      <ElTable
        :data="codesList"
        row-key="id"
        stripe
        class="codes-table"
        :row-class-name="props.rowClass"
        @header-dragend="(newWidth: number, oldWidth: number, column: any) => emit('headerDragend', newWidth, oldWidth, column)"
      >
        <ElTableColumn label="激活码" :width="props.widthOf('code', 190)">
          <template #default="{ row }">
            <div class="code-cell">
              <strong class="code-mono">{{ row.code }}</strong>
              <ElButton
                link
                size="small"
                :icon="CopyDocument"
                title="点击复制激活码"
                @click="onCopy(row.code)"
              />
            </div>
          </template>
        </ElTableColumn>

        <ElTableColumn label="状态" :width="props.widthOf('status', 115)">
          <template #default="{ row }">
            <ElTooltip
              v-if="getCodeState(row).isPlaying && row.current_playback"
              :content="`正在观看: ${row.current_playback}`"
              placement="top"
            >
              <ElTag type="success" size="small" class="status-tag-watching">
                <span class="pulse-dot">●</span> 使用中
              </ElTag>
            </ElTooltip>
            <ElTag v-else :type="getCodeState(row).tag" size="small">
              {{ getCodeState(row).label }}
            </ElTag>
          </template>
        </ElTableColumn>

        <ElTableColumn label="设备占用" :width="props.widthOf('device', 130)">
          <template #default="{ row }">
            <div
              class="device-cell"
              title="点击查看并管控此激活码绑定的设备"
              @click="onOpenDevices(row)"
            >
              <ElTag
                size="small"
                :type="(row.device_count || 0) >= (row.max_devices || 1) ? 'danger' : 'info'"
                class="device-badge-clickable"
              >
                <ElIcon style="margin-right: 2px;"><Monitor /></ElIcon>
                {{ row.device_count || 0 }} / {{ row.max_devices || 1 }} 台
              </ElTag>
              <span v-if="row.active_device_name" class="device-name-hint" :title="row.active_device_name">
                {{ row.active_device_name }}
              </span>
            </div>
          </template>
        </ElTableColumn>

        <ElTableColumn label="时长" :width="props.widthOf('duration', 95)">
          <template #default="{ row }">
            <span>{{ row.duration_hours }} 小时</span>
          </template>
        </ElTableColumn>

        <ElTableColumn label="剩余时间" :width="props.widthOf('remaining', 130)">
          <template #default="{ row }">
            <span v-if="row.activated_at" :class="{ 'a-warn-text': (row.remaining_seconds ?? 0) < 86400 }">
              {{ humanRemaining(row.remaining_seconds ?? 0) }}
            </span>
            <span v-else class="a-muted">未激活</span>
          </template>
        </ElTableColumn>

        <ElTableColumn label="首次激活" :width="props.widthOf('activated', 140)">
          <template #default="{ row }">
            <TimeAgo v-if="row.activated_at" :value="row.activated_at" />
            <span v-else class="a-muted">—</span>
          </template>
        </ElTableColumn>

        <ElTableColumn label="到期时间" :width="props.widthOf('expires', 170)">
          <template #default="{ row }">
            <span v-if="row.expires_at">{{ formatDateTime(row.expires_at) }}</span>
            <span v-else class="a-muted">—</span>
          </template>
        </ElTableColumn>

        <ElTableColumn label="备注" :min-width="props.widthOf('note', 140)">
          <template #default="{ row }">
            <span>{{ row.note || '—' }}</span>
          </template>
        </ElTableColumn>

        <ElTableColumn label="操作" fixed="right" width="220">
          <template #default="{ row }">
            <div class="action-btn-group">
              <ElButton
                link
                size="small"
                type="primary"
                @click="onOpenDevices(row)"
              >
                设备({{ row.device_count || 0 }})
              </ElButton>

              <ElButton
                link
                size="small"
                type="primary"
                :disabled="ui.readOnly"
                @click="onExtend(row)"
              >
                延长
              </ElButton>

              <ElButton
                link
                size="small"
                :type="row.disabled_at ? 'success' : 'warning'"
                :disabled="ui.readOnly"
                @click="onToggleDisabled(row)"
              >
                {{ row.disabled_at ? '解封' : '停用' }}
              </ElButton>

              <ElButton
                link
                size="small"
                type="danger"
                :disabled="ui.readOnly"
                @click="onDelete(row)"
              >
                删除
              </ElButton>
            </div>
          </template>
        </ElTableColumn>
      </ElTable>

      <div class="pagination-bar">
        <ElPagination
          background
          layout="total, sizes, prev, pager, next"
          :current-page="props.page"
          :page-size="props.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="props.data?.total ?? 0"
          @current-change="emit('pageChange', $event)"
          @size-change="emit('pageSizeChange', $event)"
        />
      </div>
    </template>
  </ElCard>
</template>

<style scoped>
.code-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}
.code-mono {
  font-family: monospace;
  font-size: 13px;
  letter-spacing: 0.5px;
}
.device-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  cursor: pointer;
}
.device-badge-clickable {
  cursor: pointer;
  width: fit-content;
}
.device-name-hint {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.status-tag-watching {
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.pulse-dot {
  color: #67c23a;
  font-size: 10px;
  animation: pulse-glow 1.5s infinite ease-in-out;
}
@keyframes pulse-glow {
  0% { opacity: 0.3; transform: scale(0.9); }
  50% { opacity: 1; transform: scale(1.1); }
  100% { opacity: 0.3; transform: scale(0.9); }
}
.pagination-bar {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
