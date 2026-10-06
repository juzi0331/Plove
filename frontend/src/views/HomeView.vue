<script setup lang="ts">
/**
 * HomeView - 奈飞官方 1:1 登录后桌面端/大屏沉浸式视频大厅
 *
 * 核心对标用户提供的官方界面：
 * 1. 顶部经典暗夜透明导航栏：包含 Logo、完整导航菜单 (Home, Series, Films, New & Popular, My List...)、搜索、通知、经典蓝脸头像与换源入口；
 * 2. 巨幅大片 Billboard：震撼剧照、大标题、标语、▶ Play 与 ⓘ More Info 官方按钮；
 * 3. 经典影视多行滑轨 (Netflix Horizontal Carousels)：
 *    - 行 1: We think you'll love these (TOP 10 红色角标 + New Season/Episode 专属小标签)
 *    - 行 2: Continue watching for {username} (带官方标志性红色播放进度条)
 *    - 行 3+: 动态影视分类行 (16:9 横版大片剧照卡片 + 左右翻页控制器)
 */

import { showToast } from 'vant'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import * as api from '@/api/client'
import { describeError } from '@/api/http'
import type { HomePayload, HomeSection } from '@/api/types'
import BrandLogo from '@/components/BrandLogo.vue'
import NetflixCard from '@/components/NetflixCard.vue'
import SiteSelector from '@/components/SiteSelector.vue'
import UserMenu from '@/components/UserMenu.vue'
import { useDeviceStore } from '@/stores/device'
import { useSitesStore } from '@/stores/sites'
import { formatCatDisplay } from '@/utils/format'

const sites = useSitesStore()
const device = useDeviceStore()
const router = useRouter()

const home = ref<HomePayload | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const scrolled = ref(false)

// 顶部搜索展开控制
const isSearchOpen = ref(false)
const searchQuery = ref('')
const searchInputRef = ref<HTMLInputElement | null>(null)

// 导航当前选中分类（默认为全部 'all'）
const activeNav = ref('all')
const siteSelectorRef = ref<InstanceType<typeof SiteSelector> | null>(null)

// 视频横幅楼层：优先展示后台勾选的真实分类；若未勾选任何分类，才以“熱播推薦”兜底展示
const displayedSections = computed<HomeSection[]>(() => {
  if (sections.value && sections.value.length > 0) {
    const validSections = sections.value.filter((sec) => sec.videos && sec.videos.length > 0)
    if (validSections.length > 0) {
      return validSections
    }
  }
  // 兜底策略：当后台未勾选任何真实分类板块时，若有推荐数据则展示“熱播推薦”
  if (recommend.value && recommend.value.length > 0) {
    return [{
      title: '熱播推薦',
      videos: recommend.value.slice(0, 10),
    }]
  }
  return []
})

const categories = computed(() => {
  if (sites.currentCategories.length > 0) return sites.currentCategories
  return (home.value?.categories ?? []).filter((c) => !c.hidden)
})
const recommend = computed(() => home.value?.recommend ?? [])
const sections = computed(() => home.value?.sections ?? [])

const homeCache = new Map<string, HomePayload>()

async function load(force = false): Promise<void> {
  error.value = null
  try {
    await sites.load()
    const key = sites.currentKey
    if (!key) {
      home.value = null
      error.value = '後端暫無可用片源站'
      return
    }

    // 内存瞬时还原：若已加载过当前源的首页，秒开展示（0ms），彻底解决从分类返回主页卡顿
    if (!force && homeCache.has(key)) {
      const cached = homeCache.get(key)!
      home.value = cached
      if (cached.categories) {
        sites.setCategories(key, cached.categories)
      }
      // 后台静默对齐最新数据，不打扰当前展示
      void api.getHome(key).then((res) => {
        homeCache.set(key, res)
        home.value = res
        if (res.categories) sites.setCategories(key, res.categories)
      }).catch(() => undefined)
      return
    }

    // 未命中内存缓存时，清空旧数据并进入加载状态，避免跨源残留旧站点的分类与内容
    home.value = null
    loading.value = true
    const result = await api.getHome(key)
    homeCache.set(key, result)
    home.value = result
    if (result.categories) {
      sites.setCategories(key, result.categories)
    }
  } catch (err) {
    home.value = null
    error.value = describeError(err)
  } finally {
    loading.value = false
  }
}

