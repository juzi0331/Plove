/**
 * useCrawlerUpload - 采集器脚本上传、本地文件拖拽解析、静态 AST 审计与落盘部署
 */

import { ElMessage } from 'element-plus'
import { ref } from 'vue'

import { describeError } from '@/api/http'
import type { CrawlerValidateResult } from '@/api/types'

import * as api from '../../api'
import { ui } from '../../ui'

export function useCrawlerUpload(onSuccess?: () => Promise<void>) {
  const isUploadVisible = ref(false)
  const uploadKey = ref('')
  const uploadCode = ref('')
  const uploadOverwrite = ref(true)
  const uploadAutoBump = ref(false)
  const validating = ref(false)
  const uploading = ref(false)
  const validateResult = ref<CrawlerValidateResult | null>(null)
  const selectedFileName = ref('')
  const selectedFileSize = ref(0)
  const fileInputRef = ref<HTMLInputElement | null>(null)

  function openUploadDialog(): void {
    uploadKey.value = ''
    uploadCode.value = ''
    uploadOverwrite.value = true
    uploadAutoBump.value = false
    validateResult.value = null
    selectedFileName.value = ''
    selectedFileSize.value = 0
    isUploadVisible.value = true
  }

  function handleFileRead(file: File): void {
    selectedFileName.value = file.name
    selectedFileSize.value = file.size
    let suggested = file.name.replace(/\.py$/i, '').trim().toLowerCase()
    suggested = suggested.replace(/[^a-z0-9_]/g, '_')
    if (!uploadKey.value) {
      uploadKey.value = suggested
    }
    const reader = new FileReader()
    reader.onload = (e) => {
      uploadCode.value = (e.target?.result as string) || ''
      validateResult.value = null
    }
    reader.readAsText(file)
  }

  function handleFileChange(e: Event): void {
    const input = e.target as HTMLInputElement
    if (input.files?.[0]) {
      handleFileRead(input.files[0])
    }
  }

  function handleFileDrop(e: DragEvent): void {
    if (e.dataTransfer?.files?.[0]) {
      handleFileRead(e.dataTransfer.files[0])
    }
  }

  function triggerFileInput(): void {
    fileInputRef.value?.click()
  }

  function clearSelectedFile(): void {
    selectedFileName.value = ''
    selectedFileSize.value = 0
    uploadCode.value = ''
    validateResult.value = null
    if (fileInputRef.value) {
      fileInputRef.value.value = ''
    }
  }

  function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`
    return `${(bytes / 1024).toFixed(1)} KB`
  }

  async function handleValidateCrawler(): Promise<boolean> {
    if (!uploadCode.value.trim()) {
      ElMessage.warning('请先输入或上传 Python 脚本代码')
      return false
    }
    validating.value = true
    try {
      const res = await api.validateCrawler({
        key: uploadKey.value.trim() || undefined,
        code: uploadCode.value,
      })
      validateResult.value = res
      if (res.valid) {
        ElMessage.success('静态审计与 meta 协议测试全部通过')
        if (res.meta?.key && !uploadKey.value) {
          uploadKey.value = res.meta.key
        }
        return true
      } else {
        ElMessage.error(`校验失败: ${res.error}`)
        return false
      }
    } catch (err) {
      ElMessage.error(describeError(err))
      return false
    } finally {
      validating.value = false
    }
  }

  async function handleSaveCrawler(): Promise<void> {
    if (ui.readOnly) {
      ElMessage.warning('演示模式只读，无法上传采集器')
      return
    }
    if (!uploadKey.value.trim()) {
      ElMessage.warning('请输入唯一的采集器标识（key）')
      return
    }
    if (!validateResult.value?.valid) {
      const ok = await handleValidateCrawler()
      if (!ok) return
    }
    uploading.value = true
    try {
      const res = await api.uploadCrawler({
        key: uploadKey.value.trim(),
        code: uploadCode.value,
        overwrite: uploadOverwrite.value,
        auto_bump_version: uploadAutoBump.value,
      })
      ElMessage.success(res.message)
      isUploadVisible.value = false
      if (onSuccess) {
        await onSuccess()
      }
    } catch (err) {
      ElMessage.error(describeError(err))
    } finally {
      uploading.value = false
    }
  }

  return {
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
  }
}
