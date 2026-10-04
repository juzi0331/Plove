<script setup lang="ts">
import { Upload } from '@element-plus/icons-vue'
import {
  ElButton,
  ElInput,
  ElMessage,
  ElSwitch,
} from 'element-plus'
import { ref } from 'vue'

import { describeError } from '@/api/http'
import type { AdminSiteItem } from '@/api/types'
import { uploadCrawler } from '@/admin/api'
import { ui } from '@/admin/ui'

const props = defineProps<{
  site: AdminSiteItem
  code: string
  mtime: string
  loadingCode: boolean
}>()

const emit = defineEmits<{
  (e: 'crawlerUploaded'): void
}>()

// 采集器源码在线上传与自定义版本号
const showCodeUpload = ref(false)
const modalUploadCode = ref('')
const modalCustomVersion = ref('')
const modalUploadOverwrite = ref(true)
const modalAutoBump = ref(false)
const modalUploading = ref(false)
const modalSelectedFileName = ref('')
const modalFileInputRef = ref<HTMLInputElement | null>(null)

function openModalUpload(): void {
  modalUploadCode.value = props.code || ''
  modalCustomVersion.value = ''
  modalUploadOverwrite.value = true
  modalAutoBump.value = false
  modalSelectedFileName.value = ''
  showCodeUpload.value = true
}

function triggerModalFileInput(): void {
  modalFileInputRef.value?.click()
}

function handleModalFileChange(e: Event): void {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  modalSelectedFileName.value = file.name
  const reader = new FileReader()
  reader.onload = (ev) => {
    modalUploadCode.value = (ev.target?.result as string) || ''
  }
  reader.readAsText(file)
}

async function handleModalSaveCrawler(): Promise<void> {
  if (ui.readOnly) {
    ElMessage.warning('演示模式只读，无法上传采集器')
    return
  }
  if (!props.site?.key) return
  if (!modalUploadCode.value.trim()) {
    ElMessage.warning('源码内容不能为空')
    return
  }

  modalUploading.value = true
  try {
    const res = await uploadCrawler({
      key: props.site.key,
      code: modalUploadCode.value,
      overwrite: modalUploadOverwrite.value,
      auto_bump_version: modalAutoBump.value,
      custom_version: modalCustomVersion.value.trim() || undefined,
    })
    ElMessage.success(res.message)
    showCodeUpload.value = false
    emit('crawlerUploaded')
  } catch (err) {
    ElMessage.error(describeError(err))
  } finally {
    modalUploading.value = false
  }
}
</script>

<template>
  <div v-loading="loadingCode" class="tab-pane-content">
    <div class="code-meta-bar">
      <div class="code-meta-left">
        <span>文件：<code>{{ site.key }}.py</code></span>
        <span v-if="mtime" style="margin-left: 12px;">最后修改：<strong class="a-mono">{{ mtime }}</strong></span>
      </div>
      <div class="code-meta-actions">
        <ElButton
          size="small"
          type="primary"
          :icon="Upload"
          :disabled="ui.readOnly"
          @click="showCodeUpload ? (showCodeUpload = false) : openModalUpload()"
        >
          {{ showCodeUpload ? '返回源码查看' : '上传/更新源码 (支持自定义版本)' }}
        </ElButton>
      </div>
    </div>

    <!-- 上传表单区 -->
    <div v-if="showCodeUpload" class="code-upload-panel">
      <input
        ref="modalFileInputRef"
        type="file"
        accept=".py"
        style="display: none;"
        @change="handleModalFileChange"
      />

      <div class="upload-tools-bar">
        <ElButton size="small" :icon="Upload" @click="triggerModalFileInput">
          选择本地 .py 文件
        </ElButton>
        <span v-if="modalSelectedFileName" class="selected-file-text">
          已选择：<strong>{{ modalSelectedFileName }}</strong>
        </span>

        <div class="version-input-box">
          <span class="version-label">自定义版本号：</span>
          <ElInput
            v-model="modalCustomVersion"
            placeholder="如 1.0.2 (选填，留空沿用原版)"
            size="small"
            style="width: 220px;"
          />
        </div>
      </div>

      <ElInput
        v-model="modalUploadCode"
        type="textarea"
        :rows="12"
        placeholder="# 请在此粘贴或编辑 Python 采集器源码"
        class="upload-code-textarea"
      />

      <div class="upload-panel-actions">
        <ElSwitch
          v-model="modalUploadOverwrite"
          active-text="允许覆盖现有文件"
          size="small"
        />
        <div style="display: flex; gap: 8px;">
          <ElButton size="small" @click="showCodeUpload = false">取消</ElButton>
          <ElButton
            size="small"
            type="primary"
            :loading="modalUploading"
            @click="handleModalSaveCrawler"
          >
            保存并部署更新
          </ElButton>
        </div>
      </div>
    </div>

    <!-- 源码查看预览框 -->
    <pre v-else class="code-pre-box"><code>{{ code || '正在载入 Python 爬虫源代码...' }}</code></pre>
  </div>
</template>

<style scoped src="./site-detail-modal.css"></style>
