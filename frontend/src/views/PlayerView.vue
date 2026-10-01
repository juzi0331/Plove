<script setup lang="ts">
/**
 * PlayerView - 奈飞官方 1:1 沉浸式影院播放大厅
 *
 * 核心设计亮点：
 * 1. 纯黑影院全屏视界：16:9 黄金银幕比例居中，无缝自适应窗口与全屏；
 * 2. 智能 HUD 悬浮感应交互：鼠标悬浮或轻触时平滑浮现，静止 3.5s 柔和淡出，免干扰极致观影；
 * 3. 顶部影视信息与导航：
 *    - 经典圆形微光返回键（返回影片详情大厅）；
 *    - 影片名称大标题与当前播放集数标签；
 *    - 右侧快捷工具栏：集数抽屉按钮、线路切换按钮、下一集快进、全屏切换；
 * 4. 右侧滑出式毛玻璃“選集大廳”抽屉：
 *    - 无需退出播放器即可直接在视频画面上选集、换线路；
 *    - 实时高亮“正在播放”集数并呈现跳动脉冲徽标；
 * 5. 线路自救与高容错机制：
 *    - 播放异常时自动呼出毛玻璃救助卡片，支持一键重试或一键换线；
 * 6. 原生流媒体底层保障：
 *    - 完美适配 HLS (hls.js)、Safari/iOS 原生 m3u8 与直接 MP4；
 *    - 支持多端安全踢线与凭据热恢复。
 */

import Hls from 'hls.js'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import * as api from '@/api/client'
import { describeError } from '@/api/http'
import type { DetailPayload, Episode, Playback } from '@/api/types'
import { useDeviceStore } from '@/stores/device'
import { useSitesStore } from '@/stores/sites'

const props = defineProps<{ vodId: string; ep: string }>()

const sites = useSitesStore()
const device = useDeviceStore()
const route = useRoute()
const router = useRouter()

// ==========================================
// 状态与数据模型
// ==========================================
const loading = ref(false)
const error = ref<string | null>(null)
const playback = ref<Playback | null>(null)
const detail = ref<DetailPayload | null>(null)

const videoEl = ref<HTMLVideoElement | null>(null)
const playerContainerRef = ref<HTMLElement | null>(null)
let hls: Hls | null = null
const failedStartupLines = new Set<number>()
const MAX_AUTO_LINE_FAILOVERS = 3

/** 当前集数名与副标题 */
const epLabel = ref('')

/** 选集抽屉开关 */
const isDrawerOpen = ref(false)
/** 线路选择弹窗开关 */
const isLineMenuOpen = ref(false)

/** HUD 悬浮控制显隐 */
const isHudVisible = ref(true)
let hudTimer: number | null = null

/** 全屏状态 */
const isFullscreen = ref(false)

// ==========================================
// 计算属性
// ==========================================
const videoMeta = computed(() => detail.value?.video ?? null)
const vodTitle = computed(() => videoMeta.value?.vod_name || (route.query.name as string) || '熱門影視')

/** 当前线路 */
const currentLine = computed<number>(() => {
  if (route.query.line) return Number(route.query.line)
  if (detail.value?.lines?.length) return detail.value.lines[0]?.line ?? 1
  return 1
})

/** 所有可用线路 */
const availableLines = computed(() => detail.value?.lines ?? [])

/** 当前线路的所有剧集 */
const lineEpisodes = computed<Episode[]>(() => {
  const all = detail.value?.episodes ?? []
  if (!all.length) return []
  const filtered = all.filter((e) => e.line === currentLine.value)
  return filtered.length ? filtered : all
})

/** 当前正在播放的集数对象 */
const currentEpisode = computed<Episode | null>(() => {
  const epIndex = Number(props.ep) || 1
  return lineEpisodes.value.find((e) => e.ep_index === epIndex) ?? null
})

/** 下一集对象（若存在） */
const nextEpisode = computed<Episode | null>(() => {
  const epIndex = Number(props.ep) || 1
  return lineEpisodes.value.find((e) => e.ep_index === epIndex + 1) ?? null
})

