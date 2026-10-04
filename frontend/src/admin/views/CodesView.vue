<script setup lang="ts">
/**
 * 激活码管理（卡片式模块架构）：
 * 1. 顶部激活码总控与批量发码卡片；
 * 2. 授权状态指标卡片（在用、未激活、到期、停用分布）；
 * 3. 激活码全功能卡片列表（包含行内一键复制、状态徽章、延长、停用/解封、彻底删除）；
 * 4. 绑定设备卡片式即时抽屉/弹窗（无需跳转新页面，直接在当前页面查看设备、踢下线或解绑释放名额）。
 */
import {
  ElAlert,
  ElButton,
  ElCard,
  ElCol,
  ElDialog,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
  ElInputNumber,
  ElLoading,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElPagination,
  ElRow,
  ElSelect,
  ElSkeleton,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus'
import {
  CopyDocument,
  Monitor,
  Plus,
  Refresh,
  Search,
  Tickets,
} from '@element-plus/icons-vue'
import { computed, onMounted, ref } from 'vue'

const vLoading = ElLoading.directive

import { describeError } from '@/api/http'
import type { CodeListItem, CodeListPayload, DeviceItem, IssueCodesRequest } from '@/api/types'

import * as api from '../api'
import EmptyState from '../components/EmptyState.vue'
import ErrorState from '../components/ErrorState.vue'
import PageHeader from '../components/PageHeader.vue'
import TimeAgo from '../components/TimeAgo.vue'
import { codeState, formatDateTime, humanRemaining, type TagType } from '../format'
import { loadIssueMemory, saveIssueMemory, ui } from '../ui'

const data = ref<CodeListPayload | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

const search = ref('')
const page = ref(1)
const pageSize = ref(20)

// ------------------------------------------------------------------ 列表加载
async function load(): Promise<void> {
  loading.value = true
  try {
    data.value = await api.listCodes({
      query: search.value.trim() || undefined,
      page: page.value,
      pageSize: pageSize.value,
    })
    error.value = null
  } catch (err) {
    error.value = describeError(err)
  } finally {
    loading.value = false
  }
}

onMounted(load)

function onSearch(): void {
  page.value = 1
  void load()
}

function onPageChange(next: number): void {
  page.value = next
  void load()
}

function onPageSizeChange(next: number): void {
  pageSize.value = next
  page.value = 1
  void load()
}

const isEmpty = computed(() => !loading.value && !error.value && (data.value?.codes?.length ?? 0) === 0)

// 统计分布
const stats = computed(() => {
  const codes = data.value?.codes || []
  let active = 0
  let unactivated = 0
  let expired = 0
  let disabled = 0

  for (const c of codes) {
    if (c.disabled_at) {
      disabled++
    } else if (!c.activated_at) {
      unactivated++
    } else if ((c.remaining_seconds ?? 0) <= 0) {
      expired++
    } else {
      active++
    }
  }

  return { active, unactivated, expired, disabled }
})

// ------------------------------------------------------------------ 行状态与列宽
function rowClass({ row }: { row: CodeListItem }): string {
  if (row.disabled_at) return 'a-row--disabled'
  if (!row.activated_at) return ''
  const remain = row.remaining_seconds ?? 0
  if (remain <= 0) return 'a-row--expired'
  if (remain < 86400) return 'a-row--warn'
  return ''
}

const COLS_KEY = 'plove.admin.cols.codes'
function readWidths(): Record<string, number> {
  try {
    const raw = localStorage.getItem(COLS_KEY)
    return raw ? (JSON.parse(raw) as Record<string, number>) : {}
  } catch {
    return {}
  }
}

const widths = ref<Record<string, number>>(readWidths())
function widthOf(key: string, fallback: number): number {
  return widths.value[key] ?? fallback
}

function onHeaderDragend(newWidth: number, _oldWidth: number, column: { property?: string; label?: string }): void {
  const key = column.property || column.label || ''
  if (!key) return
  widths.value = { ...widths.value, [key]: Math.round(newWidth) }
  try {
    localStorage.setItem(COLS_KEY, JSON.stringify(widths.value))
  } catch {
    /* 忽略隐私模式异常 */
  }
}

// ------------------------------------------------------------------ 复制
async function copyText(text: string, success: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success(success)
  } catch {
    ElMessage.warning('浏览器限制自动复制，请手动选中复制')
  }
}

