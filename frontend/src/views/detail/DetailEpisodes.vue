<script setup lang="ts">
import type { DetailPayload, Episode } from '@/api/types'

const props = defineProps<{
  desc?: string
  descOpen: boolean
  descCanExpand: boolean
  lines?: DetailPayload['lines']
  activeLine?: number
  episodes: Episode[]
  epLabel: (episode: Episode) => string
}>()

const emit = defineEmits<{
  'update:descOpen': [val: boolean]
  selectLine: [line: number]
  play: [episode: Episode]
}>()
</script>

<template>
  <div class="nf-main-col">
    <!-- 剧情简介 -->
    <section v-if="props.desc" class="nf-block nf-desc-block">
      <h2 class="nf-block-title">劇情簡介</h2>
      <p class="nf-desc-text" :class="{ 'is-open': props.descOpen }">
        {{ props.desc }}
      </p>
      <button
        v-if="props.descCanExpand"
        class="nf-desc-more-btn"
        type="button"
        @click="emit('update:descOpen', !props.descOpen)"
      >
        {{ props.descOpen ? '收起簡介 ▴' : '閱讀完整簡介 ▾' }}
      </button>
    </section>

    <!-- 多线路切换标签 -->
    <section v-if="props.lines && props.lines.length > 1" class="nf-block nf-lines-block">
      <div class="nf-lines-header">
        <span class="nf-lines-title">播放線路：</span>
        <div class="nf-lines-tabs">
          <button
            v-for="line in props.lines"
            :key="line.line"
            class="nf-line-tab"
            :class="{ 'is-active': props.activeLine === line.line }"
            type="button"
            @click="emit('selectLine', line.line)"
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
        <span class="nf-ep-count">全 {{ props.episodes.length }} 集</span>
      </div>

      <div v-if="props.episodes.length" class="nf-episodes-grid">
        <button
          v-for="episode in props.episodes"
          :key="`${episode.line ?? 0}-${episode.ep_index}-${episode.play_id}`"
          class="nf-ep-card"
          type="button"
          @click="emit('play', episode)"
        >
          <div class="nf-ep-card__top">
            <span class="nf-ep-card__play">▶</span>
            <span class="nf-ep-card__badge">高清</span>
          </div>
          <div class="nf-ep-card__name">{{ props.epLabel(episode) }}</div>
        </button>
      </div>
      <p v-else class="nf-none-text">當前線路暫無有效劇集</p>
    </section>
  </div>
</template>
