/**
 * usePlayerState - 播放器交互、画面比例与音视频控制状态
 */

import { computed, ref, type Ref } from 'vue'

export function usePlayerState(videoEl: Ref<HTMLVideoElement | null>, containerEl: Ref<HTMLElement | null>) {
  /** 播放控制核心状态 (移动端默认静音起播保障自播畅通，桌面端默认有声) */
  const isMobileClient = typeof window !== 'undefined' && (
    window.innerWidth <= 768 || /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent)
  )
  const isPlaying = ref(false)
  const isMuted = ref(isMobileClient)
  const volume = ref(1) // 0 ~ 1
  const currentTime = ref(0)
  const duration = ref(0)
  const bufferedEnd = ref(0)
  const playbackRate = ref(1.0)
  const isFullscreen = ref(false)
  const isPiP = ref(false)

  /** 自动播放受限与静音起播提示 */
  const isAutoplayBlocked = ref(false)
  const isMutedAutoplay = ref(isMobileClient)

  /** 画面比例模式: 'auto' | 'vertical' (9:16) | 'widescreen' (16:9) | 'fill' */
  const aspectMode = ref<'auto' | 'vertical' | 'widescreen' | 'fill'>('auto')
  const isVideoVertical = ref(false)

  /** 抽屉与菜单面板开关 */
  const isDrawerOpen = ref(false)
  const isLineMenuOpen = ref(false)
  const isSpeedMenuOpen = ref(false)
  const isAspectMenuOpen = ref(false)

  /** HUD 悬浮感应 */
  const isHudVisible = ref(true)
  let hudTimer: number | null = null

  /** 播放进度条拖拽状态 */
  const isDraggingProgress = ref(false)
  const hoverTime = ref<number | null>(null)
  const hoverPosition = ref<number>(0)

  /** 触控与双击动画反馈 */
  const centerActionType = ref<'play' | 'pause' | 'seek-fwd' | 'seek-bwd' | null>(null)
  let centerActionTimer: number | null = null

  /** 短剧完播自动下一集倒计时 */
  const autoNextCountdown = ref<number | null>(null)
  let autoNextTimer: number | null = null

  const progressPercent = computed(() => {
    if (!duration.value || duration.value <= 0) return 0
    return Math.min(100, Math.max(0, (currentTime.value / duration.value) * 100))
  })

  const bufferedPercent = computed(() => {
    if (!duration.value || duration.value <= 0) return 0
    return Math.min(100, Math.max(0, (bufferedEnd.value / duration.value) * 100))
  })

  function showHud(duration = 2000): void {
    isHudVisible.value = true
    if (hudTimer) clearTimeout(hudTimer)
    hudTimer = window.setTimeout(() => {
      if (
        !isDrawerOpen.value &&
        !isLineMenuOpen.value &&
        !isSpeedMenuOpen.value &&
        !isAspectMenuOpen.value &&
        !isDraggingProgress.value
      ) {
        isHudVisible.value = false
      }
    }, duration)
  }

  function triggerCenterAction(type: 'play' | 'pause' | 'seek-fwd' | 'seek-bwd') {
    centerActionType.value = type
    if (centerActionTimer) clearTimeout(centerActionTimer)
    centerActionTimer = window.setTimeout(() => {
      centerActionType.value = null
    }, 650)
  }

  function togglePlay(): void {
    const video = videoEl.value
    if (!video) return

    showHud(2000)

    if (video.paused || video.ended) {
      void video.play().then(() => {
        isPlaying.value = true
        isAutoplayBlocked.value = false
        triggerCenterAction('play')
      }).catch(() => {
        void startPlay(true)
      })
    } else {
      video.pause()
      isPlaying.value = false
      triggerCenterAction('pause')
    }
  }

  async function startPlay(muted?: boolean): Promise<void> {
    const video = videoEl.value
    if (!video) return

    // 如果未显式传入布尔值，则尊重当前 isMuted.value（跨集切换时延续用户选择，杜绝第2集突发取消静音）
    const shouldMute = typeof muted === 'boolean' ? muted : isMuted.value

    video.muted = shouldMute
    isMuted.value = shouldMute

    try {
      await video.play()
      isPlaying.value = true
      isAutoplayBlocked.value = false
      isMutedAutoplay.value = shouldMute
    } catch (playErr) {
      console.warn('播放器主动起播受限:', playErr)
      if (!shouldMute) {
        // 如果有声播放被浏览器拦截，自动降级为静音起播
        await startPlay(true)
      } else {
        isAutoplayBlocked.value = true
      }
    }
  }

  function unmuteAudio(): void {
    const video = videoEl.value
    if (video) {
      video.muted = false
      isMuted.value = false
      isMutedAutoplay.value = false
      const cur = video.volume
      const targetVol = cur > 0 ? cur : 0.8
      video.volume = targetVol
      volume.value = targetVol
    }
  }

  function toggleMute(): void {
    const video = videoEl.value
    if (!video) return
    video.muted = !video.muted
    isMuted.value = video.muted
    if (!video.muted) {
      isMutedAutoplay.value = false
      if (video.volume === 0) {
        video.volume = 0.8
        volume.value = 0.8
      }
    }
  }

  function setVolume(val: number): void {
    const video = videoEl.value
    if (!video) return
    const clamped = Math.max(0, Math.min(1, val))
    video.volume = clamped
    volume.value = clamped
    if (clamped > 0 && video.muted) {
      video.muted = false
      isMuted.value = false
    }
  }

  function setSpeed(speed: number): void {
    const video = videoEl.value
    if (video) {
      video.playbackRate = speed
      playbackRate.value = speed
    }
    isSpeedMenuOpen.value = false
  }

  function setAspectMode(mode: 'auto' | 'vertical' | 'widescreen' | 'fill'): void {
    aspectMode.value = mode
    isAspectMenuOpen.value = false
  }

  function seekRelative(offset: number): void {
    const video = videoEl.value
    if (!video || !duration.value) return
    const target = Math.max(0, Math.min(duration.value, video.currentTime + offset))
    video.currentTime = target
    currentTime.value = target
    showHud()
  }

  function toggleFullscreen(): void {
    const container = containerEl.value || document.documentElement
    if (!document.fullscreenElement) {
      void container.requestFullscreen().catch(() => undefined)
    } else {
      void document.exitFullscreen().catch(() => undefined)
    }
  }

  function onFullscreenChange(): void {
    isFullscreen.value = !!document.fullscreenElement
  }

  async function togglePiP(): Promise<void> {
    const video = videoEl.value
    if (!video) return
    try {
      if (document.pictureInPictureElement) {
        await document.exitPictureInPicture()
        isPiP.value = false
      } else if (document.pictureInPictureEnabled) {
        await video.requestPictureInPicture()
        isPiP.value = true
      }
    } catch (err) {
      console.warn('PiP 操作未支持或受限:', err)
    }
  }

  function startAutoNextCountdown(onFinish: () => void): void {
    if (autoNextTimer) clearInterval(autoNextTimer)
    autoNextCountdown.value = 5
    autoNextTimer = window.setInterval(() => {
      if (autoNextCountdown.value !== null && autoNextCountdown.value > 1) {
        autoNextCountdown.value--
      } else {
        cancelAutoNext()
        onFinish()
      }
    }, 1000)
  }

  function cancelAutoNext(): void {
    if (autoNextTimer) {
      clearInterval(autoNextTimer)
      autoNextTimer = null
    }
    autoNextCountdown.value = null
  }

  function cleanup(): void {
    if (hudTimer) clearTimeout(hudTimer)
    if (centerActionTimer) clearTimeout(centerActionTimer)
    cancelAutoNext()
  }

  return {
    isPlaying,
    isMuted,
    volume,
    currentTime,
    duration,
    bufferedEnd,
    playbackRate,
    isFullscreen,
    isPiP,
    isAutoplayBlocked,
    isMutedAutoplay,
    aspectMode,
    isVideoVertical,
    isDrawerOpen,
    isLineMenuOpen,
    isSpeedMenuOpen,
    isAspectMenuOpen,
    isHudVisible,
    isDraggingProgress,
    hoverTime,
    hoverPosition,
    centerActionType,
    autoNextCountdown,
    progressPercent,
    bufferedPercent,
    showHud,
    triggerCenterAction,
    togglePlay,
    startPlay,
    unmuteAudio,
    toggleMute,
    setVolume,
    setSpeed,
    setAspectMode,
    seekRelative,
    toggleFullscreen,
    onFullscreenChange,
    togglePiP,
    startAutoNextCountdown,
    cancelAutoNext,
    cleanup,
  }
}

export function formatTime(sec: number): string {
  if (isNaN(sec) || sec < 0) return '00:00'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = Math.floor(sec % 60)
  if (h > 0) {
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

export function stripHtml(html?: string): string {
  if (!html) return ''
  return html.replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').trim()
}
