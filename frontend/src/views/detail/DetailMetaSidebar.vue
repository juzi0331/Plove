<script setup lang="ts">
import type { VodItem } from '@/api/types'

const props = defineProps<{
  video: VodItem
}>()
</script>

<template>
  <aside class="nf-side-col">
    <!-- 演职人员与信息卡片 -->
    <div class="nf-meta-card">
      <h3 class="nf-meta-card__title">影視檔案</h3>

      <div v-if="props.video.vod_actor" class="nf-meta-item">
        <span class="nf-meta-label">主演：</span>
        <span class="nf-meta-val">{{ props.video.vod_actor }}</span>
      </div>

      <div v-if="props.video.vod_type" class="nf-meta-item">
        <span class="nf-meta-label">類型：</span>
        <span class="nf-meta-val highlight">{{ props.video.vod_type }}</span>
      </div>

      <div v-if="props.video.vod_area" class="nf-meta-item">
        <span class="nf-meta-label">地區：</span>
        <span class="nf-meta-val">{{ props.video.vod_area }}</span>
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
</template>
