import { computed, onBeforeUnmount, onMounted, ref, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import * as api from '@/api/client'
import { describeError } from '@/api/http'
import type { DetailPayload, Episode, VodItem } from '@/api/types'
import { useDeviceStore } from '@/stores/device'
import { useSitesStore } from '@/stores/sites'

export function useDetail(vodIdRef: Ref<string>) {
  const sites = useSitesStore()
  const device = useDeviceStore()
  const route = useRoute()
  const router = useRouter()

  const detail = ref<DetailPayload | null>(null)
  const relatedVideos = ref<VodItem[]>([])
  const loading = ref(true)
  const error = ref<string | null>(null)
  const descOpen = ref(false)
  const scrolled = ref(false)

  /** 当前选中的播放线路 */
  const activeLine = ref<number | undefined>(undefined)

  const video = computed(() => detail.value?.video ?? null)
  const lines = computed(() => detail.value?.lines ?? [])
  const allEpisodes = computed(() => detail.value?.episodes ?? [])

  /** 当前线路下的选集列表 */
  const episodes = computed<Episode[]>(() => {
    const line = activeLine.value
    if (line === undefined) return allEpisodes.value
    return allEpisodes.value.filter((episode) => episode.line === line)
  })

  /** 第一集 */
  const firstEpisode = computed<Episode | null>(() => episodes.value[0] ?? null)

  /** 简介太长是否支持展开 */
  const descCanExpand = computed(() => (detail.value?.desc ?? '').length > 120)

  function epLabel(episode: Episode): string {
    const name = (episode.ep_name ?? '').trim()
    const title = (video.value?.vod_name ?? '').trim()
    const usable = name.length > 0 && name.length <= 12 && (!title || !name.includes(title))
    return usable ? name : `第 ${episode.ep_index} 集`
  }

  async function loadDetail(): Promise<void> {
    loading.value = true
    error.value = null
    detail.value = null
    descOpen.value = false
    try {
      await sites.load()
      const siteFromQuery = typeof route.query.site === 'string' ? route.query.site : null
      let key = siteFromQuery || sites.currentKey
      if (!key && sites.sites.length > 0) {
        key = sites.sites[0].key
      }
      if (siteFromQuery && sites.currentKey !== siteFromQuery) {
        sites.select(siteFromQuery)
      }
      if (!key) throw new Error('後端暫無可用片源站')

      // 拉取影片真实详情（带候选站自动探测）
      let result: DetailPayload | null = null
      try {
        result = await api.getDetail(key, vodIdRef.value)
      } catch (initialErr) {
        const candidates = sites.sites.map((s) => s.key).filter((k) => k !== key)
        for (const cand of candidates) {
          try {
            result = await api.getDetail(cand, vodIdRef.value)
            key = cand
            sites.select(cand)
            break
          } catch {
            // 尝试下一源
          }
        }
        if (!result) throw initialErr
      }

      detail.value = result
      activeLine.value = result.lines?.length ? result.lines[0]?.line : undefined

      if (key && route.query.site !== key) {
        void router.replace({
          name: 'detail',
          params: { vodId: vodIdRef.value },
          query: { ...route.query, site: key },
        })
      }

      // 顺便拉取首页推荐作为底部的“更多类似好片”
      void loadRelated(key)
    } catch (err) {
      error.value = describeError(err)
    } finally {
      loading.value = false
    }
  }

  async function loadRelated(key: string): Promise<void> {
    try {
      const homeData = await api.getHome(key)
      const list = homeData.recommend ?? homeData.sections?.[0]?.videos ?? []
      relatedVideos.value = list.filter((v) => String(v.vod_id) !== String(vodIdRef.value)).slice(0, 10)
    } catch {
      relatedVideos.value = []
    }
  }

  function play(episode: Episode | null): void {
    if (!episode) return
    const label = epLabel(episode)
    const siteKey = (typeof route.query.site === 'string' ? route.query.site : null) || sites.currentKey
    void router.push({
      name: 'play',
      params: { vodId: vodIdRef.value, ep: String(episode.ep_index) },
      query: {
        site: siteKey || undefined,
        line: episode.line ?? activeLine.value,
        play_id: episode.play_id || undefined,
        title: video.value?.vod_name || undefined,
        name: label === `第 ${episode.ep_index} 集` ? undefined : label,
      },
    })
  }

  function onScroll(): void {
    scrolled.value = window.scrollY > 40
  }

  /** 记录最初进入详情页的外部路由，默认为 home */
  const initialReferrer = ref<string>('')

  onMounted(() => {
    window.addEventListener('scroll', onScroll, { passive: true })
    onScroll()
    if (device.activated) void device.heartbeatOnce()

    // 检查 history 状态中的前置路由
    const historyBack = window.history.state?.back
    if (historyBack && !historyBack.includes('/detail/')) {
      initialReferrer.value = historyBack
      sessionStorage.setItem('plove_detail_origin', historyBack)
    } else {
      initialReferrer.value = sessionStorage.getItem('plove_detail_origin') || ''
    }
  })

  onBeforeUnmount(() => {
    window.removeEventListener('scroll', onScroll)
  })

  watch(() => vodIdRef.value, () => void loadDetail(), { immediate: true })
  watch(() => sites.currentKey, () => void loadDetail())
  watch(() => device.restoredAt, () => void loadDetail())

  function goBack(): void {
    if (window.history.length > 1) {
      router.back()
    } else {
      const origin = initialReferrer.value || sessionStorage.getItem('plove_detail_origin')
      if (origin && !origin.includes('/detail/')) {
        void router.replace(origin)
      } else {
        void router.replace({ name: 'home' })
      }
    }
  }

  function selectRelated(targetVodId: string | number): void {
    window.scrollTo({ top: 0, behavior: 'smooth' })
    void router.replace({ name: 'detail', params: { vodId: String(targetVodId) } })
  }

  function scrollRow(direction: 'left' | 'right'): void {
    const el = document.getElementById('related-row')
    if (!el) return
    const offset = direction === 'left' ? -el.clientWidth * 0.75 : el.clientWidth * 0.75
    el.scrollBy({ left: offset, behavior: 'smooth' })
  }

  return {
    sites,
    device,
    detail,
    relatedVideos,
    loading,
    error,
    descOpen,
    scrolled,
    activeLine,
    video,
    lines,
    episodes,
    firstEpisode,
    descCanExpand,
    epLabel,
    loadDetail,
    play,
    goBack,
    selectRelated,
    scrollRow,
  }
}
