import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { listSites, probePlayground, searchAggregate } from '@/admin/api'
import type {
  AdminSiteItem,
  AggregateSearchPayload,
  PlaygroundProbeResult,
} from '@/api/types'

export interface MatrixItem {
  site: string
  name: string
  status: 'pending' | 'testing' | 'success' | 'error'
  elapsed_ms?: number
  items_count?: number
  cache_hit?: boolean
  error?: string
}

export function usePlayground() {
  const activeTab = ref<'probe' | 'matrix' | 'search'>('probe')

  // ------------------------------------------------------------------ 站点列表
  const sites = ref<AdminSiteItem[]>([])
  const loadingSites = ref(false)

  const probeForm = ref({
    site: '',
    command: 'home' as 'home' | 'category' | 'detail' | 'play',
    tid: '',
    page: 1,
    vod_id: '',
    ep: 1,
    bypass_cache: false,
  })

  const probing = ref(false)
  const probeResult = ref<PlaygroundProbeResult | null>(null)
  const jsonTab = ref<'cleaned' | 'raw'>('cleaned')

  // ------------------------------------------------------------------ 全站连通性体检矩阵状态
  const matrixList = ref<MatrixItem[]>([])
  const matrixTesting = ref(false)

  // ------------------------------------------------------------------ 跨源聚合搜索状态
  const searchKw = ref('')
  const searching = ref(false)
  const searchResult = ref<AggregateSearchPayload | null>(null)

  async function loadSites(): Promise<void> {
    loadingSites.value = true
    try {
      const res = await listSites()
      const siteList = res.sites ?? []
      sites.value = siteList
      if (!probeForm.value.site && siteList.length > 0) {
        probeForm.value.site = siteList[0].key
      }
      // 初始化矩阵
      matrixList.value = siteList.map((s) => ({
        site: s.key,
        name: s.name,
        status: 'pending',
      }))
    } catch (err) {
      ElMessage.error(err instanceof Error ? err.message : '加载站点列表失败')
    } finally {
      loadingSites.value = false
    }
  }

  // ------------------------------------------------------------------ 发送探针
  async function handleRunProbe(): Promise<void> {
    if (!probeForm.value.site) {
      ElMessage.warning('请选择目标站点')
      return
    }
    if ((probeForm.value.command === 'detail' || probeForm.value.command === 'play') && !probeForm.value.vod_id) {
      ElMessage.warning('该命令需要输入 vod_id，或可直接点击下方「智能连贯测试」预设')
      return
    }

    probing.value = true
    try {
      const res = await probePlayground({
        site: probeForm.value.site,
        command: probeForm.value.command,
        tid: probeForm.value.tid || undefined,
        page: probeForm.value.page,
        vod_id: probeForm.value.vod_id || undefined,
        ep: probeForm.value.ep,
        bypass_cache: probeForm.value.bypass_cache,
      })
      probeResult.value = res
      if (res.status === 'OK') {
        ElMessage.success(`探测成功，响应耗时 ${res.elapsed_ms}ms`)
      } else {
        ElMessage.warning(`探测返回异常: ${res.error_detail || '未知原因'}`)
      }
    } catch (err) {
      ElMessage.error(err instanceof Error ? err.message : '探针请求失败')
    } finally {
      probing.value = false
    }
  }

  // ------------------------------------------------------------------ 智能预设测试（免手动输入 ID）
  async function handleQuickPreset(type: 'home' | 'category' | 'detail_auto' | 'play_auto'): Promise<void> {
    if (!probeForm.value.site) {
      if (sites.value.length > 0) probeForm.value.site = sites.value[0].key
      else {
        ElMessage.warning('暂无可用的站点')
        return
      }
    }

    if (type === 'home') {
      probeForm.value.command = 'home'
      await handleRunProbe()
      return
    }

    if (type === 'category') {
      probeForm.value.command = 'category'
      probeForm.value.tid = ''
      await handleRunProbe()
      return
    }

    // 自动从首页获取首部影视的真实 vod_id
    probing.value = true
    try {
      ElMessage.info('正在自动嗅探首页片单以提取真实影片 ID...')
      const homeRes = await probePlayground({
        site: probeForm.value.site,
        command: 'home',
        bypass_cache: false,
      })

      const rawData = homeRes.cleaned_data as any
      const items = rawData?.items ?? rawData?.list ?? (Array.isArray(rawData) ? rawData : [])
      const firstItem = Array.isArray(items) && items.length > 0 ? items[0] : null
      const targetVodId = firstItem?.id ?? firstItem?.vod_id ?? '1'

      probeForm.value.vod_id = String(targetVodId)
      ElMessage.success(`提取到影片: ${firstItem?.title ?? firstItem?.name ?? targetVodId} (ID: ${targetVodId})`)

      if (type === 'detail_auto') {
        probeForm.value.command = 'detail'
        await handleRunProbe()
      } else if (type === 'play_auto') {
        probeForm.value.command = 'play'
        probeForm.value.ep = 1
        await handleRunProbe()
      }
    } catch (err) {
      ElMessage.error(err instanceof Error ? err.message : '自动测试链路异常')
      probing.value = false
    }
  }

  // ------------------------------------------------------------------ 全站并发连通性体检
  async function runFullMatrixTest(): Promise<void> {
    if (sites.value.length === 0) {
      ElMessage.warning('暂无可体检的站点')
      return
    }

    matrixTesting.value = true
    ElMessage.info(`开始全站体检：向 ${sites.value.length} 个站点并发发送连通性探针...`)

    const tasks = matrixList.value.map(async (item) => {
      item.status = 'testing'
      try {
        const res = await probePlayground({
          site: item.site,
          command: 'home',
          bypass_cache: true,
        })
        if (res.status === 'OK') {
          item.status = 'success'
          item.elapsed_ms = res.elapsed_ms
          item.cache_hit = res.cache_hit
          const raw = res.cleaned_data as any
          const items = raw?.items ?? raw?.list ?? (Array.isArray(raw) ? raw : [])
          item.items_count = Array.isArray(items) ? items.length : 0
        } else {
          item.status = 'error'
          item.elapsed_ms = res.elapsed_ms
          item.error = res.error_detail ?? '接口返回异常'
        }
      } catch (err) {
        item.status = 'error'
        item.error = err instanceof Error ? err.message : '请求超时或网络阻断'
      }
    })

    await Promise.allSettled(tasks)
    matrixTesting.value = false
    ElMessage.success('全站并发体检完成')
  }

  // ------------------------------------------------------------------ 跨源聚合搜索
  async function handleAggregateSearch(): Promise<void> {
    if (!searchKw.value.trim()) {
      ElMessage.warning('请输入搜索片名关键词')
      return
    }
    searching.value = true
    try {
      const res = await searchAggregate(searchKw.value.trim())
      searchResult.value = res
      ElMessage.success(`聚合搜索完成：向 ${res.total_sites} 个站点并发查询，累计命中 ${res.total_count} 条`)
    } catch (err) {
      ElMessage.error(err instanceof Error ? err.message : '聚合搜索异常')
    } finally {
      searching.value = false
    }
  }

  function quickSearch(kw: string): void {
    searchKw.value = kw
    void handleAggregateSearch()
  }

  function formatJson(data: any): string {
    if (!data) return ''
    try {
      return JSON.stringify(data, null, 2)
    } catch {
      return String(data)
    }
  }

  function copyText(text: string): void {
    navigator.clipboard.writeText(text).then(() => {
      ElMessage.success('已复制到剪贴板')
    })
  }

  // 抽取卡片展示数据
  const previewItemList = computed<any[]>(() => {
    if (!probeResult.value) return []
    const data = probeResult.value.cleaned_data as any
    if (!data) return []
    if (Array.isArray(data)) return data
    if (Array.isArray(data.items)) return data.items
    if (Array.isArray(data.list)) return data.list
    return []
  })

  onMounted(() => {
    void loadSites()
  })

  return {
    activeTab,
    sites,
    loadingSites,
    probeForm,
    probing,
    probeResult,
    jsonTab,
    matrixList,
    matrixTesting,
    searchKw,
    searching,
    searchResult,
    previewItemList,
    loadSites,
    handleRunProbe,
    handleQuickPreset,
    runFullMatrixTest,
    handleAggregateSearch,
    quickSearch,
    formatJson,
    copyText,
  }
}
