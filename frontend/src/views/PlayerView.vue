<script setup lang="ts">
/**
 * PlayerView - 全新重构：奈飞级 1:1 旗舰沉浸式影院播放大厅 (短剧 & 宽屏双模智能自适应)
 *
 * 核心架构与逻辑亮点：
 * 1. 【全链路起播防死锁引擎 (解决黄果短剧等加密流无法播放问题)】：
 *    - 智能应对浏览器自动播放限制：优先有声起播；若被拦截则无缝回退至静音自播并浮现微光「开启声音」胶囊；
 *    - 若完全受限，即刻唤出中央微光波纹开播巨钮，任何点击即刻瞬间起播，彻底告别“能加载但无反应”黑屏；
 *    - 纯自研全定制交互控制体系，彻底抛弃原生 <video controls>，跨平台体验极致统一；
 * 2. 【短剧 (9:16) 与宽屏 (16:9) 智能双模引擎】：
 *    - 实时探测视频元数据分辨率，短剧垂直剧集自适应居中竖屏沉浸视界 + 弥散环绕氛围灯光 (Ambient Glow)；
 *    - 提供「自适应 / 竖屏 9:16 / 宽屏 16:9 / 铺满」一键视界切换；
 * 3. 【微短剧连播闭环】：
 *    - 剧集播放结束 (ended) 自动无缝倒计时衔接下一集，支持一键快跳与取消；
 *    - HUD 底部控制台集成「上一集 / 下一集」直通快捷键；
 * 4. 【高级流媒体容错与 AES-128 解密保障】：
 *    - 内置 Hls.js 硬件 + 软件 AES 双模解密通道 (enableSoftwareAES 深度兜底)；
 *    - 致命网络/解码异常自动步进重试与线路自救；
 * 5. 【全功能定制化影院 HUD 控制台】：
 *    - 精准缓冲与进度拖拽条，支持悬浮时间预览；
 *    - 倍速调节面板 (0.5x - 2.0x)、平滑音量控制、画中画 (PiP)、全屏快捷；
 *    - 桌面端全功能键盘映射 (空格/方向键/F/M/N) 与双击快进快退交互；
 * 6. 【右侧滑出式毛玻璃选集大厅】：
 *    - 动态律动跳动音频条，高亮当前播放集；支持多线路即点即切。
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
// 状态模型
// ==========================================
const loading = ref(false)
const buffering = ref(false)
const error = ref<string | null>(null)
const playback = ref<Playback | null>(null)
const detail = ref<DetailPayload | null>(null)

const videoEl = ref<HTMLVideoElement | null>(null)
const playerContainerRef = ref<HTMLElement | null>(null)
const progressBarRef = ref<HTMLElement | null>(null)
let hls: Hls | null = null

/** 播放控制状态 */
const isPlaying = ref(false)
const isMuted = ref(false)
const volume = ref(1) // 0 ~ 1
const currentTime = ref(0)
const duration = ref(0)
const bufferedEnd = ref(0)
const playbackRate = ref(1.0)
const isFullscreen = ref(false)
const isPiP = ref(false)

/** 自动播放受限与静音起播提示 */
const isAutoplayBlocked = ref(false)
const isMutedAutoplay = ref(false)

/** 画面比例模式: 'auto' | 'vertical' (9:16) | 'widescreen' (16:9) | 'fill' */
const aspectMode = ref<'auto' | 'vertical' | 'widescreen' | 'fill'>('auto')
const isVideoVertical = ref(false)

/** 选集抽屉 & 菜单面板开关 */
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

/** 当前集显示名称 */
const epLabel = ref('')
const loadingText = ref('正在為您建立高畫質串流通道...')
let slowTimer: number | null = null

/** 兼容解码模式与故障诊断详情 */
const isCompatMode = ref(false)
const lastErrorDetail = ref<string>('')

// ==========================================
// 计算属性
// ==========================================
const videoMeta = computed(() => detail.value?.video ?? null)
const vodTitle = computed(() => videoMeta.value?.vod_name || (route.query.title as string) || (route.query.name as string) || '影視大廳')

const currentLine = computed<number>(() => {
  if (route.query.line) return Number(route.query.line)
  if (detail.value?.lines?.length) return detail.value.lines[0]?.line ?? 1
  return 1
})

const availableLines = computed(() => detail.value?.lines ?? [])

