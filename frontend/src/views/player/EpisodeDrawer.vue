<script setup lang="ts">
/**
 * EpisodeDrawer - 侧边滑出式毛玻璃选集与多线路大厅
 */

import { computed, ref, watch } from 'vue'
import type { DetailPayload, Episode } from '@/api/types'
import { stripHtml } from './usePlayerState'

const props = defineProps<{
  open: boolean
  lineEpisodes: Episode[]
  currentEpNumber: number
  currentLine: number
  availableLines: { line: number; name?: string }[]
  videoMeta?: DetailPayload['video'] | null
  detailDesc?: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'switchEpisode', ep: Episode): void
  (e: 'switchLine', line: number): void
}>()

/** 选集抽屉显示模式：'card' (详细卡片) | 'grid' (数字矩阵) */
const drawerMode = ref<'card' | 'grid'>('card')

/** 长剧集分页大小（如短剧 80-100 集，30 集一页分段） */
const EP_PAGE_SIZE = 30
const selectedEpRange = ref<number>(0)

const epRanges = computed(() => {
  const total = props.lineEpisodes.length
  if (total <= EP_PAGE_SIZE) return []
  const ranges: { start: number; end: number; label: string }[] = []
  for (let i = 0; i < total; i += EP_PAGE_SIZE) {
    const start = i + 1
    const end = Math.min(i + EP_PAGE_SIZE, total)
    ranges.push({ start, end, label: `${start}-${end}` })
  }
  return ranges
})

const pagedEpisodes = computed(() => {
  if (epRanges.value.length === 0) return props.lineEpisodes
  const range = epRanges.value[selectedEpRange.value]
  if (!range) return props.lineEpisodes
  return props.lineEpisodes.filter(
    (e) => e.ep_index >= range.start && e.ep_index <= range.end,
  )
})

watch(
  () => props.currentEpNumber,
  (ep) => {
    if (epRanges.value.length > 0) {
      const idx = epRanges.value.findIndex((r) => ep >= r.start && ep <= r.end)
      if (idx !== -1) {
        selectedEpRange.value = idx
      }
    }
  },
  { immediate: true },
)
</script>