/** 当前播放集的显示标签 */
const displayEpText = computed(() => {
  if (epLabel.value && epLabel.value !== `第 ${props.ep} 集`) {
    return `第 ${props.ep} 集 · ${epLabel.value}`
  }
  if (currentEpisode.value?.ep_name) {
    const name = currentEpisode.value.ep_name.trim()
    if (name && !name.includes(vodTitle.value)) {
      return `第 ${props.ep} 集 · ${name}`
    }
  }
  return `第 ${props.ep} 集`
})

// ==========================================
// 播放器并发控制与销毁防护 (修复 C-1)
// ==========================================
let loadSeq = 0
let isUnmounted = false

function destroyPlayer(): void {
  if (hls) {
    try {
      hls.stopLoad()
      hls.detachMedia()
      hls.destroy()
    } catch {
      // 容错处理
    }
    hls = null
  }
  const video = videoEl.value
  if (video) {
    video.pause()
    video.removeAttribute('src')
    video.load()
  }
}

function tryAutoLineFailover(): boolean {
  const video = videoEl.value
  // 只处理“刚开始就播不起来”的线路；已经正常播放过的不因瞬时抖动自动换源。
  if (video && video.currentTime > 5) return false
  if (failedStartupLines.size >= MAX_AUTO_LINE_FAILOVERS) return false

  failedStartupLines.add(currentLine.value)
  const epIndex = Number(props.ep) || 1
  const episodes = detail.value?.episodes ?? []
  const candidate = availableLines.value.find((line) => {
    if (failedStartupLines.has(line.line)) return false
    return episodes.some((episode) => episode.line === line.line && episode.ep_index === epIndex)
  })
  if (!candidate) return false

  switchLine(candidate.line)
  return true
}

function attachPlayer(result: Playback): void {
  const video = videoEl.value
  if (!video || isUnmounted) {
    console.warn('attachPlayer 被调用时 <video> 未挂载或组件已卸载')
    return
  }

  destroyPlayer()

  // 1. 直链 mp4 直接播放
  if (result.format === 'mp4') {
    video.src = result.url
    void video.play().catch(() => undefined)
    return
  }

  // 2. iOS / Safari 原生支持 HLS
  if (video.canPlayType('application/vnd.apple.mpegurl')) {
    video.src = result.url
    void video.play().catch(() => undefined)
    return
  }

  // 3. PC / Android 走 hls.js
  if (!Hls.isSupported()) {
    error.value = '當前瀏覽器環境不支援 HLS 串流播放，請升級或使用現代瀏覽器'
    return
  }

  hls = new Hls({
    xhrSetup: (xhr) => {
      for (const [key, value] of Object.entries(result.headers ?? {})) {
        try {
          xhr.setRequestHeader(key, value)
        } catch {
          // 忽略受保护的浏览器头
        }
      }
    },
    enableWorker: true,
    lowLatencyMode: true,
  })

  hls.on(Hls.Events.ERROR, (_event, data) => {
    if (data.fatal) {
      switch (data.type) {
        case Hls.ErrorTypes.NETWORK_ERROR:
          if (tryAutoLineFailover()) {
            error.value = null
            return
          }
          error.value = '網絡串流載入中斷，已嘗試可用備用線路，請重試或手動切換'
          hls?.startLoad()
          break
        case Hls.ErrorTypes.MEDIA_ERROR:
          error.value = '媒體解碼異常，正在嘗試自救恢復...'
          hls?.recoverMediaError()
          break
        default:
          error.value = `播放線路解析異常（${data.details || '未知錯誤'}）`
          destroyPlayer()
          break
      }
    }
  })

  hls.loadSource(result.url)
  hls.attachMedia(video)
  void video.play().catch(() => undefined)
}

