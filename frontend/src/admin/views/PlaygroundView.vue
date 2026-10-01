<script setup lang="ts">
/**
 * Plove Cloud Console - 探针与试播工作台
 *
 * 全面丰富化的多源在线测试中心：
 * 1. 单站深度探针：命令快速切换、自动智能串联测试（免手动输入 vod_id）；
 * 2. 常用预设快捷箱：首页片单即时嗅探、全量分类提取、首部影片详情穿透、真实视频流直放；
 * 3. 全站并发连通性体检矩阵：一键全源并发测速、健康评分对比；
 * 4. 视频流实时试播台：内置播放器、URL 分析与一键复制；
 * 5. 跨源并发搜索比对：多源横向对比返回耗时与匹配数量；
 * 6. 告别空白页面，整体采用卡片网格与专业边距排版。
 */
import {
  ElButton,
  ElCard,
  ElCol,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElOption,
  ElRadioButton,
  ElRadioGroup,
  ElRow,
  ElSelect,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus'
import {
  Aim,
  CopyDocument,
  DataAnalysis,
  Film,
  FolderOpened,
  Refresh,
  Search,
  VideoPlay,
} from '@element-plus/icons-vue'
import { computed, onMounted, ref } from 'vue'

import { listSites, probePlayground, searchAggregate } from '@/admin/api'
import type {
  AdminSiteItem,
  AggregateSearchPayload,
  PlaygroundProbeResult,
} from '@/api/types'

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
interface MatrixItem {
  site: string
  name: string
  status: 'pending' | 'testing' | 'success' | 'error'
  elapsed_ms?: number
  items_count?: number
  cache_hit?: boolean
  error?: string
}

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

onMounted(() => {
  void loadSites()
})

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

// ------------------------------------------------------------------ 智能预设测试（免手动输入 ID！）
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
</script>

<template>
  <div class="playground-page">
    <!-- 顶部工作台导航条 -->
    <div class="workbench-bar">
      <div class="workbench-header-text">
        <h1 class="workbench-title">探针与在线试播台</h1>
        <p class="workbench-desc">
          提供单站深度调试、全源并发连通性体检、HLS流媒体试播与跨源聚合搜索比对。
        </p>
      </div>
      <div class="workbench-tabs">
        <ElRadioGroup v-model="activeTab" size="default">
          <ElRadioButton value="probe">单站在线探针</ElRadioButton>
          <ElRadioButton value="matrix">全站并发连通性体检</ElRadioButton>
          <ElRadioButton value="search">跨源并发搜索比对</ElRadioButton>
        </ElRadioGroup>
      </div>
    </div>

    <!-- ==================== Tab 1: 单站在线探针 ==================== -->
    <div v-if="activeTab === 'probe'" class="tab-panel">
      <!-- 快捷智能预设箱（免手动填 ID） -->
      <div class="preset-box">
        <div class="preset-title-row">
          <span class="preset-title">常用智能测试预设（免手动找影片 ID，点击直接全自动串联测试）：</span>
          <span class="preset-sub">针对当前选定站点：<strong>{{ probeForm.site || '未选择' }}</strong></span>
        </div>
        <div class="preset-buttons">
          <ElButton :icon="Film" size="default" :loading="probing" @click="handleQuickPreset('home')">
            探测首页推荐片单
          </ElButton>
          <ElButton :icon="FolderOpened" size="default" :loading="probing" @click="handleQuickPreset('category')">
            提取分类与子标签树
          </ElButton>
          <ElButton :icon="DataAnalysis" type="primary" plain size="default" :loading="probing" @click="handleQuickPreset('detail_auto')">
            自动抽片测试详情页
          </ElButton>
          <ElButton :icon="VideoPlay" type="primary" size="default" :loading="probing" @click="handleQuickPreset('play_auto')">
            自动抽片测试视频试播
          </ElButton>
        </div>
      </div>

      <!-- 控制面板卡片 -->
      <ElCard shadow="never" class="panel-card">
        <ElForm :model="probeForm" label-position="top" inline class="custom-form">
          <ElFormItem label="目标内容源">
            <ElSelect v-model="probeForm.site" style="width: 200px">
              <ElOption
                v-for="s in sites"
                :key="s.key"
                :label="`${s.name} (${s.key})`"
                :value="s.key"
              />
            </ElSelect>
          </ElFormItem>

          <ElFormItem label="探测命令">
            <ElRadioGroup v-model="probeForm.command">
              <ElRadioButton value="home">首页推荐</ElRadioButton>
              <ElRadioButton value="category">分类列表</ElRadioButton>
              <ElRadioButton value="detail">影片详情</ElRadioButton>
              <ElRadioButton value="play">播放解析</ElRadioButton>
            </ElRadioGroup>
          </ElFormItem>

          <ElFormItem v-if="probeForm.command === 'category'" label="分类 ID (tid)">
            <ElInput v-model="probeForm.tid" placeholder="留空为默认全部" style="width: 130px" />
          </ElFormItem>

          <ElFormItem v-if="probeForm.command === 'category'" label="页码 (page)">
            <ElInputNumber v-model="probeForm.page" :min="1" :max="999" style="width: 110px" />
          </ElFormItem>

          <ElFormItem
            v-if="probeForm.command === 'detail' || probeForm.command === 'play'"
            label="影片 ID (vod_id)"
          >
            <ElInput v-model="probeForm.vod_id" placeholder="输入 ID 或点击上方预设" style="width: 200px" />
          </ElFormItem>

          <ElFormItem v-if="probeForm.command === 'play'" label="集数 (ep)">
            <ElInputNumber v-model="probeForm.ep" :min="1" :max="9999" style="width: 100px" />
          </ElFormItem>

          <ElFormItem label="缓存控制">
            <ElSwitch v-model="probeForm.bypass_cache" active-text="强制绕过缓存 (查源现抓)" />
          </ElFormItem>

          <ElFormItem label="&nbsp;">
            <ElButton
              type="primary"
              :icon="Aim"
              :loading="probing"
              @click="handleRunProbe"
            >
              发送探测请求
            </ElButton>
          </ElFormItem>
        </ElForm>
      </ElCard>

      <!-- 探测结果展示区 -->
      <div v-if="probeResult" class="result-box">
        <!-- 核心指标条 -->
        <ElRow :gutter="16" class="metrics-row">
          <ElCol :xs="24" :sm="8">
            <div class="metric-block">
              <span class="metric-title">网络响应耗时</span>
              <div class="metric-num" :class="probeResult.elapsed_ms < 600 ? 'text-good' : 'text-warn'">
                {{ probeResult.elapsed_ms }}
                <span class="unit">ms</span>
              </div>
              <span class="metric-note">{{ probeResult.elapsed_ms < 600 ? '响应敏捷' : '网络抓取耗时稍高' }}</span>
            </div>
          </ElCol>

          <ElCol :xs="24" :sm="8">
            <div class="metric-block">
              <span class="metric-title">缓存感知状态</span>
              <div class="metric-num">
                <ElTag
                  :type="probeResult.cache_hit ? 'success' : 'info'"
                  size="large"
                  effect="light"
                  class="big-tag"
                >
                  {{ probeResult.cache_hit ? 'CACHE HIT (命中缓存)' : 'CRAWLER MISS (查源现抓)' }}
                </ElTag>
              </div>
              <span class="metric-note">{{ probeResult.cache_hit ? '0 秒极速从内存返回' : '通过外部爬虫实时抓取源站' }}</span>
            </div>
          </ElCol>

          <ElCol :xs="24" :sm="8">
            <div class="metric-block">
              <span class="metric-title">HTTP 响应审计</span>
              <div class="metric-num">
                <ElTag :type="probeResult.status === 'OK' ? 'success' : 'danger'" size="large" class="big-tag">
                  {{ probeResult.status === 'OK' ? '200 OK 正常' : '执行异常' }}
                </ElTag>
              </div>
              <span class="metric-note">{{ probeResult.error_detail ? probeResult.error_detail : '无任何告警与异常' }}</span>
            </div>
          </ElCol>
        </ElRow>

        <!-- 播放器试播预览（如果命令是 play 且含有播放地址） -->
        <div v-if="probeResult.command === 'play' && probeResult.playback_url" class="player-panel">
          <div class="panel-head">
            <div class="head-left">
              <ElIcon :size="18"><VideoPlay /></ElIcon>
              <span class="head-title">视频流实时试播台</span>
            </div>
            <div class="head-actions">
              <code class="url-badge">{{ probeResult.playback_url }}</code>
              <ElButton size="small" :icon="CopyDocument" @click="copyText(probeResult.playback_url!)">
                复制地址
              </ElButton>
            </div>
          </div>
          <div class="video-container">
            <video :src="probeResult.playback_url" controls autoplay class="real-player">
              您的浏览器不支持此视频流播放
            </video>
          </div>
        </div>

        <!-- 视觉影视海报网格（如果含有列表） -->
        <div v-if="previewItemList.length > 0" class="items-preview-panel">
          <div class="panel-head">
            <div class="head-left">
              <ElIcon :size="18"><Film /></ElIcon>
              <span class="head-title">抓取到的片单视觉卡片列表 ({{ previewItemList.length }} 部)</span>
            </div>
          </div>
          <div class="movie-grid">
            <div v-for="(item, idx) in previewItemList.slice(0, 12)" :key="idx" class="movie-card">
              <div class="movie-poster">
                <img
                  v-if="item.cover || item.poster || item.pic"
                  :src="item.cover || item.poster || item.pic"
                  alt="海报"
                  loading="lazy"
                  class="poster-img"
                />
                <div v-else class="poster-placeholder">无海报</div>
                <div v-if="item.episodes || item.remarks" class="movie-badge">
                  {{ item.episodes || item.remarks }}
                </div>
              </div>
              <div class="movie-meta">
                <div class="movie-title" :title="item.title || item.name">{{ item.title || item.name }}</div>
                <div class="movie-sub">ID: {{ item.id || item.vod_id }} · {{ item.category || item.type_name || '精选' }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 原始 vs 洗后 JSON 差分对比 -->
        <ElCard shadow="never" class="json-inspect-card">
          <template #header>
            <div class="json-header-row">
              <div class="json-header-tabs">
                <ElRadioGroup v-model="jsonTab" size="small">
                  <ElRadioButton value="cleaned">清洗加工后结构 (Cleaned)</ElRadioButton>
                  <ElRadioButton value="raw">爬虫原始返回 (Raw)</ElRadioButton>
                </ElRadioGroup>
              </div>
              <ElButton size="small" :icon="CopyDocument" @click="copyText(formatJson(jsonTab === 'cleaned' ? probeResult.cleaned_data : probeResult.raw_data))">
                复制当前 JSON
              </ElButton>
            </div>
          </template>
          <pre class="json-viewer-box">{{ formatJson(jsonTab === 'cleaned' ? probeResult.cleaned_data : probeResult.raw_data) }}</pre>
        </ElCard>
      </div>

      <!-- 尚未探测时的功能引导区（替代以前单一空盒子） -->
      <div v-else class="guide-grid">
        <div class="guide-card" @click="handleQuickPreset('home')">
          <div class="guide-icon"><Film /></div>
          <div class="guide-title">一键嗅探首页片单</div>
          <div class="guide-desc">即时触发爬虫拉取当前源的首页推荐影片，查看封面与标题解析是否完整。</div>
        </div>

        <div class="guide-card" @click="handleQuickPreset('category')">
          <div class="guide-icon"><FolderOpened /></div>
          <div class="guide-title">全分类标签树解析</div>
          <div class="guide-desc">提取所有主分类与子分类标签，检查是否有需要加入黑名单的非法类目。</div>
        </div>

        <div class="guide-card" @click="handleQuickPreset('detail_auto')">
          <div class="guide-icon"><DataAnalysis /></div>
          <div class="guide-title">智能提取影片详情</div>
          <div class="guide-desc">系统全自动提取首页第 1 部影视并穿透至详情页，校验剧集列表与演职员字段。</div>
        </div>

        <div class="guide-card" @click="handleQuickPreset('play_auto')">
          <div class="guide-icon"><VideoPlay /></div>
          <div class="guide-title">视频播放流在线直放</div>
          <div class="guide-desc">自动解析首部影视第 1 集的真实 m3u8/mp4 视频流地址，并在内嵌播放器试播。</div>
        </div>
      </div>
    </div>

    <!-- ==================== Tab 2: 全站并发连通性体检矩阵 ==================== -->
    <div v-else-if="activeTab === 'matrix'" class="tab-panel">
      <div class="matrix-hero">
        <div class="matrix-hero-info">
          <h2 class="matrix-title">全站内容源并发体检中心</h2>
          <p class="matrix-desc">
            并发向所有内容源发起连通性探测，毫秒级分析各站响应延迟、首页可用率与抓取状态。
          </p>
        </div>
        <ElButton
          type="primary"
          size="large"
          :icon="Refresh"
          :loading="matrixTesting"
          @click="runFullMatrixTest"
        >
          {{ matrixTesting ? '正在并发体检中...' : '发起全站一键并发体检' }}
        </ElButton>
      </div>

      <div class="matrix-table-card">
        <ElTable :data="matrixList" size="default" style="width: 100%">
          <ElTableColumn prop="name" label="内容源名称" min-width="180">
            <template #default="{ row }">
              <span class="font-bold">{{ row.name }}</span>
              <span class="a-muted" style="margin-left: 6px; font-size: 12px">({{ row.site }})</span>
            </template>
          </ElTableColumn>

          <ElTableColumn label="体检状态" width="140">
            <template #default="{ row }">
              <ElTag v-if="row.status === 'success'" type="success" size="small" effect="light">服务正常</ElTag>
              <ElTag v-else-if="row.status === 'testing'" type="warning" size="small">探测中...</ElTag>
              <ElTag v-else-if="row.status === 'error'" type="danger" size="small">连通异常</ElTag>
              <ElTag v-else type="info" size="small">就绪待体检</ElTag>
            </template>
          </ElTableColumn>

          <ElTableColumn label="网络响应延迟" width="160">
            <template #default="{ row }">
              <span v-if="row.elapsed_ms !== undefined" class="font-mono font-bold" :class="row.elapsed_ms < 600 ? 'text-good' : 'text-warn'">
                {{ row.elapsed_ms }} ms
              </span>
              <span v-else class="text-muted">—</span>
            </template>
          </ElTableColumn>

          <ElTableColumn label="首页影视拉取数" width="150" align="center">
            <template #default="{ row }">
              <span v-if="row.items_count !== undefined" class="font-mono font-bold">{{ row.items_count }} 部</span>
              <span v-else class="text-muted">—</span>
            </template>
          </ElTableColumn>

          <ElTableColumn label="异常诊断与备注" min-width="240">
            <template #default="{ row }">
              <span v-if="row.error" class="text-danger">{{ row.error }}</span>
              <span v-else-if="row.status === 'success'" class="text-good">协议通畅，抓取成功</span>
              <span v-else class="text-muted">点击上方按钮发起体检</span>
            </template>
          </ElTableColumn>
        </ElTable>
      </div>
    </div>

    <!-- ==================== Tab 3: 跨源并发搜索比对 ==================== -->
    <div v-else class="tab-panel">
      <ElCard shadow="never" class="panel-card">
        <div class="search-hero-box">
          <div class="search-input-line">
            <ElInput
              v-model="searchKw"
              placeholder="输入片名关键词（如：繁花、庆余年、斗罗大陆）..."
              size="large"
              :prefix-icon="Search"
              clearable
              style="max-width: 520px"
              @keyup.enter="handleAggregateSearch"
            />
            <ElButton
              type="primary"
              size="large"
              :icon="Search"
              :loading="searching"
              @click="handleAggregateSearch"
            >
              并发全网检索
            </ElButton>
          </div>
          <div class="hot-words-line">
            <span class="hot-label">快速测试热词：</span>
            <ElButton link size="small" @click="quickSearch('庆余年')">庆余年</ElButton>
            <ElButton link size="small" @click="quickSearch('繁花')">繁花</ElButton>
            <ElButton link size="small" @click="quickSearch('仙逆')">仙逆</ElButton>
            <ElButton link size="small" @click="quickSearch('斗罗大陆')">斗罗大陆</ElButton>
            <ElButton link size="small" @click="quickSearch('凡人修仙传')">凡人修仙传</ElButton>
          </div>
        </div>
      </ElCard>

      <!-- 搜索比对结果 -->
      <div v-if="searchResult" class="search-result-box">
        <div class="search-summary-card">
          <div class="summary-item">
            <span class="label">查询关键词</span>
            <span class="val font-bold">{{ searchResult.kw }}</span>
          </div>
          <div class="summary-item">
            <span class="label">并发源站数</span>
            <span class="val">{{ searchResult.total_sites }} 个</span>
          </div>
          <div class="summary-item">
            <span class="label">累计命中影视</span>
            <span class="val text-good font-bold">{{ searchResult.total_count }} 部</span>
          </div>
        </div>

        <!-- 按站点分组展示比对 -->
        <div v-for="res in searchResult.results" :key="res.site" class="site-search-group">
          <div class="site-group-head">
            <div class="group-title-box">
              <span class="site-name">{{ res.site_name }}</span>
              <span class="site-key font-mono">({{ res.site }})</span>
              <ElTag :type="!res.error ? 'success' : 'danger'" size="small">
                {{ !res.error ? `命中 ${res.count} 部` : '搜索超时或异常' }}
              </ElTag>
            </div>
            <div class="group-metrics">
              <span class="metric-text font-mono">耗时 {{ res.elapsed_ms }}ms</span>
            </div>
          </div>

          <div v-if="res.items?.length" class="site-movie-grid">
            <div v-for="(it, i) in (res.items as any[])" :key="i" class="search-movie-card">
              <div class="movie-title" :title="it.title">{{ it.title }}</div>
              <div class="movie-extra">ID: {{ it.id }} · {{ it.category || '默认' }}</div>
            </div>
          </div>
          <div v-else-if="!res.error" class="site-empty-text">该站未检索到与关键词匹配的片单</div>
          <div v-else class="site-error-text">{{ res.error }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.playground-page {
  max-width: 1440px;
  margin: 0 auto;
  padding: 24px 32px 64px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 顶部工作台 */
.workbench-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
  padding: 20px 24px;
  background: var(--a-card);
  border: 1px solid var(--a-border);
  border-radius: var(--a-radius);
  box-shadow: var(--a-shadow-xs);
}

.workbench-title {
  font-size: 20px;
  font-weight: 800;
  margin: 0 0 4px 0;
  color: var(--a-text);
  letter-spacing: -0.02em;
}

.workbench-desc {
  font-size: 13px;
  color: var(--a-text-2);
  margin: 0;
}

.tab-panel {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* 预设箱 */
.preset-box {
  background: linear-gradient(135deg, rgba(79, 70, 229, 0.06) 0%, rgba(6, 182, 212, 0.04) 100%);
  border: 1px solid rgba(79, 70, 229, 0.15);
  border-radius: var(--a-radius);
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.preset-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 13px;
}

.preset-title {
  font-weight: 700;
  color: var(--a-brand);
}

.preset-sub {
  color: var(--a-text-2);
}

.preset-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

/* 表单卡片 */
.panel-card {
  border-radius: var(--a-radius);
  border: 1px solid var(--a-border);
  background: var(--a-card);
}

.custom-form {
  margin-bottom: -18px;
}

/* 引导大卡片群 (替代空盒子) */
.guide-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
  margin-top: 10px;
}

.guide-card {
  background: var(--a-card);
  border: 1px solid var(--a-border);
  border-radius: var(--a-radius);
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  cursor: pointer;
  transition: all 0.25s ease;
  box-shadow: var(--a-shadow-xs);
}

.guide-card:hover {
  transform: translateY(-3px);
  border-color: var(--a-brand);
  box-shadow: var(--a-shadow-1);
}

.guide-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  background: var(--a-bg-subtle);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  color: var(--a-brand);
}

.guide-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--a-text);
}

