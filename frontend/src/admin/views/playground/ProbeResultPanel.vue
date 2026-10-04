<script setup lang="ts">
import {
  ElButton,
  ElCard,
  ElCol,
  ElIcon,
  ElRadioButton,
  ElRadioGroup,
  ElRow,
  ElTag,
} from 'element-plus'
import {
  CopyDocument,
  Film,
} from '@element-plus/icons-vue'
import type { PlaygroundProbeResult } from '@/api/types'
import ProbePlayerPreview from './ProbePlayerPreview.vue'

const props = defineProps<{
  probeResult: PlaygroundProbeResult
  previewItemList: any[]
  jsonTab: 'cleaned' | 'raw'
  formatJson: (data: any) => string
}>()

const emit = defineEmits<{
  'update:jsonTab': [val: 'cleaned' | 'raw']
  copy: [text: string]
}>()
</script>

<template>
  <div class="result-box">
    <!-- 核心指标卡片 -->
    <ElRow :gutter="16" class="metrics-row">
      <ElCol :xs="24" :sm="8">
        <div class="metric-block">
          <span class="metric-title">网络响应耗时</span>
          <div class="metric-num" :class="props.probeResult.elapsed_ms < 600 ? 'text-good' : 'text-warn'">
            {{ props.probeResult.elapsed_ms }}
            <span class="unit">ms</span>
          </div>
          <span class="metric-note">
            {{ props.probeResult.elapsed_ms < 600 ? '响应敏捷' : '网络抓取耗时稍高' }}
          </span>
        </div>
      </ElCol>

      <ElCol :xs="24" :sm="8">
        <div class="metric-block">
          <span class="metric-title">缓存感知状态</span>
          <div class="metric-num">
            <ElTag
              :type="props.probeResult.cache_hit ? 'success' : 'info'"
              size="large"
              effect="light"
              class="big-tag"
            >
              {{ props.probeResult.cache_hit ? 'CACHE HIT (命中缓存)' : 'CRAWLER MISS (查源现抓)' }}
            </ElTag>
          </div>
          <span class="metric-note">
            {{ props.probeResult.cache_hit ? '0 秒极速从内存返回' : '通过外部爬虫实时抓取源站' }}
          </span>
        </div>
      </ElCol>

      <ElCol :xs="24" :sm="8">
        <div class="metric-block">
          <span class="metric-title">HTTP 响应审计</span>
          <div class="metric-num">
            <ElTag
              :type="props.probeResult.status === 'OK' ? 'success' : 'danger'"
              size="large"
              class="big-tag"
            >
              {{ props.probeResult.status === 'OK' ? '200 OK 正常' : '执行异常' }}
            </ElTag>
          </div>
          <span class="metric-note">
            {{ props.probeResult.error_detail ? props.probeResult.error_detail : '无任何告警与异常' }}
          </span>
        </div>
      </ElCol>
    </ElRow>

    <!-- 播放器试播预览（如果命令是 play 且含有播放地址） -->
    <ProbePlayerPreview
      v-if="props.probeResult.command === 'play' && props.probeResult.playback_url"
      :playback-url="props.probeResult.playback_url"
      @copy="emit('copy', $event)"
    />

    <!-- 视觉影视海报网格（如果含有列表） -->
    <div v-if="props.previewItemList.length > 0" class="items-preview-panel">
      <div class="panel-head">
        <div class="head-left">
          <ElIcon :size="18"><Film /></ElIcon>
          <span class="head-title">抓取到的片单视觉卡片列表 ({{ props.previewItemList.length }} 部)</span>
        </div>
      </div>
      <div class="movie-grid">
        <div
          v-for="(item, idx) in props.previewItemList.slice(0, 12)"
          :key="idx"
          class="movie-card"
        >
          <div class="movie-poster">
            <img
              v-if="item.cover || item.poster || item.pic"
              :src="item.cover || item.poster || item.pic"
              alt="海报"
              loading="lazy"
              class="poster-img"
            />
            <div v-else class="poster-placeholder">无海报</div>
            <div v-if="item.episodes || item.remarks" class="movie-badge">
              {{ item.episodes || item.remarks }}
            </div>
          </div>
          <div class="movie-meta">
            <div class="movie-title" :title="item.title || item.name">
              {{ item.title || item.name }}
            </div>
            <div class="movie-sub">
              ID: {{ item.id || item.vod_id }} · {{ item.category || item.type_name || '精选' }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 原始 vs 洗后 JSON 差分对比 -->
    <ElCard shadow="never" class="json-inspect-card">
      <template #header>
        <div class="json-header-row">
          <div class="json-header-tabs">
            <ElRadioGroup
              :model-value="props.jsonTab"
              size="small"
              @update:model-value="emit('update:jsonTab', $event as 'cleaned' | 'raw')"
            >
              <ElRadioButton value="cleaned">清洗加工后结构 (Cleaned)</ElRadioButton>
              <ElRadioButton value="raw">爬虫原始返回 (Raw)</ElRadioButton>
            </ElRadioGroup>
          </div>
          <ElButton
            size="small"
            :icon="CopyDocument"
            @click="emit('copy', props.formatJson(props.jsonTab === 'cleaned' ? props.probeResult.cleaned_data : props.probeResult.raw_data))"
          >
            复制当前 JSON
          </ElButton>
        </div>
      </template>
      <pre class="json-viewer-box">{{ props.formatJson(props.jsonTab === 'cleaned' ? props.probeResult.cleaned_data : props.probeResult.raw_data) }}</pre>
    </ElCard>
  </div>
</template>