// ==========================================
// 数据获取 (带请求互斥防重入锁)
// ==========================================
async function load(): Promise<void> {
  const currentSeq = ++loadSeq
  // 快速切集时立即销毁上一个流，避免并发争抢与资源泄漏
  destroyPlayer()

  loading.value = true
  error.value = null
  epLabel.value = typeof route.query.name === 'string' ? route.query.name : ''

  try {
    await sites.load()
    if (currentSeq !== loadSeq || isUnmounted) return

    const key = sites.currentKey
    if (!key) throw new Error('後端暫無可用片源站')

    // 并发预加载影片详情（获取完整集数、线路信息）与播放流地址
    const [playbackRes, detailRes] = await Promise.allSettled([
      api.getPlayback(key, {
        vodId: props.vodId,
        ep: Number(props.ep) || 1,
        line: route.query.line ? Number(route.query.line) : undefined,
        playId: typeof route.query.play_id === 'string' ? route.query.play_id : undefined,
      }),
      detail.value ? Promise.resolve(detail.value) : api.getDetail(key, props.vodId),
    ])

    if (currentSeq !== loadSeq || isUnmounted) return

    if (detailRes.status === 'fulfilled') {
      detail.value = detailRes.value
    }

    if (playbackRes.status === 'rejected') {
      throw playbackRes.reason
    }

    playback.value = playbackRes.value
    await nextTick()

    if (currentSeq !== loadSeq || isUnmounted) return

    attachPlayer(playbackRes.value)
  } catch (err) {
    if (currentSeq !== loadSeq || isUnmounted) return
    error.value = describeError(err)
  } finally {
    if (currentSeq === loadSeq) {
      loading.value = false
    }
  }
}

// ==========================================
// 交互：选集与换线
// ==========================================
function switchEpisode(episode: Episode): void {
  isDrawerOpen.value = false
  void router.push({
    name: 'play',
    params: { vodId: props.vodId, ep: String(episode.ep_index) },
    query: {
      line: episode.line ?? currentLine.value,
      play_id: episode.play_id || undefined,
      name: episode.ep_name || undefined,
    },
  })
}

function switchLine(lineId: number): void {
  isLineMenuOpen.value = false
  const epIndex = Number(props.ep) || 1
  const targetEpisode = (detail.value?.episodes ?? []).find(
    (episode) => episode.line === lineId && episode.ep_index === epIndex,
  )
  void router.push({
    name: 'play',
    params: { vodId: props.vodId, ep: String(targetEpisode?.ep_index ?? epIndex) },
    query: {
      line: lineId,
      // 线路变化时必须同步换成该线路自己的 play_id，不能沿用上一条线路的定位符。
      play_id: targetEpisode?.play_id || undefined,
      name: targetEpisode?.ep_name || undefined,
    },
  })
}

function playNext(): void {
  if (nextEpisode.value) {
    switchEpisode(nextEpisode.value)
  }
}

function goBack(): void {
  if (window.history.length > 1) {
    router.back()
  } else {
    void router.push({ name: 'detail', params: { vodId: props.vodId } })
  }
}

// ==========================================
// 全屏控制 (状态完全由 fullscreenchange 驱动，消除 M-6)
// ==========================================
function toggleFullscreen(): void {
  const container = playerContainerRef.value || document.documentElement
  if (!document.fullscreenElement) {
    void container.requestFullscreen().catch(() => undefined)
  } else {
    void document.exitFullscreen().catch(() => undefined)
  }
}

function onFullscreenChange(): void {
  isFullscreen.value = !!document.fullscreenElement
}

// ==========================================
// HUD 悬浮感应计时器
// ==========================================
function showHud(): void {
  isHudVisible.value = true
  if (hudTimer) clearTimeout(hudTimer)
  hudTimer = window.setTimeout(() => {
    // 如果抽屉或弹窗打开，保持 HUD 不自动关闭
    if (!isDrawerOpen.value && !isLineMenuOpen.value) {
      isHudVisible.value = false
    }
  }, 3500)
}

function onMouseMove(): void {
  showHud()
}

// ==========================================
// 生命周期与监听
// ==========================================
onMounted(() => {
  isUnmounted = false
  void load()
  document.addEventListener('fullscreenchange', onFullscreenChange)
  showHud()
})

onBeforeUnmount(() => {
  isUnmounted = true
  loadSeq++ // 作废未决请求
  destroyPlayer()
  if (hudTimer) clearTimeout(hudTimer)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
})