const lineEpisodes = computed<Episode[]>(() => {
  const all = detail.value?.episodes ?? []
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

const progressPercent = computed(() => {
  if (!duration.value || duration.value <= 0) return 0
  return Math.min(100, Math.max(0, (currentTime.value / duration.value) * 100))
})

const bufferedPercent = computed(() => {
  if (!duration.value || duration.value <= 0) return 0
  return Math.min(100, Math.max(0, (bufferedEnd.value / duration.value) * 100))
})

const availableSpeeds = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]

/** 选集抽屉显示模式：'card' (详细卡片) | 'grid' (数字矩阵) */
const drawerMode = ref<'card' | 'grid'>('card')

/** 长剧集分页大小（如短剧 80-100 集，30 集一页分段） */
const EP_PAGE_SIZE = 30
const selectedEpRange = ref<number>(0)

const epRanges = computed(() => {
  const total = lineEpisodes.value.length
  if (total <= EP_PAGE_SIZE) return []
  const ranges: { start: number; end: number; label: string }[] = []
  for (let i = 0; i < total; i += EP_PAGE_SIZE) {
    const start = i + 1
    const end = Math.min(i + EP_PAGE_SIZE, total)
    ranges.push({ start, end, label: `${start}-${end}` })
  }
  return ranges
})

const pagedEpisodes = computed(() => {
  if (epRanges.value.length === 0) return lineEpisodes.value
  const range = epRanges.value[selectedEpRange.value]
  if (!range) return lineEpisodes.value
  return lineEpisodes.value.filter(
    (e) => e.ep_index >= range.start && e.ep_index <= range.end
  )
})

watch(
  () => currentEpNumber.value,
  (ep) => {
    if (epRanges.value.length > 0) {
      const idx = epRanges.value.findIndex((r) => ep >= r.start && ep <= r.end)
      if (idx !== -1) {
        selectedEpRange.value = idx
      }
    }
  },
  { immediate: true }
)

function stripHtml(html?: string): string {
  if (!html) return ''
  return html.replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').trim()
}

// ==========================================
// 辅助格式化
// ==========================================
function formatTime(sec: number): string {
  if (isNaN(sec) || sec < 0) return '00:00'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = Math.floor(sec % 60)
  if (h > 0) {
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

function triggerCenterAction(type: 'play' | 'pause' | 'seek-fwd' | 'seek-bwd') {
  centerActionType.value = type
  if (centerActionTimer) clearTimeout(centerActionTimer)
  centerActionTimer = window.setTimeout(() => {
    centerActionType.value = null
  }, 650)
}

// ==========================================
// 播放器生命周期与核心绑定
// ==========================================
let loadSeq = 0
let isUnmounted = false

function destroyPlayer(): void {
  if (slowTimer) {
    clearTimeout(slowTimer)
    slowTimer = null
  }
  if (autoNextTimer) {
    clearInterval(autoNextTimer)
    autoNextTimer = null
    autoNextCountdown.value = null
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
  isPlaying.value = false
  buffering.value = false
  currentTime.value = 0
  duration.value = 0
  bufferedEnd.value = 0
  isAutoplayBlocked.value = false
  isMutedAutoplay.value = false
}

/** 触发立即有声播放 */
async function startPlay(muted = false): Promise<void> {
  const video = videoEl.value
  if (!video) return

  video.muted = muted
  isMuted.value = muted

  try {
    await video.play()
    isPlaying.value = true
    isAutoplayBlocked.value = false
    loading.value = false
    buffering.value = false
    if (muted) {
      isMutedAutoplay.value = true
    } else {
      isMutedAutoplay.value = false
    }
  } catch (playErr) {
    console.warn('播放器主动起播受限:', playErr)
    if (!muted) {
      // 有声播放受阻，尝试无感静音起播
      console.info('尝试降级为静音自动播放模式...')
      await startPlay(true)
    } else {
      // 哪怕静音起播依然受限，唤出专属开播大钮
      isAutoplayBlocked.value = true
      loading.value = false
    }
  }
}

function unmuteAudio(): void {
  const video = videoEl.value
  if (video) {
    video.muted = false
    isMuted.value = false
    isMutedAutoplay.value = false
    volume.value = video.volume > 0 ? video.volume : 0.8
  }
}

function bindVideoEvents(video: HTMLVideoElement): void {
  video.onplay = () => {
    isPlaying.value = true
    loading.value = false
    isAutoplayBlocked.value = false
  }

  video.onplaying = () => {
    isPlaying.value = true
    buffering.value = false
    loading.value = false
    isAutoplayBlocked.value = false
  }

  video.onpause = () => {
    isPlaying.value = false
    buffering.value = false
  }

  video.onwaiting = () => {
    buffering.value = true
  }

  video.onseeking = () => {
    buffering.value = true
  }

  video.onseeked = () => {
    buffering.value = false
  }

  video.ontimeupdate = () => {
    if (!isDraggingProgress.value) {
      currentTime.value = video.currentTime
    }
    // 更新缓冲进度
    if (video.buffered.length > 0) {
      for (let i = video.buffered.length - 1; i >= 0; i--) {
        if (video.buffered.start(i) <= video.currentTime) {
          bufferedEnd.value = video.buffered.end(i)
          break
        }
      }
    }
  }

  video.ondurationchange = () => {
    if (video.duration && !isNaN(video.duration) && video.duration !== Infinity) {
      duration.value = video.duration
    }
  }

  video.onloadedmetadata = () => {
    if (video.duration && !isNaN(video.duration)) {
      duration.value = video.duration
    }
    // 智能识别视频分辨率纵横比 (如 720x1280 识别为垂直短剧)
    if (video.videoWidth && video.videoHeight) {
      isVideoVertical.value = video.videoHeight > video.videoWidth
    }
  }

  video.onvolumechange = () => {
    volume.value = video.volume
    isMuted.value = video.muted
  }

  // 短剧核心交互：播放结束自动开启下一集倒计时
  video.onended = () => {
    isPlaying.value = false
    if (nextEpisode.value) {
      startAutoNextCountdown()
    }
  }

  video.onerror = () => {
    if (!error.value) {
      error.value = '影片串流加載失敗或解碼中斷，請重試或切換線路'
      loading.value = false
      buffering.value = false
      destroyPlayer()
    }
  }
}

function startAutoNextCountdown(): void {
  if (autoNextTimer) clearInterval(autoNextTimer)
  autoNextCountdown.value = 5
  autoNextTimer = window.setInterval(() => {
    if (autoNextCountdown.value !== null && autoNextCountdown.value > 1) {
      autoNextCountdown.value--
    } else {
      cancelAutoNext()
      playNext()
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

function attachPlayer(result: Playback): void {
  const video = videoEl.value
  if (!video || isUnmounted) return

  destroyPlayer()
  bindVideoEvents(video)

  // 1. 直链 MP4 / WebM
  if (result.format === 'mp4' || result.url.includes('.mp4')) {
    video.src = result.url
    void startPlay(false)
    return
  }

  // 2. 现代浏览器优先采用 Hls.js（集成软件 AES 双模解密引擎）
  if (Hls.isSupported()) {
    const isCompat = isCompatMode.value
    hls = new Hls({
      // 普通模式开启 Worker，兼容模式关闭 Worker 使用主线程纯软解
      enableWorker: !isCompat,
      // 核心软解密：兼容所有跨端、本地局域网以及无 WebCrypto SecureContext 限制的环境
      enableSoftwareAES: true,
      // 核心音频兼容：强制兜底至 mp4a.40.2 (AAC-LC)，规避所有 Chromium/WebKit 环境中的 BUFFER_ADD_CODEC_ERROR
      defaultAudioCodec: 'mp4a.40.2',
      lowLatencyMode: false,
      startFragPrefetch: true,
      // 致命关键点：切勿对 AES-128 加密流开启 progressive 流式解包，否则分块未达 PKCS7 对齐会导致 WebCrypto 报 OperationError
      progressive: false,
      maxBufferLength: 30,
      maxMaxBufferLength: 60,
      fragLoadingTimeOut: 30000,
      manifestLoadingTimeOut: 25000,
      levelLoadingTimeOut: 25000,
      fragLoadingMaxRetry: 4,
      levelLoadingMaxRetry: 4,
    })

    let networkRetry = 0
    let mediaRetry = 0

    hls.on(Hls.Events.ERROR, (_event, data) => {
      console.warn('HLS 状态追踪:', data.type, data.details, data.fatal ? '(fatal)' : '(non-fatal)', data)
      lastErrorDetail.value = data.details || ''

      if (data.fatal) {
        switch (data.type) {
          case Hls.ErrorTypes.NETWORK_ERROR:
            networkRetry++
            if (networkRetry <= 3) {
              console.warn(`HLS 遇到网络抖动，第 ${networkRetry} 次重启加载...`)
              hls?.startLoad()
            } else {
              error.value = '串流伺服器連接超時，請檢查網絡或切換備用線路'
              loading.value = false
              buffering.value = false
              destroyPlayer()
            }
            break

          case Hls.ErrorTypes.MEDIA_ERROR:
            mediaRetry++
            console.warn(`HLS 媒体格式解析异常 (${mediaRetry}/3), details: ${data.details}`)
            if (mediaRetry === 1) {
              // 第一阶梯：标准 recoverMediaError
              hls?.recoverMediaError()
            } else if (mediaRetry === 2) {
              // 第二阶梯：执行 swapAudioCodec 切换音频转封装并二次恢复
              console.warn('HLS 尝试 swapAudioCodec 切换音频格式自愈...')
              try {
                hls?.swapAudioCodec()
              } catch (swapErr) {
                console.warn('swapAudioCodec 触发告警:', swapErr)
              }
              hls?.recoverMediaError()
            } else if (mediaRetry === 3 && video.canPlayType('application/vnd.apple.mpegurl')) {
              // 第三阶梯：若当前环境原生支持 HLS，无缝降级为原生 HTML5 播放器
              console.warn('Hls.js 无法解密/解封装当前切片，无缝降级为原生 HTML5 播放器...')
              destroyPlayer()
              video.src = result.url
              void startPlay(false)
            } else {
              error.value = `視頻編碼解析異常（${data.details || '當前環境無法解碼'}）`
              loading.value = false
              buffering.value = false
              destroyPlayer()
            }
            break

          default:
            if (data.details === Hls.ErrorDetails.KEY_LOAD_ERROR || data.details === Hls.ErrorDetails.KEY_LOAD_TIMEOUT) {
              error.value = '串流解密密鑰 (Key) 獲取失敗，可能存在防盜鏈或跨域限制'
            } else {
              error.value = `串流解析錯誤（${data.details || '未知錯誤'}）`
            }
            loading.value = false
            buffering.value = false
            destroyPlayer()
            break
        }
      }
    })

    hls.attachMedia(video)
    hls.on(Hls.Events.MEDIA_ATTACHED, () => {
      hls?.loadSource(result.url)
    })
    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      // 清理加载通道文案
      loading.value = false
      void startPlay(false)
    })
    return
  }

  // 3. 原生 HLS (Safari / iOS)
  if (video.canPlayType('application/vnd.apple.mpegurl')) {
    video.src = result.url
    void startPlay(false)
    return
  }

  error.value = '當前瀏覽器環境不支援串流播放，請升級或使用現代瀏覽器'
  loading.value = false
}

// ==========================================
// 数据加载通道
// ==========================================
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
        vodId: props.vodId,
        ep: Number(props.ep) || 1,
        line: route.query.line ? Number(route.query.line) : undefined,
        playId: typeof route.query.play_id === 'string' ? route.query.play_id : undefined,
      })
    } catch (initialErr) {
      // 自动故障探测回退
      const candidateKeys = sites.sites.map((s) => s.key).filter((k) => k !== key)
      let recovered = false
      for (const candidateKey of candidateKeys) {
        try {
          const res = await api.getPlayback(candidateKey, {
            vodId: props.vodId,
            ep: Number(props.ep) || 1,
            line: route.query.line ? Number(route.query.line) : undefined,
            playId: typeof route.query.play_id === 'string' ? route.query.play_id : undefined,
          })
          playbackRes = res
          key = candidateKey
          sites.select(candidateKey)
          recovered = true
          break
        } catch {
          // 探测下一候选
        }
      }
      if (!recovered) throw initialErr
    }

    if (currentSeq !== loadSeq || isUnmounted) return

    // 后台非阻塞预加载剧集列表与详情
    if (!detail.value) {
      void api.getDetail(key, props.vodId).then((res) => {
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
      params: { vodId: props.vodId, ep: props.ep },
      query: { ...route.query, site: nextSite.key },
    })
  }
}

// ==========================================
// 播放控制与用户交互
// ==========================================
function togglePlay(): void {
  const video = videoEl.value
  if (!video) return

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

function handleStageClick(event: MouseEvent): void {
  // 忽略控制栏点击冒泡
  const target = event.target as HTMLElement
  if (target.closest('.nf-ctrl-bar') || target.closest('.nf-theater-nav') || target.closest('.nf-episodes-drawer')) {
    return
  }
  showHud()
  togglePlay()
}

/** 双击快速快退/快进/全屏 */
let lastClickTime = 0
function handleStagePointerDown(e: MouseEvent): void {
  const now = Date.now()
  const stage = playerContainerRef.value
  if (!stage) return

  const rect = stage.getBoundingClientRect()
  const clickX = e.clientX - rect.left
  const width = rect.width

  if (now - lastClickTime < 300) {
    // 判定为双击
    if (clickX < width * 0.35) {
      seekRelative(-10)
      triggerCenterAction('seek-bwd')
    } else if (clickX > width * 0.65) {
      seekRelative(10)
      triggerCenterAction('seek-fwd')
    } else {
      toggleFullscreen()
    }
    lastClickTime = 0
    return
  }
  lastClickTime = now
}

function seekRelative(offset: number): void {
  const video = videoEl.value
  if (!video || !duration.value) return
  const target = Math.max(0, Math.min(duration.value, video.currentTime + offset))
  video.currentTime = target
  currentTime.value = target
  showHud()
}

function toggleMute(): void {
  const video = videoEl.value
  if (!video) return
  video.muted = !video.muted
  isMuted.value = video.muted
  if (!video.muted && video.volume === 0) {
    video.volume = 0.5
    volume.value = 0.5
  }
  isMutedAutoplay.value = false
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

// ==========================================
// 进度条拖拽交互
// ==========================================
function onProgressPointerDown(e: MouseEvent): void {
  isDraggingProgress.value = true
  updateProgressByEvent(e)

  const onPointerMove = (ev: MouseEvent) => {
    if (isDraggingProgress.value) {
      updateProgressByEvent(ev)
    }
  }

  const onPointerUp = (ev: MouseEvent) => {
    if (isDraggingProgress.value) {
      updateProgressByEvent(ev)
      isDraggingProgress.value = false
      const video = videoEl.value
      if (video) {
        video.currentTime = currentTime.value
      }
    }
    window.removeEventListener('mousemove', onPointerMove)
    window.removeEventListener('mouseup', onPointerUp)
  }

  window.addEventListener('mousemove', onPointerMove)
  window.addEventListener('mouseup', onPointerUp)
}

function updateProgressByEvent(e: MouseEvent): void {
  const bar = progressBarRef.value
  if (!bar || !duration.value) return
  const rect = bar.getBoundingClientRect()
  const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  currentTime.value = ratio * duration.value
}

function onProgressHover(e: MouseEvent): void {
  const bar = progressBarRef.value
  if (!bar || !duration.value) {
    hoverTime.value = null
    return
  }
  const rect = bar.getBoundingClientRect()
  const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  hoverTime.value = ratio * duration.value
  hoverPosition.value = ratio * 100
}

function onProgressLeave(): void {
  hoverTime.value = null
}

// ==========================================
// 全屏 & 画中画
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

// ==========================================
// 选集与换线
// ==========================================
function switchEpisode(episode: Episode): void {
  cancelAutoNext()
  isDrawerOpen.value = false
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
  cancelAutoNext()
  isLineMenuOpen.value = false
  void router.replace({
    name: 'play',
    params: { vodId: props.vodId, ep: props.ep },
    query: {
      ...route.query,
      line: lineId,
    },
  })
}

function playPrev(): void {
  if (prevEpisode.value) {
    switchEpisode(prevEpisode.value)
  }
}

function playNext(): void {
  if (nextEpisode.value) {
    switchEpisode(nextEpisode.value)
  }
}

function goBack(): void {
  cancelAutoNext()
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
  cancelAutoNext()
  if (document.fullscreenElement) {
    void document.exitFullscreen().catch(() => undefined)
  }
  void router.replace({ name: 'detail', params: { vodId: props.vodId } })
}

// ==========================================
// 键盘快捷键体系
// ==========================================
function onKeyDown(e: KeyboardEvent): void {
  // 如果焦点在输入框中，不触发全局快捷键
  const tag = (e.target as HTMLElement)?.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA') return

  switch (e.code) {
    case 'Space':
    case 'KeyK':
      e.preventDefault()
      togglePlay()
      showHud()
      break
    case 'ArrowLeft':
    case 'KeyJ':
      e.preventDefault()
      seekRelative(-5)
      triggerCenterAction('seek-bwd')
      break
    case 'ArrowRight':
    case 'KeyL':
      e.preventDefault()
      seekRelative(5)
      triggerCenterAction('seek-fwd')
      break
    case 'ArrowUp':
      e.preventDefault()
      setVolume(volume.value + 0.1)
      showHud()
      break
    case 'ArrowDown':
      e.preventDefault()
      setVolume(volume.value - 0.1)
      showHud()
      break
    case 'KeyM':
      e.preventDefault()
      toggleMute()
      showHud()
      break
    case 'KeyF':
      e.preventDefault()
      toggleFullscreen()
      break
    case 'KeyN':
      e.preventDefault()
      playNext()
      break
    case 'Escape':
      if (isDrawerOpen.value) {
        isDrawerOpen.value = false
      }
      break
  }
}

// ==========================================
// HUD 感应显隐
// ==========================================
function showHud(): void {
  isHudVisible.value = true
  if (hudTimer) clearTimeout(hudTimer)
  hudTimer = window.setTimeout(() => {
    // 播放中且无下拉面板时才自动隐藏
    if (
      isPlaying.value &&
      !isDrawerOpen.value &&
      !isLineMenuOpen.value &&
      !isSpeedMenuOpen.value &&
      !isAspectMenuOpen.value &&
      !isDraggingProgress.value
    ) {
      isHudVisible.value = false
    }
  }, 3500)
}

function onMouseMove(): void {
  showHud()
}

// ==========================================
// 生命周期
// ==========================================
onMounted(() => {
  isUnmounted = false
  void load()
  document.addEventListener('fullscreenchange', onFullscreenChange)
  window.addEventListener('keydown', onKeyDown)
  showHud()
})

onBeforeUnmount(() => {
  isUnmounted = true
  loadSeq++
  destroyPlayer()
  if (hudTimer) clearTimeout(hudTimer)
  if (centerActionTimer) clearTimeout(centerActionTimer)
  cancelAutoNext()
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  window.removeEventListener('keydown', onKeyDown)
})

watch(() => [props.vodId, props.ep, route.query.line, route.query.play_id], () => void load())
watch(() => device.restoredAt, () => void load())
</script>

<template>
  <div
    ref="playerContainerRef"
    class="nf-theater"
    :class="{
      'is-idle': !isHudVisible && isPlaying,
      'is-vertical-theater': isVideoVertical || aspectMode === 'vertical',
      'is-fill': aspectMode === 'fill',
    }"
    @mousemove="onMouseMove"
  >
    <!-- ==================================================== 顶部悬浮控制栏 (Top HUD) -->
    <header class="nf-theater-nav" :class="{ 'is-hidden': !isHudVisible }">
      <div class="nf-nav-left">
        <!-- 经典返回按钮 -->
        <button class="nf-round-back-btn" type="button" title="返回詳情大廳" @click="goBack">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>

        <!-- 影片与集数信息 -->
        <div class="nf-title-group" @click="goToDetail">
          <div class="nf-title-row">
            <h1 class="nf-main-title">{{ vodTitle }}</h1>
            <span v-if="isVideoVertical" class="nf-drama-badge">📱 豎屏微短劇</span>
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
            @click.stop="isAspectMenuOpen = !isAspectMenuOpen; isLineMenuOpen = false; isSpeedMenuOpen = false"
          >
            <span class="nf-btn-icon">📐</span>
            <span class="nf-btn-text">
              {{ aspectMode === 'vertical' ? '豎屏 9:16' : aspectMode === 'widescreen' ? '寬屏 16:9' : aspectMode === 'fill' ? '鋪滿' : '自適應' }}
            </span>
          </button>
          <Transition name="nf-dropdown">
            <div v-if="isAspectMenuOpen" class="nf-pop-dropdown" @click.stop>
              <div class="nf-dropdown-head">畫面比例</div>
              <button class="nf-dropdown-item" :class="{ 'is-active': aspectMode === 'auto' }" type="button" @click="setAspectMode('auto')">
                <span>智能自適應</span>
                <span v-if="aspectMode === 'auto'">✓</span>
              </button>
              <button class="nf-dropdown-item" :class="{ 'is-active': aspectMode === 'vertical' }" type="button" @click="setAspectMode('vertical')">
                <span>豎屏短劇 (9:16)</span>
                <span v-if="aspectMode === 'vertical'">✓</span>
              </button>
              <button class="nf-dropdown-item" :class="{ 'is-active': aspectMode === 'widescreen' }" type="button" @click="setAspectMode('widescreen')">
                <span>影院寬屏 (16:9)</span>
                <span v-if="aspectMode === 'widescreen'">✓</span>
              </button>
              <button class="nf-dropdown-item" :class="{ 'is-active': aspectMode === 'fill' }" type="button" @click="setAspectMode('fill')">
                <span>拉伸鋪滿視界</span>
                <span v-if="aspectMode === 'fill'">✓</span>
              </button>
            </div>
          </Transition>
        </div>

        <!-- 线路切换按钮 -->
        <div v-if="availableLines.length > 1" class="nf-menu-wrapper">
          <button
            class="nf-tool-btn"
            type="button"
            :class="{ 'is-active': isLineMenuOpen }"
            title="選擇播放線路"
            @click.stop="isLineMenuOpen = !isLineMenuOpen; isAspectMenuOpen = false; isSpeedMenuOpen = false"
          >
            <span class="nf-btn-icon">⚡</span>
            <span class="nf-btn-text">線路 {{ currentLine }}</span>
            <span class="nf-arrow-icon" :class="{ 'is-up': isLineMenuOpen }">▾</span>
          </button>
          <Transition name="nf-dropdown">
            <div v-if="isLineMenuOpen" class="nf-pop-dropdown" @click.stop>
              <div class="nf-dropdown-head">高速串流線路</div>
              <button
                v-for="line in availableLines"
                :key="line.line"
                class="nf-dropdown-item"
                :class="{ 'is-active': line.line === currentLine }"
                type="button"
                @click="switchLine(line.line)"
              >
                <span class="nf-dot-online" />
                <span class="nf-item-label">{{ line.name || `線路 ${line.line}` }}</span>
                <span v-if="line.line === currentLine" class="nf-check-mark">✓</span>
              </button>
            </div>
          </Transition>
        </div>

        <!-- 选集抽屉按钮 -->
        <button
          v-if="lineEpisodes.length"
          class="nf-tool-btn"
          type="button"
          :class="{ 'is-active': isDrawerOpen }"
          title="查看完整劇集"
          @click.stop="isDrawerOpen = !isDrawerOpen"
        >
          <span class="nf-btn-icon">☷</span>
          <span class="nf-btn-text">選集</span>
        </button>
      </div>
    </header>

    <!-- ==================================================== 核心视界舞台 (Stage) -->
    <main
      class="nf-theater-stage"
      @click="handleStageClick"
      @mousedown="handleStagePointerDown"
    >
      <!-- 动态弥散背景氛围灯 (Ambient Light Reflection) -->
      <div
        v-if="playback && isVideoVertical"
        class="nf-ambient-backdrop"
        :style="{ backgroundImage: videoMeta?.vod_pic ? `url(${videoMeta.vod_pic})` : undefined }"
      />

      <!-- 核心视频载体 (彻底免除原生 controls，统一交互) -->
      <div
        class="nf-video-wrapper"
        :class="{
          'mode-vertical': isVideoVertical || aspectMode === 'vertical',
          'mode-widescreen': aspectMode === 'widescreen',
          'mode-fill': aspectMode === 'fill',
        }"
      >
        <video
          v-if="playback && !error"
          ref="videoEl"
          class="nf-cinema-video"
          playsinline
          preload="auto"
        />
      </div>

      <!-- 静音自动播放提示微光胶囊 -->
      <Transition name="nf-fade">
        <div v-if="isMutedAutoplay && isPlaying" class="nf-muted-toast" @click.stop="unmuteAudio">
          <span class="nf-muted-icon">🔊</span>
          <span>已為您極速靜音開播，點擊立即開啟聲音</span>
          <button class="nf-muted-btn" type="button">開啟聲音</button>
        </div>
      </Transition>

      <!-- 自动开播被拦截时的显式巨幅开播按钮 -->
      <Transition name="nf-fade">
        <div v-if="isAutoplayBlocked && !isPlaying" class="nf-blocked-gate" @click.stop="() => startPlay(false)">
          <div class="nf-gate-pulse" />
          <button class="nf-gate-play-btn" type="button">
            <svg viewBox="0 0 24 24" width="36" height="36" fill="currentColor">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
          </button>
          <p class="nf-gate-text">串流已就緒 · 點擊立即開始觀影</p>
        </div>
      </Transition>

      <!-- 双击/点击屏幕中央瞬时视觉反馈 (Play/Pause/Seek) -->
      <Transition name="nf-center-pulse">
        <div v-if="centerActionType" class="nf-center-action-badge">
          <div v-if="centerActionType === 'play'" class="nf-center-icon">▶</div>
          <div v-else-if="centerActionType === 'pause'" class="nf-center-icon">⏸</div>
          <div v-else-if="centerActionType === 'seek-fwd'" class="nf-center-seek">
            <span>+10s</span>
            <span class="nf-seek-arrow">⏭</span>
          </div>
          <div v-else-if="centerActionType === 'seek-bwd'" class="nf-center-seek">
            <span class="nf-seek-arrow">⏮</span>
            <span>-10s</span>
          </div>
        </div>
      </Transition>

      <!-- 缓冲/加载中微光旋转动效 -->
      <div v-if="loading || buffering" class="nf-loading-stage" @click.stop="togglePlay">
        <div class="nf-spinner-ring" />
        <p class="nf-loading-label">{{ loading ? loadingText : '串流緩衝中...' }}</p>
      </div>

      <!-- 短剧自动连播倒计时弹层 -->
      <Transition name="nf-pop">
        <div v-if="autoNextCountdown !== null && nextEpisode" class="nf-auto-next-card" @click.stop>
          <div class="nf-next-header">
            <span class="nf-next-pill">微短劇即刻連播</span>
            <span class="nf-next-clock">{{ autoNextCountdown }}s</span>
          </div>
          <div class="nf-next-body">
            <h4 class="nf-next-title">即將播放：第 {{ nextEpisode.ep_index }} 集</h4>
            <p v-if="nextEpisode.ep_name" class="nf-next-name">{{ nextEpisode.ep_name }}</p>
          </div>
          <div class="nf-next-actions">
            <button class="nf-next-btn primary" type="button" @click="playNext">
              立即播放
            </button>
            <button class="nf-next-btn secondary" type="button" @click="cancelAutoNext">
              稍後再看
            </button>
          </div>
        </div>
      </Transition>

      <!-- 线路故障自救卡片 -->
      <div v-if="error" class="nf-error-stage" @click.stop>
        <div class="nf-error-modal">
          <div class="nf-error-icon">⚠️</div>
          <h2 class="nf-error-title">串流解析異常</h2>
          <p class="nf-error-desc">{{ error }}</p>
          <div v-if="lastErrorDetail" class="nf-error-badge">
            故障細節：{{ lastErrorDetail }}
          </div>
          <div class="nf-error-actions">
            <button v-if="!isCompatMode" class="nf-err-btn accent" type="button" @click="reloadInCompatMode">
              以相容模式重新載入 (強制軟解)
            </button>
            <button class="nf-err-btn primary" type="button" @click="() => load()">
              重新載入
            </button>
            <button v-if="availableLines.length > 1" class="nf-err-btn secondary" type="button" @click="isLineMenuOpen = true">
              切換其他高速線路 (共 {{ availableLines.length }} 條)
            </button>
            <button v-else-if="sites.sites.length > 1" class="nf-err-btn secondary" type="button" @click="trySwitchSite">
              切換其他片源站點
            </button>
            <button class="nf-err-btn ghost" type="button" @click="goToDetail">
              返回影片詳情
            </button>
          </div>
        </div>
      </div>
    </main>

    <!-- ==================================================== 底部全定制控制台 (Bottom HUD) -->
    <footer class="nf-ctrl-bar" :class="{ 'is-hidden': !isHudVisible }">
      <!-- 1. 拖拽与缓冲进度条 -->
      <div
        ref="progressBarRef"
        class="nf-progress-container"
        @mousedown="onProgressPointerDown"
        @mousemove="onProgressHover"
        @mouseleave="onProgressLeave"
      >
        <!-- 进度条轨道 -->
        <div class="nf-progress-track">
          <!-- 缓冲段 -->
          <div class="nf-progress-buffered" :style="{ width: `${bufferedPercent}%` }" />
          <!-- 已播段 -->
          <div class="nf-progress-played" :style="{ width: `${progressPercent}%` }">
            <div class="nf-progress-thumb" />
          </div>
        </div>

        <!-- 悬停时间胶囊提示 -->
        <div
          v-if="hoverTime !== null"
          class="nf-progress-tooltip"
          :style="{ left: `${hoverPosition}%` }"
        >
          {{ formatTime(hoverTime) }}
        </div>
      </div>

      <!-- 2. 控制器功能按键列 -->
      <div class="nf-ctrl-row">
        <!-- 左侧核心控制：播放/下一集/音量/时间 -->
        <div class="nf-ctrl-left">
          <!-- 播放/暂停 -->
          <button class="nf-ctrl-btn play-btn" type="button" :title="isPlaying ? '暫停 (Space)' : '播放 (Space)'" @click="togglePlay">
            <svg v-if="!isPlaying" viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
            <svg v-else viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
              <rect x="6" y="4" width="4" height="16" rx="1" />
              <rect x="14" y="4" width="4" height="16" rx="1" />
            </svg>
          </button>

          <!-- 上一集 (短剧必备) -->
          <button
            class="nf-ctrl-btn"
            type="button"
            :disabled="!prevEpisode"
            :title="prevEpisode ? `上一集：第 ${prevEpisode.ep_index} 集` : '已是第一集'"
            @click="playPrev"
          >
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
              <polygon points="19 20 9 12 19 4 19 20" />
              <line x1="5" y1="19" x2="5" y2="5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" />
            </svg>
          </button>

          <!-- 下一集 (短剧必备) -->
          <button
            class="nf-ctrl-btn"
            type="button"
            :disabled="!nextEpisode"
            :title="nextEpisode ? `下一集：第 ${nextEpisode.ep_index} 集 (N)` : '已是最後一集'"
            @click="playNext"
          >
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
              <polygon points="5 4 15 12 5 20 5 4" />
              <line x1="19" y1="5" x2="19" y2="19" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" />
            </svg>
          </button>

          <!-- 音量控制组 -->
          <div class="nf-volume-group">
            <button class="nf-ctrl-btn" type="button" :title="isMuted ? '取消靜音 (M)' : '靜音 (M)'" @click="toggleMute">
              <svg v-if="isMuted || volume === 0" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="1" y1="1" x2="23" y2="23" stroke-width="2" />
                <path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6" />
                <path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23" />
                <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" fill="currentColor" />
              </svg>
              <svg v-else viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" fill="currentColor" />
                <path d="M15.54 8.46a5 5 0 0 1 0 7.07" stroke-linecap="round" />
                <path d="M19.07 4.93a10 10 0 0 1 0 14.14" stroke-linecap="round" />
              </svg>
            </button>
            <div class="nf-volume-slider-wrap">
              <input
                type="range"
                class="nf-volume-range"
                min="0"
                max="1"
                step="0.02"
                :value="isMuted ? 0 : volume"
                @input="(e) => setVolume(Number((e.target as HTMLInputElement).value))"
              >
            </div>
          </div>

          <!-- 时间轴当前/总时长 -->
          <div class="nf-time-display">
            <span class="nf-time-current">{{ formatTime(currentTime) }}</span>
            <span class="nf-time-sep">/</span>
            <span class="nf-time-duration">{{ formatTime(duration) }}</span>
          </div>
        </div>

        <!-- 右侧辅助功能：选集/倍速/画中画/全屏 -->
        <div class="nf-ctrl-right">
          <!-- 底部选集呼出 -->
          <button
            v-if="lineEpisodes.length"
            class="nf-ctrl-btn text-btn"
            type="button"
            :class="{ 'is-active': isDrawerOpen }"
            title="查看完整劇集"
            @click.stop="isDrawerOpen = !isDrawerOpen"
          >
            <span>選集</span>
          </button>

          <!-- 倍速切换 -->
          <div class="nf-menu-wrapper">
            <button
              class="nf-ctrl-btn text-btn"
              type="button"
              :class="{ 'is-active': isSpeedMenuOpen }"
              title="播放倍速"
              @click.stop="isSpeedMenuOpen = !isSpeedMenuOpen; isLineMenuOpen = false; isAspectMenuOpen = false"
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
                  @click="setSpeed(spd)"
                >
                  <span>{{ spd }}x</span>
                  <span v-if="playbackRate === spd">✓</span>
                </button>
              </div>
            </Transition>
          </div>

          <!-- 画中画 (PiP) -->
          <button class="nf-ctrl-btn" type="button" title="畫中畫微端小窗" @click="togglePiP">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="2" y="4" width="20" height="16" rx="2" />
              <rect x="12" y="11" width="8" height="7" rx="1" fill="currentColor" />
            </svg>
          </button>

          <!-- 全屏切换 -->
          <button class="nf-ctrl-btn" type="button" :title="isFullscreen ? '退出全螢幕 (F)' : '全螢幕 (F)'" @click="toggleFullscreen">
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

    <!-- ==================================================== 右侧滑出选集抽屉 (Episodes Drawer) -->
    <Transition name="nf-drawer">
      <aside v-if="isDrawerOpen" class="nf-episodes-drawer" @click.stop>
        <!-- 抽屉顶部标题与模式切换 -->
        <div class="nf-drawer-header">
          <div class="nf-drawer-title-group">
            <h3 class="nf-drawer-title">劇集選集</h3>
            <span class="nf-drawer-count">共 {{ lineEpisodes.length }} 集</span>
          </div>

          <div class="nf-drawer-header-actions">
            <!-- 切换卡片 / 矩阵模式 (集数大于 6 时提供切换) -->
            <div v-if="lineEpisodes.length > 6" class="nf-mode-toggle">
              <button
                class="nf-mode-btn"
                :class="{ 'is-active': drawerMode === 'card' }"
                type="button"
                title="詳細卡片列表"
                @click="drawerMode = 'card'"
              >
                卡片
              </button>
              <button
                class="nf-mode-btn"
                :class="{ 'is-active': drawerMode === 'grid' }"
                type="button"
                title="簡約數字矩陣"
                @click="drawerMode = 'grid'"
              >
                數字
              </button>
            </div>

            <!-- 关闭抽屉按钮 -->
            <button class="nf-drawer-close" type="button" title="關閉選集 (Esc)" @click="isDrawerOpen = false">
              ✕
            </button>
          </div>
        </div>

        <!-- 线路切换指示（多线路时展示） -->
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

        <!-- 长剧集分段分页栏（例如 1-30, 31-60...） -->
        <div v-if="epRanges.length > 0" class="nf-drawer-ranges">
          <button
            v-for="(rng, rIdx) in epRanges"
            :key="rng.label"
            class="nf-range-tab"
            :class="{ 'is-active': selectedEpRange === rIdx }"
            type="button"
            @click="selectedEpRange = rIdx"
          >
            {{ rng.label }}
          </button>
        </div>

        <!-- 滚动内容区：包含选集卡片与剧集介绍 -->
        <div class="nf-drawer-scroll-wrap">
          <!-- 1. 详细卡片模式 (两列紧凑卡片，顶部对齐，严禁纵向拉扯) -->
          <div v-if="drawerMode === 'card'" class="nf-drawer-card-grid">
            <button
              v-for="epItem in pagedEpisodes"
              :key="epItem.ep_index"
              class="nf-drawer-card"
              :class="{ 'is-current': epItem.ep_index === currentEpNumber }"
              type="button"
              @click="switchEpisode(epItem)"
            >
              <div class="nf-card-main">
                <span class="nf-card-ep">第 {{ epItem.ep_index }} 集</span>
                <span v-if="epItem.ep_name" class="nf-card-name" :title="epItem.ep_name">{{ epItem.ep_name }}</span>
              </div>
              <div v-if="epItem.ep_index === currentEpNumber" class="nf-card-status">
                <span class="nf-playing-bars">
                  <span class="nf-bar bar-1" />
                  <span class="nf-bar bar-2" />
                  <span class="nf-bar bar-3" />
                </span>
              </div>
            </button>
          </div>

          <!-- 2. 数字矩阵模式 (五列密集芯片，便于快速翻找上百集短剧) -->
          <div v-else class="nf-drawer-chip-grid">
            <button
              v-for="epItem in pagedEpisodes"
              :key="epItem.ep_index"
              class="nf-drawer-chip"
              :class="{ 'is-current': epItem.ep_index === currentEpNumber }"
              type="button"
              @click="switchEpisode(epItem)"
            >
              <span class="nf-chip-num">{{ epItem.ep_index }}</span>
              <span v-if="epItem.ep_index === currentEpNumber" class="nf-chip-dot" />
            </button>
          </div>

          <!-- 3. 当剧集总数较少时（如电影、单双集），在下方优雅展示剧集详情卡，避免留白与视觉拉扯 -->
          <div v-if="videoMeta" class="nf-drawer-meta-card">
            <div class="nf-meta-header">
              <span class="nf-meta-title">影片簡介</span>
              <span v-if="videoMeta.vod_remarks" class="nf-meta-remarks">{{ videoMeta.vod_remarks }}</span>
            </div>
            <div v-if="videoMeta.vod_type || videoMeta.vod_year || videoMeta.vod_area || videoMeta.vod_score" class="nf-meta-badges">
              <span v-if="videoMeta.vod_type" class="nf-meta-pill">{{ videoMeta.vod_type }}</span>
              <span v-if="videoMeta.vod_year" class="nf-meta-pill">{{ videoMeta.vod_year }}</span>
              <span v-if="videoMeta.vod_area" class="nf-meta-pill">{{ videoMeta.vod_area }}</span>
              <span v-if="videoMeta.vod_score" class="nf-meta-pill score">★ {{ videoMeta.vod_score }}</span>
            </div>
            <p v-if="detail?.desc" class="nf-meta-desc">
              {{ stripHtml(detail.desc) }}
            </p>
            <div v-if="videoMeta.vod_actor" class="nf-meta-row">
              <span class="nf-meta-k">主演：</span>
              <span class="nf-meta-v">{{ videoMeta.vod_actor }}</span>
            </div>
          </div>
        </div>
      </aside>
    </Transition>

    <!-- 抽屉蒙层 -->
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
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  z-index: 100;
}

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
  height: 84px;
  padding: 0 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(180deg, rgba(0, 0, 0, 0.92) 0%, rgba(0, 0, 0, 0.5) 60%, transparent 100%);
  z-index: 40;
  pointer-events: auto;
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.nf-theater-nav.is-hidden {
  opacity: 0;
  transform: translateY(-24px);
  pointer-events: none;
}

.nf-nav-left {
  display: flex;
  align-items: center;
  gap: 18px;
}

.nf-round-back-btn {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(24, 24, 24, 0.7);
  backdrop-filter: blur(12px);
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.nf-round-back-btn:hover {
  background: #e50914;
  border-color: #e50914;
  transform: scale(1.08);
}

.nf-title-group {
  display: flex;
  flex-direction: column;
  gap: 3px;
  cursor: pointer;
}

.nf-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.nf-main-title {
  margin: 0;
  font-size: 19px;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: -0.01em;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.9);
}

.nf-drama-badge {
  background: rgba(229, 9, 20, 0.2);
  border: 1px solid rgba(229, 9, 20, 0.5);
  color: #ff3b30;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 10px;
}

.nf-sub-title {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.75);
  font-weight: 500;
}

