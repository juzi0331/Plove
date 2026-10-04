/**
 * useSiteList - 站点列表数据加载、排序、启停与健康状态
 */

import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

import { describeError } from '@/api/http'
import type { AdminSiteItem, AdminSiteListPayload, ProxyNodeItem } from '@/api/types'

import * as api from '../../api'
import { type TagType } from '../../format'
import { ui } from '../../ui'

const STATE: Record<string, { label: string; tag: TagType }> = {
  closed: { label: '正常', tag: 'success' },
  half_open: { label: '探测中', tag: 'warning' },
  open: { label: '已熔断', tag: 'danger' },
}

export function useSiteList() {
  const data = ref<AdminSiteListPayload | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const busyKey = ref<string | null>(null)
  const proxyNodes = ref<ProxyNodeItem[]>([])

  async function load(): Promise<void> {
    loading.value = true
    try {
      const [sitesRes, nodesRes] = await Promise.all([
        api.listSites(),
        api.listProxyNodes().catch(() => ({ total: 0, nodes: [] })),
      ])
      data.value = sitesRes
      proxyNodes.value = nodesRes?.nodes ?? []
      error.value = null
    } catch (err) {
      error.value = describeError(err)
    } finally {
      loading.value = false
    }
  }

  onMounted(load)

  function getNodeById(id?: string): ProxyNodeItem | undefined {
    if (!id || id === 'direct') return undefined
    return proxyNodes.value.find((n) => n.id === id)
  }

  function formatNodeLabel(node: ProxyNodeItem): string {
    const ping = node.ping_ms ? ` (${node.ping_ms}ms)` : ''
    return `[${node.protocol.toUpperCase()}] ${node.name} · ${node.server}:${node.port}${ping}`
  }

  function getBoundNodeBadgeText(site: AdminSiteItem): string {
    if (site.proxy_node_id) {
      const node = getNodeById(site.proxy_node_id)
      if (node) {
        return node.name.length > 8 ? node.name.slice(0, 8) + '…' : node.name
      }
    }
    return '代理'
  }

  function getProxyTooltip(site: AdminSiteItem): string {
    if (site.proxy_enabled) {
      if (site.proxy_node_id) {
        const node = getNodeById(site.proxy_node_id)
        if (node) {
          return `独立代理已开启：已绑定「${node.name}」（${node.protocol.toUpperCase()} · ${node.server}:${node.port}），点击快速切换`
        }
      }
      return `独立代理已开启：${site.proxy_url || '未配置端口'}，点击快速切换`
    }
    return '独立代理已关闭（直连源站），点击快速开启或配置'
  }

  const sites = computed(() => data.value?.sites ?? [])
  const isEmpty = computed(() => !loading.value && !error.value && sites.value.length === 0)
  const firstKey = computed(() => sites.value[0]?.key)
  const lastKey = computed(() => sites.value[sites.value.length - 1]?.key)

  function healthState(site: AdminSiteItem): { label: string; tag: TagType } {
    if (!site.health.probed) return { label: '未探测', tag: 'info' }
    return STATE[site.health.state] ?? { label: site.health.state, tag: 'info' }
  }

  async function toggle(site: AdminSiteItem, next: boolean): Promise<void> {
    if (next === site.enabled) return
    if (ui.readOnly) {
      ElMessage.warning('演示模式只读，无法修改站点状态')
      return
    }

    if (!next) {
      try {
        await ElMessageBox.confirm(
          `停用 ${site.key}？用户端的站点列表里不再出现它，正在用它的人下一次请求会看到"该源已关闭"。` +
            '（缓存里已有的内容也不再发出，缓存本身不用清。）',
          '停用这个源',
          { type: 'warning', confirmButtonText: '停用', cancelButtonText: '取消' },
        )
      } catch {
        return
      }
    }

    busyKey.value = site.key
    try {
      const res = next ? await api.enableSite(site.key) : await api.disableSite(site.key)
      ElMessage.success(res.message)
      await load()
    } catch (err) {
      ElMessage.error(describeError(err))
    } finally {
      busyKey.value = null
    }
  }

  async function move(index: number, delta: number): Promise<void> {
    if (ui.readOnly) {
      ElMessage.warning('演示模式只读，无法修改站点顺序')
      return
    }
    if (!data.value) return
    const target = index + delta
    if (target < 0 || target >= sites.value.length) return
    const cur = [...sites.value]
    const [item] = cur.splice(index, 1)
    cur.splice(target, 0, item)
    const keys = cur.map((s) => s.key)
    try {
      const res = await api.orderSites(keys)
      data.value = res
      ElMessage.success('顺序已更新')
    } catch (err) {
      ElMessage.error(describeError(err))
    }
  }

  async function deleteSite(site: AdminSiteItem): Promise<void> {
    if (ui.readOnly) {
      ElMessage.warning('演示模式只读，无法删除采集器')
      return
    }
    try {
      await ElMessageBox.confirm(
        `确定要下线并彻底删除采集器「${site.name}」(${site.key}.py) 吗？该操作不可逆！`,
        '高危下线确认',
        {
          confirmButtonText: '确定删除',
          cancelButtonText: '取消',
          type: 'warning',
        },
      )
      await api.deleteCrawler(site.key)
      ElMessage.success(`采集器 ${site.key} 已成功删除`)
      await load()
    } catch {
      // 用户取消
    }
  }

  async function toggleSiteProxy(site: AdminSiteItem): Promise<void> {
    if (ui.readOnly) {
      ElMessage.warning('演示模式只读，无法修改代理设置')
      return
    }
    const nextState = !site.proxy_enabled
    try {
      await api.updateSiteAdvanced(site.key, {
        proxy_enabled: nextState,
        proxy_node_id: nextState ? (site.proxy_node_id || undefined) : '',
        proxy_url: nextState ? (site.proxy_url || undefined) : '',
      })
      site.proxy_enabled = nextState
      if (!nextState) {
        site.proxy_node_id = ''
        site.proxy_url = ''
      }
      ElMessage.success(`${site.name} 独立代理已${nextState ? '开启' : '关闭'}`)
    } catch (err) {
      ElMessage.error(describeError(err))
    }
  }

  return {
    data,
    loading,
    error,
    busyKey,
    proxyNodes,
    sites,
    isEmpty,
    firstKey,
    lastKey,
    load,
    getNodeById,
    formatNodeLabel,
    getBoundNodeBadgeText,
    getProxyTooltip,
    healthState,
    toggle,
    move,
    deleteSite,
    toggleSiteProxy,
  }
}