watch(() => [props.vodId, props.ep], () => failedStartupLines.clear())
watch(() => [props.vodId, props.ep, route.query.line, route.query.play_id], () => void load())
watch(() => device.restoredAt, () => void load())
</script>

<template>
  <div
    ref="playerContainerRef"
    class="nf-theater"
    :class="{ 'is-idle': !isHudVisible && !isDrawerOpen }"
    @mousemove="onMouseMove"
    @click="showHud"
  >
    <!-- ==================================================== 顶部悬浮控制栏 (Top HUD) -->
    <header class="nf-theater-nav" :class="{ 'is-hidden': !isHudVisible && !isDrawerOpen }">
      <div class="nf-nav-left">
        <!-- 经典 Netflix 圆形返回按钮 -->
        <button class="nf-round-back-btn" type="button" title="返回影片詳情" @click="goBack">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>

        <!-- 影视大标题与集数标识 -->
        <div class="nf-title-group">
          <h1 class="nf-main-title">{{ vodTitle }}</h1>
          <span class="nf-sub-title">{{ displayEpText }}</span>
        </div>
      </div>

      <div class="nf-nav-right">
        <!-- VIP 极速通道微光徽章 -->
        <div class="nf-vip-pill" title="尊享 4K 影院極速線路">
          <span class="nf-vip-dot" />
          <span>VIP 極速專線</span>
        </div>

        <!-- 线路切换按钮 -->
        <div v-if="availableLines.length > 1" class="nf-line-switcher-wrap">
          <button
            class="nf-tool-btn"
            type="button"
            :class="{ 'is-active': isLineMenuOpen }"
            @click.stop="isLineMenuOpen = !isLineMenuOpen"
          >
            <span class="nf-btn-icon">⚡</span>
            <span>線路 {{ currentLine }}</span>
            <span class="nf-arrow-icon" :class="{ 'is-up': isLineMenuOpen }">▾</span>
          </button>

          <!-- 线路切换下拉面板 -->
          <Transition name="nf-fade">
            <div v-if="isLineMenuOpen" class="nf-line-dropdown" @click.stop>
              <div class="nf-line-dropdown-title">選擇高速播放線路</div>
              <div class="nf-line-list">
                <button
                  v-for="line in availableLines"
                  :key="line.line"
                  class="nf-line-item"
                  :class="{ 'is-selected': line.line === currentLine }"
                  type="button"
                  @click="switchLine(line.line)"
                >
                  <span class="nf-line-status" />
                  <span class="nf-line-text">{{ line.name || `高速線路 ${line.line}` }}</span>
                  <span v-if="line.line === currentLine" class="nf-check-icon">✓</span>
                </button>
              </div>
            </div>
          </Transition>
        </div>

        <!-- 下一集快捷按钮 -->
        <button
          v-if="nextEpisode"
          class="nf-tool-btn"
          type="button"
          title="播放下一集"
          @click="playNext"
        >
          <span class="nf-btn-icon">⏭</span>
          <span class="nf-btn-text">下一集</span>
        </button>

        <!-- 选集抽屉呼出按钮 -->
        <button
          v-if="lineEpisodes.length"
          class="nf-tool-btn"
          type="button"
          :class="{ 'is-active': isDrawerOpen }"
          title="查看完整劇集列表"
          @click.stop="isDrawerOpen = !isDrawerOpen"
        >
          <span class="nf-btn-icon">☷</span>
          <span class="nf-btn-text">選集</span>
        </button>

        <!-- 全屏切换按钮 -->
        <button
          class="nf-tool-btn icon-only"
          type="button"
          :title="isFullscreen ? '退出全螢幕' : '全螢幕播放'"
          @click="toggleFullscreen"
        >
          <svg v-if="!isFullscreen" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" />
          </svg>
          <svg v-else viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3" />
          </svg>
        </button>
      </div>
    </header>

    <!-- ==================================================== 播放舞台核心视界 -->
    <main class="nf-theater-stage">
      <video
        v-if="playback && !error"
        ref="videoEl"
        class="nf-cinema-video"
        controls
        autoplay
        playsinline
        preload="auto"
      />

      <!-- 加载中 Spinner -->
      <div v-if="loading" class="nf-loading-overlay">
        <div class="nf-spinner-ring" />
        <p class="nf-loading-text">正在為您建立高畫質串流通道...</p>
      </div>

      <!-- 错误容错与自救卡片 -->
      <div v-else-if="error" class="nf-error-overlay">
        <div class="nf-error-modal">
          <div class="nf-error-icon">⚠️</div>
          <h2 class="nf-error-title">串流載入中斷</h2>
          <p class="nf-error-desc">{{ error }}</p>
          <div class="nf-error-actions">
            <button class="nf-err-btn primary" type="button" @click="load">
              重新載入
            </button>
            <button
              v-if="availableLines.length > 1"
              class="nf-err-btn secondary"
              type="button"
              @click="isLineMenuOpen = true"
            >
              切換其他線路
            </button>
            <button class="nf-err-btn ghost" type="button" @click="goBack">
              返回影片詳情
            </button>
          </div>
        </div>
      </div>
    </main>

    <!-- ==================================================== 右侧滑出选集抽屉 (Episodes Drawer) -->
    <Transition name="nf-drawer">
      <aside v-if="isDrawerOpen" class="nf-episodes-drawer" @click.stop>
        <div class="nf-drawer-header">
          <div class="nf-drawer-title-group">
            <h3 class="nf-drawer-title">劇集選集大廳</h3>
            <span class="nf-drawer-count">全 {{ lineEpisodes.length }} 集</span>
          </div>
          <button class="nf-drawer-close" type="button" @click="isDrawerOpen = false">✕</button>
        </div>

        <!-- 线路切换指示 -->
        <div v-if="availableLines.length > 1" class="nf-drawer-lines">
          <span class="nf-drawer-label">播放線路：</span>
          <div class="nf-drawer-tabs">
            <button
              v-for="line in availableLines"
              :key="line.line"
              class="nf-drawer-tab"
              :class="{ 'is-active': line.line === currentLine }"
              type="button"
              @click="switchLine(line.line)"
            >
              線路 {{ line.line }}
            </button>
          </div>
        </div>

        <!-- 集数网格列表 -->
        <div class="nf-drawer-grid">
          <button
            v-for="epItem in lineEpisodes"
            :key="epItem.ep_index"
            class="nf-drawer-card"
            :class="{ 'is-current': epItem.ep_index === Number(props.ep) }"
            type="button"
            @click="switchEpisode(epItem)"
          >
            <div class="nf-drawer-card-top">
              <span class="nf-drawer-ep-num">第 {{ epItem.ep_index }} 集</span>
              <span v-if="epItem.ep_index === Number(props.ep)" class="nf-playing-badge">
                <span class="nf-pulse-dot" /> 播放中
              </span>
            </div>
            <span v-if="epItem.ep_name" class="nf-drawer-ep-name">{{ epItem.ep_name }}</span>
          </button>
        </div>
      </aside>
    </Transition>

    <!-- 遮罩背景 (抽屉打开时) -->
    <div v-if="isDrawerOpen" class="nf-drawer-backdrop" @click="isDrawerOpen = false" />
  </div>