.nf-nav-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.nf-menu-wrapper {
  position: relative;
}

.nf-tool-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(24, 24, 24, 0.7);
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
  background: rgba(255, 255, 255, 0.22);
  border-color: rgba(255, 255, 255, 0.45);
}

.nf-pop-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 180px;
  background: rgba(24, 24, 24, 0.96);
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 10px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.85);
  backdrop-filter: blur(16px);
  padding: 8px;
  z-index: 60;
}

.nf-pop-dropdown.up {
  top: auto;
  bottom: calc(100% + 12px);
}

.nf-dropdown-head {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  font-weight: 600;
  padding: 4px 8px 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  margin-bottom: 4px;
}

.nf-dropdown-item {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: #ffffff;
  font-size: 13px;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s ease;
}

.nf-dropdown-item:hover {
  background: rgba(255, 255, 255, 0.12);
}

.nf-dropdown-item.is-active {
  background: rgba(229, 9, 20, 0.2);
  color: #e50914;
  font-weight: 700;
}

.nf-dot-online {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #46d369;
  box-shadow: 0 0 6px #46d369;
}

/* ====================================================================
   播放舞台核心 (Stage & Ambient Glow)
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
  cursor: pointer;
}

/* 弥散环绕氛围灯 (短剧模式自动开启，烘托沉浸感) */
.nf-ambient-backdrop {
  position: absolute;
  inset: -20px;
  background-size: cover;
  background-position: center;
  filter: blur(60px) brightness(0.35);
  opacity: 0.65;
  pointer-events: none;
  transform: scale(1.1);
  z-index: 1;
}