// ------------------------------------------------------------------ 发码
const PRESETS = [
  { label: '7 天', unit: 'days' as const, amount: 7 },
  { label: '30 天', unit: 'days' as const, amount: 30 },
  { label: '90 天', unit: 'days' as const, amount: 90 },
  { label: '365 天', unit: 'days' as const, amount: 365 },
]

const memory = loadIssueMemory()
const issueOpen = ref(false)
const issueBusy = ref(false)
const issueForm = ref<{ unit: 'days' | 'hours'; amount: number; count: number; max_devices: number; note: string }>({
  unit: memory.unit,
  amount: memory.amount,
  count: memory.count,
  max_devices: 1,
  note: '',
})
const issuedCodes = ref<string[]>([])

const activePreset = computed(
  () => PRESETS.find((preset) => preset.unit === issueForm.value.unit && preset.amount === issueForm.value.amount)?.label ?? null,
)

function applyPreset(preset: (typeof PRESETS)[number]): void {
  issueForm.value.unit = preset.unit
  issueForm.value.amount = preset.amount
}

async function submitIssue(): Promise<void> {
  issueBusy.value = true
  try {
    const payload: IssueCodesRequest = {
      count: issueForm.value.count,
      max_devices: issueForm.value.max_devices || 1,
      note: issueForm.value.note,
      ...(issueForm.value.unit === 'days'
        ? { days: issueForm.value.amount }
        : { hours: issueForm.value.amount }),
    }
    const result = await api.issueCodes(payload)
    issuedCodes.value = result.codes ?? []
    saveIssueMemory({ unit: issueForm.value.unit, amount: issueForm.value.amount, count: issueForm.value.count })
    issueOpen.value = false
    ElMessage.success(`已成功发出 ${issuedCodes.value.length} 个激活码`)
    await load()
  } catch (err) {
    ElMessage.error(describeError(err))
  } finally {
    issueBusy.value = false
  }
}

// ------------------------------------------------------------------ 停用 / 解封 / 延长
async function toggleDisabled(row: CodeListItem): Promise<void> {
  const disabling = !row.disabled_at
  if (disabling) {
    try {
      await ElMessageBox.confirm(
        `停用激活码 ${row.code} 后，当前正在使用的设备将立即被阻断无法继续观看。确定停用吗？`,
        '停用激活码',
        { type: 'warning', confirmButtonText: '确定停用', cancelButtonText: '取消' },
      )
    } catch {
      return
    }
  }

  try {
    const result = disabling ? await api.disableCode(row.id) : await api.enableCode(row.id)
    ElMessage.success(result.message)
    await load()
  } catch (err) {
    ElMessage.error(describeError(err))
  }
}

const extendOpen = ref(false)
const extendBusy = ref(false)
const extendHours = ref(24)
const extendTarget = ref<{ id: number; code: string; started: boolean } | null>(null)

function openExtend(row: CodeListItem): void {
  extendTarget.value = { id: row.id, code: row.code, started: Boolean(row.activated_at) }
  extendHours.value = 24
  extendOpen.value = true
}

async function submitExtend(): Promise<void> {
  if (!extendTarget.value) return
  extendBusy.value = true
  try {
    const result = await api.extendCode(extendTarget.value.id, extendHours.value)
    ElMessage.success(result.message)
    extendOpen.value = false
    await load()
  } catch (err) {
    ElMessage.error(describeError(err))
  } finally {
    extendBusy.value = false
  }
}

