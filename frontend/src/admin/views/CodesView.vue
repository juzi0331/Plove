<script setup lang="ts">
/**
 * 激活码管理：发码、停用/解封、延长、看设备、踢设备。
 *
 * 重设计（第一批）加的东西：
 * * **粘性工具栏** —— 搜索/刷新/发码滚动时不跑掉；
 * * **发码预设 + 记忆**（B7）—— 7/30/90/365 天一点就好，上次的参数留着；
 * * **行内复制**（B8）—— 每行一个复制按钮；
 * * **状态高亮**（B9）—— 到期临近变黄、已到期变灰、已停用划线；
 * * **列宽记忆 + 双击进设备**（G11）；
 * * **骨架屏 / 空状态 / 错误态**。
 *
 * 两个刻意的界面决定（保留自阶段 7）：
 * 1. **停用需要二次确认，解封不需要。** 停用会立刻把人挡在门外，误点代价高；
 * 2. **延长时提示"已激活的码会把到期时间往后挪"** —— 后端两种分支处理不一样。
 *
 * 为什么这个页面**不做自动轮询**：列表不会自己变，轮询会在你正打开发码对话框时
 * 把表格打乱。外部改动靠"刷新"按钮。
 */
import {
  ElAlert,
  ElButton,
  ElDialog,
  ElInput,
  ElInputNumber,
  ElLoading,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElPagination,
  ElSelect,
  ElSkeleton,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

// 局部注册 `v-loading` 指令（不整包注册 Element Plus，见 AdminShell 的说明）
const vLoading = ElLoading.directive

import { describeError } from '@/api/http'
import type { CodeListItem, CodeListPayload, IssueCodesRequest } from '@/api/types'

import * as api from '../api'
import EmptyState from '../components/EmptyState.vue'
import ErrorState from '../components/ErrorState.vue'
import PageHeader from '../components/PageHeader.vue'
import TimeAgo from '../components/TimeAgo.vue'
import { codeState, formatDateTime, humanRemaining } from '../format'
import { loadIssueMemory, saveIssueMemory, ui } from '../ui'

const router = useRouter()

const data = ref<CodeListPayload | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

const search = ref('')
const page = ref(1)
const pageSize = ref(20)

// ------------------------------------------------------------------ 列表

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

// ------------------------------------------------------------------ 行状态与列宽

/** 行状态 → 主题里的 a-row--* 类（颜色语义集中在 theme.css） */
function rowClass({ row }: { row: CodeListItem }): string {
  if (row.disabled_at) return 'a-row--disabled'
  if (!row.activated_at) return ''
  const remain = row.remaining_seconds ?? 0
  if (remain <= 0) return 'a-row--expired'
  if (remain < 86400) return 'a-row--warn'
  return ''
}

// 列宽记忆（G11）：拖过之后下次打开还是你调的宽度
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
    /* 隐私模式：本次会话有效 */
  }
}

// ------------------------------------------------------------------ 复制

