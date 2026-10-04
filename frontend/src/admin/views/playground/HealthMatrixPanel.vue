<script setup lang="ts">
import {
  ElButton,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import type { MatrixItem } from './usePlayground'

const props = defineProps<{
  matrixList: MatrixItem[]
  matrixTesting: boolean
}>()

const emit = defineEmits<{
  runTest: []
}>()
</script>

<template>
  <div class="tab-panel">
    <div class="matrix-hero">
      <div class="matrix-hero-info">
        <h2 class="matrix-title">全站内容源并发体检中心</h2>
        <p class="matrix-desc">
          并发向所有内容源发起连通性探测，毫秒级分析各站响应延迟、首页可用率与抓取状态。
        </p>
      </div>
      <ElButton
        type="primary"
        size="large"
        :icon="Refresh"
        :loading="props.matrixTesting"
        @click="emit('runTest')"
      >
        {{ props.matrixTesting ? '正在并发体检中...' : '发起全站一键并发体检' }}
      </ElButton>
    </div>

    <div class="matrix-table-card">
      <ElTable :data="props.matrixList" size="default" style="width: 100%">
        <ElTableColumn prop="name" label="内容源名称" min-width="180">
          <template #default="{ row }">
            <span class="font-bold">{{ row.name }}</span>
            <span class="a-muted" style="margin-left: 6px; font-size: 12px">({{ row.site }})</span>
          </template>
        </ElTableColumn>

        <ElTableColumn label="体检状态" width="140">
          <template #default="{ row }">
            <ElTag v-if="row.status === 'success'" type="success" size="small" effect="light">服务正常</ElTag>
            <ElTag v-else-if="row.status === 'testing'" type="warning" size="small">探测中...</ElTag>
            <ElTag v-else-if="row.status === 'error'" type="danger" size="small">连通异常</ElTag>
            <ElTag v-else type="info" size="small">就绪待体检</ElTag>
          </template>
        </ElTableColumn>

        <ElTableColumn label="网络响应延迟" width="160">
          <template #default="{ row }">
            <span
              v-if="row.elapsed_ms !== undefined"
              class="font-mono font-bold"
              :class="row.elapsed_ms < 600 ? 'text-good' : 'text-warn'"
            >
              {{ row.elapsed_ms }} ms
            </span>
            <span v-else class="text-muted">—</span>
          </template>
        </ElTableColumn>

        <ElTableColumn label="首页影视拉取数" width="150" align="center">
          <template #default="{ row }">
            <span v-if="row.items_count !== undefined" class="font-mono font-bold">{{ row.items_count }} 部</span>
            <span v-else class="text-muted">—</span>
          </template>
        </ElTableColumn>

        <ElTableColumn label="异常诊断与备注" min-width="240">
          <template #default="{ row }">
            <span v-if="row.error" class="text-danger">{{ row.error }}</span>
            <span v-else-if="row.status === 'success'" class="text-good">协议通畅，抓取成功</span>
            <span v-else class="text-muted">点击上方按钮发起体检</span>
          </template>
        </ElTableColumn>
      </ElTable>
    </div>
  </div>
</template>
