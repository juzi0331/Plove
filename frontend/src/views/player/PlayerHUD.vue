<script setup lang="ts">
/**
 * PlayerHUD - 奈飞级影院 HUD 控制台 (顶部导航 + 底部控制栏 + 中央手势反馈与连播倒计时)
 */

import { computed, onBeforeUnmount, ref } from 'vue'
import './player.css'
import { formatTime } from './usePlayerState'

const props = withDefaults(
  defineProps<{
    visible: boolean
    vodTitle: string
    displayEpText: string
    aspectMode: 'auto' | 'widescreen' | 'fill'
    isPlaying: boolean
    isMuted: boolean
    volume: number
    currentTime: number
    duration: number
    bufferedPercent: number
    progressPercent: number
    playbackRate: number
    isFullscreen: boolean
    isAutoplayBlocked: boolean
    isMutedAutoplay: boolean
    autoNextCountdown: number | null
    centerActionType: 'play' | 'pause' | 'seek-fwd' | 'seek-bwd' | null
    hasPrevEp: boolean
    hasNextEp: boolean
    isDrawerOpen: boolean
    allowedRates?: number[]
  }>(),
  {
    allowedRates: () => [0.5, 0.75, 1.0, 1.25, 1.5, 2.0],
  },
)

const emit = defineEmits<{
  (e: 'goBack'): void
  (e: 'goToDetail'): void
  (e: 'setAspectMode', mode: 'auto' | 'widescreen' | 'fill'): void
  (e: 'togglePlay'): void
  (e: 'toggleMute'): void
  (e: 'unmute'): void
  (e: 'setVolume', vol: number): void
  (e: 'setSpeed', speed: number): void
  (e: 'togglePiP'): void
  (e: 'toggleFullscreen'): void
  (e: 'playPrev'): void
  (e: 'playNext'): void
  (e: 'cancelAutoNext'): void
  (e: 'toggleDrawer'): void
  (e: 'seekTo', time: number): void
  (e: 'dragStart'): void
  (e: 'dragEnd'): void
}>()

const isAspectMenuOpen = ref(false)
const isSpeedMenuOpen = ref(false)