async function copyText(text: string, success: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success(success)
  } catch {
    ElMessage.warning('浏览器不让自动复制，请手动选中')
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
    // 记住这次用的时长与数量（备注不记，它每次都不一样）
    saveIssueMemory({ unit: issueForm.value.unit, amount: issueForm.value.amount, count: issueForm.value.count })
    issueOpen.value = false
    ElMessage.success(`已发出 ${issuedCodes.value.length} 个码`)
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
        `停用 ${row.code} 后，正在用它的设备立刻就看不了内容了（对方不会收到任何解释）。确定吗？`,
        '停用激活码',
        { type: 'warning', confirmButtonText: '停用', cancelButtonText: '取消' },
      )
    } catch {
      return // 用户取消
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

function openDevices(codeId: number): void {
  void router.push({ name: 'admin-devices', params: { codeId: String(codeId) } })
}

async function handleDeleteCode(row: CodeListItem): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确定彻底删除激活码 ${row.code} 吗？此操作不可逆，且会同步解除该码绑定的全部历史设备记录。`,
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
</script>

<template>
  <div class="a-page">
    <PageHeader title="激活码" desc="发码、停用、解封、延长、看设备 —— 全部在这里点，不用进数据库。" />

    <ErrorState v-if="error" :message="error" @retry="load" />

    <!-- 粘性工具栏：滚动时搜索/刷新/发码不跑掉 -->
    <div class="a-toolbar">
      <ElInput
        v-model="search"
        placeholder="搜码或备注"
        size="small"
        clearable
        style="width: 220px"
        @keyup.enter="onSearch"
        @clear="onSearch"
      />
      <ElButton size="small" @click="onSearch">搜索</ElButton>
      <ElButton size="small" :loading="loading" @click="load">刷新</ElButton>
      <span v-if="data" class="count a-muted">共 {{ data.total }} 个</span>
      <span class="spacer" />
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
        :disabled="ui.readOnly"
        @click="issueOpen = true"
      >
        发码
      </ElButton>
    </div>

    <ElAlert
      v-if="issuedCodes.length"
      type="success"
      :closable="true"
      style="margin-bottom: 14px"
      @close="issuedCodes = []"
    >
      <template #title>刚发出的码（请复制走，列表里也能查到）</template>
      <div class="issued">
        <code v-for="code in issuedCodes" :key="code" class="a-mono">{{ code }}</code>
        <ElButton size="small" text type="primary" @click="copyText(issuedCodes.join('\n'), '已复制全部')">
          复制全部
        </ElButton>
      </div>
    </ElAlert>

    <!-- 首屏加载：骨架屏 -->
    <div v-if="loading && !data" class="a-card skeleton">
      <ElSkeleton :rows="6" animated />
    </div>

    <EmptyState
      v-else-if="isEmpty && search.trim()"
      title="没有匹配的激活码"
      :hint="`搜索词：「${search.trim()}」—— 搜的是码和备注`"
    >
      <template #action>
        <ElButton size="small" @click="search = ''; onSearch()">清空搜索</ElButton>
      </template>
    </EmptyState>

    <EmptyState v-else-if="isEmpty" title="还没有激活码" hint="发一个码，用户就能在手机端激活（时长从首次激活起算）">
      <template #action>
        <ElButton size="small" type="primary" :disabled="ui.readOnly" @click="issueOpen = true">发码</ElButton>
      </template>
    </EmptyState>

    <ElTable
      v-else
      v-loading="loading"
      :data="data?.codes ?? []"
      :row-class-name="rowClass"
      size="small"
      max-height="calc(100vh - 300px)"
      @row-dblclick="(row) => openDevices((row as CodeListItem).id)"
      @header-dragend="onHeaderDragend"
    >
      <ElTableColumn label="激活码" prop="code" :width="widthOf('code', 220)">
        <template #default="{ row }">
          <span class="code-cell">
            <span class="a-mono">{{ row.code }}</span>
            <ElButton
              link
              size="small"
              class="copy"
              title="复制这个码"
              @click.stop="copyText(row.code, '已复制')"
            >
              复制
            </ElButton>
          </span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="状态" prop="state" :width="widthOf('state', 96)">
        <template #default="{ row }">
          <ElTag :type="codeState(row as CodeListItem).tag" size="small" effect="light">
            {{ codeState(row as CodeListItem).label }}
          </ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="note" label="备注" min-width="130" show-overflow-tooltip />
      <ElTableColumn label="时长" prop="duration_hours" :width="widthOf('duration_hours', 96)">
        <template #default="{ row }">{{ row.duration_hours }} 小时</template>
      </ElTableColumn>
      <ElTableColumn label="首次激活" prop="activated_at" :width="widthOf('activated_at', 130)">
        <template #default="{ row }">
          <TimeAgo :value="row.activated_at" />
        </template>
      </ElTableColumn>
      <ElTableColumn label="到期" prop="expires_at" :width="widthOf('expires_at', 150)">
        <template #default="{ row }">{{ formatDateTime(row.expires_at) }}</template>
      </ElTableColumn>
      <ElTableColumn label="剩余" prop="remaining" :width="widthOf('remaining', 120)">
        <template #default="{ row }">
          {{ humanRemaining(row.remaining_seconds ?? 0) }}
        </template>
      </ElTableColumn>
      <ElTableColumn label="绑定设备" prop="devices" :width="widthOf('devices', 170)">
        <template #default="{ row }">
          <ElButton link type="primary" size="small" @click="openDevices(row.id)">
            <ElTag
              :type="(row.device_count || 0) >= (row.max_devices || 1) ? 'danger' : 'info'"
              size="small"
              effect="plain"
            >
              {{ row.device_count || 0 }} / {{ row.max_devices || 1 }} 台
            </ElTag>
            <template v-if="row.active_device_name">
              <span style="margin-left: 4px; font-size: 11px;">({{ row.active_device_name }})</span>
            </template>
          </ElButton>
        </template>
      </ElTableColumn>
      <ElTableColumn label="操作" width="210" fixed="right">
        <template #default="{ row }">
          <ElButton link type="primary" size="small" :disabled="ui.readOnly" @click="openExtend(row as CodeListItem)">
            延长
          </ElButton>
          <ElButton
            link
            :type="row.disabled_at ? 'success' : 'warning'"
            size="small"
            :disabled="ui.readOnly"
            @click="toggleDisabled(row as CodeListItem)"
          >
            {{ row.disabled_at ? '解封' : '停用' }}
          </ElButton>
          <ElButton
            link
            type="danger"
            size="small"
            :disabled="ui.readOnly"
            @click="handleDeleteCode(row as CodeListItem)"
          >
            删除
          </ElButton>
        </template>
      </ElTableColumn>
    </ElTable>

    <div v-if="data && data.codes?.length" class="pager">
      <ElPagination
        layout="total, sizes, prev, pager, next"
        :total="data.total"
        :current-page="page"
        :page-size="pageSize"
        :page-sizes="[20, 50, 100]"
        @current-change="onPageChange"
        @size-change="onPageSizeChange"
      />
    </div>

    <!-- 发码 -->
    <ElDialog v-model="issueOpen" title="发码" width="440px" align-center>
      <div class="presets">
        <ElButton
          v-for="preset in PRESETS"
          :key="preset.label"
          size="small"
          :type="activePreset === preset.label ? 'primary' : 'default'"
          @click="applyPreset(preset)"
        >
          {{ preset.label }}
        </ElButton>
      </div>
      <div class="form">
        <div class="form-row">
          <span class="form-label">时长</span>
          <div class="inline">
            <ElInputNumber v-model="issueForm.amount" :min="1" :max="365" />
            <ElSelect v-model="issueForm.unit" style="width: 90px">
              <ElOption label="天" value="days" />
              <ElOption label="小时" value="hours" />
            </ElSelect>
          </div>
        </div>
        <div class="form-row">
          <span class="form-label">数量</span>
          <ElInputNumber v-model="issueForm.count" :min="1" :max="50" />
        </div>
        <div class="form-row">
          <span class="form-label">设备上限</span>
          <div class="inline">
            <ElInputNumber v-model="issueForm.max_devices" :min="1" :max="100" />
            <span class="a-muted" style="margin-left: 8px;">台可用设备</span>
          </div>
        </div>
        <div class="form-row">
          <span class="form-label">备注</span>
          <ElInput v-model="issueForm.note" placeholder="发给谁 / 哪一批" maxlength="255" />
        </div>
      </div>
      <p class="a-note">
        时长从首次激活那一刻开始算，不是发码时间。发出去但没人用的码不占时长。
        <br /><strong>🔒 设备限制保密机制</strong>：该激活码最多允许绑定的设备数对用户端严格保密。超出上限激活新设备时将模糊提示受限，管理员可进入设备列表一键解绑释放名额。
      </p>
      <template #footer>
        <ElButton @click="issueOpen = false">取消</ElButton>
        <ElButton type="primary" :loading="issueBusy" @click="submitIssue">签发</ElButton>
      </template>
    </ElDialog>

    <!-- 延长 -->
    <ElDialog v-model="extendOpen" title="延长时长" width="430px" align-center>
      <p class="a-note">
        码：<span class="a-mono">{{ extendTarget?.code }}</span>
      </p>
      <div class="form">
        <div class="form-row">
          <span class="form-label">延长</span>
          <div class="inline">
            <ElInputNumber v-model="extendHours" :min="1" :max="8760" />
            <span class="a-muted">小时</span>
          </div>
        </div>
      </div>
      <ElAlert
        :type="extendTarget?.started ? 'info' : 'warning'"
        :closable="false"
        show-icon
        :title="
          extendTarget?.started
            ? '这个码已经激活过：会把到期时间往后挪这么多。'
            : '这个码还没激活：会加在它的总时长上（激活时才开始倒计时）。'
        "
      />
      <template #footer>
        <ElButton @click="extendOpen = false">取消</ElButton>
        <ElButton type="primary" :loading="extendBusy" @click="submitExtend">确定</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.count {
  font-size: 12.5px;
}

.spacer {
  flex: 1 1 auto;
}

.skeleton {
  padding: 18px;
}

.issued {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}

.code-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.copy {
  opacity: 0;
  transition: opacity 0.12s ease;
}

.el-table__row:hover .copy {
  opacity: 1;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}

.presets {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.form-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.form-label {
  width: 44px;
  color: var(--a-text-2);
  font-size: 13px;
}

.inline {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
