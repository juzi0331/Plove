<script setup lang="ts">
/**
 * 缓存控制中心：
 * 全局命中率看板、容量占用透视、具体内存 Key 实时倒计时列表、
 * 一键主动预热与定向清理。
 */
import {
  ElButton,
  ElCard,
  ElDescriptions,
  ElDescriptionsItem,
  ElDrawer,
  ElEmpty,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElProgress,
  ElSelect,
  ElSwitch,
  ElTag,
} from 'element-plus'
import {
  Delete,
  DocumentCopy,
  Refresh,
  Search,
  VideoPlay,
  View,
} from '@element-plus/icons-vue'
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
import { ui } from '@/admin/ui'
import type { AdminSiteItem, CacheEntryDetail, CacheKeyEntry, CacheStatsPayload } from '@/api/types'

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

// 单条缓存详情抽屉
const isEntryDrawerVisible = ref(false)
const loadingDetail = ref(false)
const currentEntryDetail = ref<CacheEntryDetail | null>(null)

async function handleViewEntry(key: string): Promise<void> {
  isEntryDrawerVisible.value = true
  loadingDetail.value = true
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
    ElMessage.success('已复制缓存 JSON 数据到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动选取复制')
  }
}

const filterSite = ref('')
const filterNs = ref('')
const searchKw = ref('')

async function loadData(): Promise<void> {
  loading.value = true
  try {
    const [st, keys, siteRes, gCfg] = await Promise.all([
      getCacheStats(),
      listCacheKeys(filterSite.value || undefined, filterNs.value || undefined),
      listSites().catch(() => ({ sites: [] })),
      getCacheGlobalConfig().catch(() => ({ cache_enabled: false, warmup_enabled: false, warmup_interval_seconds: 86400 })),
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
    ElMessage.success('全局缓存与预热总控配置已实时保存并持久化！')
    await loadData()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '保存总控配置失败')
  } finally {
    updatingGlobal.value = false
  }
}

onMounted(() => {
  void loadData()
})

const filteredEntries = computed(() => {
  let list = entries.value
  if (searchKw.value.trim()) {
    const kw = searchKw.value.trim().toLowerCase()
    list = list.filter((item) => item.key.toLowerCase().includes(kw))
  }
  return list
})

const capacityPercent = computed(() => {
  if (!stats.value || stats.value.maxsize <= 0) return 0
  return Math.min(100, Math.round((stats.value.size / stats.value.maxsize) * 100))
})

const hitRatio = computed(() => {
  return stats.value ? stats.value.hit_ratio_percent : 0
})

async function handlePreheat(site?: string): Promise<void> {
  preheating.value = true
  try {
    const res = await preheatCache(site)
    const count = (res.preheated_sites ?? []).length
    ElMessage.success(
      `预热完成（耗时 ${res.elapsed_ms}ms），成功装载 ${count} 个站点首页`,
    )
    await loadData()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '预热失败')
  } finally {
    preheating.value = false
  }
}

