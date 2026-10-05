<script setup lang="ts">
/**
 * PlayerView - 旗舰沉浸式影院播放大厅 (短剧 & 宽屏双模智能自适应编排器)
 */

import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { reportPlaybackHeartbeat } from '@/api/client'
import type { Episode } from '@/api/types'
import { useDeviceStore } from '@/stores/device'
import { useSitesStore } from '@/stores/sites'
import { formatPosterUrl } from '@/utils/format'
import EpisodeDrawer from './EpisodeDrawer.vue'
import PlayerHUD from './PlayerHUD.vue'
import './player.css'
import { useHls } from './useHls'
import { useKeyboard } from './useKeyboard'
import { usePlayerState } from './usePlayerState'

const props = defineProps<{ vodId: string; ep: string }>()

const route = useRoute()
const router = useRouter()
const device = useDeviceStore()
const sitesStore = useSitesStore()

const videoEl = ref<HTMLVideoElement | null>(null)
const playerContainerRef = ref<HTMLElement | null>(null)

const vodIdRef = computed(() => props.vodId)
const epRef = computed(() => props.ep)

const state = usePlayerState(videoEl, playerContainerRef)

const hlsEngine = useHls(videoEl, vodIdRef, epRef, {
  startPlay: state.startPlay,
  onAutoNext: () => {
    if (nextEpisode.value) {
      state.startAutoNextCountdown(playNext)
    }
  },
  onProgressUpdate: (curr, buf) => {
    if (!state.isDraggingProgress.value) {
      state.currentTime.value = curr
    }
    state.bufferedEnd.value = buf
    triggerPlaybackTick(curr)
  },
  onDurationChange: (dur) => {
    state.duration.value = dur
  },
  onVerticalDetected: (vertical) => {
    state.isVideoVertical.value = vertical
  },
  onVolumeChange: (vol, muted) => {
    state.volume.value = vol
    state.isMuted.value = muted
  },
  onPlayStateChange: (playing) => {
    state.isPlaying.value = playing
    if (playing) {
      triggerPlaybackTick(state.currentTime.value || 1)
    }
  },
  onBufferingChange: (_buffering) => {
    // handled in state if needed
  },
  onAutoplayBlocked: () => {
    state.isAutoplayBlocked.value = true
  },
})

// ==========================================
// 计算属性与剧集索引
// ==========================================
const videoMeta = computed(() => hlsEngine.detail.value?.video ?? null)
const vodTitle = computed(
  () => videoMeta.value?.vod_name || (route.query.title as string) || (route.query.name as string) || '影視大廳',
)

const currentLine = computed<number>(() => {
  if (route.query.line) return Number(route.query.line)
  if (hlsEngine.detail.value?.lines?.length) return hlsEngine.detail.value.lines[0]?.line ?? 1
  return 1
})

const availableLines = computed(() => hlsEngine.detail.value?.lines ?? [])

const lineEpisodes = computed<Episode[]>(() => {
  const all = hlsEngine.detail.value?.episodes ?? []
  if (!all.length) return []
  const filtered = all.filter((e) => e.line === currentLine.value)
  return filtered.length ? filtered : all
})

const currentEpNumber = computed(() => Number(props.ep) || 1)

const currentEpisode = computed<Episode | null>(() => {
  return lineEpisodes.value.find((e) => e.ep_index === currentEpNumber.value) ?? null
})

const prevEpisode = computed<Episode | null>(() => {
  return lineEpisodes.value.find((e) => e.ep_index === currentEpNumber.value - 1) ?? null
})

const nextEpisode = computed<Episode | null>(() => {
  return lineEpisodes.value.find((e) => e.ep_index === currentEpNumber.value + 1) ?? null
})

