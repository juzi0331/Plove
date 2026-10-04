<script setup lang="ts">
/**
 * CacheCenterView - 全局缓存控制中心与命中率透视
 *
 * 全卡片式架构：
 * 1. 全局内容缓存与主动预热总控卡片（开关标明「开启」「关闭」）
 * 2. 5大核心指标透明透视卡片（实时命中率、L1内存占用、L2磁盘镜像、SingleFlight防击穿、TTL）
 * 3. 分站点缓存矩阵卡片（独立预热与清空）
 * 4. 内存缓存条目检索与管理
 * 5. 缓存数据深度可视化透视（将原本生涩的 JSON 转为直观的影片剧照、选集列表、分类与排盘）
 */
import {
  Delete,
  DocumentCopy,
  Film,
  Lightning,
  List,
  Platform,
  Refresh,
  Timer,
  VideoPlay,
  View,
} from '@element-plus/icons-vue'
import {
  ElButton,
  ElCard,
  ElDescriptions,
  ElDescriptionsItem,
  ElDrawer,
  ElEmpty,
  ElIcon,
  ElMessage,
  ElMessageBox,
  ElProgress,
  ElSkeleton,
  ElSwitch,
  ElTabPane,
  ElTabs,
  ElTag,
  ElTooltip,
} from 'element-plus'
import { computed, onMounted, ref } from 'vue'

import {
  clearCache,
  getCacheEntry,
  getCacheGlobalConfig,
  getCacheStats,
  listCacheKeys,
  listSites,
  preheatCache,
  updateCacheGlobalConfig,
  type CacheGlobalConfig,
} from '@/admin/api'
import PageHeader from '../components/PageHeader.vue'
import { ui } from '@/admin/ui'
import type {
  AdminSiteItem,
  CacheEntryDetail,
  CacheKeyEntry,
  CacheStatsPayload,
} from '@/api/types'

// ------------------------------------------------------------------ 状态定义

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

// 单条缓存详情抽屉与可视化解析
const isEntryDrawerVisible = ref(false)
const loadingDetail = ref(false)
const currentEntryDetail = ref<CacheEntryDetail | null>(null)
const activeDetailTab = ref<'visual' | 'json'>('visual')

// ------------------------------------------------------------------ 数据结构解析 (将生涩 JSON 还原为人类可读模型)

interface ParsedDrama {
  id?: string | number
  name: string
  pic?: string
  remarks?: string
  typeName?: string
  year?: string
  area?: string
  actor?: string
  director?: string
  desc?: string
}

interface ParsedEpisode {
  name: string
  url?: string
}

interface ParsedSection {
  title: string
  items: ParsedDrama[]
}

interface ParsedCacheResult {
  type: 'detail' | 'category' | 'home' | 'list' | 'object'
  video?: ParsedDrama
  episodes?: ParsedEpisode[]
  lines?: any[]
  total?: number
  page?: number
  pagecount?: number
  limit?: number
  items?: ParsedDrama[]
  banners?: ParsedDrama[]
  sections?: ParsedSection[]
  categories?: any[]
  raw?: any
}

function parseDramaItem(item: any): ParsedDrama {
  if (!item || typeof item !== 'object') return { name: String(item || '') }
  return {
    id: item.vod_id || item.id,
    name: item.vod_name || item.name || item.title || '未知剧名',
    pic: item.vod_pic || item.pic || item.cover || '',
    remarks: item.vod_remarks || item.remarks || item.note || '',
    typeName: item.type_name || item.category || '',
    year: item.vod_year || item.year || '',
    area: item.vod_area || item.area || '',
    actor: item.vod_actor || item.actor || '',
    director: item.vod_director || item.director || '',
    desc: item.vod_content || item.desc || item.description || '',
  }
}

