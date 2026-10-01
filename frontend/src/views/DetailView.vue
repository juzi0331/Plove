<script setup lang="ts">
/**
 * DetailView - 奈飞官方 1:1 沉浸式宽银幕大屏影视详情大厅
 *
 * 核心对标 Netflix 官方桌面端/大屏播放详情页：
 * 1. 顶部经典暗夜透明毛玻璃导航栏：Logo + 返回大厅 + 剧名标识 + 换源选择面板 + VIP 到期时间弹窗；
 * 2. 震撼 16:9 巨幅宽银幕 Hero 画卷 (Cinematic Banner)：三向暗影遮罩、剧名大标题、4K/年份/标签胶囊、▶ 立即播放与切源大按钮；
 * 3. 黄金比例双栏布局：
 *    - 左主栏 (70%)：影视剧情简介、多线路切换胶囊 (Line Tabs)、大屏现代化集数卡片矩阵 (Episodes Grid)；
 *    - 右侧栏 (30%)：主演阵容、导演类型、片源线路、VIP 尊享特权徽章；
 * 4. 底部沉浸式扩展行：“更多类似好片 (More Like This)” 16:9 横版 NetflixCard 滑轨；
 * 5. 专属 16:9 影院流光骨架屏，首屏无缝过渡，绝无突兀竖屏或巨大海报错位。
 */

import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import * as api from '@/api/client'
import { describeError } from '@/api/http'
import type { DetailPayload, Episode, VodItem } from '@/api/types'
import BrandLogo from '@/components/BrandLogo.vue'
import NetflixCard from '@/components/NetflixCard.vue'
import UserMenu from '@/components/UserMenu.vue'
import { useDeviceStore } from '@/stores/device'
import { useSitesStore } from '@/stores/sites'

const props = defineProps<{ vodId: string }>()

const sites = useSitesStore()
const device = useDeviceStore()
const router = useRouter()

const detail = ref<DetailPayload | null>(null)
const relatedVideos = ref<VodItem[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const descOpen = ref(false)

const scrolled = ref(false)

/** 当前选中的播放线路 */
const activeLine = ref<number | undefined>(undefined)
/** 用户是否主动点过线路；未主动选择时走“自动最快线路”。 */
const lineManuallySelected = ref(false)

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
    const key = sites.currentKey
    if (!key) throw new Error('後端暫無可用片源站')

    // 拉取影片真实详情
    const result = await api.getDetail(key, props.vodId)
    detail.value = result
    activeLine.value = result.lines?.length ? result.lines[0]?.line : undefined
    lineManuallySelected.value = false

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
    relatedVideos.value = list.filter((v) => String(v.vod_id) !== String(props.vodId)).slice(0, 10)
  } catch {
    relatedVideos.value = []
  }
}

function selectLine(lineId: number): void {
  activeLine.value = lineId
  lineManuallySelected.value = true
}

