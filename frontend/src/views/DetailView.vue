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
import { toRef } from 'vue'

import { useDetail } from './detail/useDetail'
import DetailNavbar from './detail/DetailNavbar.vue'
import DetailHero from './detail/DetailHero.vue'
import DetailEpisodes from './detail/DetailEpisodes.vue'
import DetailMetaSidebar from './detail/DetailMetaSidebar.vue'
import DetailRelatedSlider from './detail/DetailRelatedSlider.vue'

const props = defineProps<{ vodId: string }>()
const vodIdRef = toRef(props, 'vodId')

const {
  sites,
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
} = useDetail(vodIdRef)
</script>

<template>
  <div class="nf-detail-view">
    <!-- 顶部官方暗夜导航栏 -->
    <DetailNavbar
      :scrolled="scrolled"
      :vod-name="video?.vod_name"
      @go-back="goBack"
    />

    <!-- 首屏骨架屏 -->
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

    <!-- 真实详情大厅 -->
    <main v-else-if="video" class="nf-detail-main">
      <!-- 1. 宽银幕 Hero 画卷 (Cinematic Billboard) -->
      <DetailHero
        :video="video"
        :site-key="sites.currentKey"
        :first-episode="firstEpisode"
        @play="play"
      />

      <!-- 2. 双栏详情信息区 -->
      <div class="nf-detail-body">
        <DetailEpisodes
          v-model:desc-open="descOpen"
          :desc="detail?.desc"
          :desc-can-expand="descCanExpand"
          :lines="lines"
          :active-line="activeLine"
          :episodes="episodes"
          :ep-label="epLabel"
          @select-line="activeLine = $event"
          @play="play"
        />

        <DetailMetaSidebar :video="video" />
      </div>

      <!-- 3. 底部类似好片滑轨 -->
      <DetailRelatedSlider
        :videos="relatedVideos"
        @select="selectRelated"
      />
    </main>
  </div>
</template>

<style>
@import './detail/detail.css';
</style>