.nf-video-wrapper {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  max-width: 100vw;
  max-height: 100vh;
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

/* 短剧竖屏专属黄金视界容器 (9:16) */
.nf-video-wrapper.mode-vertical {
  width: auto;
  height: 100%;
  max-width: calc(100vh * (9 / 16));
  aspect-ratio: 9 / 16;
  border-radius: 12px;
  box-shadow: 0 0 50px rgba(0, 0, 0, 0.8), 0 0 30px rgba(229, 9, 20, 0.15);
  overflow: hidden;
}

.nf-video-wrapper.mode-widescreen {
  width: 100%;
  max-height: calc(100vw * (9 / 16));
  aspect-ratio: 16 / 9;
}

.nf-video-wrapper.mode-fill {
  width: 100%;
  height: 100%;
}

.nf-cinema-video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background-color: #000000;
  outline: none;
}

.nf-video-wrapper.mode-fill .nf-cinema-video {
  object-fit: cover;
}

/* ====================================================================
   自动播放受限与静音起播交互浮层
==================================================================== */
.nf-muted-toast {
  position: absolute;
  top: 100px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 12px;
  background: rgba(20, 20, 20, 0.9);
  border: 1px solid rgba(229, 9, 20, 0.5);
  backdrop-filter: blur(16px);
  padding: 10px 20px;
  border-radius: 28px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.7);
  z-index: 35;
  cursor: pointer;
  animation: nf-float 2.5s ease-in-out infinite;
}