</template>

<style scoped>
/* ====================================================================
   全屏影院沉浸容器
==================================================================== */
.nf-theater {
  position: fixed;
  inset: 0;
  width: 100vw;
  height: 100vh;
  background-color: #000000;
  color: #ffffff;
  overflow: hidden;
  user-select: none;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  z-index: 100;
}

/* 静止空闲观影状态：鼠标隐藏，享受无边际纯净画质 */
.nf-theater.is-idle {
  cursor: none;
}

/* ====================================================================
   顶部悬浮控制栏 (Top HUD)
==================================================================== */
.nf-theater-nav {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 80px;
  padding: 0 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(180deg, rgba(0, 0, 0, 0.88) 0%, rgba(0, 0, 0, 0.45) 60%, transparent 100%);
  z-index: 30;
  pointer-events: auto;
  transition: opacity 0.35s cubic-bezier(0.16, 1, 0.3, 1), transform 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}

.nf-theater-nav.is-hidden {
  opacity: 0;
  transform: translateY(-20px);
  pointer-events: none;
}

.nf-nav-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

/* 经典圆形返回按钮 */
.nf-round-back-btn {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(20, 20, 20, 0.65);
  backdrop-filter: blur(12px);
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
}

.nf-round-back-btn:hover {
  background: rgba(229, 9, 20, 0.85);
  border-color: rgba(255, 255, 255, 0.4);
  transform: scale(1.08);
}

