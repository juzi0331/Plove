/**
 * videoEvents - 原生 HTMLVideoElement 事件绑定与生命周期回调
 */

export interface VideoEventCallbacks {
  onPlayStateChange: (playing: boolean) => void
  onBufferingChange: (buffering: boolean) => void
  onProgressUpdate: (curr: number, buffered: number) => void
  onDurationChange: (dur: number) => void
  onVolumeChange: (vol: number, muted: boolean) => void
  onAutoNext: () => void
  onFatalVideoError: () => void
}

export function bindVideoEvents(
  video: HTMLVideoElement,
  callbacks: VideoEventCallbacks,
): void {
  video.onplay = () => {
    callbacks.onPlayStateChange(true)
  }

  video.onplaying = () => {
    callbacks.onPlayStateChange(true)
    callbacks.onBufferingChange(false)
  }

  video.onpause = () => {
    callbacks.onPlayStateChange(false)
    callbacks.onBufferingChange(false)
  }

  video.onwaiting = () => {
    callbacks.onBufferingChange(true)
  }

  video.onseeking = () => {
    callbacks.onBufferingChange(true)
  }

  video.onseeked = () => {
    callbacks.onBufferingChange(false)
  }

  video.ontimeupdate = () => {
    let bufEnd = 0
    if (video.buffered.length > 0) {
      for (let i = video.buffered.length - 1; i >= 0; i--) {
        if (video.buffered.start(i) <= video.currentTime) {
          bufEnd = video.buffered.end(i)
          break
        }
      }
    }
    callbacks.onProgressUpdate(video.currentTime, bufEnd)
  }

  video.ondurationchange = () => {
    if (video.duration && !isNaN(video.duration) && video.duration !== Infinity) {
      callbacks.onDurationChange(video.duration)
    }
  }

  video.onloadedmetadata = () => {
    if (video.duration && !isNaN(video.duration)) {
      callbacks.onDurationChange(video.duration)
    }
  }

  video.onvolumechange = () => {
    callbacks.onVolumeChange(video.volume, video.muted)
  }

  video.onended = () => {
    callbacks.onPlayStateChange(false)
    callbacks.onAutoNext()
  }

  video.onerror = () => {
    callbacks.onFatalVideoError()
  }
}