async function handleDeleteCode(row: CodeListItem): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确定彻底删除激活码 ${row.code} 吗？此操作不可逆，并将同步解除该码绑定的全部历史设备记录。`,
      '彻底删除激活码',
      { type: 'error', confirmButtonText: '彻底删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }

  try {
    const res = await api.deleteCode(row.id)
    ElMessage.success(res.message)
    await load()
  } catch (err) {
    ElMessage.error(describeError(err))
  }
}

async function handleCleanupExpired(): Promise<void> {
  try {
    const { value: daysStr } = await ElMessageBox.prompt(
      '请输入清理多少天前到期的失效激活码（默认 7 天前，输入 0 则清理当前所有已过期码）：',
      '批量清理失效激活码',
      {
        confirmButtonText: '开始清理',
        cancelButtonText: '取消',
        inputValue: '7',
        inputPattern: /^\d+$/,
        inputErrorMessage: '请输入大于等于 0 的整数天数',
      },
    )
    const days = parseInt(daysStr, 10)
    const res = await api.cleanupExpiredCodes(days)
    ElMessage.success(res.message)
    await load()
  } catch {
    // 用户取消
  }
}

// ------------------------------------------------------------------ 卡片式绑定设备即时管理（无需跳转页面）
const deviceDialogVisible = ref(false)
const currentDeviceCode = ref<CodeListItem | null>(null)
const devicesList = ref<DeviceItem[]>([])
const loadingDevices = ref(false)

const RECENT_MS = 5 * 60 * 1000
function getDeviceOnlineState(device: DeviceItem): { label: string; tag: TagType } {
  if (device.is_active) return { label: '活跃播放中', tag: 'success' }
  const seen = new Date(device.last_seen_at).getTime()
  if (!Number.isNaN(seen) && Date.now() - seen < RECENT_MS) return { label: '最近活跃', tag: 'info' }
  return { label: '离线', tag: 'info' }
}

async function openDevicesCard(row: CodeListItem): Promise<void> {
  currentDeviceCode.value = row
  deviceDialogVisible.value = true
  await loadDevices(row.id)
}

async function loadDevices(codeId: number): Promise<void> {
  loadingDevices.value = true
  try {
    const res = await api.listDevices(codeId)
    devicesList.value = res.devices || []
  } catch (err) {
    ElMessage.error(describeError(err))
  } finally {
    loadingDevices.value = false
  }
}

async function handleKickDevice(device: DeviceItem): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确定把设备「${device.name || '未命名设备'}」踢下线吗？若其正在播放影片将立即中断并提示换设备。`,
      '踢设备下线',
      { type: 'warning', confirmButtonText: '踢下线', cancelButtonText: '取消' },
    )
  } catch {
    return
  }

  try {
    const result = await api.kickDevice(device.id)
    ElMessage.success(result.message)
    if (currentDeviceCode.value) {
      await loadDevices(currentDeviceCode.value.id)
    }
    await load()
  } catch (err) {
    ElMessage.error(describeError(err))
  }
}