.nf-title-group {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.nf-main-title {
  margin: 0;
  font-size: 19px;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: -0.01em;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.9);
}

.nf-sub-title {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
  font-weight: 500;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.8);
}

/* 右侧快捷工具栏 */
.nf-nav-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.nf-vip-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(245, 197, 24, 0.12);
  border: 1px solid rgba(245, 197, 24, 0.35);
  color: #f5c518;
  font-size: 11px;
  font-weight: 700;
  padding: 5px 10px;
  border-radius: 14px;
}

.nf-vip-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #f5c518;
  box-shadow: 0 0 6px #f5c518;
}

/* 按钮通用 */
.nf-tool-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(20, 20, 20, 0.65);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 20px;
  padding: 7px 14px;
  color: #ffffff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.nf-tool-btn:hover,
.nf-tool-btn.is-active {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.4);
}

.nf-tool-btn.icon-only {
  width: 38px;
  height: 38px;
  padding: 0;
  justify-content: center;
  border-radius: 50%;
}

.nf-btn-icon {
  font-size: 14px;
}

.nf-arrow-icon {
  font-size: 11px;
  transition: transform 0.2s ease;
}

.nf-arrow-icon.is-up {
  transform: rotate(180deg);
}

/* 线路切换面板 */
.nf-line-switcher-wrap {
  position: relative;
}

.nf-line-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 190px;
  background: rgba(24, 24, 24, 0.96);
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 8px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(16px);
  padding: 8px;
  z-index: 50;
}

.nf-line-dropdown-title {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  font-weight: 600;
  padding: 4px 8px 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  margin-bottom: 4px;
}

.nf-line-list {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.nf-line-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: #ffffff;
  font-size: 13px;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s ease;
}

.nf-line-item:hover {
  background: rgba(255, 255, 255, 0.1);
}

.nf-line-item.is-selected {
  background: rgba(229, 9, 20, 0.18);
  color: #e50914;
  font-weight: 600;
}

.nf-line-status {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #46d369;
}

.nf-line-text {
  flex: 1;
}

.nf-check-icon {
  font-size: 12px;
}

/* ====================================================================
   播放舞台 (Cinema Stage)
==================================================================== */
.nf-theater-stage {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #000000;
}

.nf-cinema-video {
  width: 100%;
  height: 100%;
  max-width: 100vw;
  max-height: 100vh;
  object-fit: contain;
  background-color: #000000;
}

/* ====================================================================
   加载与缓冲状态 (Netflix Spinner)
==================================================================== */
.nf-loading-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
  background: rgba(0, 0, 0, 0.85);
  z-index: 20;
}

.nf-spinner-ring {
  width: 54px;
  height: 54px;
  border: 4px solid rgba(229, 9, 20, 0.2);
  border-top-color: #e50914;
  border-radius: 50%;
  animation: nf-spin 0.8s linear infinite;
}

.nf-loading-text {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.8);
  font-weight: 500;
  letter-spacing: 0.5px;
}

@keyframes nf-spin {
  to {
    transform: rotate(360deg);
  }
}

/* ====================================================================
   错误容错卡片 (Error Modal)
==================================================================== */
.nf-error-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.9);
  z-index: 25;
  padding: 24px;
}

.nf-error-modal {
  max-width: 440px;
  width: 100%;
  background: rgba(24, 24, 24, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 12px;
  padding: 32px 28px;
  text-align: center;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.9);
  backdrop-filter: blur(20px);
}

