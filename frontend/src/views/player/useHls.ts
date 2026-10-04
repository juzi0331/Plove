/**
 * useHls - HLS.js 引擎生命周期、AES-128 软解兜底与起播容错自愈
 */

import Hls from 'hls.js'
import { nextTick, ref, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import * as api from '@/api/client'
import { describeError } from '@/api/http'
import type { DetailPayload, Playback } from '@/api/types'
import { useSitesStore } from '@/stores/sites'

import { createHlsInstance } from './hlsFactory'
import { bindVideoEvents } from './videoEvents'

export interface HlsCallbacks {
  startPlay: (muted?: boolean) => Promise<void>
  onAutoNext: () => void
  onProgressUpdate: (curr: number, buffered: number) => void
  onDurationChange: (dur: number) => void
  onVerticalDetected: (vertical: boolean) => void
  onVolumeChange: (vol: number, muted: boolean) => void
  onPlayStateChange: (playing: boolean) => void
  onBufferingChange: (buffering: boolean) => void
  onAutoplayBlocked: () => void
}

export function useHls(
  videoEl: Ref<HTMLVideoElement | null>,
  vodId: Ref<string>,
  ep: Ref<string>,
  callbacks: HlsCallbacks,
) {
  const sites = useSitesStore()
  const route = useRoute()
  const router = useRouter()

  const loading = ref(false)
  const buffering = ref(false)
  const error = ref<string | null>(null)
  const playback = ref<Playback | null>(null)
  const detail = ref<DetailPayload | null>(null)

  const epLabel = ref('')
  const loadingText = ref('正在為您建立高畫質串流通道...')
  const isCompatMode = ref(false)
  const lastErrorDetail = ref<string>('')

  let hls: Hls | null = null
  let loadSeq = 0
  let isUnmounted = false
  let slowTimer: number | null = null

  function destroyPlayer(): void {
    if (slowTimer) {
      clearTimeout(slowTimer)
      slowTimer = null
    }
    if (hls) {
      try {
        hls.stopLoad()
        hls.detachMedia()
        hls.destroy()
      } catch {
        // 容错销毁
      }
      hls = null
    }
    const video = videoEl.value
    if (video) {
      video.pause()
      video.removeAttribute('src')
      video.load()
    }
    callbacks.onPlayStateChange(false)
    callbacks.onBufferingChange(false)
    callbacks.onProgressUpdate(0, 0)
    callbacks.onDurationChange(0)
  }

  function setupVideoEvents(video: HTMLVideoElement): void {
    bindVideoEvents(video, {
      onPlayStateChange: (playing) => {
        callbacks.onPlayStateChange(playing)
        if (playing) loading.value = false
      },
      onBufferingChange: (isBuffering) => {
        buffering.value = isBuffering
        callbacks.onBufferingChange(isBuffering)
      },
      onProgressUpdate: callbacks.onProgressUpdate,
      onDurationChange: callbacks.onDurationChange,
      onVerticalDetected: callbacks.onVerticalDetected,
      onVolumeChange: callbacks.onVolumeChange,
      onAutoNext: callbacks.onAutoNext,
      onFatalVideoError: () => {
        if (!error.value) {
          error.value = '影片串流加載失敗或解碼中斷，請重試或切換線路'
          loading.value = false
          buffering.value = false
          callbacks.onBufferingChange(false)
          destroyPlayer()
        }
      },
    })
  }

  function attachPlayer(result: Playback): void {
    const video = videoEl.value
    if (!video || isUnmounted) return

    destroyPlayer()
    setupVideoEvents(video)

    // 1. 直链 MP4 / WebM
    if (result.format === 'mp4' || result.url.includes('.mp4')) {
      video.src = result.url
      void callbacks.startPlay(false)
      return
    }

    // 2. Hls.js（集成软件 AES 双模解密引擎）
    if (Hls.isSupported()) {
      hls = createHlsInstance(isCompatMode.value, video, result.url, {
        onError: (msg) => {
          error.value = msg
        },
        onFatalCleanup: () => {
          loading.value = false
          buffering.value = false
          destroyPlayer()
        },
        onManifestParsed: () => {
          loading.value = false
          void callbacks.startPlay(false)
        },
        onFallbackNativeHls: () => {
          destroyPlayer()
          video.src = result.url
          void callbacks.startPlay(false)
        },
        onLastErrorDetail: (det) => {
          lastErrorDetail.value = det
        },
      })
      return
    }

    // 3. 原生 HLS (Safari / iOS)
    if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = result.url
      void callbacks.startPlay(false)
      return
    }

    error.value = '當前瀏覽器環境不支援串流播放，請升級或使用現代瀏覽器'
    loading.value = false
  }

  async function load(): Promise<void> {
    const currentSeq = ++loadSeq
    destroyPlayer()

    loading.value = true
    buffering.value = false
    error.value = null
    lastErrorDetail.value = ''
    loadingText.value = '正在為您建立高畫質串流通道...'

    if (slowTimer) clearTimeout(slowTimer)
    slowTimer = window.setTimeout(() => {
      if (loading.value && !error.value) {
        loadingText.value = '正在優化線路解密節點...'
      }
    }, 3500)

    epLabel.value = typeof route.query.name === 'string' ? route.query.name : ''

    try {
      await sites.load()
      if (currentSeq !== loadSeq || isUnmounted) return

      const siteFromQuery = typeof route.query.site === 'string' ? route.query.site : null
      let key = siteFromQuery || sites.currentKey
      if (!key && sites.sites.length > 0) {
        key = sites.sites[0].key
      }
      if (!key) throw new Error('伺服器暫無可用片源站點')

      if (siteFromQuery && sites.currentKey !== siteFromQuery) {
        sites.select(siteFromQuery)
      }

      let playbackRes: Playback | null = null
      try {
        playbackRes = await api.getPlayback(key, {
          vodId: vodId.value,
          ep: Number(ep.value) || 1,
          line: route.query.line ? Number(route.query.line) : undefined,
          playId: typeof route.query.play_id === 'string' ? route.query.play_id : undefined,
        })
      } catch (initialErr) {
        const candidateKeys = sites.sites.map((s) => s.key).filter((k) => k !== key)
        let recovered = false
        for (const candidateKey of candidateKeys) {
          try {
            const res = await api.getPlayback(candidateKey, {
              vodId: vodId.value,
              ep: Number(ep.value) || 1,
              line: route.query.line ? Number(route.query.line) : undefined,
              playId: typeof route.query.play_id === 'string' ? route.query.play_id : undefined,
            })
            playbackRes = res
            key = candidateKey
            sites.select(candidateKey)
            recovered = true
            break
          } catch {
            // 继续探测下一个
          }
        }
        if (!recovered) throw initialErr
      }

      if (currentSeq !== loadSeq || isUnmounted) return

      if (!detail.value) {
        void api.getDetail(key, vodId.value).then((res) => {
          if (currentSeq === loadSeq && !isUnmounted) {
            detail.value = res
          }
        }).catch(() => undefined)
      }

      if (!playbackRes) throw new Error('未能獲取有效播放串流')

      playback.value = playbackRes
      await nextTick()

      if (currentSeq !== loadSeq || isUnmounted) return
      attachPlayer(playbackRes)
    } catch (err) {
      if (currentSeq !== loadSeq || isUnmounted) return
      error.value = describeError(err)
      loading.value = false
      buffering.value = false
    }
  }

  function reloadInCompatMode(): void {
    isCompatMode.value = true
    void load()
  }

  function trySwitchSite(): void {
    const currentKey = sites.currentKey
    const nextSite = sites.sites.find((s) => s.key !== currentKey)
    if (nextSite) {
      sites.select(nextSite.key)
      void router.replace({
        name: 'play',
        params: { vodId: vodId.value, ep: ep.value },
        query: { ...route.query, site: nextSite.key },
      })
    }
  }

  function setUnmounted(val: boolean): void {
    isUnmounted = val
  }

  return {
    loading,
    buffering,
    error,
    playback,
    detail,
    epLabel,
    loadingText,
    isCompatMode,
    lastErrorDetail,
    load,
    destroyPlayer,
    reloadInCompatMode,
    trySwitchSite,
    setUnmounted,
  }
}
