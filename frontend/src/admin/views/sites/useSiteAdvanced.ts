/**
 * useSiteAdvanced - 单站高级配置、代理节点绑定与单站缓存 TTL
 */

import { ElMessage } from 'element-plus'
import { computed, ref, type Ref } from 'vue'

import { describeError } from '@/api/http'
import type {
  AdminSiteItem,
  ProxyNodeItem,
  SiteAdvancedSettingPayload,
  SiteCachePolicy,
} from '@/api/types'

import * as api from '../../api'

export function useSiteAdvanced(
  proxyNodes: Ref<ProxyNodeItem[]>,
  getNodeById: (id?: string) => ProxyNodeItem | undefined,
  onSuccess?: () => Promise<void>,
) {
  const isAdvancedVisible = ref(false)
  const advancedLoading = ref(false)
  const advancedSaving = ref(false)
  const selectedProxyChoice = ref<string>('direct')
  const testingNode = ref(false)

  const currentAdvanced = ref<SiteAdvancedSettingPayload>({
    key: '',
    custom_name: '',
    badge: '',
    timeout_seconds: 0,
    note: '',
    proxy_enabled: false,
    proxy_url: '',
    proxy_node_id: '',
  })

  const currentCachePolicy = ref<SiteCachePolicy>({
    home_ttl: null,
    category_ttl: null,
    detail_ttl: null,
  })

  const selectedNode = computed(() => {
    if (!currentAdvanced.value.proxy_node_id) return undefined
    return getNodeById(currentAdvanced.value.proxy_node_id)
  })

  function resolveProxyChoice(enabled: boolean, nodeId?: string, proxyUrl?: string): string {
    if (!enabled) return 'direct'
    if (nodeId && proxyNodes.value.some((n) => n.id === nodeId)) {
      return nodeId
    }
    if (proxyUrl) {
      const matched = proxyNodes.value.find((n) => n.proxy_url === proxyUrl)
      if (matched) return matched.id
      return 'custom'
    }
    return 'direct'
  }

  function onProxyChoiceChange(choice: string): void {
    selectedProxyChoice.value = choice
    if (choice === 'direct') {
      currentAdvanced.value.proxy_enabled = false
      currentAdvanced.value.proxy_node_id = ''
      currentAdvanced.value.proxy_url = ''
    } else if (choice === 'custom') {
      currentAdvanced.value.proxy_enabled = true
      currentAdvanced.value.proxy_node_id = ''
      if (!currentAdvanced.value.proxy_url) {
        currentAdvanced.value.proxy_url = 'http://127.0.0.1:10809'
      }
    } else {
      const node = proxyNodes.value.find((n) => n.id === choice)
      if (node) {
        currentAdvanced.value.proxy_enabled = true
        currentAdvanced.value.proxy_node_id = node.id
        currentAdvanced.value.proxy_url = node.proxy_url
      }
    }
  }

  async function testCurrentNode(): Promise<void> {
    if (!selectedNode.value) return
    testingNode.value = true
    try {
      const res = await api.testProxyNode({ node_id: selectedNode.value.id })
      if (res.ok) {
        ElMessage.success(`节点测速成功：延迟 ${res.duration_ms} ms`)
        selectedNode.value.ping_ms = res.duration_ms
        selectedNode.value.last_tested_at = new Date().toLocaleTimeString()
      } else {
        ElMessage.warning(`测速失败：${res.message || '连接超时'}`)
      }
    } catch (err) {
      ElMessage.error(describeError(err))
    } finally {
      testingNode.value = false
    }
  }

  async function openAdvanced(site: AdminSiteItem): Promise<void> {
    currentAdvanced.value = {
      key: site.key,
      custom_name: '',
      badge: '',
      timeout_seconds: 0,
      note: site.note || '',
      proxy_enabled: Boolean(site.proxy_enabled),
      proxy_url: site.proxy_url || '',
      proxy_node_id: site.proxy_node_id || '',
    }
    selectedProxyChoice.value = resolveProxyChoice(
      Boolean(site.proxy_enabled),
      site.proxy_node_id,
      site.proxy_url,
    )
    currentCachePolicy.value = {
      home_ttl: null,
      category_ttl: null,
      detail_ttl: null,
    }
    isAdvancedVisible.value = true
    advancedLoading.value = true
    try {
      const [adv, cacheP] = await Promise.all([
        api.getSiteAdvanced(site.key),
        api.getSiteCachePolicy(site.key),
      ])
      currentAdvanced.value = {
        key: adv.key,
        custom_name: adv.custom_name ?? '',
        badge: adv.badge ?? '',
        timeout_seconds: adv.timeout_seconds ?? 0,
        note: adv.note ?? '',
        proxy_enabled: Boolean(adv.proxy_enabled),
        proxy_url: adv.proxy_url ?? '',
        proxy_node_id: adv.proxy_node_id ?? '',
      }
      selectedProxyChoice.value = resolveProxyChoice(
        Boolean(adv.proxy_enabled),
        adv.proxy_node_id,
        adv.proxy_url,
      )
      currentCachePolicy.value = cacheP
    } catch (err) {
      ElMessage.error(describeError(err))
    } finally {
      advancedLoading.value = false
    }
  }

  async function saveAdvanced(): Promise<void> {
    advancedSaving.value = true
    try {
      const isDirect = selectedProxyChoice.value === 'direct' || !currentAdvanced.value.proxy_enabled
      const sendProxyEnabled = !isDirect
      const sendProxyNodeId = isDirect ? '' : currentAdvanced.value.proxy_node_id
      const sendProxyUrl = isDirect ? '' : currentAdvanced.value.proxy_url

      await Promise.all([
        api.updateSiteAdvanced(currentAdvanced.value.key, {
          custom_name: currentAdvanced.value.custom_name,
          badge: currentAdvanced.value.badge,
          timeout_seconds: currentAdvanced.value.timeout_seconds,
          note: currentAdvanced.value.note,
          proxy_enabled: sendProxyEnabled,
          proxy_url: sendProxyUrl,
          proxy_node_id: sendProxyNodeId,
        }),
        api.bindSiteProxyNode({
          site_key: currentAdvanced.value.key,
          node_id: isDirect ? 'direct' : (sendProxyNodeId || 'custom'),
        }),
        api.updateSiteCachePolicy(currentAdvanced.value.key, currentCachePolicy.value),
      ])
      ElMessage.success('单站配置、代理节点与缓存策略已保存')
      isAdvancedVisible.value = false
      if (onSuccess) {
        await onSuccess()
      }
    } catch (err) {
      ElMessage.error(describeError(err))
    } finally {
      advancedSaving.value = false
    }
  }

  return {
    isAdvancedVisible,
    advancedLoading,
    advancedSaving,
    selectedProxyChoice,
    testingNode,
    currentAdvanced,
    currentCachePolicy,
    selectedNode,
    onProxyChoiceChange,
    testCurrentNode,
    openAdvanced,
    saveAdvanced,
  }
}