const displayEpText = computed(() => {
  if (hlsEngine.epLabel.value && hlsEngine.epLabel.value !== `第 ${props.ep} 集`) {
    return `第 ${props.ep} 集 · ${hlsEngine.epLabel.value}`
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
// 换集与跳转
// ==========================================
function switchEpisode(episode: Episode): void {
  resetGestureState()
  state.cancelAutoNext()
  state.isDrawerOpen.value = false
  void router.replace({
    name: 'play',
    params: { vodId: props.vodId, ep: String(episode.ep_index) },
    query: {
      ...route.query,
      line: episode.line ?? currentLine.value,
      play_id: episode.play_id || undefined,
      name: episode.ep_name || undefined,
    },
  })
}

function switchLine(lineId: number): void {
  state.cancelAutoNext()
  state.isLineMenuOpen.value = false
  const newQuery: Record<string, any> = {
    ...route.query,
    line: lineId,
  }
  delete newQuery.play_id
  void router.replace({
    name: 'play',
    params: { vodId: props.vodId, ep: props.ep },
    query: newQuery,
  })
}

function playPrev(): void {
  if (prevEpisode.value) switchEpisode(prevEpisode.value)
}

function playNext(): void {
  if (nextEpisode.value) switchEpisode(nextEpisode.value)
}

function goBack(): void {
  state.cancelAutoNext()
  if (document.fullscreenElement) {
    void document.exitFullscreen().catch(() => undefined)
  }
  const origin = sessionStorage.getItem('plove_detail_origin')
  if (origin && !origin.includes('/play/') && !origin.includes('/detail/')) {
    void router.replace(origin)
  } else {
    void router.replace({ name: 'detail', params: { vodId: props.vodId } })
  }
}

function goToDetail(): void {
  state.cancelAutoNext()
  if (document.fullscreenElement) {
    void document.exitFullscreen().catch(() => undefined)
  }
  void router.replace({ name: 'detail', params: { vodId: props.vodId } })
}

function seekTo(time: number): void {
  state.currentTime.value = time
  if (videoEl.value) {
    videoEl.value.currentTime = time
  }
}

// ==========================================
// 点击与手势 (支持桌面端双击与移动端单/双触控切换播放与暂停)
// ==========================================
let singleClickTimer: ReturnType<typeof setTimeout> | null = null
let lastTouchTapEndTime = 0
let lastTouchTapX = 0
let lastTouchTapY = 0
let touchStartX = 0
let touchStartY = 0
let lastTouchEndTime = 0
let hudVisibleAtTouchStart = false

function resetGestureState(): void {
  if (singleClickTimer) {
    clearTimeout(singleClickTimer)
    singleClickTimer = null
  }
  lastTouchTapEndTime = 0
  lastTouchEndTime = 0
  lastTouchTapX = 0
  lastTouchTapY = 0
}

/** 统一双击处理：双击屏幕中央及主体区域一律触发 播放 / 暂停 */
function handleStageDoubleAction(clickX?: number, width?: number): void {
  if (singleClickTimer) {
    clearTimeout(singleClickTimer)
    singleClickTimer = null
  }

  // 宽屏模式下两侧极边缘（各 15%）支持快退快进，中央 70% 无论如何都是双击播放/暂停
  if (clickX !== undefined && width && width > 0) {
    const isVertical = state.isVideoVertical.value || state.aspectMode.value === 'vertical'
    if (!isVertical) {
      if (clickX < width * 0.15) {
        state.seekRelative(-10)
        state.triggerCenterAction('seek-bwd')
        state.showHud(2000)
        return
      } else if (clickX > width * 0.85) {
        state.seekRelative(10)
        state.triggerCenterAction('seek-fwd')
        state.showHud(2000)
        return
      }
    }
  }

  state.togglePlay()
}

/** 统一单击处理：唤起或隐藏控制台 HUD，不打断播放 */
function handleStageSingleAction(): void {
  if (state.isHudVisible.value) {
    state.isHudVisible.value = false
  } else {
    state.showHud(2500)
  }
}

function handleStageTouchStart(e: TouchEvent): void {
  const target = e.target as HTMLElement
  if (
    target.closest('.nf-ctrl-bar') ||
    target.closest('.nf-theater-nav') ||
    target.closest('.nf-episodes-drawer') ||
    target.closest('.nf-auto-next-card') ||
    target.closest('.nf-blocked-gate') ||
    target.closest('.nf-muted-toast')
  ) {
    state.showHud(2500)
    return
  }
  if (e.touches.length !== 1) return
  hudVisibleAtTouchStart = state.isHudVisible.value
  touchStartX = e.touches[0].clientX
  touchStartY = e.touches[0].clientY
}

function handleStageTouchEnd(e: TouchEvent): void {
  const target = e.target as HTMLElement
  if (
    target.closest('.nf-ctrl-bar') ||
    target.closest('.nf-theater-nav') ||
    target.closest('.nf-episodes-drawer') ||
    target.closest('.nf-auto-next-card') ||
    target.closest('.nf-blocked-gate') ||
    target.closest('.nf-muted-toast')
  ) {
    state.showHud(2500)
    return
  }
  const touch = e.changedTouches[0]
  if (!touch) return
  const dx = Math.abs(touch.clientX - touchStartX)
  const dy = Math.abs(touch.clientY - touchStartY)
  if (dx > 15 || dy > 15) return // 过滤手指滑动

  const now = Date.now()
  lastTouchEndTime = now
  const stage = playerContainerRef.value
  const rect = stage?.getBoundingClientRect()
  const clickX = rect ? touch.clientX - rect.left : undefined
  const width = rect?.width

  const timeSinceLastTap = now - lastTouchTapEndTime
  const distDiff = Math.hypot(touch.clientX - lastTouchTapX, touch.clientY - lastTouchTapY)

  // 触屏双击判定：两次轻触间隔 50ms ~ 380ms 且位移相近 (< 50px)
  if (timeSinceLastTap > 50 && timeSinceLastTap < 380 && distDiff < 50) {
    if (singleClickTimer) {
      clearTimeout(singleClickTimer)
      singleClickTimer = null
    }
    lastTouchTapEndTime = 0
    handleStageDoubleAction(clickX, width)
    return
  }

  // 记录第一次轻触，等待 260ms 确认不是双击后再执行单触唤起/收起 HUD
  lastTouchTapEndTime = now
  lastTouchTapX = touch.clientX
  lastTouchTapY = touch.clientY

  if (singleClickTimer) clearTimeout(singleClickTimer)
  singleClickTimer = setTimeout(() => {
    if (hudVisibleAtTouchStart) {
      state.isHudVisible.value = false
    } else {
      state.showHud(2500)
    }
    singleClickTimer = null
    lastTouchTapEndTime = 0
  }, 260)
}

function handleStageClick(event: MouseEvent): void {
  const target = event.target as HTMLElement
  if (
    target.closest('.nf-ctrl-bar') ||
    target.closest('.nf-theater-nav') ||
    target.closest('.nf-episodes-drawer') ||
    target.closest('.nf-muted-toast') ||
    target.closest('.nf-auto-next-card') ||
    target.closest('.nf-blocked-gate')
  ) {
    return
  }
  // 严格屏蔽触屏合成点击，防止与 touchEnd 重复冲突
  if (Date.now() - lastTouchEndTime < 800) {
    return
  }

  const stage = playerContainerRef.value
  const rect = stage?.getBoundingClientRect()
  const clickX = rect ? event.clientX - rect.left : undefined
  const width = rect?.width

  // 1. 如果浏览器直接派发原生双击事件 (event.detail >= 2)
  if (event.detail >= 2) {
    handleStageDoubleAction(clickX, width)
    return
  }

  // 2. 软件防抖判定：两次点击在 260ms 内接连发生 -> 触发双击
  if (singleClickTimer) {
    clearTimeout(singleClickTimer)
    singleClickTimer = null
    handleStageDoubleAction(clickX, width)
    return
  }

  singleClickTimer = setTimeout(() => {
    handleStageSingleAction()
    singleClickTimer = null
  }, 260)
}

function handleStageDblClick(event: MouseEvent): void {
  const target = event.target as HTMLElement
  if (
    target.closest('.nf-ctrl-bar') ||
    target.closest('.nf-theater-nav') ||
    target.closest('.nf-episodes-drawer') ||
    target.closest('.nf-muted-toast') ||
    target.closest('.nf-auto-next-card') ||
    target.closest('.nf-blocked-gate')
  ) {
    return
  }
  if (Date.now() - lastTouchEndTime < 800) {
    return
  }

  const stage = playerContainerRef.value
  const rect = stage?.getBoundingClientRect()
  const clickX = rect ? event.clientX - rect.left : undefined
  const width = rect?.width

  handleStageDoubleAction(clickX, width)
}

// 绑定全局快捷键
useKeyboard({
  togglePlay: state.togglePlay,
  showHud: state.showHud,
  seekRelative: state.seekRelative,
  triggerCenterAction: state.triggerCenterAction,
  setVolume: state.setVolume,
  getVolume: () => state.volume.value,
  toggleMute: state.toggleMute,
  toggleFullscreen: state.toggleFullscreen,
  playNext,
  closeDrawer: () => {
    state.isDrawerOpen.value = false
  },
  isDrawerOpen: () => state.isDrawerOpen.value,
})

// ==========================================
// 播放状态与观看足迹心跳上报
// ==========================================
let heartbeatTimer: ReturnType<typeof setInterval> | null = null
let lastHeartbeatTime = 0
let hasSentInitialPlayHeartbeat = false

function triggerPlaybackTick(curr: number): void {
  if (curr > 0) {
    if (!state.isPlaying.value) {
      state.isPlaying.value = true
    }
    const now = Date.now()
    if (!hasSentInitialPlayHeartbeat || now - lastHeartbeatTime >= 20000) {
      hasSentInitialPlayHeartbeat = true
      lastHeartbeatTime = now
      sendHeartbeat(true)
    }
  }
}

function sendHeartbeat(isPlaying: boolean): void {
  if (!props.vodId) return
  const dur = Math.round(state.duration.value || 0)
  const pos = Math.round(state.currentTime.value || 0)
  const pct = dur > 0 ? Math.min(100, Math.max(0, Math.round((pos / dur) * 100))) : 0

  const pic = videoMeta.value?.vod_pic || (route.query.pic as string) || ''
  const name = vodTitle.value || (route.query.title as string) || (route.query.name as string) || '影視大廳'
  const ep = displayEpText.value || (route.query.name as string) || `第 ${props.ep} 集`
  const site = (route.query.site as string) || sitesStore.currentKey || ''

  reportPlaybackHeartbeat({
    vod_id: String(props.vodId),
    vod_name: name,
    vod_pic: pic,
    ep_name: ep,
    site,
    position: pos,
    duration: dur,
    progress: pct,
    is_playing: isPlaying,
  })
    .then(() => {
      // 心跳与观看历史记录上报成功
    })
    .catch((err) => {
      console.warn('[PlayerHeartbeat] 播放心跳上报失败:', err)
    })
}

function startHeartbeatLoop(): void {
  stopHeartbeatLoop()
  sendHeartbeat(true)
  heartbeatTimer = setInterval(() => {
    if (state.isPlaying.value) {
      sendHeartbeat(true)
    }
  }, 20000)
}

function stopHeartbeatLoop(): void {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer)
    heartbeatTimer = null
  }
}

watch(
  () => state.isPlaying.value,
  (playing) => {
    if (playing) {
      startHeartbeatLoop()
    } else {
      stopHeartbeatLoop()
      sendHeartbeat(false)
    }
  },
)

watch(
  () => [props.vodId, props.ep],
  () => {
    hasSentInitialPlayHeartbeat = false
    lastHeartbeatTime = 0
  },
)

onMounted(() => {
  hlsEngine.setUnmounted(false)
  void hlsEngine.load()
  document.addEventListener('fullscreenchange', state.onFullscreenChange)
  state.showHud()
})

onBeforeUnmount(() => {
  resetGestureState()
  stopHeartbeatLoop()
  sendHeartbeat(false)
  hlsEngine.setUnmounted(true)
  hlsEngine.destroyPlayer()
  state.cleanup()
  document.removeEventListener('fullscreenchange', state.onFullscreenChange)
})

watch(
  () => [props.vodId, props.ep, route.query.site, route.query.line, route.query.play_id],
  (newVal, oldVal) => {
    resetGestureState()
    if (oldVal && (newVal[0] !== oldVal[0] || newVal[2] !== oldVal[2])) {
      hlsEngine.detail.value = null
    }
    void hlsEngine.load()
  },
)
watch(() => device.restoredAt, () => void hlsEngine.load())
</script>

<template>
  <div
    ref="playerContainerRef"
    class="nf-theater"
    :class="{
      'is-idle': !state.isHudVisible.value && state.isPlaying.value,
      'is-vertical-theater': state.isVideoVertical.value || state.aspectMode.value === 'vertical',
      'is-fill': state.aspectMode.value === 'fill',
    }"
    @mousemove="state.showHud(2000)"
  >
    <!-- 背景流光氛围灯 (Ambient Glow) -->
    <div
      v-if="state.isVideoVertical.value || state.aspectMode.value === 'vertical'"
      class="nf-ambient-backdrop"
      :style="{ backgroundImage: videoMeta?.vod_pic ? `url(${formatPosterUrl(videoMeta.vod_pic, sitesStore.currentKey)})` : 'none' }"
    />

    <!-- 视频渲染舞台 -->
    <div
      class="nf-theater-stage nf-video-stage"
      @click="handleStageClick"
      @dblclick="handleStageDblClick"
      @touchstart.passive="handleStageTouchStart"
      @touchend.passive="handleStageTouchEnd"
    >
      <div
        class="nf-video-wrapper"
        :class="{
          'mode-vertical': state.isVideoVertical.value || state.aspectMode.value === 'vertical',
          'mode-widescreen': state.aspectMode.value === 'widescreen',
          'mode-fill': state.aspectMode.value === 'fill',
        }"
      >
        <video
          ref="videoEl"
          class="nf-cinema-video nf-video-element"
          playsinline
          webkit-playsinline
          x5-video-player-type="h5-page"
        />
      </div>
    </div>

    <!-- 加载中遮罩 -->
    <div v-if="hlsEngine.loading.value" class="nf-loading-stage nf-theater-loading">
      <div class="nf-spinner-ring" />
      <span class="nf-loading-label">{{ hlsEngine.loadingText.value }}</span>
    </div>

    <!-- 异常故障拦截层 -->
    <div v-else-if="hlsEngine.error.value" class="nf-error-stage nf-theater-error">
      <div class="nf-error-modal">
        <div class="nf-error-icon">⚠️</div>
        <h2 class="nf-error-title">串流加載受阻</h2>
        <p class="nf-error-desc">{{ hlsEngine.error.value }}</p>
        <div class="nf-error-actions">
          <button class="nf-err-btn primary" type="button" @click="hlsEngine.load()">
            重試加載
          </button>
          <button
            v-if="!hlsEngine.isCompatMode.value"
            class="nf-err-btn accent"
            type="button"
            @click="hlsEngine.reloadInCompatMode()"
          >
            切換純軟解模式
          </button>
          <button class="nf-err-btn secondary" type="button" @click="hlsEngine.trySwitchSite()">
            換個片源站
          </button>
          <button class="nf-err-btn ghost" type="button" @click="goBack">
            返回詳情
          </button>
        </div>
      </div>
    </div>

    <!-- 影院 HUD 控制台 -->
    <PlayerHUD
      :visible="state.isHudVisible.value"
      :vod-title="vodTitle"
      :display-ep-text="displayEpText"
      :is-video-vertical="state.isVideoVertical.value"
      :aspect-mode="state.aspectMode.value"
      :is-playing="state.isPlaying.value"
      :is-muted="state.isMuted.value"
      :volume="state.volume.value"
      :current-time="state.currentTime.value"
      :duration="state.duration.value"
      :buffered-percent="state.bufferedPercent.value"
      :progress-percent="state.progressPercent.value"
      :playback-rate="state.playbackRate.value"
      :is-fullscreen="state.isFullscreen.value"
      :is-autoplay-blocked="state.isAutoplayBlocked.value"
      :is-muted-autoplay="state.isMutedAutoplay.value"
      :auto-next-countdown="state.autoNextCountdown.value"
      :center-action-type="state.centerActionType.value"
      :has-prev-ep="!!prevEpisode"
      :has-next-ep="!!nextEpisode"
      :is-drawer-open="state.isDrawerOpen.value"
      @go-back="goBack"
      @go-to-detail="goToDetail"
      @set-aspect-mode="state.setAspectMode"
      @toggle-play="state.togglePlay"
      @toggle-mute="state.toggleMute"
      @unmute="state.unmuteAudio"
      @set-volume="state.setVolume"
      @set-speed="state.setSpeed"
      @toggle-pi-p="state.togglePiP"
      @toggle-fullscreen="state.toggleFullscreen"
      @play-prev="playPrev"
      @play-next="playNext"
      @cancel-auto-next="state.cancelAutoNext"
      @toggle-drawer="state.isDrawerOpen.value = !state.isDrawerOpen.value"
      @seek-to="seekTo"
    />

    <!-- 右侧滑出选集抽屉 -->
    <EpisodeDrawer
      :open="state.isDrawerOpen.value"
      :line-episodes="lineEpisodes"
      :current-ep-number="currentEpNumber"
      :current-line="currentLine"
      :available-lines="availableLines"
      :video-meta="videoMeta"
      :detail-desc="hlsEngine.detail.value?.desc"
      @close="state.isDrawerOpen.value = false"
      @switch-episode="switchEpisode"
      @switch-line="switchLine"
    />
  </div>
</template>

<style>
@import './player.css';
</style>