const availableSpeeds = computed(() =>
  props.allowedRates && props.allowedRates.length > 0
    ? props.allowedRates
    : [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
)

const progressBarRef = ref<HTMLElement | null>(null)
const hoverTime = ref<number | null>(null)
const hoverPosition = ref<number>(0)
const isDragging = ref(false)

function onProgressPointerDown(e: MouseEvent): void {
  isDragging.value = true
  emit('dragStart')
  updateProgressByEvent(e, true)

  const onPointerMove = (ev: MouseEvent) => {
    if (isDragging.value) {
      updateProgressByEvent(ev, false)
    }
  }

  const onPointerUp = (ev: MouseEvent) => {
    if (isDragging.value) {
      updateProgressByEvent(ev, true)
      isDragging.value = false
      emit('dragEnd')
    }
    window.removeEventListener('mousemove', onPointerMove)
    window.removeEventListener('mouseup', onPointerUp)
  }

  window.addEventListener('mousemove', onPointerMove)
  window.addEventListener('mouseup', onPointerUp)
}

function onProgressTouchStart(e: TouchEvent): void {
  const touch = e.touches[0]
  if (!touch || !props.duration) return
  isDragging.value = true
  emit('dragStart')
  updateProgressByTouch(touch, true)
}

function onProgressTouchMove(e: TouchEvent): void {
  const touch = e.touches[0]
  if (!isDragging.value || !touch || !props.duration) return
  updateProgressByTouch(touch, false)
}

function onProgressTouchEnd(e: TouchEvent): void {
  if (isDragging.value) {
    const touch = e.changedTouches[0]
    if (touch) {
      updateProgressByTouch(touch, true)
    }
    isDragging.value = false
    hoverTime.value = null
    emit('dragEnd')
  }
}

function onProgressTouchCancel(): void {
  if (isDragging.value) {
    isDragging.value = false
    hoverTime.value = null
    emit('dragEnd')
  }
}

onBeforeUnmount(() => {
  if (isDragging.value) {
    isDragging.value = false
    hoverTime.value = null
    emit('dragEnd')
  }
})

function updateProgressByTouch(touch: Touch, commit: boolean): void {
  const bar = progressBarRef.value
  if (!bar || !props.duration) return
  const rect = bar.getBoundingClientRect()
  const ratio = Math.max(0, Math.min(1, (touch.clientX - rect.left) / rect.width))
  const target = ratio * props.duration
  hoverTime.value = target
  hoverPosition.value = ratio * 100
  if (commit) {
    emit('seekTo', target)
  }
}

function updateProgressByEvent(e: MouseEvent, commit: boolean): void {
  const bar = progressBarRef.value
  if (!bar || !props.duration) return
  const rect = bar.getBoundingClientRect()
  const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  const target = ratio * props.duration
  if (commit) {
    emit('seekTo', target)
  }
}

function onProgressHover(e: MouseEvent): void {
  const bar = progressBarRef.value
  if (!bar || !props.duration) {
    hoverTime.value = null
    return
  }
  const rect = bar.getBoundingClientRect()
  const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  hoverTime.value = ratio * props.duration
  hoverPosition.value = ratio * 100
}

function onProgressLeave(): void {
  hoverTime.value = null
}
</script>

<template>
  <div class="nf-hud-root">
    <!-- ==================================================== 顶部悬浮控制栏 (Top HUD) -->
    <header class="nf-theater-nav" :class="{ 'is-hidden': !visible }">
      <div class="nf-nav-left">
        <button class="nf-round-back-btn" type="button" title="返回詳情大廳" @click="emit('goBack')">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>

        <div class="nf-title-group" @click="emit('goToDetail')">
          <div class="nf-title-row">
            <h1 class="nf-main-title">{{ vodTitle }}</h1>
          </div>
          <span class="nf-sub-title">{{ displayEpText }}</span>
        </div>
      </div>

      <div class="nf-nav-right">
        <!-- 画面比例菜单 -->
        <div class="nf-menu-wrapper">
          <button
            class="nf-tool-btn"
            type="button"
            :class="{ 'is-active': isAspectMenuOpen }"
            title="畫面比例調整"
            @click.stop="isAspectMenuOpen = !isAspectMenuOpen; isSpeedMenuOpen = false"
          >
            <span class="nf-btn-icon">📐</span>
            <span class="nf-btn-text">
              {{ aspectMode === 'widescreen' ? '寬屏 16:9' : aspectMode === 'fill' ? '鋪滿' : '自適應' }}
            </span>
          </button>
          <Transition name="nf-dropdown">
            <div v-if="isAspectMenuOpen" class="nf-pop-dropdown" @click.stop>
              <div class="nf-dropdown-head">畫面比例</div>
              <button class="nf-dropdown-item" :class="{ 'is-active': aspectMode === 'auto' }" type="button" @click="emit('setAspectMode', 'auto'); isAspectMenuOpen = false">
                <span>智能自適應</span>
                <span v-if="aspectMode === 'auto'">✓</span>
              </button>
              <button class="nf-dropdown-item" :class="{ 'is-active': aspectMode === 'widescreen' }" type="button" @click="emit('setAspectMode', 'widescreen'); isAspectMenuOpen = false">
                <span>影院寬屏 (16:9)</span>
                <span v-if="aspectMode === 'widescreen'">✓</span>
              </button>
              <button class="nf-dropdown-item" :class="{ 'is-active': aspectMode === 'fill' }" type="button" @click="emit('setAspectMode', 'fill'); isAspectMenuOpen = false">
                <span>鋪滿視界</span>
                <span v-if="aspectMode === 'fill'">✓</span>
              </button>
            </div>
          </Transition>
        </div>
      </div>
    </header>

    <!-- ==================================================== 中央即时触控 / 双击反馈波纹 -->
    <Transition name="nf-center-pulse">
      <div v-if="centerActionType" class="nf-center-action-badge">
        <svg v-if="centerActionType === 'play'" viewBox="0 0 24 24" width="36" height="36" fill="currentColor">
          <polygon points="5 3 19 12 5 21 5 3" />
        </svg>
        <svg v-else-if="centerActionType === 'pause'" viewBox="0 0 24 24" width="36" height="36" fill="currentColor">
          <rect x="6" y="4" width="4" height="16" />
          <rect x="14" y="4" width="4" height="16" />
        </svg>
        <div v-else-if="centerActionType === 'seek-fwd'" class="nf-center-seek">
          <span class="nf-seek-arrow">⏩</span>
          <span>+10s</span>
        </div>
        <div v-else-if="centerActionType === 'seek-bwd'" class="nf-center-seek">
          <span class="nf-seek-arrow">⏪</span>
          <span>-10s</span>
        </div>
      </div>
    </Transition>

    <!-- 浏览器强行禁止自播兜底大门 -->
    <div v-if="isAutoplayBlocked && !isPlaying" class="nf-blocked-gate" @click.stop="emit('togglePlay')">
      <button class="nf-gate-play-btn" type="button">
        <svg viewBox="0 0 24 24" width="40" height="40" fill="currentColor">
          <polygon points="5 3 19 12 5 21 5 3" />
        </svg>
      </button>
      <span class="nf-gate-text">點擊解鎖並開啟高畫質影院</span>
    </div>

    <!-- 静音提示胶囊 (任何处于静音播放时均显示，触屏与点击均可一键恢复声音) -->
    <Transition name="nf-fade">
      <div
        v-if="isMuted && isPlaying"
        class="nf-muted-toast"
        @click.stop="emit('unmute')"
        @touchend.stop.prevent="emit('unmute')"
      >
        <span class="nf-muted-toast-icon">🔊</span>
        <span class="nf-muted-toast-text">當前為靜音播放</span>
        <button
          class="nf-muted-btn"
          type="button"
          @click.stop="emit('unmute')"
          @touchend.stop.prevent="emit('unmute')"
        >
          開啟聲音
        </button>
      </div>
    </Transition>

    <!-- 剧集自动下一集倒计时浮层 -->
    <Transition name="nf-fade">
      <div v-if="autoNextCountdown !== null" class="nf-auto-next-card">
        <div class="nf-next-header">
          <span class="nf-next-pill">自動連播</span>
          <span class="nf-next-clock">{{ autoNextCountdown }}s</span>
        </div>
        <div class="nf-next-title">即將為您播放下一集</div>
        <div class="nf-next-actions">
          <button class="nf-next-btn primary" type="button" @click="emit('playNext')">
            立即連播
          </button>
          <button class="nf-next-btn secondary" type="button" @click="emit('cancelAutoNext')">
            留在本集
          </button>
        </div>
      </div>
    </Transition>

    <!-- ==================================================== 底部悬浮控制台 (Bottom HUD) -->
    <footer class="nf-ctrl-bar" :class="{ 'is-hidden': !visible }">
      <!-- 进度条系统 -->
      <div
        ref="progressBarRef"
        class="nf-progress-container"
        @mousedown="onProgressPointerDown"
        @mousemove="onProgressHover"
        @mouseleave="onProgressLeave"
        @touchstart.passive="onProgressTouchStart"
        @touchmove.passive="onProgressTouchMove"
        @touchend.passive="onProgressTouchEnd"
        @touchcancel="onProgressTouchCancel"
      >
        <div class="nf-progress-track">
          <div class="nf-progress-buffered" :style="{ width: `${bufferedPercent}%` }" />
          <div class="nf-progress-played" :style="{ width: `${progressPercent}%` }">
            <span class="nf-progress-thumb" />
          </div>
        </div>

        <!-- 悬停/触摸时间预览气泡 -->
        <div
          v-if="hoverTime !== null"
          class="nf-progress-tooltip"
          :style="{ left: `${hoverPosition}%` }"
        >
          {{ formatTime(hoverTime) }}
        </div>
      </div>

      <!-- 控制按钮栏 -->
      <div class="nf-ctrl-row">
        <!-- 左侧核心控制组 -->
        <div class="nf-ctrl-left">
          <!-- 播放 / 暂停 -->
          <button class="nf-ctrl-btn play-btn" type="button" :title="isPlaying ? '暫停 (Space)' : '播放 (Space)'" @click="emit('togglePlay')">
            <svg v-if="!isPlaying" viewBox="0 0 24 24" width="26" height="26" fill="currentColor">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
            <svg v-else viewBox="0 0 24 24" width="26" height="26" fill="currentColor">
              <rect x="6" y="4" width="4" height="16" />
              <rect x="14" y="4" width="4" height="16" />
            </svg>
          </button>

          <!-- 上一集 (移动端紧凑排布) -->
          <button
            class="nf-ctrl-btn prev-ep-btn"
            type="button"
            :disabled="!hasPrevEp"
            title="上一集"
            @click="emit('playPrev')"
          >
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
              <polygon points="19 20 9 12 19 4 19 20" />
              <line x1="5" y1="19" x2="5" y2="5" stroke="currentColor" stroke-width="2.5" />
            </svg>
          </button>

          <!-- 下一集 -->
          <button
            class="nf-ctrl-btn next-ep-btn"
            type="button"
            :disabled="!hasNextEp"
            title="下一集 (N)"
            @click="emit('playNext')"
          >
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
              <polygon points="5 4 15 12 5 20 5 4" />
              <line x1="19" y1="5" x2="19" y2="19" stroke="currentColor" stroke-width="2.5" />
            </svg>
          </button>

          <!-- 音量调节 (移动端仅隐藏滑动条，保留一键静音/取消静音图标) -->
          <div class="nf-volume-group">
            <button
              class="nf-ctrl-btn mute-btn"
              :class="{ 'is-muted': isMuted || volume === 0 }"
              type="button"
              :title="isMuted ? '取消靜音 (M)' : '靜音 (M)'"
              @click.stop="emit('toggleMute')"
              @touchend.stop.prevent="emit('toggleMute')"
            >
              <svg v-if="isMuted || volume === 0" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 5L6 9H2v6h4l5 4V5z" fill="currentColor" />
                <line x1="23" y1="9" x2="17" y2="15" stroke-width="2.5" />
                <line x1="17" y1="9" x2="23" y2="15" stroke-width="2.5" />
              </svg>
              <svg v-else-if="volume < 0.5" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 5L6 9H2v6h4l5 4V5z" fill="currentColor" />
                <path d="M15.54 8.46a5 5 0 0 1 0 7.07" stroke-width="2" />
              </svg>
              <svg v-else viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 5L6 9H2v6h4l5 4V5z" fill="currentColor" />
                <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07" stroke-width="2" />
              </svg>
            </button>
            <div class="nf-volume-slider-wrap">
              <input
                type="range"
                min="0"
                max="1"
                step="0.02"
                :value="isMuted ? 0 : volume"
                class="nf-volume-range"
                @input="emit('setVolume', Number(($event.target as HTMLInputElement).value))"
              />
            </div>
          </div>

          <!-- 时间轴数字显示 -->
          <div class="nf-time-display">
            <span class="nf-time-curr">{{ formatTime(currentTime) }}</span>
            <span class="nf-time-sep">/</span>
            <span class="nf-time-duration">{{ formatTime(duration) }}</span>
          </div>
        </div>

        <!-- 右侧视界控制组 -->
        <div class="nf-ctrl-right">
          <!-- 展开选集抽屉 -->
          <button
            class="nf-ctrl-btn text-btn drawer-btn"
            type="button"
            :class="{ 'is-active': isDrawerOpen }"
            title="查看完整劇集"
            @click.stop="emit('toggleDrawer')"
          >
            <span>選集</span>
          </button>

          <!-- 倍速切换 -->
          <div class="nf-menu-wrapper speed-menu">
            <button
              class="nf-ctrl-btn text-btn"
              type="button"
              :class="{ 'is-active': isSpeedMenuOpen }"
              title="播放倍速"
              @click.stop="isSpeedMenuOpen = !isSpeedMenuOpen; isAspectMenuOpen = false"
            >
              <span>{{ playbackRate === 1.0 ? '倍速' : `${playbackRate}x` }}</span>
            </button>
            <Transition name="nf-dropdown">
              <div v-if="isSpeedMenuOpen" class="nf-pop-dropdown up" @click.stop>
                <div class="nf-dropdown-head">播放倍速</div>
                <button
                  v-for="spd in availableSpeeds"
                  :key="spd"
                  class="nf-dropdown-item"
                  :class="{ 'is-active': playbackRate === spd }"
                  type="button"
                  @click="emit('setSpeed', spd); isSpeedMenuOpen = false"
                >
                  <span>{{ spd }}x</span>
                  <span v-if="playbackRate === spd">✓</span>
                </button>
              </div>
            </Transition>
          </div>

          <!-- 画中画 (PiP) -->
          <button class="nf-ctrl-btn pip-btn" type="button" title="畫中畫微端小窗" @click="emit('togglePiP')">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="2" y="4" width="20" height="16" rx="2" />
              <rect x="12" y="11" width="8" height="7" rx="1" fill="currentColor" />
            </svg>
          </button>

          <!-- 全屏切换 -->
          <button class="nf-ctrl-btn fullscreen-btn" type="button" :title="isFullscreen ? '退出全螢幕 (F)' : '全螢幕 (F)'" @click="emit('toggleFullscreen')">
            <svg v-if="!isFullscreen" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" />
            </svg>
            <svg v-else viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3" />
            </svg>
          </button>
        </div>
      </div>
    </footer>
  </div>
</template>