const parsedCacheView = computed<ParsedCacheResult | null>(() => {
  if (!currentEntryDetail.value || !currentEntryDetail.value.data) {
    return null
  }
  const raw: any = currentEntryDetail.value.data
  const ns = currentEntryDetail.value.namespace

  // 1. DETAIL 详情页与选集
  if (ns === 'detail' || raw.video || raw.episodes) {
    const videoRaw = raw.video || raw
    const video = parseDramaItem(videoRaw)
    const rawEpisodes = raw.episodes || videoRaw.episodes || []
    let episodes: ParsedEpisode[] = []

    if (Array.isArray(rawEpisodes)) {
      episodes = rawEpisodes.map((ep, i) => {
        if (typeof ep === 'string') return { name: ep }
        return {
          name: ep.name || ep.title || `第 ${i + 1} 集`,
          url: ep.url || ep.link || '',
        }
      })
    } else if (typeof rawEpisodes === 'string') {
      episodes = rawEpisodes.split('#').filter(Boolean).map((part, i) => {
        const segs = part.split('$')
        return {
          name: segs[0] || `第 ${i + 1} 集`,
          url: segs[1] || '',
        }
      })
    }

    const lines = Array.isArray(raw.lines) ? raw.lines : []
    return {
      type: 'detail',
      video,
      episodes,
      lines,
    }
  }

  // 2. CATEGORY 分类筛选页
  if (ns === 'category' || Array.isArray(raw.items) || Array.isArray(raw.videos) || Array.isArray(raw.list)) {
    const listRaw = raw.items || raw.videos || raw.list || []
    const items = listRaw.map(parseDramaItem)
    return {
      type: 'category',
      total: raw.total ?? items.length,
      page: raw.page ?? 1,
      pagecount: raw.pagecount ?? 1,
      limit: raw.limit ?? items.length,
      items,
    }
  }

  // 3. HOME 首页大盘
  if (ns === 'home' || raw.banners || raw.sections) {
    const banners = (raw.banners || []).map(parseDramaItem)
    const sections: ParsedSection[] = []
    if (Array.isArray(raw.sections)) {
      for (const sec of raw.sections) {
        sections.push({
          title: sec.title || sec.name || '热门推荐',
          items: (sec.items || sec.videos || []).map(parseDramaItem),
        })
      }
    }
    const categories = Array.isArray(raw.categories) ? raw.categories : []
    return {
      type: 'home',
      banners,
      sections,
      categories,
    }
  }

  // 4. 纯数组列表
  if (Array.isArray(raw)) {
    return {
      type: 'list',
      items: raw.map(parseDramaItem),
    }
  }

  // 5. 其他复合对象
  return {
    type: 'object',
    raw,
  }
})


// ------------------------------------------------------------------ 数据交互

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

async function handleViewEntry(key: string): Promise<void> {
  isEntryDrawerVisible.value = true
  loadingDetail.value = true
  activeDetailTab.value = 'visual'
  try {
    currentEntryDetail.value = await getCacheEntry(key)
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '获取缓存数据详情失败')
  } finally {
    loadingDetail.value = false
  }
}