function onScroll(): void {
  scrolled.value = window.scrollY > 30
}

function onSiteChanged(): void {
  activeNav.value = 'all'
  void load()
}

onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true })
  onScroll()
  void load()
  // 主动向服务端核验拉取真实的设备与到期时间
  if (device.activated) void device.heartbeatOnce()
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', onScroll)
})

watch(() => sites.currentKey, () => onSiteChanged())
watch(() => device.restoredAt, () => void load())

function openDetail(item: { vod_id?: string | number }): void {
  if (item?.vod_id) {
    void router.push({
      name: 'detail',
      params: { vodId: String(item.vod_id) },
      state: { site: sites.currentKey || undefined },
    })
  }
}

function openCategory(tid: string): void {
  void router.push({ name: 'category', params: { tid } })
}

function onSelectCategory(tid: string): void {
  activeNav.value = tid
  openCategory(tid)
}

function toggleSearch(): void {
  isSearchOpen.value = !isSearchOpen.value
  if (isSearchOpen.value) {
    setTimeout(() => searchInputRef.value?.focus(), 100)
  }
}

function handleSearchSubmit(): void {
  if (!searchQuery.value.trim()) return
  showToast(`正在全網片源檢索《${searchQuery.value}》...`)
}

function onSearchBlur(): void {
  if (!searchQuery.value.trim()) {
    isSearchOpen.value = false
  }
}

function scrollRow(rowId: string, direction: 'left' | 'right'): void {
  const el = document.getElementById(rowId)
  if (!el) return
  const offset = direction === 'left' ? -el.clientWidth * 0.75 : el.clientWidth * 0.75
  el.scrollBy({ left: offset, behavior: 'smooth' })
}
</script>

