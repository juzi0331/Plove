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
  RefreshRight,
  Search,
  TopRight,
  VideoPlay,
  Warning,
} from '@element-plus/icons-vue'
import Hls from 'hls.js'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

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

// ------------------------------------------------------------------ HLS 试播播放器内核
const videoPlayerRef = ref<HTMLVideoElement | null>(null)
let hlsInstance: Hls | null = null
const videoStatus = ref<'idle' | 'loading' | 'playing' | 'paused' | 'error'>('idle')
const videoErrorMsg = ref('')
const videoResolution = ref('')
const videoDuration = ref(0)
const videoCurrentTime = ref(0)
const currentRate = ref(1.0)

function cleanupHls(): void {
  if (hlsInstance) {
    hlsInstance.destroy()
    hlsInstance = null
  }
}

function initVideoPlayer(url: string): void {
  cleanupHls()
  const video = videoPlayerRef.value
  if (!video || !url) return

  videoStatus.value = 'loading'
  videoErrorMsg.value = ''
  videoResolution.value = ''
  videoDuration.value = 0
  videoCurrentTime.value = 0

  const isM3u8 = url.includes('.m3u8') || url.includes('m3u8')

  if (isM3u8 && Hls.isSupported()) {
    hlsInstance = new Hls({
      enableWorker: true,
      lowLatencyMode: true,
    })
    hlsInstance.loadSource(url)
    hlsInstance.attachMedia(video)
    hlsInstance.on(Hls.Events.MANIFEST_PARSED, (_event, data) => {
      videoStatus.value = 'playing'
      if (data.levels && data.levels.length > 0) {
        const topLevel = data.levels[data.levels.length - 1]
        if (topLevel.width && topLevel.height) {
          videoResolution.value = `${topLevel.width}×${topLevel.height}`
        }
      }
      video.play().catch(() => {
        videoStatus.value = 'paused'
      })
    })
    hlsInstance.on(Hls.Events.ERROR, (_event, data) => {
      if (data.fatal) {
        videoStatus.value = 'error'
        videoErrorMsg.value = `HLS 流加载异常: ${data.details || '源站跨域限制 (CORS) 或切片已失效'}`
      }
    })
  } else if (video.canPlayType('application/vnd.apple.mpegurl') || !isM3u8) {
    video.src = url
    video.play().then(() => {
      videoStatus.value = 'playing'
    }).catch(() => {
      videoStatus.value = 'paused'
    })
  } else {
    video.src = url
  }
}

function setPlaybackRate(rate: number): void {
  currentRate.value = rate
  if (videoPlayerRef.value) {
    videoPlayerRef.value.playbackRate = rate
  }
}

function onTimeUpdate(): void {
  if (videoPlayerRef.value) {
    videoCurrentTime.value = Math.floor(videoPlayerRef.value.currentTime)
    videoDuration.value = Math.floor(videoPlayerRef.value.duration || 0)
    if (!videoResolution.value && videoPlayerRef.value.videoWidth) {
      videoResolution.value = `${videoPlayerRef.value.videoWidth}×${videoPlayerRef.value.videoHeight}`
    }
  }
}

function onVideoPlay(): void {
  videoStatus.value = 'playing'
}

function onVideoPause(): void {
  videoStatus.value = 'paused'
}

function onVideoWaiting(): void {
  videoStatus.value = 'loading'
}

function onVideoError(): void {
  videoStatus.value = 'error'
  if (!videoErrorMsg.value) {
    videoErrorMsg.value = '视频流无法播放，可能受到源站防盗链/CORS限制'
  }
}