function copyJson(data: any): void {
  try {
    navigator.clipboard.writeText(JSON.stringify(data, null, 2))
    ElMessage.success('已复制缓存数据到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动选取复制')
  }
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

// ------------------------------------------------------------------ 衍生计算

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

interface SiteCacheSummary {
  site: string
  name: string
  total: number
  homeCount: number
  categoryCount: number
  detailCount: number
}

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

function nsTagType(ns: string): 'primary' | 'success' | 'warning' | 'info' {
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

function nsFriendlyName(ns: string): string {
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

onMounted(() => {
  void loadData()
})
</script>

<template>
  <div class="a-page cache-page">
    <PageHeader
      title="全局缓存控制中心与命中率透视"
      desc="全面透视内存与磁盘缓存容量、防击穿 SingleFlight 队列及命中状态（HIT / MISS），支持全站一键预热与深层数据解析。"
    >
      <template #actions>
        <ElButton :icon="Refresh" :loading="loading" @click="loadData">刷新状态</ElButton>
        <ElButton
          type="primary"
          :icon="VideoPlay"
          :loading="preheating"
          :disabled="ui.readOnly"
          @click="() => handlePreheat()"
        >
          一键全站预热
        </ElButton>
        <ElButton
          type="danger"
          plain
          :icon="Delete"
          :disabled="ui.readOnly"
          @click="handleClearAll"
        >
          全量清空缓存
        </ElButton>
      </template>
    </PageHeader>

    <!-- 骨架屏加载状态 -->
    <div v-if="loading && !stats" class="a-card skeleton">
      <ElSkeleton :rows="6" animated />
    </div>

    <template v-else>
      <!-- 1. 全局缓存与主动预热总控卡片 (开关标明「开启」「关闭」) -->
      <div class="control-cards-grid">
      <!-- 缓存总开关卡片 -->
      <ElCard shadow="hover" class="switch-box-card">
        <div class="switch-box-content">
          <div class="switch-icon-col icon-primary">
            <ElIcon :size="24"><Lightning /></ElIcon>
          </div>
          <div class="switch-info-col">
            <div class="switch-title-row">
              <span class="switch-main-name">全局内容缓存总开关</span>
              <ElTag size="small" :type="globalConfig.cache_enabled ? 'success' : 'info'" effect="dark">
                {{ globalConfig.cache_enabled ? '已开启' : '已关闭' }}
              </ElTag>
            </div>
            <p class="switch-sub-desc">
              开启后，首页、分类大厅和详情页将自动享受 0ms 内存与磁盘极速响应，大幅降低源站压力；关闭后所有请求穿透直达源站。
            </p>
          </div>
          <div class="switch-toggle-col">
            <ElSwitch
              v-model="globalConfig.cache_enabled"
              :disabled="ui.readOnly || updatingGlobal"
              inline-prompt
              active-text="开启"
              inactive-text="关闭"
              @change="handleSaveGlobalConfig"
            />
          </div>
        </div>
      </ElCard>

      <!-- 预热总开关卡片 -->
      <ElCard shadow="hover" class="switch-box-card">
        <div class="switch-box-content">
          <div class="switch-icon-col icon-success">
            <ElIcon :size="24"><Timer /></ElIcon>
          </div>
          <div class="switch-info-col">
            <div class="switch-title-row">
              <span class="switch-main-name">自动定时预热总开关</span>
              <ElTag size="small" :type="globalConfig.warmup_enabled ? 'success' : 'info'" effect="dark">
                {{ globalConfig.warmup_enabled ? '已开启' : '已关闭' }}
              </ElTag>
            </div>
            <p class="switch-sub-desc">
              开启后，后台每隔 24 小时主动模拟访问各源站热门页面注入缓存，杜绝冷启动首访等待；关闭后服务不在后台自主请求。
            </p>
          </div>
          <div class="switch-toggle-col">
            <ElSwitch
              v-model="globalConfig.warmup_enabled"
              :disabled="ui.readOnly || updatingGlobal"
              inline-prompt
              active-text="开启"
              inactive-text="关闭"
              @change="handleSaveGlobalConfig"
            />
          </div>
        </div>
      </ElCard>
    </div>

    <!-- 2. KPI 统计卡片（纯 Grid 等宽响应式排布） -->
    <div class="metric-row">
      <ElCard shadow="hover" class="metric-card metric-card--primary">
        <div class="metric-head">
          <span>实时缓存命中率</span>
          <ElTag size="small" type="success" effect="plain">透明可感知</ElTag>
        </div>
        <div class="metric-val highlight">
          {{ hitRatio }}<span class="metric-unit">%</span>
        </div>
        <div class="metric-foot">
          <span>节约流量: ~{{ savedBandwidthMb }} MB</span>
          <span class="foot-sep">·</span>
          <span>命中: {{ stats?.hits ?? 0 }} / 穿透: {{ stats?.misses ?? 0 }}</span>
        </div>
      </ElCard>

      <ElCard shadow="hover" class="metric-card">
        <div class="metric-head">
          <span>L1 内存缓存容量</span>
          <span class="a-muted">{{ capacityPercent }}%</span>
        </div>
        <div class="metric-val">
          {{ stats?.size ?? 0 }}
          <span class="metric-sub">/ {{ stats?.maxsize ?? 512 }}</span>
        </div>
        <ElProgress
          :percentage="capacityPercent"
          :show-text="false"
          :stroke-width="6"
          color="var(--el-color-primary)"
        />
      </ElCard>

      <ElCard shadow="hover" class="metric-card">
        <div class="metric-head">
          <span>L2 磁盘持久化镜像</span>
          <ElTag size="small" type="success" effect="plain">SQLite WAL</ElTag>
        </div>
        <div class="metric-val">
          {{ stats?.disk?.count ?? 0 }}
          <span class="metric-unit">条目</span>
        </div>
        <div class="metric-foot">
          <span>磁盘: {{ stats?.disk?.size_mb ?? 0 }} MB</span>
          <span class="foot-sep">·</span>
          <span class="a-muted">重启零丢失</span>
        </div>
      </ElCard>

      <ElCard shadow="hover" class="metric-card">
        <div class="metric-head">
          <span>防击穿并发队列</span>
          <ElTag size="small" :type="stats?.inflight ? 'warning' : 'info'">SingleFlight</ElTag>
        </div>
        <div class="metric-val">
          {{ stats?.inflight ?? 0 }}
          <span class="metric-unit">tasks</span>
        </div>
        <div class="metric-foot a-muted">并发请求瞬间合并为 1 次请求</div>
      </ElCard>

      <ElCard shadow="hover" class="metric-card">
        <div class="metric-head">
          <span>默认存活时间</span>
          <span class="a-muted">TTL 策略</span>
        </div>
        <div class="metric-kv">
          <span>首页: {{ stats?.ttl?.home ?? 600 }}s</span>
          <span>列表: {{ stats?.ttl?.category ?? 300 }}s</span>
          <span>详情: {{ stats?.ttl?.detail ?? 300 }}s</span>
        </div>
        <div class="metric-foot a-muted">播放地址不缓存</div>
      </ElCard>
    </div>

    <!-- 3. 分站点缓存矩阵卡片（展示全量接入源站状态） -->
    <div v-if="siteSummaries.length > 0" class="section-container">
      <div class="section-title-bar">
        <div class="title-with-icon">
          <ElIcon :size="16"><Platform /></ElIcon>
          <span>分源站缓存矩阵 ({{ siteSummaries.length }} 个源站)</span>
        </div>
      </div>

      <div class="site-cache-grid">
        <ElCard
          v-for="s in siteSummaries"
          :key="s.site"
          shadow="hover"
          class="site-item-card"
        >
          <div class="s-card-top">
            <div class="s-card-title-box">
              <span class="s-card-name" :title="s.site">{{ s.name }}</span>
              <code class="s-card-key">{{ s.site }}</code>
            </div>
            <ElTag size="small" :type="s.total > 0 ? 'success' : 'info'" effect="plain">
              {{ s.total > 0 ? `${s.total} 条缓存` : '暂无缓存' }}
            </ElTag>
          </div>

          <div class="s-card-counts">
            <div class="count-pill">
              <span class="c-label">首页:</span>
              <span class="c-num">{{ s.homeCount }}</span>
            </div>
            <div class="count-pill">
              <span class="c-label">分类:</span>
              <span class="c-num">{{ s.categoryCount }}</span>
            </div>
            <div class="count-pill">
              <span class="c-label">详情:</span>
              <span class="c-num">{{ s.detailCount }}</span>
            </div>
          </div>

          <div class="s-card-actions">
            <ElButton
              size="small"
              type="primary"
              plain
              :icon="VideoPlay"
              :loading="preheating"
              :disabled="ui.readOnly"
              @click="handlePreheatSite(s.site)"
            >
              预热该站
            </ElButton>
            <ElButton
              size="small"
              type="danger"
              plain
              :icon="Delete"
              :disabled="s.total === 0 || ui.readOnly"
              @click="handleClearSite(s.site)"
            >
              清空该站
            </ElButton>
          </div>
        </ElCard>
      </div>
    </div>

    <!-- 4. 内存缓存条目卡片管理 -->
    <div class="section-container">
      <div class="section-title-bar">
        <div class="title-with-icon">
          <ElIcon :size="16"><List /></ElIcon>
          <span>当前内存缓存条目 (共 {{ filteredEntries.length }} 项)</span>
        </div>
      </div>

      <!-- 条目卡片网格 -->
      <div v-if="filteredEntries.length > 0" class="entry-cards-grid">
        <ElCard
          v-for="row in filteredEntries"
          :key="row.key"
          shadow="hover"
          class="entry-item-card"
        >
          <div class="entry-card-header">
            <div class="entry-tags">
              <ElTag size="small" effect="plain">{{ row.site }}</ElTag>
              <ElTag size="small" :type="nsTagType(row.namespace)" effect="dark">
                {{ nsFriendlyName(row.namespace) }}
              </ElTag>
              <ElTag v-if="row.is_disk" size="small" type="success" effect="plain">L2磁盘</ElTag>
            </div>
            <span class="entry-ttl-pill">
              剩余 {{ row.remaining_seconds }}s
            </span>
          </div>

          <div class="entry-card-body">
            <div class="entry-ident" :title="row.ident || '首页推荐排盘'">
              {{ row.ident ? `标识: ${row.ident}` : '全站首页推荐排盘' }}
            </div>
            <code class="entry-full-key" :title="row.key">{{ row.key }}</code>
          </div>

          <div class="entry-card-footer">
            <ElButton
              type="primary"
              size="small"
              plain
              :icon="View"
              @click="handleViewEntry(row.key)"
            >
              查看数据
            </ElButton>
            <ElButton
              type="danger"
              size="small"
              plain
              :icon="Delete"
              :disabled="ui.readOnly"
              @click="handleClearKey(row.key)"
            >
              删除键
            </ElButton>
          </div>
        </ElCard>
      </div>

      <ElCard v-else shadow="hover" class="empty-entries-card">
        <ElEmpty description="当前未发现匹配的缓存条目，可点击上方「一键全站预热」或通过前台访问自动生成" />
      </ElCard>
    </div>
  </template>

    <!-- ---------------------------------------------------------- 缓存数据可视化透视抽屉 (用户一目了然看懂内容) -->
    <ElDrawer
      v-model="isEntryDrawerVisible"
      title="缓存内容数据透视"
      size="680px"
      destroy-on-close
      class="cache-detail-drawer"
    >
      <div v-loading="loadingDetail" class="drawer-inner-box">
        <template v-if="currentEntryDetail">
          <!-- 顶部元信息卡片 -->
          <ElCard shadow="never" class="entry-meta-card">
            <div class="meta-row">
              <span class="meta-label">完整缓存 Key:</span>
              <code class="meta-key">{{ currentEntryDetail.key }}</code>
              <ElButton
                size="small"
                text
                :icon="DocumentCopy"
                @click="copyJson(currentEntryDetail.key)"
              >
                复制
              </ElButton>
            </div>
            <div class="meta-badges-row">
              <ElTag size="small" effect="plain">{{ currentEntryDetail.site }}</ElTag>
              <ElTag size="small" :type="nsTagType(currentEntryDetail.namespace)" effect="dark">
                {{ nsFriendlyName(currentEntryDetail.namespace) }}
              </ElTag>
              <span class="meta-ttl">TTL 剩余存活: <strong>{{ currentEntryDetail.remaining_seconds }} 秒</strong></span>
            </div>
          </ElCard>

          <!-- 模式切换：默认可视化预览，技术人员可切换查看 JSON -->
          <div class="tab-switcher-row">
            <ElTabs v-model="activeDetailTab" class="detail-tabs">
              <ElTabPane label="结构化可视化预览" name="visual" />
              <ElTabPane label="原始技术报文 (JSON)" name="json" />
            </ElTabs>

            <ElButton
              size="small"
              type="primary"
              plain
              :icon="DocumentCopy"
              @click="copyJson(currentEntryDetail.data)"
            >
              复制完整数据
            </ElButton>
          </div>

          <!-- TAB 1: 可视化结构预览 (告别生涩 JSON，一目了然看懂电影/剧集) -->
          <div v-if="activeDetailTab === 'visual'" class="visual-container">
            <!-- 1.1 详情页展示 -->
            <div v-if="parsedCacheView?.type === 'detail' && parsedCacheView.video" class="detail-visual-box">
              <ElCard shadow="hover" class="drama-hero-card">
                <div class="drama-hero-inner">
                  <div class="drama-poster-box">
                    <img
                      v-if="parsedCacheView.video?.pic"
                      :src="parsedCacheView.video.pic"
                      :alt="parsedCacheView.video.name"
                      class="drama-poster-img"
                      loading="lazy"
                    />
                    <div v-else class="drama-poster-fallback">
                      <ElIcon :size="32"><Film /></ElIcon>
                    </div>
                  </div>
                  <div class="drama-info-box">
                    <h2 class="drama-title">{{ parsedCacheView.video?.name }}</h2>
                    <div class="drama-tags-row">
                      <ElTag v-if="parsedCacheView.video?.typeName" size="small" type="primary" effect="plain">
                        {{ parsedCacheView.video.typeName }}
                      </ElTag>
                      <ElTag v-if="parsedCacheView.video?.remarks" size="small" type="success" effect="plain">
                        {{ parsedCacheView.video.remarks }}
                      </ElTag>
                      <ElTag v-if="parsedCacheView.video?.year" size="small" type="info" effect="plain">
                        {{ parsedCacheView.video.year }}
                      </ElTag>
                      <ElTag v-if="parsedCacheView.video?.area" size="small" type="info" effect="plain">
                        {{ parsedCacheView.video.area }}
                      </ElTag>
                    </div>

                    <div v-if="parsedCacheView.video?.actor" class="drama-actor-row">
                      <span class="actor-label">主演:</span>
                      <span class="actor-text">{{ parsedCacheView.video.actor }}</span>
                    </div>

                    <div v-if="parsedCacheView.video?.director" class="drama-actor-row">
                      <span class="actor-label">导演:</span>
                      <span class="actor-text">{{ parsedCacheView.video.director }}</span>
                    </div>
                  </div>
                </div>

                <div v-if="parsedCacheView.video?.desc" class="drama-desc-box">
                  <div class="desc-title">剧情简介</div>
                  <p class="desc-text">{{ parsedCacheView.video.desc }}</p>
                </div>
              </ElCard>

              <!-- 选集列表预览 -->
              <ElCard shadow="hover" class="episodes-card">
                <div class="episodes-card-header">
                  <span class="episodes-card-title">选集列表 (共 {{ parsedCacheView.episodes?.length || 0 }} 集)</span>
                  <span class="episodes-card-tip">点击集数可查看对应切片流地址</span>
                </div>

                <div v-if="(parsedCacheView.episodes?.length || 0) > 0" class="episodes-grid">
                  <ElTooltip
                    v-for="(ep, i) in (parsedCacheView.episodes || [])"
                    :key="i"
                    :content="ep.url || '暂无直链'"
                    placement="top"
                  >
                    <div class="episode-chip">
                      {{ ep.name }}
                    </div>
                  </ElTooltip>
                </div>
                <div v-else class="no-episodes">暂未解析到分集列表</div>
              </ElCard>
            </div>

            <!-- 1.2 分类列表页展示 -->
            <div v-else-if="parsedCacheView?.type === 'category'" class="category-visual-box">
              <ElCard shadow="hover" class="category-summary-card">
                <div class="cat-summary-text">
                  当前分类大厅已缓存 <strong>{{ parsedCacheView.items?.length || 0 }}</strong> 部剧目
                  <span class="cat-pager-meta">（第 {{ parsedCacheView.page || 1 }} 页 / 共 {{ parsedCacheView.total || 0 }} 部）</span>
                </div>
              </ElCard>

              <div class="drama-grid-box">
                <div
                  v-for="(item, idx) in (parsedCacheView.items || [])"
                  :key="idx"
                  class="drama-mini-card"
                >
                  <div class="mini-poster-box">
                    <img
                      v-if="item.pic"
                      :src="item.pic"
                      :alt="item.name"
                      class="mini-poster-img"
                      loading="lazy"
                    />
                    <div v-else class="mini-poster-fallback">
                      <ElIcon :size="20"><Film /></ElIcon>
                    </div>
                    <span v-if="item.remarks" class="mini-remarks">{{ item.remarks }}</span>
                  </div>
                  <div class="mini-name" :title="item.name">{{ item.name }}</div>
                  <div class="mini-type">{{ item.typeName || '短剧' }}</div>
                </div>
              </div>
            </div>

            <!-- 1.3 首页大盘展示 -->
            <div v-else-if="parsedCacheView?.type === 'home'" class="home-visual-box">
              <!-- 轮播焦点 -->
              <div v-if="(parsedCacheView.banners?.length || 0) > 0" class="home-section-block">
                <div class="home-section-title">首页轮播焦点 ({{ parsedCacheView.banners?.length || 0 }} 部)</div>
                <div class="drama-grid-box">
                  <div
                    v-for="(item, idx) in (parsedCacheView.banners || [])"
                    :key="idx"
                    class="drama-mini-card"
                  >
                    <div class="mini-poster-box">
                      <img v-if="item.pic" :src="item.pic" class="mini-poster-img" loading="lazy" />
                      <div v-else class="mini-poster-fallback"><ElIcon><Film /></ElIcon></div>
                      <span v-if="item.remarks" class="mini-remarks">{{ item.remarks }}</span>
                    </div>
                    <div class="mini-name">{{ item.name }}</div>
                  </div>
                </div>
              </div>

              <!-- 分区板块 -->
              <div
                v-for="(sec, sIdx) in (parsedCacheView.sections || [])"
                :key="sIdx"
                class="home-section-block"
              >
                <div class="home-section-title">{{ sec.title }} ({{ sec.items?.length || 0 }} 部)</div>
                <div class="drama-grid-box">
                  <div
                    v-for="(item, idx) in (sec.items || [])"
                    :key="idx"
                    class="drama-mini-card"
                  >
                    <div class="mini-poster-box">
                      <img v-if="item.pic" :src="item.pic" class="mini-poster-img" loading="lazy" />
                      <div v-else class="mini-poster-fallback"><ElIcon><Film /></ElIcon></div>
                      <span v-if="item.remarks" class="mini-remarks">{{ item.remarks }}</span>
                    </div>
                    <div class="mini-name">{{ item.name }}</div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 1.4 通用数组 -->
            <div v-else-if="parsedCacheView?.type === 'list'" class="generic-list-box">
              <div class="drama-grid-box">
                <div
                  v-for="(item, idx) in (parsedCacheView.items || [])"
                  :key="idx"
                  class="drama-mini-card"
                >
                  <div class="mini-name">{{ item.name }}</div>
                </div>
              </div>
            </div>


            <!-- 1.5 通用对象 -->
            <div v-else class="generic-obj-box">
              <ElDescriptions :column="1" border size="small">
                <ElDescriptionsItem
                  v-for="(val, key) in parsedCacheView?.raw"
                  :key="key"
                  :label="String(key)"
                >
                  <span class="a-mono" style="font-size: 12.5px;">{{ typeof val === 'object' ? JSON.stringify(val) : String(val) }}</span>
                </ElDescriptionsItem>
              </ElDescriptions>
            </div>
          </div>

          <!-- TAB 2: 原始 JSON 报文 -->
          <div v-else class="json-container">
            <pre class="json-code-box">{{ JSON.stringify(currentEntryDetail.data, null, 2) }}</pre>
          </div>
        </template>
      </div>
    </ElDrawer>
  </div>
</template>

<style scoped>
.cache-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.skeleton {
  padding: 24px;
  background: var(--a-card, #ffffff);
  border-radius: 12px;
  border: 1px solid var(--a-border, #e2e8f0);
}

/* 1. 全局控制开关卡片 */
.control-cards-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

@media (max-width: 820px) {
  .control-cards-grid {
    grid-template-columns: 1fr;
  }
}

.switch-box-card {
  border-radius: 12px;
  border: 1px solid var(--a-border, #e2e8f0);
}

.switch-box-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.switch-icon-col {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.icon-primary {
  background: #eff6ff;
  color: #2563eb;
}

.icon-success {
  background: #f0fdf4;
  color: #16a34a;
}

.switch-info-col {
  flex: 1;
}

.switch-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.switch-main-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--a-text, #0f172a);
}

.switch-sub-desc {
  margin: 0;
  font-size: 12.5px;
  color: var(--a-text-2, #64748b);
  line-height: 1.45;
}

.switch-toggle-col {
  flex-shrink: 0;
}

/* 2. KPI 指标统计卡片 */
.metric-row {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
}

@media (max-width: 1200px) {
  .metric-row {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .metric-row {
    grid-template-columns: 1fr;
  }
}

.metric-card {
  border-radius: 12px;
  border: 1px solid var(--a-border, #e2e8f0);
}

.metric-card--primary {
  border-top: 3px solid #0284c7;
}

.metric-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--a-text-2, #64748b);
}

.metric-val {
  margin: 8px 0;
  font-size: 26px;
  font-weight: 800;
  color: var(--a-text, #0f172a);
  font-family: 'JetBrains Mono', Consolas, monospace;
}

.metric-val.highlight {
  color: #0284c7;
}

.metric-unit {
  font-size: 14px;
  font-weight: 600;
  margin-left: 2px;
}

.metric-sub {
  font-size: 14px;
  font-weight: 500;
  color: var(--a-text-3, #94a3b8);
}

.metric-foot {
  font-size: 12px;
  color: var(--a-text-3, #94a3b8);
  display: flex;
  align-items: center;
  gap: 6px;
}

.foot-sep {
  opacity: 0.5;
}

.metric-kv {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
  font-family: 'JetBrains Mono', Consolas, monospace;
  color: var(--a-text-2, #64748b);
  margin: 6px 0;
}

/* 3. 分站点矩阵 */
.section-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-title-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}

.title-with-icon {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 700;
  color: var(--a-text, #0f172a);
}

.site-cache-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 16px;
}

.site-item-card {
  border-radius: 12px;
  border: 1px solid var(--a-border, #e2e8f0);
}

.s-card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.s-card-title-box {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.s-card-name {
  font-size: 14.5px;
  font-weight: 700;
  color: var(--a-text, #0f172a);
}

.s-card-key {
  font-size: 11.5px;
  color: var(--a-text-3, #94a3b8);
}

.s-card-counts {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}

.count-pill {
  flex: 1;
  background: var(--a-bg-subtle, #f8fafc);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: 6px;
  padding: 6px 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.c-label {
  font-size: 11px;
  color: var(--a-text-3, #94a3b8);
}

.c-num {
  font-size: 14px;
  font-weight: 800;
  font-family: 'JetBrains Mono', Consolas, monospace;
  color: var(--a-text, #0f172a);
}

.s-card-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  border-top: 1px dashed var(--a-border, #e2e8f0);
  padding-top: 10px;
}

/* 4. 条目卡片网格 */
.entry-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 16px;
}

.entry-item-card {
  border-radius: 12px;
  border: 1px solid var(--a-border, #e2e8f0);
}

.entry-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.entry-tags {
  display: flex;
  align-items: center;
  gap: 6px;
}

.entry-ttl-pill {
  font-size: 11.5px;
  font-family: 'JetBrains Mono', Consolas, monospace;
  color: #0284c7;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
}

.entry-card-body {
  margin-bottom: 12px;
}

.entry-ident {
  font-size: 13.5px;
  font-weight: 700;
  color: var(--a-text, #0f172a);
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.entry-full-key {
  display: block;
  font-size: 11px;
  font-family: 'JetBrains Mono', Consolas, monospace;
  color: var(--a-text-3, #94a3b8);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.entry-card-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  border-top: 1px dashed var(--a-border, #e2e8f0);
  padding-top: 8px;
}

.empty-entries-card {
  border-radius: 12px;
  border: 1px solid var(--a-border, #e2e8f0);
}

/* 5. 抽屉数据透视 */
.drawer-inner-box {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.entry-meta-card {
  border-radius: 10px;
  border: 1px solid var(--a-border, #e2e8f0);
  background: var(--a-bg-subtle, #f8fafc);
}

.meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.meta-label {
  font-size: 12px;
  color: var(--a-text-3, #94a3b8);
}

.meta-key {
  flex: 1;
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 12px;
  color: var(--a-text, #0f172a);
  background: #ffffff;
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid var(--a-border, #e2e8f0);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.meta-badges-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.meta-ttl {
  font-size: 12px;
  color: var(--a-text-2, #64748b);
  margin-left: auto;
}

.meta-ttl strong {
  color: #0284c7;
  font-family: 'JetBrains Mono', Consolas, monospace;
}

.tab-switcher-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--a-border, #e2e8f0);
  padding-bottom: 8px;
}

.detail-tabs {
  margin-bottom: -9px;
}

/* 结构化可视化组件 */
.visual-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.drama-hero-card {
  border-radius: 12px;
  border: 1px solid var(--a-border, #e2e8f0);
}

.drama-hero-inner {
  display: flex;
  gap: 16px;
}

.drama-poster-box {
  width: 100px;
  height: 140px;
  border-radius: 8px;
  overflow: hidden;
  background: var(--a-bg-subtle, #f1f5f9);
  flex-shrink: 0;
  border: 1px solid var(--a-border, #e2e8f0);
}

.drama-poster-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.drama-poster-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
}

.drama-info-box {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.drama-title {
  font-size: 18px;
  font-weight: 800;
  color: var(--a-text, #0f172a);
  margin: 0;
}

.drama-tags-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.drama-actor-row {
  font-size: 12.5px;
  color: var(--a-text-2, #64748b);
}

.actor-label {
  font-weight: 600;
  margin-right: 6px;
}

.drama-desc-box {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed var(--a-border, #e2e8f0);
}

.desc-title {
  font-size: 12.5px;
  font-weight: 700;
  color: var(--a-text, #0f172a);
  margin-bottom: 4px;
}

.desc-text {
  font-size: 12.5px;
  color: var(--a-text-2, #64748b);
  line-height: 1.5;
  margin: 0;
}

/* 选集列表 */
.episodes-card {
  border-radius: 12px;
  border: 1px solid var(--a-border, #e2e8f0);
}

.episodes-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.episodes-card-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--a-text, #0f172a);
}

.episodes-card-tip {
  font-size: 11.5px;
  color: var(--a-text-3, #94a3b8);
}

.episodes-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  max-height: 240px;
  overflow-y: auto;
}

.episode-chip {
  padding: 8px 10px;
  border-radius: 6px;
  background: var(--a-bg-subtle, #f8fafc);
  border: 1px solid var(--a-border, #e2e8f0);
  font-size: 12px;
  font-weight: 600;
  color: var(--a-text, #0f172a);
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.episode-chip:hover {
  border-color: #0284c7;
  color: #0284c7;
  background: #f0f9ff;
}

.no-episodes {
  font-size: 12.5px;
  color: var(--a-text-3, #94a3b8);
  text-align: center;
  padding: 16px 0;
}

/* 分类与首页板块卡片 */
.category-summary-card {
  border-radius: 10px;
  border: 1px solid var(--a-border, #e2e8f0);
  margin-bottom: 12px;
}

.cat-summary-text {
  font-size: 13.5px;
  color: var(--a-text, #0f172a);
}

.cat-pager-meta {
  color: var(--a-text-2, #64748b);
  font-size: 12px;
  margin-left: 6px;
}

.home-section-block {
  margin-bottom: 16px;
}

.home-section-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--a-text, #0f172a);
  margin-bottom: 8px;
}

.drama-grid-box {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.drama-mini-card {
  border-radius: 8px;
  border: 1px solid var(--a-border, #e2e8f0);
  background: #ffffff;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mini-poster-box {
  width: 100%;
  height: 110px;
  border-radius: 6px;
  overflow: hidden;
  position: relative;
  background: #f1f5f9;
}

.mini-poster-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.mini-poster-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
}

.mini-remarks {
  position: absolute;
  bottom: 4px;
  right: 4px;
  font-size: 10.5px;
  color: #ffffff;
  background: rgba(0, 0, 0, 0.7);
  padding: 1px 4px;
  border-radius: 3px;
}

.mini-name {
  font-size: 12.5px;
  font-weight: 700;
  color: var(--a-text, #0f172a);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mini-type {
  font-size: 11px;
  color: var(--a-text-3, #94a3b8);
}

/* JSON 容器 */
.json-code-box {
  background: #0f172a;
  color: #f8fafc;
  padding: 14px;
  border-radius: 8px;
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 12px;
  max-height: 480px;
  overflow: auto;
  line-height: 1.5;
}
</style>
