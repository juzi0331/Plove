/**
 * useKeyboard - 播放器全功能键盘映射体系
 */

import { onBeforeUnmount, onMounted } from 'vue'

export interface KeyboardActions {
  togglePlay: () => void
  showHud: () => void
  seekRelative: (offset: number) => void
  triggerCenterAction: (type: 'play' | 'pause' | 'seek-fwd' | 'seek-bwd') => void
  setVolume: (val: number) => void
  getVolume: () => number
  toggleMute: () => void
  toggleFullscreen: () => void
  playNext: () => void
  closeDrawer: () => void
  isDrawerOpen: () => boolean
}

export function useKeyboard(actions: KeyboardActions) {
  function onKeyDown(e: KeyboardEvent): void {
    const tag = (e.target as HTMLElement)?.tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA') return

    switch (e.code) {
      case 'Space':
      case 'KeyK':
        e.preventDefault()
        actions.togglePlay()
        actions.showHud()
        break
      case 'ArrowLeft':
      case 'KeyJ':
        e.preventDefault()
        actions.seekRelative(-5)
        actions.triggerCenterAction('seek-bwd')
        break
      case 'ArrowRight':
      case 'KeyL':
        e.preventDefault()
        actions.seekRelative(5)
        actions.triggerCenterAction('seek-fwd')
        break
      case 'ArrowUp':
        e.preventDefault()
        actions.setVolume(actions.getVolume() + 0.1)
        actions.showHud()
        break
      case 'ArrowDown':
        e.preventDefault()
        actions.setVolume(actions.getVolume() - 0.1)
        actions.showHud()
        break
      case 'KeyM':
        e.preventDefault()
        actions.toggleMute()
        actions.showHud()
        break
      case 'KeyF':
        e.preventDefault()
        actions.toggleFullscreen()
        break
      case 'KeyN':
        e.preventDefault()
        actions.playNext()
        break
      case 'Escape':
        if (actions.isDrawerOpen()) {
          actions.closeDrawer()
        }
        break
    }
  }

  onMounted(() => {
    window.addEventListener('keydown', onKeyDown)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('keydown', onKeyDown)
  })
}