async function handleUnbindDevice(device: DeviceItem): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确定解绑设备「${device.name || '未命名设备'}」吗？解绑后将彻底移除该设备绑定记录，并释放 1 个名额供新设备使用。`,
      '解绑设备',
      { type: 'warning', confirmButtonText: '确定解绑', cancelButtonText: '取消' },
    )
  } catch {
    return
  }

  try {
    const result = await api.unbindDevice(device.id)
    ElMessage.success(result.message)
    if (currentDeviceCode.value) {
      await loadDevices(currentDeviceCode.value.id)
    }
    await load()
  } catch (err) {
    ElMessage.error(describeError(err))
  }
}
</script>

<template>
  <div class="codes-page">
    <PageHeader
      title="激活码管理"
      desc="全功能卡片式授权总控。支持生成多设备激活码、有效期延长、停用/解封，以及卡片内即时管控绑定设备与踢线，无需跳转页面。"
    />

    <ErrorState v-if="error" :message="error" @retry="load" />

    <!-- 顶部总控卡片矩阵 (全卡片化设计) -->
    <div class="cards-grid">
      <!-- 卡片 1: 发码与快速控制中心 -->
      <ElCard shadow="hover" class="module-card">
        <div class="card-top-bar">
          <div class="card-title-group">
            <div class="card-icon-box icon-box--primary">
              <ElIcon :size="20"><Tickets /></ElIcon>
            </div>
            <div>
              <div class="card-title">激活码总控与操作</div>
              <div class="card-subtitle">支持批量生成、有效期时长预设与条件检索</div>
            </div>
          </div>
          <ElTag type="primary" effect="dark" class="status-tag">
            共 {{ data?.total ?? 0 }} 个激活码
          </ElTag>
        </div>

        <div class="card-body-section">
          <div class="control-row">
            <ElInput
              v-model="search"
              placeholder="搜索激活码或备注关键词..."
              size="small"
              clearable
              :prefix-icon="Search"
              style="max-width: 320px;"
              @keyup.enter="onSearch"
              @clear="onSearch"
            />
            <ElButton size="small" :icon="Search" @click="onSearch">搜索</ElButton>
            <ElButton size="small" :icon="Refresh" :loading="loading" @click="load">刷新</ElButton>
          </div>
        </div>

        <div class="card-footer-bar">
          <span class="footer-hint">支持单台或多设备共用同一激活码</span>
          <div class="card-footer-actions">
            <ElButton
              size="small"
              type="danger"
              plain
              :disabled="ui.readOnly"
              @click="handleCleanupExpired"
            >
              清理失效码
            </ElButton>
            <ElButton
              size="small"
              type="primary"
              :icon="Plus"
              :disabled="ui.readOnly"
              @click="issueOpen = true"
            >
              发行新激活码
            </ElButton>
          </div>
        </div>
      </ElCard>

      <!-- 卡片 2: 授权分布状态指标 -->
      <ElCard shadow="hover" class="module-card">
        <div class="card-top-bar">
          <div class="card-title-group">
            <div class="card-icon-box icon-box--success">
              <ElIcon :size="20"><Monitor /></ElIcon>
            </div>
            <div>
              <div class="card-title">授权状态分布</div>
              <div class="card-subtitle">当前页激活状态与设备使用健康状况</div>
            </div>
          </div>
          <span class="footer-hint">第 {{ page }} 页 / 共 {{ Math.ceil((data?.total || 1) / pageSize) }} 页</span>
        </div>

        <div class="card-body-section">
          <div class="stats-pills-grid">
            <div class="stat-pill-box">
              <span class="stat-pill-label">正常使用中</span>
              <span class="stat-pill-value stat-active">{{ stats.active }}</span>
            </div>
            <div class="stat-pill-box">
              <span class="stat-pill-label">待首次激活</span>
              <span class="stat-pill-value stat-unactivated">{{ stats.unactivated }}</span>
            </div>
            <div class="stat-pill-box">
              <span class="stat-pill-label">已过期失效</span>
              <span class="stat-pill-value stat-expired">{{ stats.expired }}</span>
            </div>
            <div class="stat-pill-box">
              <span class="stat-pill-label">手动停用中</span>
              <span class="stat-pill-value stat-disabled">{{ stats.disabled }}</span>
            </div>
          </div>
        </div>

        <div class="card-footer-bar">
          <span class="footer-hint">双击列表任意行或点击设备名称即可就地管理</span>
        </div>
      </ElCard>
    </div>

    <!-- 刚发出的码展示区 -->
    <ElAlert
      v-if="issuedCodes.length"
      type="success"
      :closable="true"
      style="margin-bottom: 4px;"
      @close="issuedCodes = []"
    >
      <template #title>
        <div style="font-weight: 700; margin-bottom: 6px;">最新发出的激活码批次（点击可直接复制）：</div>
      </template>
      <div class="issued-codes-box">
        <code
          v-for="code in issuedCodes"
          :key="code"
          class="issued-code-chip"
          @click="copyText(code, '已复制此激活码')"
        >
          {{ code }}
        </code>
        <ElButton
          size="small"
          type="primary"
          plain
          :icon="CopyDocument"
          style="margin-left: 8px;"
          @click="copyText(issuedCodes.join('\n'), '已复制全部新激活码')"
        >
          复制全部 ({{ issuedCodes.length }} 个)
        </ElButton>
      </div>
    </ElAlert>

    <!-- 主列表卡片容器 -->
    <ElCard shadow="hover" class="module-card table-card">
      <div v-if="loading && !data" class="skeleton-pad">
        <ElSkeleton :rows="6" animated />
      </div>

      <EmptyState
        v-else-if="isEmpty && search.trim()"
        title="没有匹配的激活码"
        :hint="`搜索词：「${search.trim()}」未匹配到任何激活码或备注`"
      >
        <template #action>
          <ElButton size="small" @click="search = ''; onSearch()">清空搜索</ElButton>
        </template>
      </EmptyState>

      <EmptyState
        v-else-if="isEmpty"
        title="暂无激活码"
        hint="点击上方「发行新激活码」即可生成授权凭证"
      >
        <template #action>
          <ElButton size="small" type="primary" :disabled="ui.readOnly" @click="issueOpen = true">
            发行新激活码
          </ElButton>
        </template>
      </EmptyState>

      <template v-else>
        <ElTable
          v-loading="loading"
          :data="data?.codes ?? []"
          :row-class-name="rowClass"
          size="small"
          class="codes-table"
          @row-dblclick="(row) => openDevicesCard(row as CodeListItem)"
          @header-dragend="onHeaderDragend"
        >
          <ElTableColumn label="激活码" prop="code" :width="widthOf('code', 220)">
            <template #default="{ row }">
              <div class="code-cell">
                <span class="code-mono">{{ row.code }}</span>
                <ElButton
                  link
                  type="primary"
                  size="small"
                  :icon="CopyDocument"
                  title="复制激活码"
                  @click.stop="copyText(row.code, '已复制激活码')"
                />
              </div>
            </template>
          </ElTableColumn>

          <ElTableColumn label="状态" prop="state" :width="widthOf('state', 100)">
            <template #default="{ row }">
              <ElTag :type="codeState(row as CodeListItem).tag" size="small" effect="light">
                {{ codeState(row as CodeListItem).label }}
              </ElTag>
            </template>
          </ElTableColumn>

          <ElTableColumn prop="note" label="备注说明" min-width="140" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.note">{{ row.note }}</span>
              <span v-else class="a-muted">—</span>
            </template>
          </ElTableColumn>

          <ElTableColumn label="授权时长" prop="duration_hours" :width="widthOf('duration_hours', 96)">
            <template #default="{ row }">{{ row.duration_hours }} 小时</template>
          </ElTableColumn>

          <ElTableColumn label="首次激活" prop="activated_at" :width="widthOf('activated_at', 130)">
            <template #default="{ row }">
              <TimeAgo v-if="row.activated_at" :value="row.activated_at" />
              <span v-else class="a-muted">未激活</span>
            </template>
          </ElTableColumn>

          <ElTableColumn label="到期时间" prop="expires_at" :width="widthOf('expires_at', 150)">
            <template #default="{ row }">
              <span v-if="row.expires_at">{{ formatDateTime(row.expires_at) }}</span>
              <span v-else class="a-muted">—</span>
            </template>
          </ElTableColumn>

          <ElTableColumn label="剩余时长" prop="remaining" :width="widthOf('remaining', 120)">
            <template #default="{ row }">
              <span v-if="row.activated_at">{{ humanRemaining(row.remaining_seconds ?? 0) }}</span>
              <span v-else class="a-muted">待起算</span>
            </template>
          </ElTableColumn>

          <!-- 绑定设备（点击就地弹窗，绝不跳转页面） -->
          <ElTableColumn label="绑定设备" prop="devices" :width="widthOf('devices', 180)">
            <template #default="{ row }">
              <div class="device-cell" @click.stop="openDevicesCard(row as CodeListItem)">
                <ElTag
                  :type="(row.device_count || 0) >= (row.max_devices || 1) ? 'danger' : 'info'"
                  size="small"
                  effect="plain"
                  class="device-badge-clickable"
                  title="点击就地管理设备"
                >
                  {{ row.device_count || 0 }} / {{ row.max_devices || 1 }} 台
                </ElTag>
                <span v-if="row.active_device_name" class="device-name-hint" :title="row.active_device_name">
                  {{ row.active_device_name }}
                </span>
                <span v-else-if="!row.device_count" class="a-muted" style="font-size: 11px;">无设备</span>
              </div>
            </template>
          </ElTableColumn>

          <ElTableColumn label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <div class="action-btn-group">
                <ElButton
                  link
                  type="primary"
                  size="small"
                  :disabled="ui.readOnly"
                  @click.stop="openExtend(row as CodeListItem)"
                >
                  延长
                </ElButton>
                <ElButton
                  link
                  :type="row.disabled_at ? 'success' : 'warning'"
                  size="small"
                  :disabled="ui.readOnly"
                  @click.stop="toggleDisabled(row as CodeListItem)"
                >
                  {{ row.disabled_at ? '解封' : '停用' }}
                </ElButton>
                <ElButton
                  link
                  type="primary"
                  size="small"
                  @click.stop="openDevicesCard(row as CodeListItem)"
                >
                  设备
                </ElButton>
                <ElButton
                  link
                  type="danger"
                  size="small"
                  :disabled="ui.readOnly"
                  @click.stop="handleDeleteCode(row as CodeListItem)"
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
            :current-page="page"
            :page-size="pageSize"
            :page-sizes="[10, 20, 50, 100]"
            :total="data?.total ?? 0"
            @current-change="onPageChange"
            @size-change="onPageSizeChange"
          />
        </div>
      </template>
    </ElCard>

    <!-- 弹窗 1: 发码对话框 -->
    <ElDialog v-model="issueOpen" title="发行新激活码" width="520px" destroy-on-close>
      <ElForm label-position="top">
        <ElFormItem label="快捷时长预设">
          <div class="preset-btn-row">
            <ElButton
              v-for="p in PRESETS"
              :key="p.label"
              size="small"
              :type="activePreset === p.label ? 'primary' : 'default'"
              @click="applyPreset(p)"
            >
              {{ p.label }}
            </ElButton>
          </div>
        </ElFormItem>

        <ElRow :gutter="16">
          <ElCol :xs="24" :sm="14">
            <ElFormItem label="自定义时长数值">
              <ElInputNumber v-model="issueForm.amount" :min="1" :max="10000" style="width: 100%" />
            </ElFormItem>
          </ElCol>
          <ElCol :xs="24" :sm="10">
            <ElFormItem label="单位">
              <ElSelect v-model="issueForm.unit" style="width: 100%">
                <ElOption label="天" value="days" />
                <ElOption label="小时" value="hours" />
              </ElSelect>
            </ElFormItem>
          </ElCol>
        </ElRow>

        <ElRow :gutter="16">
          <ElCol :xs="24" :sm="12">
            <ElFormItem label="生成数量">
              <ElInputNumber v-model="issueForm.count" :min="1" :max="100" style="width: 100%" />
            </ElFormItem>
          </ElCol>
          <ElCol :xs="24" :sm="12">
            <ElFormItem label="允许绑定设备数上限">
              <ElInputNumber v-model="issueForm.max_devices" :min="1" :max="10" style="width: 100%" />
            </ElFormItem>
          </ElCol>
        </ElRow>

        <ElFormItem label="备注（选填，方便后台识别）">
          <ElInput v-model="issueForm.note" placeholder="如：活动赠送、VIP客户、特定渠道" />
        </ElFormItem>
      </ElForm>

      <template #footer>
        <div class="dialog-footer">
          <ElButton @click="issueOpen = false">取消</ElButton>
          <ElButton type="primary" :loading="issueBusy" @click="submitIssue">
            生成激活码
          </ElButton>
        </div>
      </template>
    </ElDialog>

    <!-- 弹窗 2: 延长有效期对话框 -->
    <ElDialog
      v-model="extendOpen"
      :title="`延长激活码有效期 · ${extendTarget?.code}`"
      width="440px"
      destroy-on-close
    >
      <ElForm label-position="top">
        <ElFormItem label="延长时长（小时）">
          <ElInputNumber v-model="extendHours" :min="1" :max="87600" style="width: 100%" />
        </ElFormItem>
        <p class="a-muted" style="font-size: 12px; margin: 0;">
          {{
            extendTarget?.started
              ? '该码已激活使用中：将在现有到期时间的基础上向后顺延指定小时数。'
              : '该码尚未激活：将在首次激活后的总可用时长中追加指定小时数。'
          }}
        </p>
      </ElForm>
      <template #footer>
        <div class="dialog-footer">
          <ElButton @click="extendOpen = false">取消</ElButton>
          <ElButton type="primary" :loading="extendBusy" @click="submitExtend">
            确认延长
          </ElButton>
        </div>
      </template>
    </ElDialog>

    <!-- 弹窗 3: 卡片式绑定设备即时管理（完全就地展示，绝不跳转新页面！） -->
    <ElDialog
      v-model="deviceDialogVisible"
      :title="`绑定设备管控 · ${currentDeviceCode?.code || ''}`"
      width="720px"
      destroy-on-close
    >
      <div v-loading="loadingDevices" class="device-modal-content">
        <!-- 激活码摘要条 -->
        <div class="device-code-summary">
          <div class="summary-item">
            <span class="summary-label">激活码</span>
            <strong class="code-mono">{{ currentDeviceCode?.code }}</strong>
          </div>
          <div class="summary-item">
            <span class="summary-label">设备占用</span>
            <ElTag
              :type="(devicesList.length || 0) >= (currentDeviceCode?.max_devices || 1) ? 'danger' : 'info'"
              size="small"
            >
              {{ devicesList.length }} / {{ currentDeviceCode?.max_devices || 1 }} 台
            </ElTag>
          </div>
          <div class="summary-item">
            <span class="summary-label">授权时长</span>
            <span>{{ currentDeviceCode?.duration_hours }} 小时</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">剩余时间</span>
            <span>{{ humanRemaining(currentDeviceCode?.remaining_seconds ?? 0) }}</span>
          </div>
        </div>

        <div v-if="devicesList.length === 0" class="device-empty-box">
          <EmptyState
            title="该激活码暂无任何绑定设备"
            hint="用户在客户端输入此激活码激活成功后，设备信息将实时在此呈现（设备令牌前 6 位脱敏展示）"
          />
        </div>

        <div v-else class="devices-list-cards">
          <div v-for="dev in devicesList" :key="dev.id" class="device-card-item">
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
                @click="handleKickDevice(dev)"
              >
                踢下线
              </ElButton>
              <ElButton
                size="small"
                type="danger"
                plain
                :disabled="ui.readOnly"
                @click="handleUnbindDevice(dev)"
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
            :loading="loadingDevices"
            @click="currentDeviceCode && loadDevices(currentDeviceCode.id)"
          >
            刷新设备
          </ElButton>
          <ElButton size="small" type="primary" @click="deviceDialogVisible = false">
            关闭
          </ElButton>
        </div>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.codes-page {
  padding: 24px 32px;
  max-width: 1440px;
  margin: 0 auto;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
}

/* 卡片通用架构 */
.cards-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

@media (max-width: 900px) {
  .cards-grid {
    grid-template-columns: 1fr;
  }
}

.module-card {
  background: var(--a-card, #ffffff);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: var(--a-radius, 12px);
  box-shadow: var(--a-shadow, 0 1px 3px rgba(0, 0, 0, 0.05));
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.module-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.07);
}

.card-top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--a-border, #e2e8f0);
}

.card-title-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.card-icon-box {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.icon-box--primary {
  background: rgba(14, 165, 233, 0.12);
  color: #0284c7;
}

.icon-box--success {
  background: rgba(16, 185, 129, 0.12);
  color: #10b981;
}

.card-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--a-text, #1e293b);
  line-height: 1.3;
}

.card-subtitle {
  font-size: 12px;
  color: var(--a-text-2, #64748b);
  margin-top: 2px;
}

.status-tag {
  font-weight: 600;
}

.card-body-section {
  padding: 16px 20px;
}

.control-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.stats-pills-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

@media (max-width: 640px) {
  .stats-pills-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.stat-pill-box {
  background: var(--el-fill-color-light, #f8fafc);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-pill-label {
  font-size: 11px;
  color: var(--a-text-2, #64748b);
}

.stat-pill-value {
  font-size: 18px;
  font-weight: 800;
}

.stat-active {
  color: #10b981;
}

.stat-unactivated {
  color: #0284c7;
}

.stat-expired {
  color: #64748b;
}

.stat-disabled {
  color: #ef4444;
}

.card-footer-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: var(--el-fill-color-extra-light, #fafafa);
  border-top: 1px solid var(--a-border, #e2e8f0);
}

.footer-hint {
  font-size: 12px;
  color: var(--a-text-2, #64748b);
}

.card-footer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 批次发码展示 */
.issued-codes-box {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-top: 6px;
}

.issued-code-chip {
  font-family: monospace;
  font-size: 13px;
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.3);
  color: #047857;
  padding: 3px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.issued-code-chip:hover {
  background: rgba(16, 185, 129, 0.25);
  transform: translateY(-1px);
}

/* 列表卡片与表格 */
.table-card {
  padding: 0;
  overflow: hidden;
}

.codes-table {
  width: 100%;
}

.code-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.code-mono {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-weight: 700;
  font-size: 13px;
  letter-spacing: 0.5px;
}

.device-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}

.device-badge-clickable {
  cursor: pointer;
  transition: all 0.15s ease;
}

.device-badge-clickable:hover {
  filter: brightness(0.92);
  transform: scale(1.04);
}

.device-name-hint {
  font-size: 11px;
  color: var(--a-text, #1e293b);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 90px;
}

.action-btn-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pagination-bar {
  padding: 14px 20px;
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid var(--a-border, #e2e8f0);
}

.skeleton-pad {
  padding: 24px;
}

.preset-btn-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

/* 绑定设备卡片式弹窗内部样式 */
.device-modal-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.device-code-summary {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  background: var(--el-fill-color-light, #f8fafc);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: 8px;
  padding: 12px 16px;
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
}

.summary-label {
  color: var(--a-text-2, #64748b);
  font-size: 11px;
}

.device-empty-box {
  padding: 20px 0;
}

.devices-list-cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 380px;
  overflow-y: auto;
}

.device-card-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--a-card, #ffffff);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: 8px;
  padding: 14px 16px;
  gap: 16px;
  transition: all 0.2s ease;
}

.device-card-item:hover {
  border-color: #0284c7;
  background: var(--el-fill-color-light, #f8fafc);
}

.device-card-main {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}

.device-header-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.device-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--a-text, #1e293b);
}

.device-meta-row {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 12px;
  color: var(--a-text-2, #64748b);
}

.device-card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
