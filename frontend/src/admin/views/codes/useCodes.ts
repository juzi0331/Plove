import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { describeError } from '@/api/http'
import type { CodeListItem, CodeListPayload, DeviceItem, IssueCodesRequest } from '@/api/types'
import * as api from '@/admin/api'
import { loadIssueMemory, saveIssueMemory } from '@/admin/ui'
import type { TagType } from '@/admin/format'

export const PRESETS = [
  { label: '7 天', unit: 'days' as const, amount: 7 },
  { label: '30 天', unit: 'days' as const, amount: 30 },
  { label: '90 天', unit: 'days' as const, amount: 90 },
  { label: '365 天', unit: 'days' as const, amount: 365 },
]

export function useCodes() {
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

  // ------------------------------------------------------------------ 卡片式绑定设备即时管理
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

  return {
    data,
    loading,
    error,
    search,
    page,
    pageSize,
    load,
    onSearch,
    onPageChange,
    onPageSizeChange,
    isEmpty,
    stats,
    rowClass,
    widthOf,
    onHeaderDragend,
    copyText,
    issueOpen,
    issueBusy,
    issueForm,
    issuedCodes,
    activePreset,
    applyPreset,
    submitIssue,
    toggleDisabled,
    extendOpen,
    extendBusy,
    extendHours,
    extendTarget,
    openExtend,
    submitExtend,
    handleDeleteCode,
    handleCleanupExpired,
    deviceDialogVisible,
    currentDeviceCode,
    devicesList,
    loadingDevices,
    getDeviceOnlineState,
    openDevicesCard,
    loadDevices,
    handleKickDevice,
    handleUnbindDevice,
  }
}
