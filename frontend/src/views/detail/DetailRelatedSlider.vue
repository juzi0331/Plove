<script setup lang="ts">
import type { VodItem } from '@/api/types'
import NetflixCard from '@/components/NetflixCard.vue'

const props = defineProps<{
  videos: VodItem[]
}>()

const emit = defineEmits<{
  select: [vodId: string | number]
}>()

function scrollRow(direction: 'left' | 'right'): void {
  const el = document.getElementById('related-row')
  if (!el) return
  const offset = direction === 'left' ? -el.clientWidth * 0.75 : el.clientWidth * 0.75
  el.scrollBy({ left: offset, behavior: 'smooth' })
}
</script>

<template>
  <section v-if="props.videos.length" class="nf-related-section">
    <h2 class="nf-related-title">更多類似好片 · More Like This</h2>
    <div class="nf-related-slider-wrap">
      <button class="nf-row-arrow left" type="button" @click="scrollRow('left')">‹</button>
      <div id="related-row" class="nf-related-track">
        <NetflixCard
          v-for="item in props.videos"
          :key="item.vod_id"
          :item="item"
          @select="(it) => emit('select', it.vod_id)"
        />
      </div>
      <button class="nf-row-arrow right" type="button" @click="scrollRow('right')">›</button>
    </div>
  </section>
</template>