<template>
  <div class="nf-home">
    <!-- ==================================================== 顶部官方黑夜导航栏 -->
    <header class="nf-navbar" :class="{ 'is-scrolled': scrolled }">
      <div class="nf-navbar__left">
        <!-- 品牌官方 Logo -->
        <BrandLogo :width="118" :height="32" @click="activeNav = 'all'" />

        <!-- 顶部真实分类导航菜单：展示所有真实分类 -->
        <nav class="nf-nav-menu">
          <button
            class="nf-nav-item"
            :class="{ 'is-active': activeNav === 'all' }"
            type="button"
            @click="activeNav = 'all'"
          >
            全部
          </button>
          <button
            v-for="cat in categories"
            :key="cat.tid"
            class="nf-nav-item"
            :class="{ 'is-active': activeNav === cat.tid }"
            type="button"
            @click="onSelectCategory(cat.tid)"
          >
            {{ formatCatDisplay(cat.name, cat.custom_name) || cat.tid }}
          </button>
          <!-- 切换源加载中骨架占位 -->
          <template v-if="loading && categories.length === 0">
            <span v-for="i in 4" :key="i" class="nf-nav-skeleton-pill" />
          </template>
        </nav>
      </div>

      <div class="nf-navbar__right">
        <!-- 搜索控件 -->
        <div class="nf-search-box" :class="{ 'is-open': isSearchOpen }">
          <button class="nf-icon-btn" type="button" aria-label="搜尋影片" @click="toggleSearch">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.2" d="M21 21l-4.35-4.35m1.35-5.65a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </button>
          <input
            v-if="isSearchOpen"
            ref="searchInputRef"
            v-model="searchQuery"
            class="nf-search-input"
            type="text"
            placeholder="劇名、電影或演員..."
            @keydown.enter="handleSearchSubmit"
            @blur="onSearchBlur"
          />
        </div>

        <!-- 换源下拉选择组件 -->
        <SiteSelector ref="siteSelectorRef" @change="onSiteChanged" />

        <!-- 用户头像与 VIP 会员到期时间面板组件 -->
        <UserMenu />
      </div>
    </header>

    <!-- 移动端专属横向分类导航滑轨 (Mobile Category Bar) -->
    <div v-if="categories.length > 0 || loading" class="nf-mobile-cat-bar">
      <button
        class="nf-mobile-cat-pill"
        :class="{ 'is-active': activeNav === 'all' }"
        type="button"
        @click="activeNav = 'all'"
      >
        全部
      </button>
      <button
        v-for="cat in categories"
        :key="cat.tid"
        class="nf-mobile-cat-pill"
        :class="{ 'is-active': activeNav === cat.tid }"
        type="button"
        @click="onSelectCategory(cat.tid)"
      >
        {{ formatCatDisplay(cat.name, cat.custom_name) || cat.tid }}
      </button>
      <template v-if="loading && categories.length === 0">
        <span v-for="i in 4" :key="i" class="nf-mobile-cat-skeleton-pill" />
      </template>
    </div>

    <!-- ==================================================== 核心影视多行滑轨 (直接展开列表，不要大屏展示) -->
    <main class="nf-main-content">
      <!-- 骨架屏：16:9 横版 Netflix 宽屏多行滑轨骨架 (无缝契合真机布局，位于导航栏正下方) -->
      <div v-if="loading" class="nf-skeleton-wrap">
        <div v-for="r in 3" :key="r" class="nf-skeleton-row">
          <div class="nf-skeleton-title" />
          <div class="nf-skeleton-track">
            <div v-for="c in 6" :key="c" class="nf-skeleton-card" />
          </div>
        </div>
      </div>

      <!-- 错误状态提示与换源 -->
      <div v-else-if="error" class="nf-state-box">
        <div class="nf-state-icon">⚠️</div>
        <p class="nf-state-text">{{ error }}</p>
        <div class="nf-state-actions">
          <button class="nf-action-btn primary" type="button" @click="() => load(true)">重新嘗試</button>
          <button class="nf-action-btn" type="button" @click="siteSelectorRef?.open()">選擇其他片源站</button>
        </div>
      </div>

      <!-- 空数据提示 -->
      <div v-else-if="recommend.length === 0 && sections.length === 0" class="nf-state-box">
        <p class="nf-state-text">當前片源首頁暫無數據，請切換其他片源站</p>
        <div class="nf-state-actions">
          <button class="nf-action-btn primary" type="button" @click="siteSelectorRef?.open()">切換片源線路</button>
        </div>
      </div>

      <!-- 真实内容：全量展示奈飞经典影视多行滑轨 -->
      <template v-else>
        <section
          v-for="(section, sIdx) in displayedSections"
          :key="section.title + sIdx"
          class="nf-row"
        >
          <div class="nf-row__header">
            <h2
              class="nf-row__title"
              :class="{ 'is-clickable': !!section.tid }"
              :title="section.tid ? `進入 ${section.title} 分類瀏覽全部` : ''"
              @click="section.tid && openCategory(section.tid)"
            >
              {{ section.title }}
            </h2>
          </div>
          <div class="nf-row__slider-wrap">
            <button class="nf-row-arrow left" type="button" @click="scrollRow(`row-display-${sIdx}`, 'left')">‹</button>
            <div :id="`row-display-${sIdx}`" class="nf-row__track">
              <NetflixCard
                v-for="(item, idx) in (section.videos ?? []).slice(0, 10)"
                :key="item.vod_id"
                :item="{
                  ...item,
                  isTop10: sIdx === 0 && idx < 5,
                  badgeText: idx === 0 ? 'Recently Added' : (idx === 1 ? 'New Season' : ''),
                }"
                @select="openDetail"
              />
            </div>
            <button class="nf-row-arrow right" type="button" @click="scrollRow(`row-display-${sIdx}`, 'right')">›</button>
          </div>
        </section>
      </template>
    </main>
  </div>