.guide-desc {
  font-size: 12.5px;
  color: var(--a-text-3);
  line-height: 1.6;
}

/* 结果区 */
.result-box {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.metrics-row {
  margin-bottom: 2px;
}

.metric-block {
  background: var(--a-card);
  border: 1px solid var(--a-border);
  border-radius: var(--a-radius);
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  box-shadow: var(--a-shadow-xs);
}

.metric-title {
  font-size: 12.5px;
  color: var(--a-text-3);
}

.metric-num {
  font-size: 24px;
  font-weight: 800;
  font-family: 'JetBrains Mono', monospace;
  color: var(--a-text);
}

.metric-num .unit {
  font-size: 13px;
  color: var(--a-text-3);
}

.metric-note {
  font-size: 12px;
  color: var(--a-text-2);
}

.big-tag {
  font-size: 13px;
  font-weight: 600;
}

/* 播放器试播 */
.player-panel {
  background: var(--a-card);
  border: 1px solid var(--a-border);
  border-radius: var(--a-radius);
  overflow: hidden;
  box-shadow: var(--a-shadow-xs);
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding: 14px 20px;
  background: var(--a-bg-subtle);
  border-bottom: 1px solid var(--a-border);
}

.head-left {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  font-size: 14.5px;
}

.head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.url-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11.5px;
  background: var(--a-card);
  border: 1px solid var(--a-border);
  padding: 3px 8px;
  border-radius: 4px;
  max-width: 480px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.video-container {
  padding: 20px;
  background: #000000;
  display: flex;
  justify-content: center;
}

.real-player {
  max-height: 420px;
  width: 100%;
  max-width: 800px;
  border-radius: 8px;
  outline: none;
}

/* 海报预览网格 */
.items-preview-panel {
  background: var(--a-card);
  border: 1px solid var(--a-border);
  border-radius: var(--a-radius);
  padding: 18px 20px;
}

.movie-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 14px;
  margin-top: 14px;
}

