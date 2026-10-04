<script setup lang="ts">
/**
 * NetflixCard - 奈飞官方登录后 1:1 横版 16:9 影视卡片
 *
 * 核心特性：
 * 1. 16:9 黄金宽银幕比例（超清晰剧照/海报横屏展示）；
 * 2. 右上角可选红色 TOP 10 标签；
 * 3. 底部专属胶囊标签 (New Season, New Episodes, Watch Now, Recently Added)；
 * 4. 可选播放进度条 (Continue Watching 专属红色进度)；
 * 5. 鼠标悬停平滑浮起放大 (scale 1.15~1.2) + 纵深投影。
 */

import { computed } from 'vue'

const props = defineProps<{
  item: {
    vod_id: string | number
    vod_name: string
    vod_pic: string
    vod_remarks?: string
    isTop10?: boolean
    badgeText?: string
    badgeType?: 'red' | 'white' | 'gray'
    progress?: number // 0 ~ 100 观看进度
  }
}>()

const emit = defineEmits<{
  (event: 'select', item: any): void
}>()

import { getDeviceToken } from '@/api/session'
import { formatPosterUrl } from '@/utils/format'

// 容错与防盗链代理图片
const displayPic = computed(() => {
  const raw = props.item.vod_pic || 'https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=500&q=80'
  const siteKey = (props.item as any)?.site || (props.item as any)?.site_key
  return formatPosterUrl(raw, siteKey)
})

function handleImgError(e: Event): void {
  const target = e.target as HTMLImageElement
  if (!target) return
  // 如果直接加载失败且未走代理，自动切换到防盗链代理中继重试一次
  if (target.src && !target.src.includes('/api/v1/proxy/image') && target.src.startsWith('http')) {
    const siteKey = (props.item as any)?.site || (props.item as any)?.site_key
    const siteParam = siteKey ? `&site=${encodeURIComponent(siteKey)}` : ''
    const devToken = getDeviceToken()
    const tokenParam = devToken ? `&token=${encodeURIComponent(devToken)}` : ''
    target.src = `/api/v1/proxy/image?url=${encodeURIComponent(target.src)}${siteParam}${tokenParam}`
    return
  }
  target.style.display = 'none'
}
</script>

<template>
  <div class="nf-card" role="button" tabindex="0" @click="emit('select', item)">
    <div class="nf-card__inner">
      <!-- 16:9 横版大片剧照 -->
      <img
        :src="displayPic"
        :alt="item.vod_name"
        class="nf-card__img"
        referrerpolicy="no-referrer"
        loading="lazy"
        @error="handleImgError"
      />

      <!-- 底部暗影遮罩 (保证标题与标签清晰) -->
      <div class="nf-card__scrim" />

      <!-- 右上角 TOP 10 标签 (官方红底竖形徽标) -->
      <div v-if="item.isTop10" class="nf-card__top10">
        <span class="nf-card__top10-top">TOP</span>
        <span class="nf-card__top10-num">10</span>
      </div>

      <!-- 底部信息区：标题 + 专属小标签 -->
      <div class="nf-card__bottom">
        <h4 class="nf-card__title">{{ item.vod_name }}</h4>

        <div v-if="item.badgeText || item.vod_remarks" class="nf-card__tags">
          <span
            v-if="item.badgeText"
            class="nf-badge"
            :class="`is-${item.badgeType || 'red'}`"
          >
            {{ item.badgeText }}
          </span>
          <span v-else-if="item.vod_remarks" class="nf-badge is-gray">
            {{ item.vod_remarks }}
          </span>
        </div>
      </div>

      <!-- 底部红色播放进度条 (Continue Watching 专属) -->
      <div v-if="item.progress && item.progress > 0" class="nf-card__progress-track">
        <div class="nf-card__progress-bar" :style="{ width: `${item.progress}%` }" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.nf-card {
  position: relative;
  flex: 0 0 auto;
  width: 250px;
  cursor: pointer;
  outline: none;
  user-select: none;
  transition: transform 0.3s cubic-bezier(0.2, 0, 0.2, 1), z-index 0.3s ease;
  z-index: 1;
}

@media (min-width: 1200px) {
  .nf-card {
    width: 275px;
  }
}

@media (min-width: 1600px) {
  .nf-card {
    width: 310px;
  }
}

@media (max-width: 768px) {
  .nf-card {
    width: 165px;
  }
}

@media (max-width: 480px) {
  .nf-card {
    width: 142px;
  }
}

@media (hover: hover) and (pointer: fine) {
  .nf-card:hover {
    transform: scale(1.18);
    z-index: 10;
  }
}

.nf-card:active {
  transform: scale(0.97);
}

.nf-card__inner {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: 4px;
  overflow: hidden;
  background-color: #1a1a1a;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.7);
  transition: box-shadow 0.3s ease;
}

.nf-card:hover .nf-card__inner {
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.95);
}

.nf-card__img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.nf-card__scrim {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    180deg,
    rgba(0, 0, 0, 0.1) 0%,
    rgba(0, 0, 0, 0) 50%,
    rgba(0, 0, 0, 0.88) 100%
  );
  pointer-events: none;
}

/* 官方红底竖形 TOP 10 徽章 */
.nf-card__top10 {
  position: absolute;
  top: 0;
  right: 10px;
  background-color: #e50914;
  color: #ffffff;
  padding: 3px 5px 4px;
  border-radius: 0 0 2px 2px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  line-height: 1;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.6);
  z-index: 2;
}

.nf-card__top10-top {
  font-size: 8px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.nf-card__top10-num {
  font-size: 11px;
  font-weight: 900;
  letter-spacing: -0.05em;
  margin-top: 1px;
}

/* 底部文字信息 */
.nf-card__bottom {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 8px 10px;
  z-index: 2;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nf-card__title {
  color: #ffffff;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.25;
  margin: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.9);
}

.nf-card__tags {
  display: flex;
  align-items: center;
  gap: 6px;
}

.nf-badge {
  display: inline-block;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 5px;
  border-radius: 2px;
  line-height: 1.1;
  letter-spacing: 0.02em;
}

.nf-badge.is-red {
  background-color: #e50914;
  color: #ffffff;
}

.nf-badge.is-white {
  background-color: #ffffff;
  color: #000000;
}

.nf-badge.is-gray {
  background-color: rgba(255, 255, 255, 0.2);
  color: #e5e5e5;
}

/* 底部红色播放进度条 */
.nf-card__progress-track {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 3px;
  background-color: rgba(120, 120, 120, 0.6);
  z-index: 3;
}

.nf-card__progress-bar {
  height: 100%;
  background-color: #e50914;
}
</style>
