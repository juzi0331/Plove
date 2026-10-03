<script setup lang="ts">
/**
 * CategoryView - 奈飞官方 1:1 风格沉浸式分类大屏与 16:9 无限瀑布流
 *
 * 核心对标主页设计：
 * 1. 顶部经典暗夜毛玻璃导航栏：包含 Logo、返回按钮、当前分类名与全部分类横滑菜单；
 * 2. 右侧与主页对齐：片源下拉菜单 + VIP 头像点击弹窗（展示真实到期时间与天数）；
 * 3. 核心流式内容：16:9 黄金宽银幕 NetflixCard 响应式无限瀑布流（触底自动加载下一页）；
 * 4. 专属 16:9 极速流光骨架屏，无缝过渡，绝无巨大竖版卡片与跳屏现象。
 */

import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import * as api from '@/api/client'
import { describeError } from '@/api/http'
import type { VodCategory, VodItem } from '@/api/types'
import BrandLogo from '@/components/BrandLogo.vue'
import NetflixCard from '@/components/NetflixCard.vue'
import SiteSelector from '@/components/SiteSelector.vue'
import UserMenu from '@/components/UserMenu.vue'
import { useDeviceStore } from '@/stores/device'
import { useSitesStore } from '@/stores/sites'

const props = defineProps<{ tid: string }>()

const sites = useSitesStore()
const device = useDeviceStore()
const router = useRouter()

const siteSelectorRef = ref<InstanceType<typeof SiteSelector> | null>(null)
const items = ref<VodItem[]>([])
const allCategories = ref<VodCategory[]>([])
const firstLoading = ref(true)
const firstError = ref<string | null>(null)
const loadingMore = ref(false)
const finished = ref(false)
const page = ref(1)

const scrolled = ref(false)

// 当前分类名称
const categoryTitle = computed(() => {
  const found = allCategories.value.find((c) => String(c.tid) === String(props.tid))
  return found?.name || `分類 #${props.tid}`
})

// ==========================================
// 瀑布流页面持久缓存（带 LRU 容量上限保护，修复 H-3）
// ==========================================
interface CategoryCacheData {
  items: VodItem[]
  page: number
  finished: boolean
  scrollY: number
  siteKey: string
}
const MAX_CACHE_SIZE = 20
const categoryCache = new Map<string, CategoryCacheData>()

function getCacheKey(): string {
  return `${sites.currentKey}_${props.tid}`
}

function saveState(): void {
  if (items.value.length > 0) {
    const key = getCacheKey()
    // LRU 策略：先删后插
    if (categoryCache.has(key)) {
      categoryCache.delete(key)
    } else if (categoryCache.size >= MAX_CACHE_SIZE) {
      const oldestKey = categoryCache.keys().next().value
      if (oldestKey) categoryCache.delete(oldestKey)
    }
    categoryCache.set(key, {
      items: items.value,
      page: page.value,
      finished: finished.value,
      scrollY: window.scrollY || document.documentElement.scrollTop || 0,
      siteKey: sites.currentKey || '',
    })
  }
}

async function loadCategories(): Promise<void> {
  try {
    const key = sites.currentKey
    if (!key) return
    const homeData = await api.getHome(key)
    allCategories.value = homeData.categories ?? []
  } catch {
    /* 忽略分类菜单拉取失败 */
  }
}

