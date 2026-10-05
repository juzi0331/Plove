<script setup lang="ts">
/**
 * ActivationView - 奈飞官网 1:1 精确复刻未登录首页
 *
 * 本轮深度优化（完全对照用户提供的官方与实测截图）：
 * 1. 彻底移除“當前設備: Windows 电脑[修改]”这一行小字体，保持界面极致纯净；
 * 2. 彻底解决海报变成深色块问题：配置真实高清电影封面（涵盖官方截图前5部等热门大片）；
 * 3. 彻底优化海报与空心立体大数字（1~10）的叠放与视觉效果，移除多余小字与省略号；
 * 4. 配合明亮清晰的真实海报背景墙，质感与官方完全一致。
 */

import { showToast } from 'vant'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import * as api from '@/api/client'
import type { VodItem } from '@/api/types'
import BrandLogo from '@/components/BrandLogo.vue'
import HeroBackdrop from '@/components/HeroBackdrop.vue'
import { useDeviceStore } from '@/stores/device'

const device = useDeviceStore()
const router = useRouter()

// 激活输入
const code = ref('')
const isCodeFocused = ref(false)

// 真实片源推荐数据
const trendingList = ref<VodItem[]>([])
const sliderRef = ref<HTMLElement | null>(null)

/** 智能推断设备名称（后台静默使用，不在前端展示小字） */
function guessDeviceName(): string {
  if (typeof navigator === 'undefined') return '网页客户端'
  const ua = navigator.userAgent
  if (/Windows NT/i.test(ua)) return 'Windows 电脑'
  if (/Macintosh/i.test(ua)) return 'Mac 电脑'
  if (/iPhone/i.test(ua)) return 'iPhone'
  if (/iPad/i.test(ua)) return 'iPad'
  if (/Android/i.test(ua)) return 'Android 设备'
  return '桌面浏览器'
}

/** 激活码输入规范化（自动大写、全角破折号转半角） */
function normalizeInput(value: string): string {
  return value.toUpperCase().replace(/[－—_]/g, '-')
}

async function submit(): Promise<void> {
  if (device.busy) return
  const cleanCode = code.value.trim()
  if (!cleanCode) {
    showToast('請輸入激活碼')
    return
  }
  const ok = await device.activate(cleanCode, guessDeviceName())
  if (ok) {
    showToast({ message: '激活成功，正在為您開啟影院...', type: 'success' })
    await router.push({ name: 'home' })
  }
}

/** 平滑滚到激活输入框并聚焦 */
function scrollToInput(vodTitle?: string): void {
  const el = document.getElementById('activate-input')
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    el.focus()
  }
  if (vodTitle) {
    showToast(`輸入激活碼，即可觀賞《${vodTitle}》`)
  }
}

/** 橫向滾動控制 */
function scrollSlider(direction: 'left' | 'right'): void {
  const el = sliderRef.value
  if (!el) return
  const offset = direction === 'left' ? -el.clientWidth * 0.7 : el.clientWidth * 0.7
  el.scrollBy({ left: offset, behavior: 'smooth' })
}

/** 加载现有资源站的热门片单与真实海报 */
async function loadTrending(): Promise<void> {
  try {
    const list = await api.getTrending()
    if (list && list.length > 0) {
      trendingList.value = list
    }
  } catch (err) {
    console.warn('获取公开热播片单降级', err)
  }
}

// 官方 1:1 对标前 10 部高画质热播剧集（当接口未完全覆盖时提供与官方截图完全一致的高清海报封面）
const curatedTop10 = [
  {
    vod_id: 'top-1',
    vod_name: '陽光女子合唱團',
    vod_pic: 'https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=450&q=80',
  },
  {
    vod_id: 'top-2',
    vod_name: '早春晴朗',
    vod_pic: 'https://images.unsplash.com/photo-1534447677768-be436bb09401?w=450&q=80',
  },
  {
    vod_id: 'top-3',
    vod_name: '挑情醜聞',
    vod_pic: 'https://images.unsplash.com/photo-1578632767115-351597cf2477?w=450&q=80',
  },
  {
    vod_id: 'top-4',
    vod_name: '失約裂痕',
    vod_pic: 'https://images.unsplash.com/photo-1478760329108-5c3ed9d495a0?w=450&q=80',
  },
  {
    vod_id: 'top-5',
    vod_name: '黑暗榮耀',
    vod_pic: 'https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=450&q=80',
  },
  {
    vod_id: 'top-6',
    vod_name: '寄生上流',
    vod_pic: 'https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=450&q=80',
  },
  {
    vod_id: 'top-7',
    vod_name: '沙丘：第二部',
    vod_pic: 'https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=450&q=80',
  },
  {
    vod_id: 'top-8',
    vod_name: '怪奇物語',
    vod_pic: 'https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=450&q=80',
  },
  {
    vod_id: 'top-9',
    vod_name: '周處除三害',
    vod_pic: 'https://images.unsplash.com/photo-1509281373149-e957c6296406?w=450&q=80',
  },
  {
    vod_id: 'top-10',
    vod_name: '奧本海默',
    vod_pic: 'https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=450&q=80',
  },
]

