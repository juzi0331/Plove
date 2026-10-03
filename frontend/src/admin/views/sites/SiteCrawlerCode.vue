<script setup lang="ts">
/**
 * SiteCrawlerCode - 采集器源码在线查看抽屉
 */
import { ElDrawer } from 'element-plus'

defineProps<{
  modelValue: boolean
  siteKey: string
  code: string
  mtime: string
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()
</script>

<template>
  <ElDrawer
    :model-value="modelValue"
    :title="`采集器源码查看 · ${siteKey}.py`"
    size="800px"
    destroy-on-close
    @update:model-value="(val) => emit('update:modelValue', val)"
  >
    <div v-loading="loading" class="code-viewer-container">
      <div class="code-meta-bar">
        最后更新时间：<span class="a-mono">{{ mtime || '—' }}</span>
      </div>
      <pre class="code-pre"><code>{{ code }}</code></pre>
    </div>
  </ElDrawer>
</template>