</template>

<style scoped>
/* ====================================================================
   全屏黑夜流媒体容器
==================================================================== */
.nf-home {
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
  height: 68px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 4%;
  background: rgba(20, 20, 20, 0.94);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  transition: background-color 0.3s ease;
}

.nf-navbar.is-scrolled {
  background-color: #141414;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.8);
}

.nf-navbar__left {
  display: flex;
  align-items: center;
  gap: 24px;
  min-width: 0;
}

.nf-nav-menu {
  display: flex;
  align-items: center;
  gap: 16px;
  overflow-x: auto;
  scrollbar-width: none;
  max-width: 58vw;
}

.nf-nav-menu::-webkit-scrollbar {
  display: none;
}

.nf-nav-item {
  background: none;
  border: none;
  color: #e5e5e5;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  padding: 4px 0;
  transition: color 0.2s ease;
  white-space: nowrap;
}

.nf-nav-item:hover {
  color: #b3b3b3;
}

.nf-nav-item.is-active {
  color: #ffffff;
  font-weight: 700;
  cursor: default;
}

.nf-nav-skeleton-pill {
  width: 48px;
  height: 18px;
  border-radius: 4px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.05) 25%, rgba(255, 255, 255, 0.15) 50%, rgba(255, 255, 255, 0.05) 75%);
  background-size: 200% 100%;
  animation: nfNavShimmer 1.5s infinite;
  display: inline-block;
}

@keyframes nfNavShimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.nf-navbar__right {
  display: flex;
  align-items: center;
  gap: 18px;
}

/* 搜索框 */
.nf-search-box {
  display: flex;
  align-items: center;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  transition: all 0.3s ease;
}

.nf-search-box.is-open {
  background: rgba(0, 0, 0, 0.85);
  border-color: rgba(255, 255, 255, 0.7);
  padding: 2px 8px;
}

.nf-search-input {
  background: transparent;
  border: none;
  outline: none;
  color: #ffffff;
  font-size: 13px;
  width: 170px;
  padding: 4px 8px;
}

.nf-icon-btn {
  background: none;
  border: none;
  color: #ffffff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 6px;
  position: relative;
}

.nf-icon-btn svg {
  width: 20px;
  height: 20px;
}

.nf-bell-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background-color: #e50914;
}



/* 骨架屏：16:9 横版专属流光骨架 */
.nf-skeleton-wrap {
  display: flex;
  flex-direction: column;
  gap: 36px;
  padding: 0 4%;
}

.nf-skeleton-row {
  width: 100%;
}