.nf-error-icon {
  font-size: 40px;
  margin-bottom: 12px;
}

.nf-error-title {
  margin: 0 0 10px;
  font-size: 20px;
  font-weight: 700;
  color: #ffffff;
}

.nf-error-desc {
  margin: 0 0 24px;
  font-size: 14px;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.65);
}

.nf-error-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.nf-err-btn {
  width: 100%;
  padding: 11px 0;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.nf-err-btn.primary {
  background: #e50914;
  border: none;
  color: #ffffff;
}

.nf-err-btn.primary:hover {
  background: #f40612;
}

.nf-err-btn.secondary {
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: #ffffff;
}

.nf-err-btn.secondary:hover {
  background: rgba(255, 255, 255, 0.25);
}

.nf-err-btn.ghost {
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.6);
}

.nf-err-btn.ghost:hover {
  color: #ffffff;
}

/* ====================================================================
   右侧滑出选集抽屉 (Episodes Drawer)
==================================================================== */
.nf-episodes-drawer {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  height: 100vh;
  width: 380px;
  max-width: 90vw;
  background: rgba(18, 18, 18, 0.96);
  backdrop-filter: blur(28px);
  border-left: 1px solid rgba(255, 255, 255, 0.12);
  box-shadow: -12px 0 48px rgba(0, 0, 0, 0.9);
  z-index: 40;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.nf-drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 22px 20px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.nf-drawer-title-group {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.nf-drawer-title {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: #ffffff;
}

.nf-drawer-count {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.nf-drawer-close {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background: rgba(255, 255, 255, 0.1);
  color: #ffffff;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s ease;
}

.nf-drawer-close:hover {
  background: rgba(255, 255, 255, 0.25);
}

.nf-drawer-lines {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  background: rgba(0, 0, 0, 0.3);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.nf-drawer-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}

.nf-drawer-tabs {
  display: flex;
  gap: 6px;
}

.nf-drawer-tab {
  padding: 3px 10px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: transparent;
  color: rgba(255, 255, 255, 0.7);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
}

.nf-drawer-tab.is-active {
  background: #e50914;
  border-color: #e50914;
  color: #ffffff;
}

.nf-drawer-grid {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 14px 14px 40px 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.25) transparent;
}

.nf-drawer-grid::-webkit-scrollbar {
  width: 5px;
}

.nf-drawer-grid::-webkit-scrollbar-track {
  background: transparent;
}

.nf-drawer-grid::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.25);
  border-radius: 3px;
}

.nf-drawer-grid::-webkit-scrollbar-thumb:hover {
  background: rgba(229, 9, 20, 0.8);
}

.nf-drawer-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  color: #ffffff;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s ease;
  width: 100%;
  box-sizing: border-box;
  flex-shrink: 0;
}

.nf-drawer-card:hover {
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.2);
  transform: translateX(-2px);
}

.nf-drawer-card.is-current {
  background: rgba(229, 9, 20, 0.18);
  border-color: #e50914;
}

.nf-drawer-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.nf-drawer-ep-num {
  font-size: 14px;
  font-weight: 700;
  color: #ffffff;
}

.nf-drawer-card.is-current .nf-drawer-ep-num {
  color: #e50914;
}

.nf-playing-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  font-weight: 600;
  color: #46d369;
}

.nf-pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #46d369;
  box-shadow: 0 0 6px #46d369;
  animation: nf-pulse 1.4s infinite ease-in-out;
}

@keyframes nf-pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.4);
    opacity: 0.6;
  }
}

.nf-drawer-ep-name {
  font-size: 12px;
  line-height: 1.4;
  color: rgba(255, 255, 255, 0.55);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: normal;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  word-break: break-all;
}

.nf-drawer-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 35;
}

/* ====================================================================
   Transitions
==================================================================== */
.nf-drawer-enter-active,
.nf-drawer-leave-active {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.3s ease;
}

.nf-drawer-enter-from,
.nf-drawer-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

.nf-fade-enter-active,
.nf-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.nf-fade-enter-from,
.nf-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
