<script setup lang="ts">
import { CopyDocument } from '@element-plus/icons-vue'
import {
  ElButton,
  ElDialog,
  ElInputNumber,
} from 'element-plus'
import type { ProxyNodeItem } from '@/api/types'

const props = defineProps<{
  modelValue: boolean
  currentExportNode: ProxyNodeItem | null
  xrayPort: number
  xrayConfigJson: string
  exporting: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'update:xrayPort', val: number): void
  (e: 'fetchConfig'): void
  (e: 'copy'): void
}>()
</script>

<template>
  <ElDialog
    :model-value="props.modelValue"
    :title="`Xray-core 配置文件 (备用) · ${props.currentExportNode?.name || ''}`"
    width="680px"
    align-center
    append-to-body
    destroy-on-close
    class="submodal-dialog"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div v-loading="props.exporting">
      <div class="xray-desc">
        💡 系统默认已通过<strong>内置 Xray 引擎</strong>在本机自动托管运行此节点。此配置生成器仅供您备份或在外部独立机器上执行：
      </div>

      <div class="xray-port-bar">
        <span class="port-label">修改本地 HTTP 映射端口：</span>
        <ElInputNumber
          :model-value="props.xrayPort"
          :min="1024"
          :max="65535"
          size="small"
          @update:model-value="emit('update:xrayPort', $event as number)"
          @change="emit('fetchConfig')"
        />
      </div>

      <div class="code-wrapper">
        <pre class="json-code"><code>{{ props.xrayConfigJson }}</code></pre>
      </div>
    </div>

    <template #footer>
      <ElButton :icon="CopyDocument" type="primary" @click="emit('copy')">
        一键复制 config.json
      </ElButton>
      <ElButton @click="emit('update:modelValue', false)">关闭</ElButton>
    </template>
  </ElDialog>
</template>
