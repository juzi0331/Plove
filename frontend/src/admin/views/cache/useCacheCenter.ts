import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  clearCache,
  getCacheGlobalConfig,
  getCacheStats,
  listCacheKeys,
  listSites,
  preheatCache,
  updateCacheGlobalConfig,
  type CacheGlobalConfig,
} from '@/admin/api'
import type {
  AdminSiteItem,
  CacheKeyEntry,
  CacheStatsPayload,
} from '@/api/types'

export interface SiteCacheSummary {
  site: string
  name: string
  total: number
  homeCount: number
  categoryCount: number
  detailCount: number
}

export function nsTagType(ns: string): 'primary' | 'success' | 'warning' | 'info' {
  switch (ns) {
    case 'home':
      return 'primary'
    case 'category':
      return 'success'
    case 'detail':
      return 'warning'
    default:
      return 'info'
  }
}

export function nsFriendlyName(ns: string): string {
  switch (ns) {
    case 'home':
      return '首页推荐大盘'
    case 'category':
      return '分类剧目列表'
    case 'detail':
      return '单剧详情与选集'
    default:
      return ns
  }
}

export function useCacheCenter() {
  const loading = ref(false)
  const preheating = ref(false)
  const updatingGlobal = ref(false)
  const stats = ref<CacheStatsPayload | null>(null)
  const entries = ref<CacheKeyEntry[]>([])
  const allSites = ref<AdminSiteItem[]>([])

  const globalConfig = ref<CacheGlobalConfig>({
    cache_enabled: false,
    warmup_enabled: false,
    warmup_interval_seconds: 86400,
  })

  // 抽屉状态
  const isEntryDrawerVisible = ref(false)
  const selectedEntryKey = ref<string>('')

  async function loadData(): Promise<void> {
    loading.value = true
    try {
      const [st, keys, siteRes, gCfg] = await Promise.all([
        getCacheStats(),
        listCacheKeys(),
        listSites().catch(() => ({ sites: [] })),
        getCacheGlobalConfig().catch(() => ({
          cache_enabled: false,
          warmup_enabled: false,
          warmup_interval_seconds: 86400,
        })),
      ])
      stats.value = st
      entries.value = keys
      allSites.value = siteRes.sites || []
      globalConfig.value = gCfg
    } catch (err) {
      ElMessage.error(err instanceof Error ? err.message : '加载缓存数据失败')
    } finally {
      loading.value = false
    }
  }

  async function handleSaveGlobalConfig(): Promise<void> {
    updatingGlobal.value = true
    try {
      const res = await updateCacheGlobalConfig(globalConfig.value)
      globalConfig.value = res
      ElMessage.success('缓存总控配置已保存并实时生效！')
      await loadData()
    } catch (err) {
      ElMessage.error(err instanceof Error ? err.message : '保存总控配置失败')
    } finally {
      updatingGlobal.value = false
    }
  }

  function handleViewEntry(key: string): void {
    selectedEntryKey.value = key
    isEntryDrawerVisible.value = true
  }

  async function handlePreheat(site?: string): Promise<void> {
    preheating.value = true
    try {
      const res = await preheatCache(site)
      const count = (res.preheated_sites ?? []).length
      ElMessage.success(`预热完成（耗时 ${res.elapsed_ms}ms），成功装载 ${count} 个站点首页`)
      await loadData()
    } catch (err) {
      ElMessage.error(err instanceof Error ? err.message : '预热失败')
    } finally {
      preheating.value = false
    }
  }

  async function handleClearAll(): Promise<void> {
    try {
      await ElMessageBox.confirm('确定要清空所有内存与磁盘缓存吗？清空后客户端下次访问将重新穿透至源站。', '清空警告', {
        confirmButtonText: '确定清空',
        cancelButtonText: '取消',
        type: 'warning',
      })
      const res = await clearCache()
      ElMessage.success(res.message)
      await loadData()
    } catch {
      /* 用户取消 */
    }
  }

  async function handleClearKey(entryKey: string): Promise<void> {
    try {
      const res = await clearCache(undefined, entryKey)
      ElMessage.success(res.message)
      entries.value = entries.value.filter((e) => e.key !== entryKey)
      if (stats.value) stats.value.size = Math.max(0, stats.value.size - 1)
    } catch (err) {
      ElMessage.error(err instanceof Error ? err.message : '清理失败')
    }
  }

  async function handleClearSite(site: string): Promise<void> {
    try {
      const res = await clearCache(site)
      ElMessage.success(res.message || `已清空站点 ${site} 的缓存`)
      await loadData()
    } catch (err) {
      ElMessage.error(err instanceof Error ? err.message : '清空失败')
    }
  }

  async function handlePreheatSite(site: string): Promise<void> {
    preheating.value = true
    try {
      const res = await preheatCache(site)
      ElMessage.success(`站点 ${site} 预热成功！耗时 ${res.elapsed_ms}ms`)
      await loadData()
    } catch (err) {
      ElMessage.error(err instanceof Error ? err.message : '预热失败')
    } finally {
      preheating.value = false
    }
  }

  const filteredEntries = computed(() => entries.value)

  const capacityPercent = computed(() => {
    if (!stats.value || stats.value.maxsize <= 0) return 0
    return Math.min(100, Math.round((stats.value.size / stats.value.maxsize) * 100))
  })

  const hitRatio = computed(() => stats.value ? stats.value.hit_ratio_percent : 0)

  const savedBandwidthMb = computed(() => {
    if (!stats.value) return '0.0'
    return (stats.value.hits * 0.18).toFixed(1)
  })

  const siteSummaries = computed<SiteCacheSummary[]>(() => {
    const map: Record<string, SiteCacheSummary> = {}
    for (const s of allSites.value) {
      map[s.key] = {
        site: s.key,
        name: s.name || s.key,
        total: 0,
        homeCount: 0,
        categoryCount: 0,
        detailCount: 0,
      }
    }
    for (const entry of entries.value) {
      const s = entry.site || 'unknown'
      if (!map[s]) {
        map[s] = {
          site: s,
          name: s,
          total: 0,
          homeCount: 0,
          categoryCount: 0,
          detailCount: 0,
        }
      }
      map[s].total++
      if (entry.namespace === 'home') map[s].homeCount++
      else if (entry.namespace === 'category') map[s].categoryCount++
      else if (entry.namespace === 'detail') map[s].detailCount++
    }
    return Object.values(map)
  })

  onMounted(() => {
    void loadData()
  })

  return {
    loading,
    preheating,
    updatingGlobal,
    stats,
    entries,
    allSites,
    globalConfig,
    isEntryDrawerVisible,
    selectedEntryKey,
    loadData,
    handleSaveGlobalConfig,
    handleViewEntry,
    handlePreheat,
    handleClearAll,
    handleClearKey,
    handleClearSite,
    handlePreheatSite,
    filteredEntries,
    capacityPercent,
    hitRatio,
    savedBandwidthMb,
    siteSummaries,
    nsTagType,
    nsFriendlyName,
  }
}
