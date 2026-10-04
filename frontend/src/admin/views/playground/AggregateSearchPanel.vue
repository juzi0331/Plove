<script setup lang="ts">
import {
  ElButton,
  ElCard,
  ElInput,
  ElTag,
} from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import type { AggregateSearchPayload } from '@/api/types'

const props = defineProps<{
  searchKw: string
  searching: boolean
  searchResult: AggregateSearchPayload | null
}>()

const emit = defineEmits<{
  'update:searchKw': [val: string]
  search: []
  quickSearch: [kw: string]
}>()
</script>

<template>
  <div class="tab-panel">
    <ElCard shadow="never" class="panel-card">
      <div class="search-hero-box">
        <div class="search-input-line">
          <ElInput
            :model-value="props.searchKw"
            placeholder="输入片名关键词（如：繁花、庆余年、斗罗大陆）..."
            size="large"
            :prefix-icon="Search"
            clearable
            style="max-width: 520px"
            @update:model-value="emit('update:searchKw', $event)"
            @keyup.enter="emit('search')"
          />
          <ElButton
            type="primary"
            size="large"
            :icon="Search"
            :loading="props.searching"
            @click="emit('search')"
          >
            并发全网检索
          </ElButton>
        </div>
        <div class="hot-words-line">
          <span class="hot-label">快速测试热词：</span>
          <ElButton link size="small" @click="emit('quickSearch', '庆余年')">庆余年</ElButton>
          <ElButton link size="small" @click="emit('quickSearch', '繁花')">繁花</ElButton>
          <ElButton link size="small" @click="emit('quickSearch', '仙逆')">仙逆</ElButton>
          <ElButton link size="small" @click="emit('quickSearch', '斗罗大陆')">斗罗大陆</ElButton>
          <ElButton link size="small" @click="emit('quickSearch', '凡人修仙传')">凡人修仙传</ElButton>
        </div>
      </div>
    </ElCard>

    <!-- 搜索比对结果 -->
    <div v-if="props.searchResult" class="search-result-box">
      <div class="search-summary-card">
        <div class="summary-item">
          <span class="label">查询关键词</span>
          <span class="val font-bold">{{ props.searchResult.kw }}</span>
        </div>
        <div class="summary-item">
          <span class="label">并发源站数</span>
          <span class="val">{{ props.searchResult.total_sites }} 个</span>
        </div>
        <div class="summary-item">
          <span class="label">累计命中影视</span>
          <span class="val text-good font-bold">{{ props.searchResult.total_count }} 部</span>
        </div>
      </div>

      <!-- 按站点分组展示比对 -->
      <div v-for="res in props.searchResult.results" :key="res.site" class="site-search-group">
        <div class="site-group-head">
          <div class="group-title-box">
            <span class="site-name">{{ res.site_name }}</span>
            <span class="site-key font-mono">({{ res.site }})</span>
            <ElTag :type="!res.error ? 'success' : 'danger'" size="small">
              {{ !res.error ? `命中 ${res.count} 部` : '搜索超时或异常' }}
            </ElTag>
          </div>
          <div class="group-metrics">
            <span class="metric-text font-mono">耗时 {{ res.elapsed_ms }}ms</span>
          </div>
        </div>

        <div v-if="res.items?.length" class="site-movie-grid">
          <div v-for="(it, i) in (res.items as any[])" :key="i" class="search-movie-card">
            <div class="movie-title" :title="it.title">{{ it.title }}</div>
            <div class="movie-extra">ID: {{ it.id }} · {{ it.category || '默认' }}</div>
          </div>
        </div>
        <div v-else-if="!res.error" class="site-empty-text">该站未检索到与关键词匹配的片单</div>
        <div v-else class="site-error-text">{{ res.error }}</div>
      </div>
    </div>
  </div>
</template>