.nf-muted-btn {
  background: #e50914;
  color: #ffffff;
  border: none;
  border-radius: 14px;
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

/* 受限时的巨型开播大门 */
.nf-blocked-gate {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 18px;
  background: rgba(0, 0, 0, 0.75);
  z-index: 30;
  cursor: pointer;
}

.nf-gate-play-btn {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: #e50914;
  color: #ffffff;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 35px rgba(229, 9, 20, 0.6);
  cursor: pointer;
  transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.nf-gate-play-btn:hover {
  transform: scale(1.12);
}

.nf-gate-text {
  font-size: 16px;
  font-weight: 600;
  color: #ffffff;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.8);
}

/* 屏幕中央微交互脉冲 */
.nf-center-action-badge {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 90px;
  height: 90px;
  border-radius: 50%;
  background: rgba(20, 20, 20, 0.75);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  font-size: 32px;
  pointer-events: none;
  z-index: 25;
}

.nf-center-seek {
  display: flex;
  flex-direction: column;
  align-items: center;
  font-size: 14px;
  font-weight: 700;
}

.nf-center-seek .nf-seek-arrow {
  font-size: 20px;
}

/* 加载 Spinner */
.nf-loading-stage {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  background: rgba(0, 0, 0, 0.6);
  z-index: 20;
  pointer-events: none;
}

.nf-spinner-ring {
  width: 52px;
  height: 52px;
  border: 4px solid rgba(229, 9, 20, 0.2);
  border-top-color: #e50914;
  border-radius: 50%;
  animation: nf-spin 0.8s linear infinite;
}

.nf-loading-label {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.85);
  font-weight: 500;
}

/* 短剧自动连播倒计时卡片 */
.nf-auto-next-card {
  position: absolute;
  bottom: 110px;
  right: 32px;
  width: 320px;
  background: rgba(24, 24, 24, 0.94);
  border: 1px solid rgba(229, 9, 20, 0.4);
  border-radius: 12px;
  padding: 18px;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.85);
  backdrop-filter: blur(20px);
  z-index: 35;
}