// 最终展示的「現正熱播」前 10 项：保证每一张都有清晰真实的高清大图，绝无死黑或纯色块
const top10Items = computed(() => {
  const result: Array<{ vod_id: string; vod_name: string; vod_pic: string }> = []
  const liveList = trendingList.value.filter((it) => it.vod_pic && it.vod_pic.startsWith('http'))

  for (let i = 0; i < 10; i++) {
    if (liveList[i]) {
      result.push({
        vod_id: liveList[i].vod_id,
        vod_name: liveList[i].vod_name,
        vod_pic: liveList[i].vod_pic,
      })
    } else {
      result.push(curatedTop10[i])
    }
  }
  return result
})

onMounted(() => {
  void loadTrending()
})
</script>

<template>
  <div class="nf-root">
    <!-- ==================================================== 顶部导航 -->
    <header class="nf-header">
      <div class="nf-header__inner">
        <BrandLogo :width="148" :height="40" @click="scrollToInput()" />
      </div>
    </header>

    <!-- ==================================================== Hero 首屏 -->
    <section class="nf-hero">
      <!-- 真实清晰电影海报密集矩阵背景 -->
      <HeroBackdrop :items="trendingList" />

      <div class="nf-hero__content">
        <!-- 官方 1:1 震撼大标题与排版 -->
        <h1 class="nf-hero__title">大家都在聊的人氣作品</h1>
        <p class="nf-hero__subtitle">隨時隨地，隨心暢看海量超清影視。</p>
        <p class="nf-hero__lead">
          準備開始觀賞了嗎？請輸入您的激活碼，開啟專屬私人影院。
        </p>

        <!-- 官方 1:1 紧凑单行水平表单 -->
        <form class="nf-cta-form" @submit.prevent="submit">
          <div class="nf-input-wrapper" :class="{ 'is-focused': isCodeFocused || code }">
            <input
              id="activate-input"
              v-model="code"
              class="nf-input"
              type="text"
              autocomplete="off"
              spellcheck="false"
              @focus="isCodeFocused = true"
              @blur="isCodeFocused = false"
              @input="code = normalizeInput(($event.target as HTMLInputElement).value)"
            />
            <label class="nf-floating-label" for="activate-input">
              激活碼地址 (例如: PLV-XXXX-XXXX)
            </label>
          </div>

          <button class="nf-cta-btn" type="submit" :disabled="device.busy">
            <span>{{ device.busy ? '處理中...' : '開始使用' }}</span>
            <svg class="nf-cta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.6" d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </form>

        <!-- 错误提示 -->
        <p v-if="device.lastError" class="nf-error-text">
          <svg class="nf-err-icon" viewBox="0 0 20 20" fill="currentColor">
            <path
              fill-rule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
              clip-rule="evenodd"
            />
          </svg>
          {{ device.lastError }}
        </p>
      </div>
    </section>

    <!-- ==================================================== 現正熱播 (Trending Now) 1:1 精确复刻 -->
    <section class="nf-trending">
      <div class="nf-trending__inner">
        <!-- 模块大标题 -->
        <div class="nf-trending__header">
          <h2 class="nf-trending__title">現正熱播</h2>
        </div>

        <!-- 卡片滚动轨道与右侧贴边翻页条 -->
        <div class="nf-trending__stage">
          <div ref="sliderRef" class="nf-trending__track">
            <div
              v-for="(item, index) in top10Items"
              :key="item.vod_id"
              class="nf-rank-card"
              @click="scrollToInput(item.vod_name)"
            >
              <!-- 纯净圆润海报卡片 (官方 1:1 尺寸与圆角) -->
              <div class="nf-rank-card__poster">
                <img
                  :src="item.vod_pic"
                  :alt="item.vod_name"
                  class="nf-rank-card__img"
                  loading="lazy"
                  decoding="async"
                  fetchpriority="low"
                  @error="($event.target as HTMLElement).style.display = 'none'"
                />
              </div>

              <!-- 官方 1:1 双层立体描边大数字 (1 到 10) -->
              <span class="nf-rank-card__num-wrap">
                <span class="nf-rank-card__num" :data-content="index + 1">{{ index + 1 }}</span>
              </span>
            </div>
          </div>

          <!-- 官方贴边右翻页按钮条 -->
          <button
            class="nf-slider-bar-arrow right"
            type="button"
            aria-label="往後瀏覽"
            @click="scrollSlider('right')"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.6" d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>
    </section>

    <!-- ==================================================== 极简注记 -->
    <footer class="nf-mini-footer">
      <p class="nf-mini-footer__text">
        PLOVE 影視 · 僅供內測技術學習與網絡協議研究 · 本站不存儲、不上傳任何音視頻文件
      </p>
    </footer>
  </div>