async function handleClearAll(): Promise<void> {
  try {
    await ElMessageBox.confirm('确定要全量清空所有系统缓存吗？清空后下一次访问将重新穿透请求源站爬虫。', '清空警告', {
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

  // 1. 先把系统接入的所有站点放入 map，保证哪怕 0 条缓存也会展示！
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

  // 2. 统计现存的所有条目
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

function nsTagType(ns: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' {
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
</script>

<template>
  <div class="cache-hub">
    <!-- 顶栏状态与说明 -->
    <div class="hub-header">
      <div>
        <h2 class="hub-title">全局缓存控制中心与命中率透视</h2>
        <p class="hub-sub">
          监控全局内存缓存容量与防击穿队列，透明感知命中状态（CACHE HIT / MISS），支持全站一键刷新与深层数据透视。
        </p>
      </div>
      <div class="hub-actions">
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
      </div>
    </div>

    <!-- 全局缓存与主动预热总控开关 -->
    <div class="global-switch-card">
      <div class="switch-col">
        <div class="switch-meta">
          <div class="switch-badge-title">
            <span class="dot" :class="{ 'dot--on': globalConfig.cache_enabled }"></span>
            <strong>全局内容缓存总开关</strong>
            <ElTag size="small" :type="globalConfig.cache_enabled ? 'success' : 'info'">
              {{ globalConfig.cache_enabled ? '极速缓存中' : '已停用（纯实时穿透）' }}
            </ElTag>
          </div>
          <p class="switch-desc">
            默认关闭。开启后，前台首页、分类大厅和详情页将自动享受 0ms 内存与持久化磁盘极速响应，大幅减轻源站压力；关闭后所有请求均穿透直达源站爬虫。
          </p>
        </div>
        <ElSwitch
          v-model="globalConfig.cache_enabled"
          :disabled="ui.readOnly || updatingGlobal"
          active-text="开启缓存"
          inactive-text="关闭"
          @change="handleSaveGlobalConfig"
        />
      </div>

      <div class="switch-divider"></div>

      <div class="switch-col">
        <div class="switch-meta">
          <div class="switch-badge-title">
            <span class="dot" :class="{ 'dot--on': globalConfig.warmup_enabled }"></span>
            <strong>自动定时预热总开关</strong>
            <ElTag size="small" :type="globalConfig.warmup_enabled ? 'success' : 'info'">
              {{ globalConfig.warmup_enabled ? '后台定时预热中' : '已停用（按需手动预热）' }}
            </ElTag>
          </div>
          <p class="switch-desc">
            默认关闭。开启后，服务端每隔 24 小时在后台主动模拟访问各源站首页与热门分类填入缓存，彻底杜绝冷启动首访等待；关闭后服务绝不在后台自主请求源站。
          </p>
        </div>
        <ElSwitch
          v-model="globalConfig.warmup_enabled"
          :disabled="ui.readOnly || updatingGlobal"
          active-text="开启预热"
          inactive-text="关闭"
          @change="handleSaveGlobalConfig"
        />
      </div>
    </div>

    <!-- 职责说明卡片 -->
    <div class="cache-scope-tip">
      <span class="tip-icon">💡</span>
      <span class="tip-text">
        <strong>缓存中心运维看板</strong>：支持按站点独立预热与清空缓存，实时监控内存占用、命中率与防击穿并发队列。
      </span>
    </div>

    <!-- KPI 统计卡片（纯 Grid 等宽响应式排布） -->
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
          <span>命中: {{ stats?.hits ?? 0 }}</span>
          <span class="foot-sep">/</span>
          <span>穿透: {{ stats?.misses ?? 0 }}</span>
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
        <div class="metric-foot a-muted">同一 Key 瞬间并发合并为 1 次请求</div>
      </ElCard>

      <ElCard shadow="hover" class="metric-card">
        <div class="metric-head">
          <span>默认存活时间</span>
          <span class="a-muted">TTL</span>
        </div>
        <div class="metric-kv">
          <span>首页: {{ stats?.ttl?.home ?? 600 }}s</span>
          <span>列表: {{ stats?.ttl?.category ?? 300 }}s</span>
          <span>详情: {{ stats?.ttl?.detail ?? 300 }}s</span>
        </div>
        <div class="metric-foot a-muted">播放地址不缓存</div>
      </ElCard>
    </div>

    <!-- 分站点缓存矩阵卡片（展示系统全部接入站点状态） -->
    <div v-if="siteSummaries.length > 0" class="site-cache-section">
      <div class="section-title-row">
        <span class="section-title">分站点缓存矩阵卡片 ({{ siteSummaries.length }} 个源站)</span>
        <span class="section-sub">实时展示全量接入源站的缓存落盘现状，支持单站一键预热与即时清空</span>
      </div>
      <div class="site-cache-grid">
        <div v-for="s in siteSummaries" :key="s.site" class="site-cache-card">
          <div class="s-card-top">
            <span class="s-card-name" :title="s.site">{{ s.name }} <small class="a-muted" style="font-weight: normal; font-size: 11px">({{ s.site }})</small></span>
            <ElTag size="small" :type="s.total > 0 ? 'primary' : 'info'" :effect="s.total > 0 ? 'dark' : 'plain'">
              {{ s.total > 0 ? `${s.total} 条缓存` : '无缓存 (冷)' }}
            </ElTag>
          </div>
          <div class="s-card-badges">
            <span class="badge-pill pill-home">首页: {{ s.homeCount }}</span>
            <span class="badge-pill pill-cat">分类: {{ s.categoryCount }}</span>
            <span class="badge-pill pill-detail">详情: {{ s.detailCount }}</span>
          </div>
          <div class="s-card-actions">
            <ElButton
              size="small"
              type="primary"
              plain
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
              :disabled="ui.readOnly"
              @click="handleClearSite(s.site)"
            >
              清空该站
            </ElButton>
          </div>
        </div>
      </div>
    </div>

    <!-- 缓存条目明细（卡片流视图，彻底告别死板表格） -->
    <div class="entries-card-panel">
      <div class="panel-header-bar">
        <div class="bar-left">
          <span class="panel-title">当前内存缓存条目 ({{ filteredEntries.length }})</span>
        </div>
        <div class="bar-right">
          <ElSelect
            v-model="filterNs"
            placeholder="命名空间筛选"
            clearable
            size="small"
            style="width: 140px"
            @change="loadData"
          >
            <ElOption label="全部类型" value="" />
            <ElOption label="首页 (home)" value="home" />
            <ElOption label="分类 (category)" value="category" />
            <ElOption label="详情 (detail)" value="detail" />
          </ElSelect>

          <ElInput
            v-model="searchKw"
            placeholder="检索 Key / 影片ID..."
            size="small"
            :prefix-icon="Search"
            clearable
            style="width: 220px"
          />
        </div>
      </div>

      <!-- 条目卡片网格 -->
      <div v-if="filteredEntries.length > 0" class="entry-cards-grid">
        <div v-for="row in filteredEntries" :key="row.key" class="entry-card">
          <div class="entry-card-header">
            <div class="entry-tags">
              <ElTag size="small" effect="plain">{{ row.site }}</ElTag>
              <ElTag size="small" :type="nsTagType(row.namespace)">{{ row.namespace }}</ElTag>
              <ElTag v-if="row.is_disk" size="small" type="success" effect="plain">L2磁盘镜像</ElTag>
            </div>
            <span class="entry-ttl-pill">
              剩余 {{ row.remaining_seconds }}s
            </span>
          </div>

          <div class="entry-card-body">
            <div class="entry-ident" :title="row.ident || '首页默认'">
              {{ row.ident ? `标识: ${row.ident}` : '全局首页推荐' }}
            </div>
            <code class="entry-full-key" :title="row.key">{{ row.key }}</code>
          </div>

          <div class="entry-card-footer">
            <ElButton
              link
              type="primary"
              size="small"
              :icon="View"
              @click="handleViewEntry(row.key)"
            >
              查看数据
            </ElButton>
            <ElButton
              link
              type="danger"
              size="small"
              :icon="Delete"
              :disabled="ui.readOnly"
              @click="handleClearKey(row.key)"
            >
              删除键
            </ElButton>
          </div>
        </div>
      </div>

      <div v-else class="entries-empty">
        <ElEmpty description="当前未匹配到缓存条目（可点击上方「一键全站预热」或通过前台浏览自动生成）" />
      </div>
    </div>

    <!-- 缓存条目具体内容透视抽屉 -->
    <ElDrawer
      v-model="isEntryDrawerVisible"
      title="缓存数据深层透视"
      size="650px"
      destroy-on-close
    >
      <div v-loading="loadingDetail" class="entry-drawer-box">
        <template v-if="currentEntryDetail">
          <ElDescriptions :column="1" border size="small" class="entry-desc-table">
            <ElDescriptionsItem label="完整 Key">
              <code class="key-code font-bold">{{ currentEntryDetail.key }}</code>
            </ElDescriptionsItem>
            <ElDescriptionsItem label="所属源站">
              <ElTag size="small">{{ currentEntryDetail.site }}</ElTag>
            </ElDescriptionsItem>
            <ElDescriptionsItem label="命名空间">
              <ElTag size="small" :type="nsTagType(currentEntryDetail.namespace)">
                {{ currentEntryDetail.namespace }}
              </ElTag>
            </ElDescriptionsItem>
            <ElDescriptionsItem label="剩余存活 (TTL)">
              <span class="ttl-badge">{{ currentEntryDetail.remaining_seconds }} 秒</span>
            </ElDescriptionsItem>
          </ElDescriptions>

          <div class="data-preview-head">
            <span>内存中反序列化真实数据内容：</span>
            <ElButton
              size="small"
              type="primary"
              plain
              :icon="DocumentCopy"
              @click="copyJson(currentEntryDetail.data)"
            >
              复制 JSON
            </ElButton>
          </div>

          <pre class="json-code-box">{{ JSON.stringify(currentEntryDetail.data, null, 2) }}</pre>
        </template>
      </div>
    </ElDrawer>
  </div>
</template>

<style scoped>
.cache-hub {
  max-width: 1440px;
  margin: 0 auto;
  padding: 24px 32px 64px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.hub-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  padding: 20px 24px;
  background: var(--a-card, #ffffff);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: var(--a-radius, 8px);
  box-shadow: var(--a-shadow-xs, 0 1px 3px rgba(0, 0, 0, 0.05));
}

.hub-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--a-text, #1e293b);
  letter-spacing: -0.01em;
}

.hub-sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--a-text-2, #64748b);
}

.hub-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.global-switch-card {
  display: flex;
  align-items: stretch;
  background: var(--el-bg-color-overlay, #ffffff);
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 18px 24px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
  gap: 24px;
}

.switch-col {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.switch-divider {
  width: 1px;
  background: var(--el-border-color-lighter);
}

.switch-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.switch-badge-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
  color: var(--el-text-color-primary);
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--el-color-info-light-3, #94a3b8);
  transition: all 0.3s ease;
}

.dot--on {
  background: var(--el-color-success, #10b981);
  box-shadow: 0 0 8px rgba(16, 185, 129, 0.6);
}

.switch-desc {
  margin: 0;
  font-size: 12.5px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}

@media (max-width: 900px) {
  .global-switch-card {
    flex-direction: column;
    gap: 16px;
  }
  .switch-divider {
    width: 100%;
    height: 1px;
  }
}

.cache-scope-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.08) 0%, rgba(147, 51, 234, 0.04) 100%);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 12.5px;
  color: var(--el-text-color-regular);
  line-height: 1.5;
}

.tip-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.tip-text strong {
  color: var(--el-text-color-primary);
}

.metric-row {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 4px;
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
  border-radius: 8px;
  min-height: 124px;
}

.metric-card--primary {
  border-top: 3px solid var(--el-color-primary);
}

.metric-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.metric-val {
  margin: 8px 0;
  font-size: 26px;
  font-weight: 800;
  color: var(--el-text-color-primary);
}

.metric-val.highlight {
  color: var(--el-color-primary);
}

.metric-unit {
  font-size: 14px;
  font-weight: 500;
  margin-left: 2px;
}

.metric-sub {
  font-size: 14px;
  font-weight: normal;
  color: var(--el-text-color-placeholder);
}

.metric-foot {
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--el-text-color-secondary);
}

.foot-sep {
  color: var(--el-text-color-placeholder);
}

.metric-kv {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-regular);
  margin: 8px 0;
}

/* 分站点缓存矩阵卡片 */
.site-cache-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.section-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.section-sub {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.site-cache-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
}

.site-cache-card {
  background: var(--a-card, #ffffff);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: all 0.2s ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.site-cache-card:hover {
  border-color: var(--el-color-primary);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.s-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.s-card-name {
  font-weight: 700;
  font-size: 15px;
  color: var(--el-text-color-primary);
}

.s-card-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.badge-pill {
  font-size: 11.5px;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
}

.pill-home {
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
}

.pill-cat {
  background: rgba(16, 185, 129, 0.1);
  color: #059669;
}

.pill-detail {
  background: rgba(245, 158, 11, 0.1);
  color: #d97706;
}

.s-card-actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}

.s-card-actions .el-button {
  flex: 1;
}

/* 条目明细面板与卡片网格 */
.entries-card-panel {
  background: var(--a-card, #ffffff);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: 8px;
  padding: 20px;
}

.panel-header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.panel-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.bar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.entry-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px;
}

.entry-card {
  background: var(--el-fill-color-blank, #ffffff);
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 8px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: all 0.2s ease;
}

.entry-card:hover {
  border-color: var(--el-color-primary);
  background: var(--el-fill-color-light);
}

.entry-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.entry-tags {
  display: flex;
  gap: 6px;
}

.entry-ttl-pill {
  font-size: 11.5px;
  font-family: ui-monospace, monospace;
  font-weight: 600;
  color: var(--el-color-primary);
  background: rgba(59, 130, 246, 0.08);
  padding: 2px 6px;
  border-radius: 4px;
}

.entry-card-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.entry-ident {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.entry-full-key {
  font-family: ui-monospace, SFMono-Regular, monospace;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-light);
  padding: 2px 6px;
  border-radius: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.entry-card-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 4px;
  padding-top: 6px;
  border-top: 1px dashed var(--el-border-color-lighter);
}

.entries-empty {
  padding: 40px 0;
}

.entry-drawer-box {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.data-preview-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  font-size: 13px;
  color: var(--el-text-color-primary);
}

.json-code-box {
  margin: 0;
  padding: 16px;
  background: var(--el-fill-color-dark, #1e1e1e);
  color: #38bdf8;
  border-radius: 8px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12.5px;
  line-height: 1.5;
  max-height: 520px;
  overflow: auto;
  border: 1px solid var(--el-border-color-lighter);
}
</style>