.nf-next-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.nf-next-pill {
  background: rgba(229, 9, 20, 0.2);
  color: #ff3b30;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 6px;
}

.nf-next-clock {
  font-size: 16px;
  font-weight: 800;
  color: #e50914;
}

.nf-next-title {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 700;
  color: #ffffff;
}

.nf-next-name {
  margin: 0 0 14px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.65);
}

.nf-next-actions {
  display: flex;
  gap: 10px;
}

.nf-next-btn {
  flex: 1;
  padding: 8px;
  border-radius: 6px;
  border: none;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.nf-next-btn.primary {
  background: #e50914;
  color: #ffffff;
}

.nf-next-btn.primary:hover {
  background: #f40612;
}

.nf-next-btn.secondary {
  background: rgba(255, 255, 255, 0.12);
  color: #ffffff;
}

/* 错误提示卡片 */
.nf-error-stage {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.92);
  z-index: 45;
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
  font-size: 44px;
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
  padding: 12px;
  border-radius: 6px;
  border: none;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.nf-err-btn.primary {
  background: #e50914;
  color: #ffffff;
}

.nf-err-btn.accent {
  background: linear-gradient(135deg, #e65100, #ff9800);
  color: #ffffff;
}

.nf-err-btn.accent:hover {
  background: linear-gradient(135deg, #ef6c00, #ffa726);
}

.nf-err-btn.secondary {
  background: rgba(255, 255, 255, 0.15);
  color: #ffffff;
}

.nf-err-btn.ghost {
  background: transparent;
  color: rgba(255, 255, 255, 0.7);
}

.nf-error-badge {
  display: inline-block;
  margin-top: -12px;
  margin-bottom: 20px;
  padding: 4px 12px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 4px;
  font-family: monospace;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.65);
}

/* ====================================================================
   底部全定制控制台 (Bottom HUD)
==================================================================== */
.nf-ctrl-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 24px 32px 20px;
  background: linear-gradient(0deg, rgba(0, 0, 0, 0.94) 0%, rgba(0, 0, 0, 0.6) 60%, transparent 100%);
  z-index: 40;
  pointer-events: auto;
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.nf-ctrl-bar.is-hidden {
  opacity: 0;
  transform: translateY(24px);
  pointer-events: none;
}

/* 进度条轨道体系 */
.nf-progress-container {
  position: relative;
  width: 100%;
  height: 20px;
  display: flex;
  align-items: center;
  cursor: pointer;
}

.nf-progress-track {
  position: relative;
  width: 100%;
  height: 4px;
  background: rgba(255, 255, 255, 0.24);
  border-radius: 2px;
  transition: height 0.15s ease;
}

.nf-progress-container:hover .nf-progress-track {
  height: 6px;
}

.nf-progress-buffered {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: rgba(255, 255, 255, 0.4);
  border-radius: 2px;
  pointer-events: none;
}

.nf-progress-played {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: #e50914;
  border-radius: 2px;
  pointer-events: none;
}

.nf-progress-thumb {
  position: absolute;
  right: -6px;
  top: 50%;
  transform: translateY(-50%) scale(0);
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #ffffff;
  box-shadow: 0 0 10px rgba(229, 9, 20, 0.8);
  transition: transform 0.15s cubic-bezier(0.16, 1, 0.3, 1);
}

.nf-progress-container:hover .nf-progress-thumb {
  transform: translateY(-50%) scale(1);
}

.nf-progress-tooltip {
  position: absolute;
  bottom: 24px;
  transform: translateX(-50%);
  background: rgba(20, 20, 20, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.2);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
  color: #ffffff;
  pointer-events: none;
  white-space: nowrap;
}

/* 控制按钮列 */
.nf-ctrl-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
}

.nf-ctrl-left,
.nf-ctrl-right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.nf-ctrl-btn {
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.85);
  padding: 8px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: color 0.15s ease, transform 0.15s ease;
}