function formatDuration(sec: number): string {
  if (!sec || isNaN(sec)) return '00:00'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`
}

function reloadStream(): void {
  if (probeResult.value?.playback_url) {
    initVideoPlayer(probeResult.value.playback_url)
  }
}

function openStreamExternal(): void {
  if (probeResult.value?.playback_url) {
    window.open(probeResult.value.playback_url, '_blank')
  }
}

watch(
  () => probeResult.value?.playback_url,
  (newUrl) => {
    if (newUrl && probeResult.value?.command === 'play') {
      nextTick(() => {
        initVideoPlayer(newUrl)
      })
    }
  }
)

onBeforeUnmount(() => {
  cleanupHls()
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
      <!-- 顶部控制与源站切换卡片 -->
      <div class="probe-toolbar-card">
        <div class="toolbar-left">
          <span class="toolbar-label">调试目标源：</span>
          <ElSelect v-model="probeForm.site" style="width: 240px">
            <ElOption
              v-for="s in sites"
              :key="s.key"
              :label="`${s.name} (${s.key})`"
              :value="s.key"
            />
          </ElSelect>
        </div>
        <div class="toolbar-right">
          <ElSwitch v-model="probeForm.bypass_cache" active-text="强制穿透源站 (跳过缓存)" />
        </div>
      </div>

      <!-- 「4步全链路体检工作流」卡片矩阵（彻底去重） -->
      <div class="workflow-cards-grid">
        <!-- 步骤 1: 首页推荐 -->
        <div
          class="workflow-card"
          :class="{ 'is-active': probeForm.command === 'home' }"
          @click="probeForm.command = 'home'"
        >
          <div class="wf-header">
            <span class="wf-badge">步骤 1</span>
            <ElIcon :size="20"><Film /></ElIcon>
          </div>
          <div class="wf-title">首页推荐嗅探</div>
          <div class="wf-desc">提取源站首页骨架与推荐片单</div>
          <div class="wf-btn-box">
            <ElButton
              size="small"
              type="primary"
              :loading="probing && probeForm.command === 'home'"
              @click.stop="handleQuickPreset('home')"
            >
              一键探测首页
            </ElButton>
          </div>
        </div>

        <!-- 步骤 2: 分类提取 -->
        <div
          class="workflow-card"
          :class="{ 'is-active': probeForm.command === 'category' }"
          @click="probeForm.command = 'category'"
        >
          <div class="wf-header">
            <span class="wf-badge">步骤 2</span>
            <ElIcon :size="20"><FolderOpened /></ElIcon>
          </div>
          <div class="wf-title">分类标签抽样</div>
          <div class="wf-desc">提取所有主分类与二级标签树</div>
          <div class="wf-btn-box">
            <ElButton
              size="small"
              type="primary"
              :loading="probing && probeForm.command === 'category'"
              @click.stop="handleQuickPreset('category')"
            >
              一键提取分类
            </ElButton>
          </div>
        </div>

        <!-- 步骤 3: 详情穿透 -->
        <div
          class="workflow-card"
          :class="{ 'is-active': probeForm.command === 'detail' }"
          @click="probeForm.command = 'detail'"
        >
          <div class="wf-header">
            <span class="wf-badge">步骤 3</span>
            <ElIcon :size="20"><DataAnalysis /></ElIcon>
          </div>
          <div class="wf-title">详情全量穿透</div>
          <div class="wf-desc">自动抽片提取剧集、线路与简介</div>
          <div class="wf-btn-box">
            <ElButton
              size="small"
              type="primary"
              plain
              :loading="probing && probeForm.command === 'detail'"
              @click.stop="handleQuickPreset('detail_auto')"
            >
              自动抽片测详情
            </ElButton>
          </div>
        </div>

        <!-- 步骤 4: 播放嗅探 -->
        <div
          class="workflow-card"
          :class="{ 'is-active': probeForm.command === 'play' }"
          @click="probeForm.command = 'play'"
        >
          <div class="wf-header">
            <span class="wf-badge">步骤 4</span>
            <ElIcon :size="20"><VideoPlay /></ElIcon>
          </div>
          <div class="wf-title">视频播放流嗅探</div>
          <div class="wf-desc">解析真实 m3u8 并直接在播放器试播</div>
          <div class="wf-btn-box">
            <ElButton
              size="small"
              type="success"
              :loading="probing && probeForm.command === 'play'"
              @click.stop="handleQuickPreset('play_auto')"
            >
              自动抽片试播
            </ElButton>
          </div>
        </div>
      </div>

      <!-- 可选手填自定义参数栏（高级运维输入特定 ID） -->
      <div v-if="probeForm.command === 'category' || probeForm.command === 'detail' || probeForm.command === 'play'" class="custom-param-bar">
        <span class="param-tip">自定义参数调试：</span>
        <template v-if="probeForm.command === 'category'">
          <span class="param-label">分类 ID (tid):</span>
          <ElInput v-model="probeForm.tid" placeholder="留空为全部" size="small" style="width: 140px" />
          <span class="param-label">页码:</span>
          <ElInputNumber v-model="probeForm.page" :min="1" :max="999" size="small" style="width: 100px" />
        </template>
        <template v-if="probeForm.command === 'detail' || probeForm.command === 'play'">
          <span class="param-label">影片 ID (vod_id):</span>
          <ElInput v-model="probeForm.vod_id" placeholder="输入 ID 或点击上方卡片自动抽片" size="small" style="width: 220px" />
        </template>
        <template v-if="probeForm.command === 'play'">
          <span class="param-label">集数 (ep):</span>
          <ElInputNumber v-model="probeForm.ep" :min="1" :max="9999" size="small" style="width: 90px" />
        </template>
        <ElButton type="primary" size="small" :icon="Aim" :loading="probing" style="margin-left: 12px" @click="handleRunProbe">
          以自定义参数执行
        </ElButton>
      </div>

      <!-- 探测结果展示区（大屏卡片化排布） -->
      <div v-if="probeResult" class="result-box">
        <!-- 核心指标卡片 -->
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
              <ElIcon :size="20"><VideoPlay /></ElIcon>
              <span class="head-title">视频流实时试播台 (HLS / m3u8)</span>
              <!-- 播放状态徽章 -->
              <ElTag
                v-if="videoStatus === 'playing'"
                type="success"
                effect="dark"
                size="small"
              >
                🟢 正在播放
              </ElTag>
              <ElTag
                v-else-if="videoStatus === 'loading'"
                type="warning"
                effect="dark"
                size="small"
              >
                🟡 缓冲就绪中...
              </ElTag>
              <ElTag
                v-else-if="videoStatus === 'paused'"
                type="info"
                effect="plain"
                size="small"
              >
                ⏸ 已暂停
              </ElTag>
              <ElTag
                v-else-if="videoStatus === 'error'"
                type="danger"
                effect="dark"
                size="small"
              >
                🔴 播放受限
              </ElTag>

              <!-- 分辨率与时长 -->
              <ElTag v-if="videoResolution" size="small" type="primary" effect="plain">
                {{ videoResolution }}
              </ElTag>
              <span v-if="videoDuration > 0" class="time-counter a-muted font-mono">
                {{ formatDuration(videoCurrentTime) }} / {{ formatDuration(videoDuration) }}
              </span>
            </div>

            <div class="head-actions">
              <!-- 倍速选择 -->
              <div class="speed-group">
                <span
                  v-for="rate in [1.0, 1.25, 1.5, 2.0]"
                  :key="rate"
                  class="speed-btn"
                  :class="{ active: currentRate === rate }"
                  @click="setPlaybackRate(rate)"
                >
                  {{ rate }}x
                </span>
              </div>

              <ElButton size="small" :icon="RefreshRight" @click="reloadStream">
                重新加载
              </ElButton>
              <ElButton size="small" :icon="TopRight" @click="openStreamExternal">
                新窗口播放
              </ElButton>
              <ElButton size="small" :icon="CopyDocument" @click="copyText(probeResult.playback_url!)">
                复制地址
              </ElButton>
            </div>
          </div>

          <!-- 播放地址提示 -->
          <div class="url-bar">
            <span class="url-label">视频流直链:</span>
            <code class="url-badge">{{ probeResult.playback_url }}</code>
          </div>

          <!-- 播放器容器 -->
          <div class="video-container">
            <video
              ref="videoPlayerRef"
              controls
              playsinline
              class="real-player"
              @timeupdate="onTimeUpdate"
              @play="onVideoPlay"
              @pause="onVideoPause"
              @waiting="onVideoWaiting"
              @error="onVideoError"
            >
              您的浏览器不支持此视频流播放
            </video>
          </div>

          <!-- 错误提示 / 跨域指引 -->
          <div v-if="videoStatus === 'error'" class="video-error-bar">
            <ElIcon :size="16" style="margin-right: 6px;"><Warning /></ElIcon>
            <span>{{ videoErrorMsg }}。提示：部分源站切片限制当前网页同源播放，可点击右上角「新窗口播放」直接通过浏览器原生流媒体插件解析。</span>
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

      <!-- 尚未探测时的就绪引导卡片 -->
      <div v-else class="ready-banner-card">
        <div class="ready-icon"><ElIcon :size="28"><Aim /></ElIcon></div>
        <div class="ready-title">在线探针控制台已就绪</div>
        <div class="ready-sub">点击上方「步骤 1 ~ 4」任一工作流卡片，即可一键对选定源站发起全自动穿透体检与在线播放测试。</div>
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

/* 顶部工具栏卡片 */
.probe-toolbar-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--a-card);
  border: 1px solid var(--a-border);
  border-radius: var(--a-radius);
  padding: 14px 20px;
  margin-bottom: 14px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.toolbar-label {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--a-text);
}

/* 4步全链路体检工作流卡片网格 */
.workflow-cards-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-bottom: 14px;
}

@media (max-width: 992px) {
  .workflow-cards-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.workflow-card {
  background: var(--a-card);
  border: 1px solid var(--a-border);
  border-radius: var(--a-radius);
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  flex-direction: column;
  position: relative;
}

.workflow-card:hover {
  border-color: var(--a-brand);
  transform: translateY(-2px);
  box-shadow: var(--a-shadow-sm);
}

.workflow-card.is-active {
  border-color: var(--a-brand);
  background: rgba(229, 9, 20, 0.04);
  box-shadow: 0 0 0 1px var(--a-brand);
}

.wf-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  color: var(--a-brand);
}

.wf-badge {
  font-size: 11px;
  font-weight: 700;
  background: rgba(255, 255, 255, 0.08);
  padding: 2px 6px;
  border-radius: 4px;
  color: var(--a-text-2);
}

.wf-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--a-text);
  margin-bottom: 4px;
}

.wf-desc {
  font-size: 12px;
  color: var(--a-text-3);
  margin-bottom: 12px;
  line-height: 1.4;
  flex: 1;
}

.wf-btn-box {
  display: flex;
}

.wf-btn-box .el-button {
  width: 100%;
}

/* 自定义参数条 */
.custom-param-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  background: var(--a-bg-subtle);
  border: 1px dashed var(--a-border);
  border-radius: 8px;
  padding: 10px 16px;
  margin-bottom: 16px;
  font-size: 12.5px;
}

.param-tip {
  font-weight: 600;
  color: var(--a-brand);
}

.param-label {
  color: var(--a-text-2);
  margin-left: 8px;
}

/* 就绪横幅卡片 */
.ready-banner-card {
  text-align: center;
  padding: 60px 24px;
  background: var(--a-card);
  border: 1px dashed var(--a-border);
  border-radius: var(--a-radius);
  margin-top: 10px;
}

.ready-icon {
  font-size: 36px;
  margin-bottom: 12px;
}

.ready-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--a-text);
  margin-bottom: 6px;
}

.ready-sub {
  font-size: 13px;
  color: var(--a-text-3);
  max-width: 500px;
  margin: 0 auto;
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
  gap: 10px;
  font-weight: 700;
  font-size: 14.5px;
}

.time-counter {
  font-size: 12px;
  background: var(--a-bg-surface);
  padding: 2px 8px;
  border-radius: 4px;
}

.head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.speed-group {
  display: flex;
  align-items: center;
  background: var(--a-card);
  border: 1px solid var(--a-border);
  border-radius: 4px;
  overflow: hidden;
}

.speed-btn {
  padding: 3px 8px;
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
  color: var(--a-text-2);
  cursor: pointer;
  transition: all 0.15s ease;
  user-select: none;
}

.speed-btn:hover {
  background: var(--a-hover);
  color: var(--a-text);
}

.speed-btn.active {
  background: var(--a-brand);
  color: #ffffff;
  font-weight: 700;
}

.url-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 20px;
  background: rgba(0, 0, 0, 0.2);
  border-bottom: 1px solid var(--a-border);
}

.url-label {
  font-size: 12px;
  color: var(--a-text-3);
  font-weight: 600;
  white-space: nowrap;
}

.url-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11.5px;
  background: var(--a-card);
  border: 1px solid var(--a-border);
  padding: 3px 8px;
  border-radius: 4px;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--a-text);
}

.video-container {
  padding: 20px;
  background: #000000;
  display: flex;
  justify-content: center;
  position: relative;
}

.real-player {
  max-height: 480px;
  width: 100%;
  max-width: 900px;
  border-radius: 8px;
  outline: none;
  background: #000000;
}

.video-error-bar {
  display: flex;
  align-items: center;
  padding: 10px 20px;
  background: rgba(239, 68, 68, 0.12);
  border-top: 1px solid rgba(239, 68, 68, 0.3);
  color: #ef4444;
  font-size: 12.5px;
  line-height: 1.5;
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
