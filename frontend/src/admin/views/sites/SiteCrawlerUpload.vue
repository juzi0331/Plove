<script setup lang="ts">
/**
 * SiteCrawlerUpload - 采集器脚本上传与安全校验对话框
 */
import { UploadFilled } from '@element-plus/icons-vue'
import {
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
  ElSwitch,
} from 'element-plus'
import { watch } from 'vue'

import { useCrawlerUpload } from './useCrawlerUpload'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'uploaded'): void
}>()

const {
  isUploadVisible,
  uploadKey,
  uploadCode,
  uploadOverwrite,
  uploadAutoBump,
  validating,
  uploading,
  validateResult,
  selectedFileName,
  selectedFileSize,
  fileInputRef,
  openUploadDialog,
  triggerFileInput,
  clearSelectedFile,
  handleFileChange,
  handleFileDrop,
  formatFileSize,
  handleValidateCrawler,
  handleSaveCrawler,
} = useCrawlerUpload(async () => {
  emit('uploaded')
})

watch(
  () => props.modelValue,
  (val) => {
    if (val && !isUploadVisible.value) {
      openUploadDialog()
    } else if (!val && isUploadVisible.value) {
      isUploadVisible.value = false
    }
  },
)

watch(isUploadVisible, (val) => {
  emit('update:modelValue', val)
})
</script>

<template>
  <ElDialog
    v-model="isUploadVisible"
    title="部署 / 上传 Python 采集器脚本"
    width="780px"
    align-center
    destroy-on-close
  >
    <ElForm label-position="top">
      <div
        class="file-upload-dropzone"
        @dragover.prevent
        @drop.prevent="handleFileDrop"
        @click="triggerFileInput"
      >
        <input
          ref="fileInputRef"
          type="file"
          accept=".py"
          style="display: none;"
          @change="handleFileChange"
        />
        <div class="dropzone-content">
          <ElIcon class="dropzone-icon"><UploadFilled /></ElIcon>
          <div class="dropzone-text">
            <strong>点击选择本地 .py 文件</strong> 或直接拖拽文件到这里
          </div>
          <div class="dropzone-sub">
            选择后将自动提取站点 Key、载入完整源代码并自动执行全链路安全冒烟校验
          </div>
        </div>
        <div v-if="selectedFileName" class="selected-file-badge" @click.stop>
          <span class="file-name-tag">
            📄 已载入文件：<strong>{{ selectedFileName }}</strong>（{{ formatFileSize(selectedFileSize) }}）
          </span>
          <ElButton size="small" type="primary" link @click.stop="triggerFileInput">更换文件</ElButton>
          <ElButton size="small" type="danger" link @click.stop="clearSelectedFile">清除</ElButton>
        </div>
      </div>

      <ElFormItem label="站点 Key（英文小写下划线，对应 crawler/sites/<key>.py）" required>
        <ElInput v-model="uploadKey" placeholder="如：my_vod_site" />
      </ElFormItem>

      <ElFormItem label="采集器 Python 源代码（支持上方直接选文件载入，或在此手动粘贴与微调）" required>
        <ElInput
          v-model="uploadCode"
          type="textarea"
          :rows="14"
          placeholder="# 请在此粘贴完整的 Python 采集器脚本（必须遵循 Plove 命令行信封协议）"
          class="code-textarea"
        />
      </ElFormItem>

      <div v-if="validateResult" class="validate-box" :class="{ 'is-ok': validateResult.valid, 'is-fail': !validateResult.valid }">
        <div class="val-title">
          {{ validateResult.valid ? '语法与协议审计通过' : '校验失败' }}
        </div>
        <div v-if="validateResult.error" class="val-err">
          {{ validateResult.error }}
        </div>
        <div v-if="validateResult.meta" class="val-meta">
          站点名称：<strong>{{ validateResult.meta.name }}</strong> | 模式：{{ validateResult.meta.mode }} | 能力：{{ (validateResult.meta.capabilities || []).join(', ') }}
        </div>
      </div>

      <ElFormItem>
        <div class="upload-options">
          <ElSwitch v-model="uploadOverwrite" active-text="允许覆盖已有文件" />
          <ElSwitch
            v-if="uploadOverwrite"
            v-model="uploadAutoBump"
            active-text="自动自增修订版本号 (如 v1.0.0 ➔ v1.0.1)"
          />
        </div>
      </ElFormItem>
    </ElForm>

    <template #footer>
      <div class="dialog-footer">
        <ElButton :loading="validating" @click="handleValidateCrawler">
          在线校验 (AST + 冒烟测试)
        </ElButton>
        <ElButton @click="isUploadVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="uploading" @click="handleSaveCrawler">
          确认落盘部署
        </ElButton>
      </div>
    </template>
  </ElDialog>
</template>
