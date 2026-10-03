/**
 * hlsFactory - Hls.js 引擎实例化、AES 软解配置与异常恢复调度
 */

import Hls from 'hls.js'
import { getDeviceToken } from '@/api/session'

export interface HlsFactoryCallbacks {
  onError: (msg: string) => void
  onFatalCleanup: () => void
  onManifestParsed: () => void
  onFallbackNativeHls: () => void
  onLastErrorDetail: (detail: string) => void
}

export function createHlsInstance(
  isCompat: boolean,
  video: HTMLVideoElement,
  url: string,
  callbacks: HlsFactoryCallbacks,
): Hls {
  const hls = new Hls({
    xhrSetup: (xhr) => {
      const token = getDeviceToken()
      if (token) {
        xhr.setRequestHeader('X-Device-Token', token)
      }
    },
    enableWorker: !isCompat,
    enableSoftwareAES: true,
    defaultAudioCodec: 'mp4a.40.2',
    lowLatencyMode: false,
    startFragPrefetch: true,
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
    callbacks.onLastErrorDetail(data.details || '')

    if (data.fatal) {
      switch (data.type) {
        case Hls.ErrorTypes.NETWORK_ERROR:
          networkRetry++
          if (networkRetry <= 3) {
            hls.startLoad()
          } else {
            callbacks.onError('串流伺服器連接超時，請檢查網絡或切換備用線路')
            callbacks.onFatalCleanup()
          }
          break

        case Hls.ErrorTypes.MEDIA_ERROR:
          mediaRetry++
          if (mediaRetry === 1) {
            hls.recoverMediaError()
          } else if (mediaRetry === 2) {
            try {
              hls.swapAudioCodec()
            } catch (swapErr) {
              console.warn('swapAudioCodec 触发告警:', swapErr)
            }
            hls.recoverMediaError()
          } else if (mediaRetry === 3 && video.canPlayType('application/vnd.apple.mpegurl')) {
            callbacks.onFallbackNativeHls()
          } else {
            callbacks.onError(`視頻編碼解析異常（${data.details || '當前環境無法解碼'}）`)
            callbacks.onFatalCleanup()
          }
          break

        default:
          if (data.details === Hls.ErrorDetails.KEY_LOAD_ERROR || data.details === Hls.ErrorDetails.KEY_LOAD_TIMEOUT) {
            callbacks.onError('串流解密密鑰 (Key) 獲取失敗，可能存在防盜鏈或跨域限制')
          } else {
            callbacks.onError(`串流解析錯誤（${data.details || '未知錯誤'}）` )
          }
          callbacks.onFatalCleanup()
          break
      }
    }
  })

  hls.attachMedia(video)
  hls.on(Hls.Events.MEDIA_ATTACHED, () => {
    hls.loadSource(url)
  })
  hls.on(Hls.Events.MANIFEST_PARSED, () => {
    callbacks.onManifestParsed()
  })

  return hls
}