.movie-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.movie-poster {
  width: 100%;
  aspect-ratio: 2 / 3;
  border-radius: 8px;
  overflow: hidden;
  background: var(--a-bg-subtle);
  position: relative;
  border: 1px solid var(--a-border);
}

.poster-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.poster-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: var(--a-text-3);
}

.movie-badge {
  position: absolute;
  bottom: 4px;
  right: 4px;
  background: rgba(0, 0, 0, 0.75);
  color: #ffffff;
  font-size: 10px;
  padding: 2px 5px;
  border-radius: 4px;
}

.movie-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.movie-title {
  font-size: 12.5px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.movie-sub {
  font-size: 11px;
  color: var(--a-text-3);
}

/* JSON 审查器 */
.json-inspect-card {
  border-radius: var(--a-radius);
  border: 1px solid var(--a-border);
}

.json-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.json-viewer-box {
  margin: 0;
  background: var(--a-bg-subtle);
  padding: 16px;
  border-radius: 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12.5px;
  line-height: 1.5;
  max-height: 480px;
  overflow: auto;
}

/* 体检矩阵 */
.matrix-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
  padding: 24px 28px;
  background: linear-gradient(135deg, rgba(79, 70, 229, 0.08) 0%, rgba(16, 185, 129, 0.05) 100%);
  border: 1px solid var(--a-border);
  border-radius: var(--a-radius);
}

