<script setup lang="ts">
/**
 * 缓存控制中心：
 * 全局命中率看板、容量占用透视、具体内存 Key 实时倒计时列表、
 * 一键主动预热与定向清理。
 */
import {
  ElButton,
  ElCard,
  ElCol,
  ElEmpty,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElProgress,
  ElRow,
  ElSelect,
  ElTable,
  ElTableColumn,
  ElTag,
  ElDrawer,
  ElDescriptions,
  ElDescriptionsItem,
} from 'element-plus'
import {
  Delete,
  Refresh,
  Search,
  VideoPlay,
  View,
  DocumentCopy,
} from '@element-plus/icons-vue'
import { computed, onMounted, ref } from 'vue'

import { clearCache, getCacheEntry, getCacheStats, listCacheKeys, preheatCache } from '@/admin/api'
import { ui } from '@/admin/ui'
import { adminPath } from '@/admin/config'
import type { CacheEntryDetail, CacheKeyEntry, CacheStatsPayload } from '@/api/types'

const loading = ref(false)
const preheating = ref(false)
const stats = ref<CacheStatsPayload | null>(null)
const entries = ref<CacheKeyEntry[]>([])

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
    const [st, keys] = await Promise.all([
      getCacheStats(),
      listCacheKeys(filterSite.value || undefined, filterNs.value || undefined),
    ])
    stats.value = st
    entries.value = keys
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '加载缓存数据失败')
  } finally {
    loading.value = false
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

    <!-- 职责边界整合指引横幅 -->
    <div class="cache-scope-tip">
      <span class="tip-icon">[指南]</span>
      <span class="tip-text">
        <strong>架构运维职责整合说明</strong>：单站点的实时预热与清空已彻底收拢至
        <RouterLink :to="adminPath('/sites')" style="color: var(--el-color-primary); font-weight: 600">「内容源管理」</RouterLink>
        的每个站点卡片上一键操作并查看详细战报；本中心专职负责<strong>全局宏观容量看板、实时命中率监控、所有内存 Key 倒计时审查与全量运维</strong>。
      </span>
    </div>

    <!-- KPI 统计卡片 -->
    <ElRow :gutter="16" class="metric-row">
      <ElCol :xs="24" :sm="12" :md="6">
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
      </ElCol>

      <ElCol :xs="24" :sm="12" :md="6">
        <ElCard shadow="hover" class="metric-card">
          <div class="metric-head">
            <span>已存条目 / 最大容量</span>
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
      </ElCol>

      <ElCol :xs="24" :sm="12" :md="6">
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
      </ElCol>

      <ElCol :xs="24" :sm="12" :md="6">
        <ElCard shadow="hover" class="metric-card">
          <div class="metric-head">
            <span>全局默认存活时间</span>
            <span class="a-muted">TTL</span>
          </div>
          <div class="metric-kv">
            <span>首页: {{ stats?.ttl?.home ?? 600 }}s</span>
            <span>列表: {{ stats?.ttl?.category ?? 300 }}s</span>
            <span>详情: {{ stats?.ttl?.detail ?? 300 }}s</span>
          </div>
          <div class="metric-foot a-muted">播放地址不缓存（时效保护）</div>
        </ElCard>
      </ElCol>
    </ElRow>

    <!-- 缓存条目明细表格 -->
    <ElCard shadow="never" class="table-card">
      <template #header>
        <div class="table-header">
          <div class="table-title">
            <span>当前内存缓存条目清单 ({{ filteredEntries.length }})</span>
          </div>
          <div class="table-filter">
            <ElSelect
              v-model="filterNs"
              placeholder="命名空间"
              clearable
              size="small"
              style="width: 130px"
              @change="loadData"
            >
              <ElOption label="全部类型" value="" />
              <ElOption label="首页 (home)" value="home" />
              <ElOption label="分类 (category)" value="category" />
              <ElOption label="详情 (detail)" value="detail" />
            </ElSelect>

            <ElInput
              v-model="searchKw"
              placeholder="搜索 Key..."
              size="small"
              :prefix-icon="Search"
              clearable
              style="width: 200px"
            />
          </div>
        </div>
      </template>

      <ElTable :data="filteredEntries" stripe size="small" v-loading="loading">
        <ElTableColumn prop="site" label="源站点" width="130">
          <template #default="{ row }">
            <ElTag size="small" effect="light">{{ row.site }}</ElTag>
          </template>
        </ElTableColumn>

        <ElTableColumn prop="namespace" label="命名空间" width="110">
          <template #default="{ row }">
            <ElTag size="small" :type="nsTagType(row.namespace)">{{ row.namespace }}</ElTag>
          </template>
        </ElTableColumn>

        <ElTableColumn prop="ident" label="标识定位符" width="160" show-overflow-tooltip />

        <ElTableColumn prop="key" label="完整缓存 Key" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <code class="key-code">{{ row.key }}</code>
          </template>
        </ElTableColumn>

        <ElTableColumn prop="remaining_seconds" label="剩余存活时间 (TTL)" width="160" sortable>
          <template #default="{ row }">
            <span class="ttl-badge">{{ row.remaining_seconds }} 秒</span>
          </template>
        </ElTableColumn>

        <ElTableColumn label="操作" width="160" align="right">
          <template #default="{ row }">
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
              :disabled="ui.readOnly"
              @click="handleClearKey(row.key)"
            >
              删除此键
            </ElButton>
          </template>
        </ElTableColumn>

        <template #empty>
          <ElEmpty description="内存中暂无缓存数据（可点击上方预热或前台浏览视频自动载入）" />
        </template>
      </ElTable>
    </ElCard>

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
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hub-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.hub-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.hub-sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.hub-actions {
  display: flex;
  align-items: center;
  gap: 8px;
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
  margin-bottom: 4px;
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

.table-card {
  border-radius: 8px;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.table-title {
  font-weight: 600;
  font-size: 15px;
}

.table-filter {
  display: flex;
  align-items: center;
  gap: 8px;
}

.key-code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  background: var(--el-fill-color-light);
  padding: 2px 6px;
  border-radius: 4px;
}

.ttl-badge {
  font-family: ui-monospace, SFMono-Regular, monospace;
  font-size: 12px;
  font-weight: 600;
  color: var(--el-color-primary);
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