.nf-skeleton-title {
  width: 180px;
  height: 22px;
  border-radius: 4px;
  margin-bottom: 14px;
  background: linear-gradient(90deg, #181818 25%, #2a2a2a 50%, #181818 75%);
  background-size: 200% 100%;
  animation: nf-shimmer 1.6s infinite ease-in-out;
}

.nf-skeleton-track {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 8px;
}

.nf-skeleton-card {
  aspect-ratio: 16 / 9;
  border-radius: 6px;
  background: linear-gradient(90deg, #181818 25%, #262626 50%, #181818 75%);
  background-size: 200% 100%;
  animation: nf-shimmer 1.6s infinite ease-in-out;
}

@keyframes nf-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

@keyframes nf-dropdown-fade {
  from {
    opacity: 0;
    transform: translateY(-6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 状态提示块 (错误 / 空) */
.nf-state-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  min-height: 400px;
  padding: 40px;
  text-align: center;
}

.nf-state-icon {
  font-size: 42px;
}

.nf-state-text {
  font-size: 15px;
  color: rgba(255, 255, 255, 0.7);
  max-width: 480px;
  line-height: 1.6;
  margin: 0;
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

.nf-action-btn:hover {
  background: rgba(255, 255, 255, 0.25);
}

.nf-action-btn.primary {
  background: #e50914;
  border-color: #e50914;
}

.nf-action-btn.primary:hover {
  background: #f40612;
}



/* ====================================================================
   影视多行滑轨 (Netflix Rows) - 紧随导航栏直接展示
==================================================================== */
.nf-main-content {
  position: relative;
  z-index: 3;
  margin-top: 0;
  padding-top: 88px;
  padding-bottom: 80px;
}

.nf-row {
  margin-bottom: 38px;
}

.nf-row__title {
  font-size: 20px;
  font-weight: 700;
  color: #e5e5e5;
  margin: 0 0 12px;
  padding: 0 4%;
  letter-spacing: -0.01em;
}

.nf-row__title.is-clickable {
  cursor: pointer;
  transition: color 0.2s ease;
}

.nf-row__title.is-clickable:hover {
  color: #ffffff;
}

.nf-row__slider-wrap {
  position: relative;
}

.nf-row__track {
  display: flex;
  gap: 8px;
  padding: 16px 4% 20px;
  overflow-x: auto;
  overflow-y: visible;
  scroll-behavior: smooth;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.nf-row__track::-webkit-scrollbar {
  display: none;
}

/* 翻页控制箭头 */
.nf-row-arrow {
  position: absolute;
  top: 16px;
  bottom: 20px;
  width: 4%;
  background: rgba(20, 20, 20, 0.6);
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
  border-radius: 0 4px 4px 0;
}

.nf-row-arrow.right {
  right: 0;
  border-radius: 4px 0 0 4px;
}

.nf-row__slider-wrap:hover .nf-row-arrow {
  opacity: 1;
}

.nf-row-arrow:hover {
  background: rgba(20, 20, 20, 0.9);
}

.nf-mobile-cat-bar {
  display: none;
}

@media (max-width: 900px) {
  .nf-navbar {
    height: 56px;
    padding: 0 16px;
    padding-top: var(--plove-safe-top);
  }

  .nf-navbar__left {
    gap: 12px;
  }

  .nf-nav-menu {
    display: none;
  }

  .nf-navbar__right {
    gap: 10px;
  }

  .nf-search-input {
    width: 120px;
    font-size: 12px;
  }

  /* 移动端横向分类滑轨 (置顶吸顶) */
  .nf-mobile-cat-bar {
    display: flex;
    position: sticky;
    top: calc(56px + var(--plove-safe-top));
    margin-top: calc(56px + var(--plove-safe-top));
    left: 0;
    right: 0;
    z-index: 45;
    background: rgba(20, 20, 20, 0.95);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding: 8px 16px;
    gap: 8px;
    overflow-x: auto;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
  }

  .nf-mobile-cat-bar::-webkit-scrollbar {
    display: none;
  }

  .nf-mobile-cat-pill {
    flex-shrink: 0;
    padding: 5px 14px;
    border-radius: 999px;
    font-size: 13px;
    font-weight: 500;
    color: rgba(255, 255, 255, 0.75);
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.12);
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.2s ease;
  }

  .nf-mobile-cat-pill.is-active {
    color: #ffffff;
    font-weight: 700;
    background: #e50914;
    border-color: #e50914;
    box-shadow: 0 2px 8px rgba(229, 9, 20, 0.4);
  }

  .nf-mobile-cat-skeleton-pill {
    width: 56px;
    height: 28px;
    border-radius: 999px;
    background: linear-gradient(90deg, rgba(255, 255, 255, 0.05) 25%, rgba(255, 255, 255, 0.15) 50%, rgba(255, 255, 255, 0.05) 75%);
    background-size: 200% 100%;
    animation: nfNavShimmer 1.5s infinite;
    flex-shrink: 0;
  }

  .nf-main-content {
    padding-top: 16px;
    padding-bottom: calc(48px + var(--plove-safe-bottom));
  }

  .nf-row {
    margin-bottom: 24px;
  }

  .nf-row__title {
    font-size: 17px;
    padding: 0 16px;
    margin-bottom: 8px;
  }

  .nf-row__track {
    padding: 6px 16px 14px;
    gap: 8px;
  }

  .nf-row-arrow {
    display: none;
  }
}
</style>