async function loadFirstPage(force = false): Promise<void> {
  const cacheKey = getCacheKey()
  // 非强制刷新时，如果存在此分类缓存，直接瞬时恢复，保持下拉加载的几十部影片和滚动位置
  if (!force && categoryCache.has(cacheKey)) {
    const cached = categoryCache.get(cacheKey)!
    if (cached.items.length > 0 && cached.siteKey === sites.currentKey) {
      items.value = cached.items
      page.value = cached.page
      finished.value = cached.finished
      firstLoading.value = false
      void loadCategories()

      // 瞬时恢复滚动高度
      nextTick(() => {
        window.scrollTo({ top: cached.scrollY, behavior: 'instant' as ScrollBehavior })
        setTimeout(() => {
          window.scrollTo({ top: cached.scrollY, behavior: 'instant' as ScrollBehavior })
        }, 60)
      })
      return
    }
  }

  firstLoading.value = true
  firstError.value = null
  items.value = []
  page.value = 1
  finished.value = false
  try {
    await sites.load()
    const key = sites.currentKey
    if (!key) throw new Error('後端暫無可用片源站')

    void loadCategories()

    const result = await api.getCategory(key, { tid: props.tid, page: 1 })
    items.value = result.videos ?? []
    finished.value = !result.has_more || (result.videos?.length ?? 0) === 0
    saveState()
  } catch (err) {
    firstError.value = describeError(err)
  } finally {
    firstLoading.value = false
  }
}

/**
 * 触底无限滚动加载更多
 */
async function loadMore(): Promise<void> {
  if (loadingMore.value || finished.value || firstLoading.value) return
  loadingMore.value = true
  try {
    const key = sites.currentKey
    if (!key) {
      finished.value = true
      return
    }
    const next = page.value + 1
    const result = await api.getCategory(key, { tid: props.tid, page: next })
    const videos = result.videos ?? []

    // 智能去重：源站翻页偶发重叠
    const seen = new Set(items.value.map((item) => item.vod_id))
    const unique = videos.filter((item) => !seen.has(item.vod_id))

    items.value.push(...unique)
    page.value = next
    finished.value = !result.has_more || videos.length === 0
    // 保存翻页更新状态
    saveState()
  } catch (err) {
    console.warn('瀑布流翻頁異常：', describeError(err))
    finished.value = true
  } finally {
    loadingMore.value = false
  }
}

function onScroll(): void {
  scrolled.value = window.scrollY > 30

  // 接近页面底部 350px 时自动触发无限瀑布流加载
  const scrollHeight = document.documentElement.scrollHeight
  const scrollTop = window.scrollY || document.documentElement.scrollTop
  const clientHeight = window.innerHeight || document.documentElement.clientHeight
  if (scrollHeight - scrollTop - clientHeight < 350) {
    void loadMore()
  }
}

onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true })
  onScroll()
  if (device.activated) void device.heartbeatOnce()
})

onBeforeUnmount(() => {
  saveState()
  window.removeEventListener('scroll', onScroll)
})

watch(() => props.tid, () => void loadFirstPage(), { immediate: true })
watch(() => sites.currentKey, () => void loadFirstPage(true))
watch(() => device.restoredAt, () => void loadFirstPage())

function switchCategory(tid: string): void {
  if (String(tid) === String(props.tid)) return
  saveState()
  void router.push({ name: 'category', params: { tid } })
}

function openDetail(item: { vod_id?: string | number }): void {
  if (item?.vod_id) {
    saveState()
    void router.push({ name: 'detail', params: { vodId: String(item.vod_id) } })
  }
}

function goBack(): void {
  saveState()
  if (window.history.length > 1) {
    router.back()
  } else {
    void router.push({ name: 'home' })
  }
}
</script>

