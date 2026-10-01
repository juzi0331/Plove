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

// 下面视频展示行：随机选取 3 个互不重复的真实分类行展示
const displayedSections = ref<HomeSection[]>([])

const categories = computed(() => home.value?.categories ?? [])
const recommend = computed(() => home.value?.recommend ?? [])
const sections = computed(() => home.value?.sections ?? [])

function pickRandomSections(): void {
  const pool: HomeSection[] = []

  // 1. 如果后端有真实推荐 recommend，加入候选行
  if (recommend.value && recommend.value.length > 0) {
    pool.push({
      title: '熱播推薦',
      videos: recommend.value,
    })
  }

  // 2. 将后端源站所有有视频的真实板块加入候选
  for (const sec of sections.value) {
    if (sec.videos && sec.videos.length > 0) {
      // 避免标题重复
      if (!pool.some((p) => p.title === sec.title)) {
        pool.push(sec)
      }
    }
  }

  if (pool.length <= 3) {
    displayedSections.value = pool
    return
  }

  // Fisher-Yates 洗牌算法随机选取 3 个不重复的分类行 (消除 M-3)
  const shuffled = [...pool]
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    const temp = shuffled[i]
    shuffled[i] = shuffled[j]
    shuffled[j] = temp
  }
  displayedSections.value = shuffled.slice(0, 3)
}

async function load(): Promise<void> {
  if (loading.value) return
  loading.value = true
  error.value = null
  try {
    await sites.load()
    const key = sites.currentKey
    if (!key) {
      home.value = null
      error.value = '後端暫無可用片源站'
      return
    }
    home.value = await api.getHome(key)
    pickRandomSections()
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

watch(() => sites.currentKey, () => void load())
watch(() => device.restoredAt, () => void load())

function openDetail(item: { vod_id?: string | number }): void {
  if (item?.vod_id) {
    void router.push({ name: 'detail', params: { vodId: String(item.vod_id) } })
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
            {{ cat.name || cat.tid }}
          </button>
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
        <SiteSelector ref="siteSelectorRef" />

        <!-- 用户头像与 VIP 会员到期时间面板组件 -->
        <UserMenu />
      </div>
    </header>

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
          <button class="nf-action-btn primary" type="button" @click="load">重新嘗試</button>
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

      <!-- 真实内容：随机展示 3 个互不重复的真实分类行 -->
      <template v-else>
        <section
          v-for="(section, sIdx) in displayedSections"
          :key="section.title + sIdx"
          class="nf-row"
        >
          <h2 class="nf-row__title">{{ section.title }}</h2>
          <div class="nf-row__slider-wrap">
            <button class="nf-row-arrow left" type="button" @click="scrollRow(`row-display-${sIdx}`, 'left')">‹</button>
            <div :id="`row-display-${sIdx}`" class="nf-row__track">
              <NetflixCard
                v-for="(item, idx) in section.videos ?? []"
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

@media (max-width: 900px) {
  .nf-nav-menu { display: none; }
  .nf-billboard { height: 60vh; min-height: 420px; }
  .nf-row-arrow { display: none; }
}
</style>
