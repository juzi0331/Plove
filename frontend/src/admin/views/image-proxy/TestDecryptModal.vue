<script setup lang="ts">
import {
  ElAlert,
  ElButton,
  ElDialog,
  ElFormItem,
  ElInput,
} from 'element-plus'
import { VideoPlay } from '@element-plus/icons-vue'
import type { ImageDecryptionRule, TestDecryptResult } from '@/api/types'

const props = defineProps<{
  modelValue: boolean
  rule: ImageDecryptionRule | null
  testUrl: string
  loading: boolean
  result: TestDecryptResult | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'update:testUrl', val: string): void
  (e: 'run'): void
}>()
</script>

<template>
  <ElDialog
    :model-value="props.modelValue"
    :title="`解密验证: ${props.rule?.name || props.rule?.id || ''}`"
    width="600px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div v-if="props.rule" class="modal-rule-info">
      <div class="info-row">
        <span>所属站点:</span>
        <b>{{ props.rule.site_key || '通用' }}</b>
      </div>
      <div class="info-row">
        <span>算法 / Key:</span>
        <code>{{ props.rule.algorithm }} | {{ props.rule.key }}</code>
      </div>
    </div>

    <div style="margin-top: 14px;">
      <ElFormItem label="待验证的图片 URL">
        <div style="display: flex; gap: 8px; width: 100%;">
          <ElInput
            :model-value="props.testUrl"
            placeholder="输入目标加密图床图片 URL（若图床开启鉴权需带完整 ?auth_key= 等参数）"
            clearable
            @update:model-value="emit('update:testUrl', $event)"
          />
          <ElButton
            type="primary"
            :loading="props.loading"
            :icon="VideoPlay"
            @click="emit('run')"
          >
            执行解密
          </ElButton>
        </div>
      </ElFormItem>
    </div>

    <div v-if="props.result" style="margin-top: 14px;">
      <ElAlert
        :type="props.result.success ? 'success' : 'error'"
        :closable="false"
        show-icon
      >
        <template #title>
          <span>{{ props.result.message }}</span>
        </template>
      </ElAlert>

      <div v-if="props.result.preview_data_url" class="test-modal-preview">
        <img :src="props.result.preview_data_url" alt="解密成功预览" class="modal-preview-img" />
        <div class="modal-preview-meta">
          <div>MIME 类型: <b>{{ props.result.mime_type }}</b></div>
          <div>图片大小: <b>{{ (((props.result.size_bytes || 0)) / 1024).toFixed(1) }} KB</b></div>
          <div>解密耗时: <b>{{ props.result.elapsed_ms }} ms</b></div>
        </div>
      </div>
    </div>

    <template #footer>
      <ElButton @click="emit('update:modelValue', false)">关闭</ElButton>
    </template>
  </ElDialog>
</template>