<template>
  <div class="nf-category-view">
    <!-- ==================================================== 顶部官方暗夜导航栏 -->
    <header class="nf-navbar" :class="{ 'is-scrolled': scrolled }">
      <div class="nf-navbar__left">
        <!-- 品牌官方 Logo -->
        <BrandLogo :width="118" :height="32" @click="router.push({ name: 'home' })" />

        <!-- 返回主页按钮 -->
        <button class="nf-back-btn" type="button" @click="goBack">
          <span class="nf-back-arrow">‹</span>
          <span class="nf-back-text">返回大廳</span>
        </button>

        <!-- 真实分类横向滚动列表 (支持直接在分类页切换浏览) -->
        <nav class="nf-cat-menu">
          <button
            class="nf-cat-item"
            type="button"
            @click="router.push({ name: 'home' })"
          >
            全部
          </button>
          <button
            v-for="cat in allCategories"
            :key="cat.tid"
            class="nf-cat-item"
            :class="{ 'is-active': String(cat.tid) === String(props.tid) }"
            type="button"
            @click="switchCategory(cat.tid)"
          >
            {{ cat.name || cat.tid }}
          </button>
        </nav>
      </div>

      <div class="nf-navbar__right">
        <!-- 换源下拉选择组件 -->
        <SiteSelector ref="siteSelectorRef" @change="() => loadFirstPage(true)" />

        <!-- 用户头像与 VIP 会员到期时间面板组件 -->
        <UserMenu />
      </div>
    </header>

    <!-- ==================================================== 主体无限瀑布流 -->
    <main class="nf-category-main">
      <!-- 页面顶部标题与分类信息栏 -->
      <section class="nf-cat-header">
        <div class="nf-cat-header__title-wrap">
          <h1 class="nf-cat-header__title">{{ categoryTitle }}</h1>
          <span class="nf-cat-header__count" v-if="items.length > 0">
            已加載 {{ items.length }} 部大片
          </span>
        </div>
        <p class="nf-cat-header__desc">
          16:9 高清旗艦寬銀幕視界 · 無線流式瀑布加載
        </p>
      </section>

      <!-- 首屏 16:9 横版 Netflix 微光流光骨架屏 -->
      <div v-if="firstLoading" class="category__skeleton-grid">
        <div v-for="n in 15" :key="n" class="category__skeleton-card" />
      </div>

      <!-- 出错提示与换源 -->
      <div v-else-if="firstError" class="category__state-box">
        <div class="category__state-icon">⚠️</div>
        <p class="category__state-text">{{ firstError }}</p>
        <div class="category__state-actions">
          <button class="category__action-btn primary" type="button" @click="() => loadFirstPage(true)">重新載入</button>
          <button class="category__action-btn" type="button" @click="siteSelectorRef?.open()">更換片源線路</button>
        </div>
      </div>

      <!-- 空数据状态 -->
      <div v-else-if="items.length === 0" class="category__state-box">
        <p class="category__state-text">當前片源在此分類下暫無收錄內容</p>
        <button class="category__action-btn primary" type="button" @click="siteSelectorRef?.open()">嘗試切換其他片源</button>
      </div>

      <!-- 16:9 横版无限瀑布流影视卡片网格 -->
      <template v-else>
        <div class="category__waterfall">
          <NetflixCard
            v-for="(item, idx) in items"
            :key="item.vod_id + '-' + idx"
            :item="{
              ...item,
              isTop10: idx < 3,
            }"
            @select="openDetail"
          />
        </div>

        <!-- 触底加载指示器与提示 -->
        <div class="category__footer">
          <div v-if="loadingMore" class="category__loading-more">
            <span class="category__spinner" />
            <span class="category__loading-text">正在載入更多大片...</span>
          </div>
          <div v-else-if="finished" class="category__finished">
            — 已呈現全部精彩片源 (共 {{ items.length }} 部) —
          </div>
        </div>
      </template>
    </main>
  </div>
</template>

<style scoped>
/* ====================================================================
   全屏黑夜流媒体容器
==================================================================== */
.nf-category-view {
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
  background: rgba(20, 20, 20, 0.94);
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
  gap: 24px;
  flex: 1;
  overflow: hidden;
}

.nf-back-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 18px;
  padding: 4px 12px;
  color: #ffffff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s ease;
}

.nf-back-btn:hover {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.35);
}

.nf-back-arrow {
  font-size: 18px;
  line-height: 1;
}