.nf-ctrl-btn:hover:not(:disabled) {
  color: #ffffff;
  transform: scale(1.12);
}

.nf-ctrl-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.nf-ctrl-btn.play-btn {
  color: #ffffff;
  transform: scale(1.08);
}

.nf-ctrl-btn.text-btn {
  font-size: 14px;
  font-weight: 700;
  border-radius: 4px;
  padding: 4px 8px;
}

/* 音量控制 */
.nf-volume-group {
  display: flex;
  align-items: center;
  gap: 4px;
}

.nf-volume-slider-wrap {
  width: 0;
  overflow: hidden;
  transition: width 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  display: flex;
  align-items: center;
}

.nf-volume-group:hover .nf-volume-slider-wrap {
  width: 80px;
}

.nf-volume-range {
  width: 76px;
  height: 4px;
  accent-color: #e50914;
  cursor: pointer;
}

.nf-time-display {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.85);
}

.nf-time-sep {
  opacity: 0.5;
}

.nf-time-duration {
  opacity: 0.65;
}

/* ====================================================================
   右侧滑出选集抽屉 (Episodes Drawer)
==================================================================== */
.nf-episodes-drawer {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 380px;
  max-width: 90vw;
  background: rgba(18, 18, 18, 0.96);
  border-left: 1px solid rgba(255, 255, 255, 0.12);
  box-shadow: -15px 0 45px rgba(0, 0, 0, 0.85);
  backdrop-filter: blur(28px);
  z-index: 50;
  display: flex;
  flex-direction: column;
}