.matrix-title {
  font-size: 18px;
  font-weight: 800;
  margin: 0 0 4px 0;
}

.matrix-desc {
  font-size: 13px;
  color: var(--a-text-2);
  margin: 0;
}

.matrix-table-card {
  background: var(--a-card);
  border: 1px solid var(--a-border);
  border-radius: var(--a-radius);
  overflow: hidden;
}

/* 聚合搜索 */
.search-hero-box {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.search-input-line {
  display: flex;
  align-items: center;
  gap: 12px;
}

.hot-words-line {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
}

.hot-label {
  color: var(--a-text-3);
}

.search-result-box {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.search-summary-card {
  display: flex;
  gap: 32px;
  padding: 16px 20px;
  background: var(--a-card);
  border: 1px solid var(--a-border);
  border-radius: var(--a-radius);
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12.5px;
}

.summary-item .label {
  color: var(--a-text-3);
}

.summary-item .val {
  font-size: 16px;
}

.site-search-group {
  background: var(--a-card);
  border: 1px solid var(--a-border);
  border-radius: var(--a-radius);
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.site-group-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.group-title-box {
  display: flex;
  align-items: center;
  gap: 8px;
}

.site-name {
  font-weight: 700;
  font-size: 15px;
}

.site-key {
  font-size: 12px;
  color: var(--a-text-3);
}

.site-movie-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
}

.search-movie-card {
  background: var(--a-bg-subtle);
  border: 1px solid var(--a-border);
  border-radius: 6px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.movie-extra {
  font-size: 11px;
  color: var(--a-text-3);
}

.site-empty-text {
  font-size: 12.5px;
  color: var(--a-text-3);
  padding: 10px 0;
}

.site-error-text {
  font-size: 12.5px;
  color: var(--el-color-danger);
  padding: 10px 0;
}

/* 颜色工具类 */
.text-good {
  color: var(--el-color-success);
}

.text-warn {
  color: var(--el-color-warning);
}

.text-danger {
  color: var(--el-color-danger);
}

.text-muted {
  color: var(--a-text-3);
}

.font-bold {
  font-weight: 700;
}

.font-mono {
  font-family: 'JetBrains Mono', monospace;
}
</style>
