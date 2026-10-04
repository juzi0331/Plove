<script setup lang="ts">
/**
 * PlayerView - 旗舰沉浸式影院播放大厅 (短剧 & 宽屏双模智能自适应编排器)
 */

import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import type { Episode } from '@/api/types'
import { useDeviceStore } from '@/stores/device'
import { useSitesStore } from '@/stores/sites'
import { formatPosterUrl } from '@/utils/format'
import EpisodeDrawer from './EpisodeDrawer.vue'
import PlayerHUD from './PlayerHUD.vue'
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
// 点击与手势 (支持桌面端双击与移动端单/双触控)
// ==========================================
let lastClickTime = 0
let lastTouchTime = 0
let touchStartX = 0
let touchStartY = 0
let touchStartTime = 0

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
    state.showHud(2000)
    return
  }
  if (e.touches.length !== 1) return
  touchStartX = e.touches[0].clientX
  touchStartY = e.touches[0].clientY
  touchStartTime = Date.now()
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
    state.showHud(2000)
    return
  }
  const touch = e.changedTouches[0]
  if (!touch) return
  const dx = Math.abs(touch.clientX - touchStartX)
  const dy = Math.abs(touch.clientY - touchStartY)
  if (dx > 12 || dy > 12) return

  const now = Date.now()
  const stage = playerContainerRef.value
  if (!stage) return
  const rect = stage.getBoundingClientRect()
  const clickX = touch.clientX - rect.left
  const width = rect.width

  // 双击判定 (< 300ms)
  if (now - lastTouchTime < 300) {
    lastTouchTime = 0
    if (clickX < width * 0.35) {
      state.seekRelative(-10)
      state.triggerCenterAction('seek-bwd')
      state.showHud(2000)
    } else if (clickX > width * 0.65) {
      state.seekRelative(10)
      state.triggerCenterAction('seek-fwd')
      state.showHud(2000)
    } else {
      state.togglePlay()
    }
    return
  }
  lastTouchTime = now

  // 单触：切换暂停和播放，控制台同步唤起并在无操作2秒后自动隐藏
  setTimeout(() => {
    if (lastTouchTime !== 0 && Date.now() - lastTouchTime >= 280) {
      state.togglePlay()
      lastTouchTime = 0
    }
  }, 290)
}

function handleStagePointerDown(e: MouseEvent): void {
  const now = Date.now()
  const stage = playerContainerRef.value
  if (!stage) return

  const rect = stage.getBoundingClientRect()
  const clickX = e.clientX - rect.left
  const width = rect.width

  if (now - lastClickTime < 300) {
    if (clickX < width * 0.35) {
      state.seekRelative(-10)
      state.triggerCenterAction('seek-bwd')
    } else if (clickX > width * 0.65) {
      state.seekRelative(10)
      state.triggerCenterAction('seek-fwd')
    } else {
      state.toggleFullscreen()
    }
    lastClickTime = 0
    return
  }
  lastClickTime = now
}

function handleStageClick(event: MouseEvent): void {
  const target = event.target as HTMLElement
  if (target.closest('.nf-ctrl-bar') || target.closest('.nf-theater-nav') || target.closest('.nf-episodes-drawer')) {
    return
  }
  // 屏蔽触屏触发的合成点击，防止与 touchEnd 重复冲突
  if (Date.now() - touchStartTime < 450) {
    return
  }
  state.showHud()
  state.togglePlay()
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

onMounted(() => {
  hlsEngine.setUnmounted(false)
  void hlsEngine.load()
  document.addEventListener('fullscreenchange', state.onFullscreenChange)
  state.showHud()
})

onBeforeUnmount(() => {
  hlsEngine.setUnmounted(true)
  hlsEngine.destroyPlayer()
  state.cleanup()
  document.removeEventListener('fullscreenchange', state.onFullscreenChange)
})

watch(
  () => [props.vodId, props.ep, route.query.site, route.query.line, route.query.play_id],
  (newVal, oldVal) => {
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
    @touchstart.passive="state.showHud(2000)"
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
      @mousedown="handleStagePointerDown"
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
