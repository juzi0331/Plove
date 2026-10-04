<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import {
  ElButton,
  ElIcon,
  ElTag,
} from 'element-plus'
import {
  CopyDocument,
  RefreshRight,
  TopRight,
  VideoPlay,
  Warning,
} from '@element-plus/icons-vue'
import Hls from 'hls.js'

const props = defineProps<{
  playbackUrl: string
}>()

const emit = defineEmits<{
  copy: [text: string]
}>()

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
  if (props.playbackUrl) {
    initVideoPlayer(props.playbackUrl)
  }
}

function openStreamExternal(): void {
  if (props.playbackUrl) {
    window.open(props.playbackUrl, '_blank')
  }
}

watch(
  () => props.playbackUrl,
  (newUrl) => {
    if (newUrl) {
      nextTick(() => {
        initVideoPlayer(newUrl)
      })
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  cleanupHls()
})
</script>

<template>
  <div class="player-panel">
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
        <ElButton size="small" :icon="CopyDocument" @click="emit('copy', props.playbackUrl)">
          复制地址
        </ElButton>
      </div>
    </div>

    <!-- 播放地址提示 -->
    <div class="url-bar">
      <span class="url-label">视频流直链:</span>
      <code class="url-badge">{{ props.playbackUrl }}</code>
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
</template>