<template>
  <Transition name="nf-drawer">
    <aside v-if="open" class="nf-episodes-drawer" @click.stop>
      <!-- 抽屉顶部标题与模式切换 -->
      <div class="nf-drawer-header">
        <div class="nf-drawer-title-group">
          <h3 class="nf-drawer-title">劇集選集</h3>
          <span class="nf-drawer-count">共 {{ lineEpisodes.length }} 集</span>
        </div>

        <div class="nf-drawer-header-actions">
          <!-- 切换卡片 / 矩阵模式 (集数大于 6 时提供切换) -->
          <div v-if="lineEpisodes.length > 6" class="nf-mode-toggle">
            <button
              class="nf-mode-btn"
              :class="{ 'is-active': drawerMode === 'card' }"
              type="button"
              title="詳細卡片列表"
              @click="drawerMode = 'card'"
            >
              卡片
            </button>
            <button
              class="nf-mode-btn"
              :class="{ 'is-active': drawerMode === 'grid' }"
              type="button"
              title="簡約數字矩陣"
              @click="drawerMode = 'grid'"
            >
              數字
            </button>
          </div>

          <!-- 关闭抽屉按钮 -->
          <button class="nf-drawer-close" type="button" title="關閉選集 (Esc)" @click="emit('close')">
            ✕
          </button>
        </div>
      </div>

      <!-- 线路切换指示（多线路时展示） -->
      <div v-if="availableLines.length > 1" class="nf-drawer-lines">
        <span class="nf-drawer-label">播放線路：</span>
        <div class="nf-drawer-tabs">
          <button
            v-for="line in availableLines"
            :key="line.line"
            class="nf-drawer-tab"
            :class="{ 'is-active': line.line === currentLine }"
            type="button"
            @click="emit('switchLine', line.line)"
          >
            線路 {{ line.line }}
          </button>
        </div>
      </div>

      <!-- 长剧集分段分页栏（例如 1-30, 31-60...） -->
      <div v-if="epRanges.length > 0" class="nf-drawer-ranges">
        <button
          v-for="(rng, rIdx) in epRanges"
          :key="rng.label"
          class="nf-range-tab"
          :class="{ 'is-active': selectedEpRange === rIdx }"
          type="button"
          @click="selectedEpRange = rIdx"
        >
          {{ rng.label }}
        </button>
      </div>

      <!-- 滚动内容区：包含选集卡片与剧集介绍 -->
      <div class="nf-drawer-scroll-wrap">
        <!-- 1. 详细卡片模式 (两列紧凑卡片，顶部对齐) -->
        <div v-if="drawerMode === 'card'" class="nf-drawer-card-grid">
          <button
            v-for="epItem in pagedEpisodes"
            :key="epItem.ep_index"
            class="nf-drawer-card"
            :class="{ 'is-current': epItem.ep_index === currentEpNumber }"
            type="button"
            @click="emit('switchEpisode', epItem)"
          >
            <div class="nf-card-main">
              <span class="nf-card-ep">第 {{ epItem.ep_index }} 集</span>
              <span v-if="epItem.ep_name" class="nf-card-name" :title="epItem.ep_name">{{ epItem.ep_name }}</span>
            </div>
            <div v-if="epItem.ep_index === currentEpNumber" class="nf-card-status">
              <span class="nf-playing-bars">
                <span class="nf-bar bar-1" />
                <span class="nf-bar bar-2" />
                <span class="nf-bar bar-3" />
              </span>
            </div>
          </button>
        </div>

        <!-- 2. 数字矩阵模式 (五列密集芯片，便于快速翻找上百集短剧) -->
        <div v-else class="nf-drawer-chip-grid">
          <button
            v-for="epItem in pagedEpisodes"
            :key="epItem.ep_index"
            class="nf-drawer-chip"
            :class="{ 'is-current': epItem.ep_index === currentEpNumber }"
            type="button"
            @click="emit('switchEpisode', epItem)"
          >
            <span class="nf-chip-num">{{ epItem.ep_index }}</span>
            <span v-if="epItem.ep_index === currentEpNumber" class="nf-chip-dot" />
          </button>
        </div>

        <!-- 3. 当剧集总数较少时（如电影、单双集），在下方优雅展示剧集详情卡 -->
        <div v-if="videoMeta" class="nf-drawer-meta-card">
          <div class="nf-meta-header">
            <span class="nf-meta-title">影片簡介</span>
            <span v-if="videoMeta.vod_remarks" class="nf-meta-remarks">{{ videoMeta.vod_remarks }}</span>
          </div>
          <div v-if="videoMeta.vod_type || videoMeta.vod_year || videoMeta.vod_area || videoMeta.vod_score" class="nf-meta-badges">
            <span v-if="videoMeta.vod_type" class="nf-meta-pill">{{ videoMeta.vod_type }}</span>
            <span v-if="videoMeta.vod_year" class="nf-meta-pill">{{ videoMeta.vod_year }}</span>
            <span v-if="videoMeta.vod_area" class="nf-meta-pill">{{ videoMeta.vod_area }}</span>
            <span v-if="videoMeta.vod_score" class="nf-meta-pill score">★ {{ videoMeta.vod_score }}</span>
          </div>
          <p v-if="detailDesc" class="nf-meta-desc">
            {{ stripHtml(detailDesc) }}
          </p>
          <div v-if="videoMeta.vod_actor" class="nf-meta-row">
            <span class="nf-meta-k">主演：</span>
            <span class="nf-meta-v">{{ videoMeta.vod_actor }}</span>
          </div>
        </div>
      </div>
    </aside>
  </Transition>
  <div v-if="open" class="nf-drawer-backdrop" @click="emit('close')" />
</template>
