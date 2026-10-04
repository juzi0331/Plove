/**
 * useCrawlerCode - 采集器源码在线查看
 */

import { ElMessage } from 'element-plus'
import { ref } from 'vue'

import { describeError } from '@/api/http'
import type { AdminSiteItem } from '@/api/types'

import * as api from '../../api'

export function useCrawlerCode() {
  const isCodeViewerVisible = ref(false)
  const currentCodeKey = ref('')
  const currentCode = ref('')
  const currentCodeMtime = ref('')
  const loadingCode = ref(false)

  async function openCodeViewer(site: AdminSiteItem): Promise<void> {
    currentCodeKey.value = site.key
    currentCode.value = ''
    currentCodeMtime.value = ''
    isCodeViewerVisible.value = true
    loadingCode.value = true
    try {
      const res = await api.getCrawlerCode(site.key)
      currentCode.value = res.code
      currentCodeMtime.value = res.updated_at ?? ''
    } catch (err) {
      ElMessage.error(describeError(err))
    } finally {
      loadingCode.value = false
    }
  }

  return {
    isCodeViewerVisible,
    currentCodeKey,
    currentCode,
    currentCodeMtime,
    loadingCode,
    openCodeViewer,
  }
}