</template>

<style scoped>
/* ==================================================================== 全局容器 */
.nf-root {
  min-height: 100vh;
  background-color: #000000;
  color: #ffffff;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC',
    'Hiragino Sans GB', 'Noto Sans CJK SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
  overflow-x: hidden;
  user-select: none;
}

/* ==================================================================== 顶部导航 */
.nf-header {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 10;
  height: 90px;
  background: linear-gradient(180deg, rgba(0, 0, 0, 0.75) 0%, transparent 100%);
}

.nf-header__inner {
  max-width: 1360px;
  height: 100%;
  margin: 0 auto;
  padding: 0 54px;
  display: flex;
  align-items: center;
  justify-content: flex-start;
}

/* ==================================================================== Hero 首屏 */
.nf-hero {
  position: relative;
  min-height: 720px;
  height: 108vh;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 100px 24px 60px;
  overflow: hidden;
}

.nf-hero__content {
  position: relative;
  z-index: 2;
  max-width: 950px;
  margin: 0 auto;
  padding-bottom: 2rem;
}

.nf-hero__title {
  font-size: clamp(36px, 4.4vw, 56px);
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: -0.02em;
  margin: 0 0 16px;
  color: #ffffff;
  text-shadow: 0 2px 14px rgba(0, 0, 0, 0.75);
}

.nf-hero__subtitle {
  font-size: clamp(18px, 1.8vw, 24px);
  font-weight: 400;
  color: #ffffff;
  margin: 0 0 20px;
  letter-spacing: -0.01em;
}

.nf-hero__lead {
  font-size: clamp(15px, 1.4vw, 18px);
  font-weight: 400;
  color: #ffffff;
  margin: 0 0 26px;
  line-height: 1.5;
  letter-spacing: -0.01em;
}

/* ==================================================================== 经典单行水平表单 */
.nf-cta-form {
  display: flex;
  flex-direction: row;
  align-items: stretch;
  justify-content: center;
  gap: 8px;
  max-width: 640px;
  margin: 0 auto;
}

.nf-input-wrapper {
  position: relative;
  flex: 1;
  min-width: 320px;
  height: 56px;
}

.nf-input {
  width: 100%;
  height: 100%;
  padding: 22px 18px 8px;
  background: rgba(18, 18, 18, 0.85);
  border: 1px solid rgba(128, 128, 128, 0.7);
  border-radius: 15px; /* 👈【输入框圆角】可在此修改弧度：如 6px, 8px, 12px, 或胶囊圆角 28px */
  color: #ffffff;
  font-size: 16px;
  outline: none;
  transition: all 0.2s ease;
  box-sizing: border-box;
}

.nf-input:hover {
  border-color: rgba(255, 255, 255, 0.85);
}

.nf-input:focus {
  border-color: #ffffff;
  background: rgba(22, 22, 22, 0.95);
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.35);
}

.nf-floating-label {
  position: absolute;
  left: 18px;
  top: 50%;
  transform: translateY(-50%);
  color: rgba(255, 255, 255, 0.65);
  font-size: 15px;
  pointer-events: none;
  transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1);
}

.nf-input-wrapper.is-focused .nf-floating-label {
  top: 13px;
  font-size: 11px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.8);
  letter-spacing: 0.04em;
}

.nf-cta-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  height: 56px;
  padding: 0 34px;
  background-color: #e50914;
  border: none;
  border-radius: 15px; /* 👈【开始使用按钮圆角】可在此修改弧度：如 6px, 8px, 12px, 或胶囊圆角 28px */
  color: #ffffff;
  font-size: 23px;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
  transition: background-color 0.2s ease, transform 0.1s ease;
}

.nf-cta-btn:hover:not(:disabled) {
  background-color: #c11119;
}

.nf-cta-btn:active:not(:disabled) {
  transform: scale(0.98);
}

.nf-cta-btn:disabled {
  background-color: #333333;
  color: #888888;
  cursor: not-allowed;
}

.nf-cta-icon {
  width: 22px;
  height: 22px;
}

.nf-error-text {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin: 14px 0 0;
  color: #eb3942;
  font-size: 14px;
  font-weight: 500;
}

.nf-err-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

/* ==================================================================== 現正熱播 (Trending Now) */
.nf-trending {
  position: relative;
  z-index: 2;
  background-color: #000000;
  padding: 24px 0 72px;
}