function play(episode: Episode | null): void {
  if (!episode) return
  const label = epLabel(episode)
  const manualLine = lineManuallySelected.value
  // 小鸭的详情页内嵌几十条 CDN，可在 play 阶段并行测速后选最快；
  // 网飞猫等源则保留详情返回的优选 play_id，避免为了自动选线再抓一次详情页。
  const autoProbe = !manualLine && sites.currentKey === 'xiaoyakankan'
  void router.push({
    name: 'play',
    params: { vodId: props.vodId, ep: String(episode.ep_index) },
    query: {
      line: autoProbe ? undefined : (episode.line ?? activeLine.value),
      play_id: autoProbe ? undefined : (episode.play_id || undefined),
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

watch(() => props.vodId, () => void loadDetail(), { immediate: true })
watch(() => sites.currentKey, () => void loadDetail())
watch(() => device.restoredAt, () => void loadDetail())

function goBack(): void {
  // 优先返回最初进入详情页的列表/大厅（分类页或主页）
  const origin = initialReferrer.value || sessionStorage.getItem('plove_detail_origin')
  if (origin && !origin.includes('/detail/')) {
    void router.push(origin)
  } else if (window.history.length > 1) {
    router.back()
  } else {
    void router.push({ name: 'home' })
  }
}

/**
 * 切换更多类似好片：使用 replace 避免详情页层级套娃
 */
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
</script>

<template>
  <div class="nf-detail-view">
    <!-- ==================================================== 顶部官方暗夜导航栏 -->
    <header class="nf-navbar" :class="{ 'is-scrolled': scrolled }">
      <div class="nf-navbar__left">
        <!-- 品牌官方 Logo -->
        <BrandLogo :width="118" :height="32" @click="router.push({ name: 'home' })" />

        <!-- 返回主页按钮 -->
        <button class="nf-back-btn" type="button" @click="goBack">
          <span class="nf-back-arrow">‹</span>
          <span class="nf-back-text">返回</span>
        </button>

        <!-- 当前影片标题标签 -->
        <span v-if="video" class="nf-nav-vod-title">{{ video.vod_name }}</span>
      </div>

      <div class="nf-navbar__right">
        <!-- 用户头像与 VIP 会员到期时间面板组件 -->
        <UserMenu />
      </div>
    </header>

    <!-- ==================================================== 首屏骨架屏 -->
    <div v-if="loading" class="nf-detail-skeleton">
      <div class="nf-skeleton-hero" />
      <div class="nf-skeleton-content">
        <div class="nf-skeleton-main">
          <div class="nf-skeleton-bar lg" />
          <div class="nf-skeleton-bar md" />
          <div class="nf-skeleton-bar sm" />
          <div class="nf-skeleton-grid">
            <div v-for="n in 8" :key="n" class="nf-skeleton-box" />
          </div>
        </div>
      </div>
    </div>

    <!-- 错误处理 -->
    <div v-else-if="error" class="nf-state-box">
      <div class="nf-state-icon">⚠️</div>
      <p class="nf-state-text">{{ error }}</p>
      <div class="nf-state-actions">
        <button class="nf-action-btn primary" type="button" @click="loadDetail">重新嘗試</button>
        <button class="nf-action-btn" type="button" @click="goBack">返回大廳</button>
      </div>
    </div>

    <!-- ==================================================== 真实详情大厅 -->
    <main v-else-if="video" class="nf-detail-main">
      <!-- 1. 宽银幕 Hero 画卷 (Cinematic Billboard) -->
      <section class="nf-detail-hero">
        <div
          class="nf-hero-bg"
          :style="{ backgroundImage: `url(${video.vod_pic || ''})` }"
        />
        <div class="nf-hero-vignette" />

        <!-- Hero 底部核心内容面板 -->
        <div class="nf-hero-caption">
          <div class="nf-hero-badges">
            <span class="nf-badge-gold">★ 9.8 評分</span>
            <span class="nf-badge-red">Netflix 首選推薦</span>
            <span class="nf-badge-hd">4K Ultra HD</span>
            <span v-if="video.vod_year" class="nf-badge-gray">{{ video.vod_year }}</span>
            <span v-if="video.vod_remarks" class="nf-badge-gray">{{ video.vod_remarks }}</span>
          </div>

          <h1 class="nf-hero-title">{{ video.vod_name }}</h1>

          <!-- 播放与快速交互按钮组 -->
          <div class="nf-hero-actions">
            <button
              class="nf-btn-play"
              type="button"
              :disabled="!firstEpisode"
              @click="play(firstEpisode)"
            >
              <span class="nf-play-icon">▶</span>
              <span class="nf-play-text">{{ firstEpisode ? '立即播放' : '暫無片源' }}</span>
            </button>
          </div>
        </div>
      </section>

      <!-- 2. 双栏详情信息区 -->
      <div class="nf-detail-body">
        <!-- 左侧核心区 (选集与简介) -->
        <div class="nf-main-col">
          <!-- 剧情简介 -->
          <section v-if="detail?.desc" class="nf-block nf-desc-block">
            <h2 class="nf-block-title">劇情簡介</h2>
            <p class="nf-desc-text" :class="{ 'is-open': descOpen }">
              {{ detail.desc }}
            </p>
            <button
              v-if="descCanExpand"
              class="nf-desc-more-btn"
              type="button"
              @click="descOpen = !descOpen"
            >
              {{ descOpen ? '收起簡介 ▴' : '閱讀完整簡介 ▾' }}
            </button>
          </section>

          <!-- 多线路切换标签 -->
          <section v-if="lines.length > 1" class="nf-block nf-lines-block">
            <div class="nf-lines-header">
              <span class="nf-lines-title">播放線路：</span>
              <div class="nf-lines-tabs">
                <button
                  v-for="line in lines"
                  :key="line.line"
                  class="nf-line-tab"
                  :class="{ 'is-active': activeLine === line.line }"
                  type="button"
                  @click="selectLine(line.line)"
                >
                  <span class="nf-line-dot" />
                  <span>{{ line.name || `高速線路 ${line.line}` }}</span>
                </button>
              </div>
            </div>
          </section>

          <!-- 选集大厅 (Episodes Matrix) -->
          <section class="nf-block nf-episodes-block">
            <div class="nf-ep-header">
              <h2 class="nf-block-title">劇集列表</h2>
              <span class="nf-ep-count">全 {{ episodes.length }} 集</span>
            </div>

            <div v-if="episodes.length" class="nf-episodes-grid">
              <button
                v-for="episode in episodes"
                :key="`${episode.line ?? 0}-${episode.ep_index}-${episode.play_id}`"
                class="nf-ep-card"
                type="button"
                @click="play(episode)"
              >
                <div class="nf-ep-card__top">
                  <span class="nf-ep-card__play">▶</span>
                  <span class="nf-ep-card__badge">高清</span>
                </div>
                <div class="nf-ep-card__name">{{ epLabel(episode) }}</div>
              </button>
            </div>
            <p v-else class="nf-none-text">當前線路暫無有效劇集</p>
          </section>
        </div>

        <!-- 右侧辅助信息栏 -->
        <aside class="nf-side-col">
          <!-- 演职人员与信息卡片 -->
          <div class="nf-meta-card">
            <h3 class="nf-meta-card__title">影視檔案</h3>

            <div v-if="video.vod_actor" class="nf-meta-item">
              <span class="nf-meta-label">主演：</span>
              <span class="nf-meta-val">{{ video.vod_actor }}</span>
            </div>


            <div v-if="video.vod_type" class="nf-meta-item">
              <span class="nf-meta-label">類型：</span>
              <span class="nf-meta-val highlight">{{ video.vod_type }}</span>
            </div>

            <div v-if="video.vod_area" class="nf-meta-item">
              <span class="nf-meta-label">地區：</span>
              <span class="nf-meta-val">{{ video.vod_area }}</span>
            </div>

            <div class="nf-meta-item">
              <span class="nf-meta-label">畫質規格：</span>
              <span class="nf-meta-val green">4K 超高清 HDR</span>
            </div>

            <div class="nf-meta-item">
              <span class="nf-meta-label">播放權益：</span>
              <span class="nf-meta-val gold">VIP 無限次暢享</span>
            </div>
          </div>
        </aside>
      </div>

      <!-- 3. 底部“猜你喜欢 / 相关推荐”滑轨 -->
      <section v-if="relatedVideos.length" class="nf-related-section">
        <h2 class="nf-related-title">更多類似好片 · More Like This</h2>
        <div class="nf-related-slider-wrap">
          <button class="nf-row-arrow left" type="button" @click="scrollRow('left')">‹</button>
          <div id="related-row" class="nf-related-track">
            <NetflixCard
              v-for="item in relatedVideos"
              :key="item.vod_id"
              :item="item"
              @select="(it) => selectRelated(it.vod_id)"
            />
          </div>
          <button class="nf-row-arrow right" type="button" @click="scrollRow('right')">›</button>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
/* ====================================================================
   全屏黑夜流媒体容器
==================================================================== */
.nf-detail-view {
  min-height: 100vh;
  background-color: #141414;
  color: #ffffff;
  overflow-x: hidden;
  user-select: none;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* ====================================================================
   官方顶部导航栏 (Navbar)
==================================================================== */
.nf-navbar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 4%;
  height: 68px;
  background: rgba(20, 20, 20, 0.85);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}

.nf-navbar.is-scrolled {
  background: rgba(14, 14, 14, 0.98);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.9);
}

.nf-navbar__left {
  display: flex;
  align-items: center;
  gap: 20px;
  flex: 1;
  overflow: hidden;
}

.nf-back-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 18px;
  padding: 5px 14px;
  color: #ffffff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s ease;
}

.nf-back-btn:hover {
  background: rgba(255, 255, 255, 0.22);
}

.nf-back-arrow {
  font-size: 18px;
  line-height: 1;
}

.nf-nav-vod-title {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 320px;
}

.nf-navbar__right {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
}


/* ====================================================================
   宽银幕 Hero 画卷 (Cinematic Billboard)
==================================================================== */
.nf-detail-hero {
  position: relative;
  width: 100%;
  height: 62vh;
  min-height: 480px;
  max-height: 720px;
  overflow: hidden;
  background-color: #0b0b0b;
}

.nf-hero-bg {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center top;
  filter: brightness(0.72) saturate(1.1);
  transform: scale(1.02);
  transition: transform 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}

.nf-hero-vignette {
  position: absolute;
  inset: 0;
  background:
    /* 左侧向右深色遮罩，保证大标题与操作区文字极清晰 */
    linear-gradient(90deg, rgba(20, 20, 20, 0.95) 0%, rgba(20, 20, 20, 0.6) 40%, transparent 80%),
    /* 底部向上与全屏背景完美融合 */
    linear-gradient(0deg, #141414 0%, rgba(20, 20, 20, 0.8) 25%, transparent 60%),
    /* 顶部导航微阴影 */
    linear-gradient(180deg, rgba(0, 0, 0, 0.6) 0%, transparent 30%);
}

.nf-hero-caption {
  position: absolute;
  left: 4%;
  bottom: 40px;
  max-width: 680px;
  z-index: 10;
}

.nf-hero-badges {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.nf-badge-gold {
  background: rgba(245, 197, 24, 0.2);
  color: #f5c518;
  border: 1px solid rgba(245, 197, 24, 0.4);
  font-size: 12px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 4px;
}

.nf-badge-red {
  background: #e50914;
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 4px;
  letter-spacing: 0.5px;
}

.nf-badge-hd {
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 3px;
}

.nf-badge-gray {
  color: rgba(255, 255, 255, 0.7);
  font-size: 12px;
}

.nf-hero-title {
  margin: 0 0 24px;
  font-size: 40px;
  font-weight: 800;
  line-height: 1.15;
  color: #ffffff;
  letter-spacing: -0.02em;
  text-shadow: 0 4px 18px rgba(0, 0, 0, 0.8);
}

.nf-hero-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.nf-btn-play {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 12px 28px;
  border: none;
  border-radius: 6px;
  background-color: #ffffff;
  color: #000000;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4);
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.nf-btn-play:hover:not(:disabled) {
  background-color: rgba(255, 255, 255, 0.85);
  transform: scale(1.05);
}

.nf-btn-play:disabled {
  background: #333333;
  color: #888888;
  cursor: not-allowed;
}

.nf-play-icon {
  font-size: 15px;
}



/* ====================================================================
   双栏详情内容区
==================================================================== */
.nf-detail-body {
  display: flex;
  gap: 40px;
  padding: 30px 4% 60px;
}

.nf-main-col {
  flex: 1 1 68%;
  min-width: 0;
}

.nf-side-col {
  flex: 0 0 320px;
  width: 320px;
}

.nf-block {
  margin-bottom: 32px;
}

.nf-block-title {
  margin: 0 0 14px;
  font-size: 20px;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: -0.01em;
}

/* 剧情简介 */
.nf-desc-text {
  margin: 0;
  color: #d2d2d2;
  font-size: 15px;
  line-height: 1.8;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.nf-desc-text.is-open {
  -webkit-line-clamp: unset;
}

.nf-desc-more-btn {
  margin-top: 8px;
  background: none;
  border: none;
  color: #e50914;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  padding: 0;
}

/* 播放线路 */
.nf-lines-header {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.nf-lines-title {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.6);
  font-weight: 600;
}

.nf-lines-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.nf-line-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 20px;
  color: #ffffff;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.nf-line-tab:hover {
  background: rgba(255, 255, 255, 0.18);
}

.nf-line-tab.is-active {
  background: rgba(229, 9, 20, 0.9);
  border-color: #e50914;
  font-weight: 600;
  box-shadow: 0 2px 10px rgba(229, 9, 20, 0.4);
}

.nf-line-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: #46d369;
}

/* 选集大厅 (Episodes Matrix) */
.nf-ep-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.nf-ep-count {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
  font-weight: 600;
}

.nf-episodes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 12px;
}

.nf-ep-card {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 72px;
  padding: 10px 12px;
  background: rgba(36, 36, 36, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  cursor: pointer;
  text-align: left;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.nf-ep-card:hover {
  background: rgba(50, 50, 50, 0.95);
  border-color: rgba(255, 255, 255, 0.35);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.5);
}

.nf-ep-card__top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.nf-ep-card__play {
  font-size: 11px;
  color: #e50914;
}

.nf-ep-card__badge {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.5);
}

.nf-ep-card__name {
  font-size: 13px;
  font-weight: 600;
  color: #ffffff;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nf-none-text {
  color: rgba(255, 255, 255, 0.4);
  font-size: 14px;
}

/* 侧边信息卡片 */
.nf-meta-card {
  background: rgba(26, 26, 26, 0.75);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  padding: 24px;
  backdrop-filter: blur(10px);
}

.nf-meta-card__title {
  margin: 0 0 18px;
  font-size: 16px;
  font-weight: 700;
  color: #ffffff;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  padding-bottom: 10px;
}

.nf-meta-item {
  display: flex;
  margin-bottom: 14px;
  font-size: 13px;
  line-height: 1.6;
}

.nf-meta-label {
  color: rgba(255, 255, 255, 0.5);
  width: 70px;
  flex-shrink: 0;
}

.nf-meta-val {
  color: #ffffff;
  word-break: break-all;
}

.nf-meta-val.highlight {
  color: #e50914;
  font-weight: 600;
}

.nf-meta-val.green {
  color: #46d369;
}

.nf-meta-val.gold {
  color: #ffd700;
  font-weight: 600;
}

/* ====================================================================
   底部类似影片滑轨 (More Like This)
==================================================================== */
.nf-related-section {
  padding: 0 4% 80px;
}

.nf-related-title {
  font-size: 22px;
  font-weight: 700;
  color: #ffffff;
  margin: 0 0 18px;
  letter-spacing: -0.01em;
}

.nf-related-slider-wrap {
  position: relative;
}

.nf-related-track {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  scroll-behavior: smooth;
  scrollbar-width: none;
  -ms-overflow-style: none;
  padding: 12px 0 24px;
}

.nf-related-track::-webkit-scrollbar {
  display: none;
}

.nf-row-arrow {
  position: absolute;
  top: 12px;
  bottom: 24px;
  width: 40px;
  background: rgba(20, 20, 20, 0.7);
  border: none;
  color: #ffffff;
  font-size: 32px;
  cursor: pointer;
  z-index: 15;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s ease, background-color 0.2s ease;
}

.nf-row-arrow.left {
  left: 0;
  border-radius: 0 6px 6px 0;
}

.nf-row-arrow.right {
  right: 0;
  border-radius: 6px 0 0 6px;
}

.nf-related-slider-wrap:hover .nf-row-arrow {
  opacity: 1;
}

.nf-row-arrow:hover {
  background: rgba(20, 20, 20, 0.95);
}

/* ====================================================================
   首屏骨架屏与状态
==================================================================== */
.nf-detail-skeleton {
  padding-top: 68px;
}

.nf-skeleton-hero {
  width: 100%;
  height: 50vh;
  min-height: 400px;
  background: linear-gradient(90deg, #181818 25%, #242424 50%, #181818 75%);
  background-size: 200% 100%;
  animation: nf-shimmer 1.6s infinite ease-in-out;
}

.nf-skeleton-content {
  padding: 30px 4%;
}

.nf-skeleton-bar {
  border-radius: 4px;
  background: linear-gradient(90deg, #181818 25%, #242424 50%, #181818 75%);
  background-size: 200% 100%;
  animation: nf-shimmer 1.6s infinite ease-in-out;
  margin-bottom: 16px;
}

.nf-skeleton-bar.lg { width: 50%; height: 36px; }
.nf-skeleton-bar.md { width: 35%; height: 20px; }
.nf-skeleton-bar.sm { width: 70%; height: 16px; }

.nf-skeleton-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px;
  margin-top: 30px;
}

.nf-skeleton-box {
  height: 60px;
  border-radius: 6px;
  background: linear-gradient(90deg, #181818 25%, #242424 50%, #181818 75%);
  background-size: 200% 100%;
  animation: nf-shimmer 1.6s infinite ease-in-out;
}

@keyframes nf-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* 状态提示块 (错误) */
.nf-state-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  min-height: 500px;
  padding: 40px;
  text-align: center;
}

.nf-state-icon { font-size: 42px; }
.nf-state-text {
  font-size: 15px;
  color: rgba(255, 255, 255, 0.7);
  max-width: 480px;
  line-height: 1.6;
}

.nf-state-actions {
  display: flex;
  gap: 12px;
  margin-top: 10px;
}

.nf-action-btn {
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 4px;
  color: #ffffff;
  padding: 8px 20px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.nf-action-btn.primary {
  background: #e50914;
  border-color: #e50914;
}

@media (max-width: 900px) {
  .nf-detail-body {
    flex-direction: column;
  }
  .nf-side-col {
    width: 100%;
  }
  .nf-hero-title {
    font-size: 28px;
  }
}
</style>