/* 分类菜单横向平滑滚动条 */
.nf-cat-menu {
  display: flex;
  align-items: center;
  gap: 16px;
  overflow-x: auto;
  scrollbar-width: none;
  -ms-overflow-style: none;
  white-space: nowrap;
  padding: 4px 0;
}

.nf-cat-menu::-webkit-scrollbar {
  display: none;
}

.nf-cat-item {
  background: none;
  border: none;
  color: #b3b3b3;
  font-size: 14px;
  cursor: pointer;
  transition: color 0.2s ease;
  padding: 4px 2px;
}

.nf-cat-item:hover {
  color: #ffffff;
}

.nf-cat-item.is-active {
  color: #ffffff;
  font-weight: 700;
  border-bottom: 2px solid #e50914;
}

.nf-navbar__right {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
}



/* ====================================================================
   分类页主体与 16:9 无限瀑布流
==================================================================== */
.nf-category-main {
  padding-top: 88px;
  min-height: calc(100vh - 88px);
}

.nf-cat-header {
  padding: 18px 4% 12px;
}

.nf-cat-header__title-wrap {
  display: flex;
  align-items: baseline;
  gap: 16px;
  flex-wrap: wrap;
}

.nf-cat-header__title {
  margin: 0;
  font-size: 28px;
  font-weight: 800;
  color: #ffffff;
  letter-spacing: -0.02em;
}

.nf-cat-header__count {
  font-size: 13px;
  color: #e50914;
  font-weight: 600;
  background: rgba(229, 9, 20, 0.12);
  border: 1px solid rgba(229, 9, 20, 0.3);
  padding: 3px 10px;
  border-radius: 12px;
}

.nf-cat-header__desc {
  margin: 6px 0 0;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
}

/* 16:9 黄金宽银幕无限瀑布流网格 */
.category__waterfall {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 20px 12px;
  padding: 16px 4% 40px;
}

/* 覆盖并使其充满网格列，同时保持 16:9 */
.category__waterfall :deep(.nf-card) {
  width: 100% !important;
  flex: none !important;
}

/* 骨架屏：首屏 16:9 瀑布流微光骨架 */
.category__skeleton-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 20px 12px;
  padding: 16px 4% 40px;
}

.category__skeleton-card {
  aspect-ratio: 16 / 9;
  border-radius: 6px;
  background: linear-gradient(90deg, #181818 25%, #282828 50%, #181818 75%);
  background-size: 200% 100%;
  animation: nf-shimmer 1.6s infinite ease-in-out;
}

@keyframes nf-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* 状态提示块 (错误 / 空) */
.category__state-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  min-height: 400px;
  padding: 40px;
  text-align: center;
}

.category__state-icon {
  font-size: 42px;
}

.category__state-text {
  font-size: 15px;
  color: rgba(255, 255, 255, 0.7);
  max-width: 480px;
  line-height: 1.6;
  margin: 0;
}

.category__state-actions {
  display: flex;
  gap: 12px;
  margin-top: 10px;
}

.category__action-btn {
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 4px;
  color: #ffffff;
  padding: 8px 20px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.category__action-btn:hover {
  background: rgba(255, 255, 255, 0.25);
}

.category__action-btn.primary {
  background: #e50914;
  border-color: #e50914;
}

.category__action-btn.primary:hover {
  background: #f40612;
}

/* 底部触底无限瀑布流指示器 */
.category__footer {
  padding: 24px 0 60px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.category__loading-more {
  display: flex;
  align-items: center;
  gap: 10px;
  color: rgba(255, 255, 255, 0.7);
  font-size: 13px;
}

.category__spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-top-color: #e50914;
  border-radius: 50%;
  animation: nf-spin 0.8s linear infinite;
}

@keyframes nf-spin {
  to { transform: rotate(360deg); }
}

.category__finished {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.4);
  letter-spacing: 0.5px;
}

@media (max-width: 900px) {
  .nf-cat-menu { display: none; }
  .category__waterfall {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px 8px;
  }
}
</style>