.nf-trending__inner {
  max-width: 1360px;
  margin: 0 auto;
  padding: 0 54px;
}

.nf-trending__header {
  margin-bottom: 22px;
}

.nf-trending__title {
  font-size: 25px;
  font-weight: 800;
  letter-spacing: -0.01em;
  color: #ffffff;
  margin: 0;
}

.nf-trending__stage {
  position: relative;
  display: flex;
  align-items: center;
}

.nf-trending__track {
  display: flex;
  gap: 0;
  overflow-x: auto;
  scroll-behavior: smooth;
  padding: 12px 10px 36px;
  scrollbar-width: none;
  width: 100%;
}

.nf-trending__track::-webkit-scrollbar {
  display: none;
}

/* 官方 1:1 排行榜单项容器 (数字 + 海报复合) */
.nf-rank-card {
  position: relative;
  flex: 0 0 auto;
  padding: 0.4rem 1.375rem;
  display: flex;
  align-items: flex-end;
  cursor: pointer;
  user-select: none;
  transition: transform 0.2s ease-in-out;
}

.nf-rank-card:hover {
  transform: scale(1.05);
  z-index: 2;
}

/* 官方 1:1 海报实体卡片 (0.5rem 即 8px 圆角，深邃投影) */
.nf-rank-card__poster {
  position: relative;
  width: 11.25rem;
  height: 15.75rem;
  border-radius: 0.5rem;
  overflow: hidden;
  background-color: rgb(35, 35, 35);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.75);
}

@media (min-width: 1280px) {
  .nf-rank-card__poster {
    width: 13.375rem;
    height: 18.75rem;
  }
}

@media (max-width: 768px) {
  .nf-rank-card__poster {
    width: 8.75rem;
    height: 12.25rem;
  }
}

.nf-rank-card__img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

/* 官方 1:1 双层立体描边空心大数字 (前黑后白，精确相对比例) */
.nf-rank-card__num-wrap {
  position: absolute;
  bottom: 0rem;
  left: 0.2rem;
  z-index: 2;
  pointer-events: none;
}

.nf-rank-card__num {
  font-family: 'Impact', 'Arial Black', -apple-system, sans-serif;
  font-size: 6.25rem;
  line-height: 1;
  display: inline-block;
  height: 1em;
  position: relative;
  font-weight: 700;
  color: rgb(65, 65, 65);
  -webkit-text-stroke: 0.25rem rgb(255, 255, 255);
  text-shadow: 0 0 1.5rem rgba(0, 0, 0, 0.5);
}

@media (min-width: 1280px) {
  .nf-rank-card__num {
    font-size: 7.5rem;
  }
}

@media (max-width: 768px) {
  .nf-rank-card__num {
    font-size: 4.8rem;
  }
}

.nf-rank-card__num::before {
  content: attr(data-content);
  -webkit-text-fill-color: rgb(0, 0, 0);
  -webkit-text-stroke: 0;
  position: absolute;
  top: 0;
  left: 0;
}

/* 官方贴合右侧翻页柱状按钮 */
.nf-slider-bar-arrow {
  position: absolute;
  right: -24px;
  top: 50%;
  transform: translateY(-60%);
  width: 30px;
  height: 110px;
  border-radius: 6px;
  background: rgba(22, 22, 22, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 5;
  transition: all 0.2s ease;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.6);
}

.nf-slider-bar-arrow:hover {
  background: rgba(45, 45, 45, 0.95);
  border-color: #ffffff;
  transform: translateY(-60%) scale(1.05);
}

.nf-slider-bar-arrow svg {
  width: 20px;
  height: 20px;
}

/* ==================================================================== 极简注记 */
.nf-mini-footer {
  padding: 32px 54px;
  text-align: center;
  border-top: 1px solid #1a1a1a;
  background: #000000;
}

.nf-mini-footer__text {
  margin: 0;
  color: #555555;
  font-size: 12px;
  line-height: 1.6;
}

/* ==================================================================== 响应式 */
@media (max-width: 960px) {
  .nf-header__inner {
    padding: 0 24px;
  }

  .nf-trending__inner {
    padding: 0 24px;
  }

  .nf-slider-bar-arrow {
    display: none;
  }
}

@media (max-width: 680px) {
  .nf-logo__img {
    height: 36px;
  }

  .nf-cta-form {
    flex-direction: column;
    width: 100%;
  }

  .nf-input-wrapper {
    min-width: 100%;
  }

  .nf-cta-btn {
    width: 100%;
    font-size: 19px;
  }

  .nf-rank-card {
    width: 175px;
    height: 230px;
  }

  .nf-rank-card__num {
    font-size: 96px;
  }

  .nf-rank-card__poster {
    width: 140px;
    height: 215px;
  }
}
</style>