.nf-drawer-header {
  padding: 20px 22px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
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
  letter-spacing: -0.3px;
}

.nf-drawer-count {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  background: rgba(255, 255, 255, 0.08);
  padding: 2px 8px;
  border-radius: 10px;
}

.nf-drawer-header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.nf-mode-toggle {
  display: flex;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  padding: 2px;
}

.nf-mode-btn {
  background: transparent;
  border: none;
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.65);
  cursor: pointer;
  transition: all 0.15s ease;
}

.nf-mode-btn.is-active {
  background: rgba(255, 255, 255, 0.18);
  color: #ffffff;
  font-weight: 600;
}

.nf-drawer-close {
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.1);
  width: 30px;
  height: 30px;
  border-radius: 50%;
  color: rgba(255, 255, 255, 0.7);
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
}

.nf-drawer-close:hover {
  background: rgba(255, 255, 255, 0.2);
  color: #ffffff;
  transform: scale(1.08);
}

.nf-drawer-lines {
  padding: 10px 22px;
  display: flex;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.nf-drawer-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.nf-drawer-tabs {
  display: flex;
  gap: 8px;
}

.nf-drawer-tab {
  background: rgba(255, 255, 255, 0.08);
  border: none;
  border-radius: 12px;
  padding: 4px 12px;
  color: #ffffff;
  font-size: 12px;
  cursor: pointer;
}

.nf-drawer-tab.is-active {
  background: #e50914;
  font-weight: 700;
}

.nf-drawer-ranges {
  display: flex;
  gap: 6px;
  padding: 10px 22px;
  overflow-x: auto;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
  scrollbar-width: none;
}

.nf-drawer-ranges::-webkit-scrollbar {
  display: none;
}

.nf-range-tab {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  padding: 4px 10px;
  color: rgba(255, 255, 255, 0.7);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s ease;
}

.nf-range-tab.is-active {
  background: #e50914;
  border-color: #e50914;
  color: #ffffff;
}

.nf-drawer-scroll-wrap {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 16px 20px 30px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 详细卡片列表：单列自适应整齐排列，杜绝双列挤爆与偶数集丢失 */
.nf-drawer-card-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.nf-drawer-card {
  width: 100%;
  height: 54px;
  min-height: 54px;
  max-height: 54px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 8px 14px;
  text-align: left;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  box-sizing: border-box;
  min-width: 0;
  overflow: hidden;
  transition: all 0.18s ease;
}

.nf-drawer-card:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.22);
  transform: translateX(-2px);
}

.nf-drawer-card.is-current {
  background: linear-gradient(135deg, rgba(229, 9, 20, 0.25), rgba(229, 9, 20, 0.08));
  border-color: #e50914;
  box-shadow: 0 4px 16px rgba(229, 9, 20, 0.2);
}

.nf-card-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.nf-card-ep {
  font-size: 13px;
  font-weight: 700;
  color: #ffffff;
  white-space: nowrap;
}

.nf-drawer-card.is-current .nf-card-ep {
  color: #ff3b30;
}

.nf-card-name {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.nf-card-status {
  flex-shrink: 0;
}

/* 简约数字芯片网格（5列） */
.nf-drawer-chip-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
  align-content: start;
  width: 100%;
}

.nf-drawer-chip {
  height: 42px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.85);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  min-width: 0;
  overflow: hidden;
  transition: all 0.15s ease;
}

.nf-drawer-chip:hover {
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.25);
}

.nf-drawer-chip.is-current {
  background: #e50914;
  border-color: #e50914;
  color: #ffffff;
  box-shadow: 0 2px 10px rgba(229, 9, 20, 0.4);
}

.nf-chip-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #ffffff;
}

/* 抽屉底部影片简介卡片（避免留白） */
.nf-drawer-meta-card {
  margin-top: auto;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.nf-meta-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.nf-meta-title {
  font-size: 13px;
  font-weight: 700;
  color: #ffffff;
}

.nf-meta-remarks {
  font-size: 11px;
  color: #ff9800;
  font-weight: 600;
}

.nf-meta-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.nf-meta-pill {
  font-size: 10px;
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.7);
  padding: 2px 6px;
  border-radius: 4px;
}

.nf-meta-desc {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.55);
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.nf-meta-row {
  display: flex;
  font-size: 11px;
  line-height: 1.5;
}

.nf-meta-k {
  color: rgba(255, 255, 255, 0.4);
  flex-shrink: 0;
}

.nf-meta-v {
  color: rgba(255, 255, 255, 0.75);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ====================================================================
   动画定义
==================================================================== */
@keyframes nf-spin {
  to { transform: rotate(360deg); }
}

@keyframes nf-float {
  0%, 100% { transform: translate(-50%, 0); }
  50% { transform: translate(-50%, -6px); }
}

@keyframes nf-equalizer {
  from { height: 2px; }
  to { height: 12px; }
}

/* 过渡动效 */
.nf-fade-enter-active, .nf-fade-leave-active { transition: opacity 0.25s ease; }
.nf-fade-enter-from, .nf-fade-leave-to { opacity: 0; }

.nf-dropdown-enter-active, .nf-dropdown-leave-active { transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1); }
.nf-dropdown-enter-from, .nf-dropdown-leave-to { opacity: 0; transform: translateY(-8px); }

.nf-drawer-enter-active, .nf-drawer-leave-active { transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
.nf-drawer-enter-from, .nf-drawer-leave-to { transform: translateX(100%); }

.nf-pop-enter-active, .nf-pop-leave-active { transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1); }
.nf-pop-enter-from, .nf-pop-leave-to { opacity: 0; transform: scale(0.9); }

.nf-center-pulse-enter-active { transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1); }
.nf-center-pulse-leave-active { transition: all 0.35s ease; }
.nf-center-pulse-enter-from { opacity: 0; transform: translate(-50%, -50%) scale(0.5); }
.nf-center-pulse-leave-to { opacity: 0; transform: translate(-50%, -50%) scale(1.4); }

/* 移动端视界优化 */
@media (max-width: 768px) {
  .nf-theater-nav {
    height: 64px;
    padding: 0 16px;
  }
  .nf-ctrl-bar {
    padding: 16px 16px 14px;
  }
  .nf-main-title {
    font-size: 16px;
  }
  .nf-tool-btn .nf-btn-text {
    display: none;
  }
  .nf-auto-next-card {
    right: 16px;
    left: 16px;
    width: auto;
    bottom: 90px;
  }
}
</style>
