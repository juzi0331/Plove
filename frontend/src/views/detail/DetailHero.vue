<script setup lang="ts">
import type { Episode, VodItem } from '@/api/types'
import { formatPosterUrl } from '@/utils/format'

const props = defineProps<{
  video: VodItem
  siteKey?: string | null
  firstEpisode: Episode | null
}>()

const emit = defineEmits<{
  play: [episode: Episode | null]
}>()
</script>

<template>
  <section class="nf-detail-hero">
    <div
      class="nf-hero-bg"
      :style="{ backgroundImage: `url(${formatPosterUrl(props.video.vod_pic, props.siteKey || undefined) || ''})` }"
    />
    <div class="nf-hero-vignette" />

    <!-- Hero 底部核心内容面板 -->
    <div class="nf-hero-caption">
      <div class="nf-hero-badges">
        <span class="nf-badge-gold">★ 9.8 評分</span>
        <span class="nf-badge-red">Netflix 首選推薦</span>
        <span class="nf-badge-hd">4K Ultra HD</span>
        <span v-if="props.video.vod_year" class="nf-badge-gray">{{ props.video.vod_year }}</span>
        <span v-if="props.video.vod_remarks" class="nf-badge-gray">{{ props.video.vod_remarks }}</span>
      </div>

      <h1 class="nf-hero-title">{{ props.video.vod_name }}</h1>

      <!-- 播放与快速交互按钮组 -->
      <div class="nf-hero-actions">
        <button
          class="nf-btn-play"
          type="button"
          :disabled="!props.firstEpisode"
          @click="emit('play', props.firstEpisode)"
        >
          <span class="nf-play-icon">▶</span>
          <span class="nf-play-text">{{ props.firstEpisode ? '立即播放' : '暫無片源' }}</span>
        </button>
      </div>
    </div>
  </section>
</template>
