import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { describeError } from '@/api/http'
import type {
  AdminSiteItem,
  ProxyEngineStatusPayload,
  ProxyNodeItem,
  ProxyNodeListPayload,
  ProxyTestResult,
} from '@/api/types'
import * as api from '@/admin/api'

export function useProxyNodes() {
  const loading = ref(false)
  const nodesData = ref<ProxyNodeListPayload>({ nodes: [], bindings: {} })
  const sites = ref<AdminSiteItem[]>([])

  // Xray 内置引擎状态
  const engineStatus = ref<ProxyEngineStatusPayload | null>(null)
  const engineActionLoading = ref(false)

  // 测速状态映射: { [nodeId]: { loading: boolean, result?: ProxyTestResult } }
  const testStates = ref<Record<string, { loading: boolean; result?: ProxyTestResult }>>({})

  // ------------------------------------------------------------------ 数据加载
  async function load(): Promise<void> {
    loading.value = true
    try {
      const [nodeRes, siteRes, engStatus] = await Promise.all([
        api.listProxyNodes(),
        api.listSites(),
        api.getProxyEngineStatus().catch(() => null),
      ])
      nodesData.value = nodeRes
      sites.value = siteRes.sites ?? []
      if (engStatus) {
        engineStatus.value = engStatus
      }
    } catch (err) {
      ElMessage.error(describeError(err))
    } finally {
      loading.value = false
    }
  }

  onMounted(load)

  const nodes = computed(() => nodesData.value.nodes ?? [])
  const bindings = computed(() => nodesData.value.bindings ?? {})

  // 获取绑定到某节点的采集器列表（修复直连仍显示使用的 Bug）
  function getBoundSites(nodeId: string): AdminSiteItem[] {
    return sites.value.filter((s) => {
      // 只要采集器设置了直连 (proxy_enabled 为 false)，绝对不视为正在使用任何节点
      if (!s.proxy_enabled) return false
      // 优先匹配单站配置明确指派的 proxy_node_id
      if (s.proxy_node_id) {
        return s.proxy_node_id === nodeId
      }
      // 备选匹配节点池中的映射
      return bindings.value[s.key] === nodeId
    })
  }

  // 统计数据
  const totalNodes = computed(() => nodes.value.length)
  const vlessNodes = computed(() => nodes.value.filter((n) => n.protocol === 'vless').length)
  const totalBindings = computed(() => {
    return sites.value.filter((s) => s.proxy_enabled && (s.proxy_node_id || bindings.value[s.key])).length
  })

  // ------------------------------------------------------------------ 内置 Xray 引擎控制
  async function handleInstallEngine(): Promise<void> {
    engineActionLoading.value = true
    try {
      ElMessage.info('开始自动下载并安装 Xray-core 独立内核，请稍候...')
      const res = await api.installProxyEngine()
      engineStatus.value = res.status
      ElMessage.success(res.message || 'Xray-core 内核安装成功，内置转发服务已就绪！')
      await load()
    } catch (err) {
      ElMessage.error(describeError(err))
    } finally {
      engineActionLoading.value = false
    }
  }

  async function handleStartEngine(): Promise<void> {
    engineActionLoading.value = true
    try {
      const res = await api.startProxyEngine()
      engineStatus.value = res.status
      if (res.success) {
        ElMessage.success(res.message || '内置 Xray 引擎已成功启动')
      } else {
        ElMessage.error(res.message || 'Xray 引擎启动失败')
      }
      await load()
    } catch (err) {
      ElMessage.error(describeError(err))
    } finally {
      engineActionLoading.value = false
    }
  }

  async function handleStopEngine(): Promise<void> {
    engineActionLoading.value = true
    try {
      const res = await api.stopProxyEngine()
      engineStatus.value = res.status
      if (res.success) {
        ElMessage.info(res.message || '内置 Xray 引擎已停止')
      } else {
        ElMessage.error(res.message || '停止 Xray 引擎失败')
      }
      await load()
    } catch (err) {
      ElMessage.error(describeError(err))
    } finally {
      engineActionLoading.value = false
    }
  }

  async function handleRestartEngine(): Promise<void> {
    engineActionLoading.value = true
    try {
      const res = await api.restartProxyEngine()
      engineStatus.value = res.status
      if (res.success) {
        ElMessage.success(res.message || '内置 Xray 引擎已重新加载配置并重启')
      } else {
        ElMessage.error(res.message || 'Xray 引擎重启失败')
      }
      await load()
    } catch (err) {
      ElMessage.error(describeError(err))
    } finally {
      engineActionLoading.value = false
    }
  }

  // ------------------------------------------------------------------ 快速解除绑定 / 指派
  async function handleUnbindSite(siteKey: string, siteName: string): Promise<void> {
    try {
      await ElMessageBox.confirm(
        `确定将采集器「${siteName}」切换为直连模式吗？`,
        '恢复直连',
        { type: 'info', confirmButtonText: '确定直连', cancelButtonText: '取消' },
      )
      await api.bindSiteProxyNode({ site_key: siteKey, node_id: 'direct' })
      ElMessage.success(`采集器「${siteName}」已恢复为直连模式`)
      await load()
    } catch (err) {
      if (err !== 'cancel') ElMessage.error(describeError(err))
    }
  }

  const isBindDialogVisible = ref(false)
  const currentBindTargetNode = ref<ProxyNodeItem | null>(null)
  const selectedSiteKeyToBind = ref('')
  const bindSaving = ref(false)

  function openBindDialog(node: ProxyNodeItem): void {
    currentBindTargetNode.value = node
    selectedSiteKeyToBind.value = ''
    isBindDialogVisible.value = true
  }

  async function handleConfirmBind(): Promise<void> {
    if (!currentBindTargetNode.value || !selectedSiteKeyToBind.value) {
      ElMessage.warning('请选择需要指派的采集器')
      return
    }
    bindSaving.value = true
    try {
      await api.bindSiteProxyNode({
        site_key: selectedSiteKeyToBind.value,
        node_id: currentBindTargetNode.value.id,
      })
      ElMessage.success(`采集器已成功绑定到节点「${currentBindTargetNode.value.name}」`)
      isBindDialogVisible.value = false
      await load()
    } catch (err) {
      ElMessage.error(describeError(err))
    } finally {
      bindSaving.value = false
    }
  }

  async function handleInlineBind(nodeId: string, siteKey: string): Promise<void> {
    if (!siteKey) return
    try {
      await api.bindSiteProxyNode({
        site_key: siteKey,
        node_id: nodeId,
      })
      const site = sites.value.find((s) => s.key === siteKey)
      ElMessage.success(`采集器「${site?.name || siteKey}」已指派至当前节点`)
      await load()
    } catch (err) {
      ElMessage.error(describeError(err))
    }
  }

  function getAvailableSitesForNode(nodeId: string): AdminSiteItem[] {
    const boundKeys = new Set(getBoundSites(nodeId).map((s) => s.key))
    return sites.value.filter((s) => !boundKeys.has(s.key))
  }

  // ------------------------------------------------------------------ 连通性测速
  async function handleTestNode(node: ProxyNodeItem): Promise<void> {
    testStates.value[node.id] = { loading: true }
    try {
      const res = await api.testProxyNode({
        node_id: node.id,
        proxy_url: node.proxy_url,
        target_url: 'https://www.google.com',
      })
      testStates.value[node.id] = { loading: false, result: res }
      if (res.ok) {
        ElMessage.success(`${node.name}: 连通正常，延迟 ${res.duration_ms}ms`)
      } else {
        ElMessage.warning(`${node.name}: 连接失败 (${res.message})`)
      }
    } catch (err) {
      testStates.value[node.id] = {
        loading: false,
        result: {
          ok: false,
          duration_ms: 0,
          status_code: 0,
          proxy_used: node.proxy_url,
          message: describeError(err),
        },
      }
      ElMessage.error(describeError(err))
    }
  }

  async function handleTestAllNodes(): Promise<void> {
    if (nodes.value.length === 0) return
    ElMessage.info('开始全节点并发连通性测速...')
    await Promise.allSettled(nodes.value.map((n) => handleTestNode(n)))
  }

  // ------------------------------------------------------------------ 添加节点弹窗
  const isAddDialogVisible = ref(false)
  const addMode = ref<'vless' | 'http'>('vless')
  const addForm = ref({
    raw_url: '',
    name: '',
    local_port: 10809,
  })
  const adding = ref(false)

  function openAddDialog(): void {
    addForm.value = {
      raw_url: '',
      name: '',
      local_port: 10809,
    }
    addMode.value = 'vless'
    isAddDialogVisible.value = true
  }

  const parsedPreview = computed(() => {
    const url = addForm.value.raw_url.trim()
    if (!url) return null
    if (url.startsWith('vless://')) {
      try {
        const rest = url.slice('vless://'.length)
        let main = rest
        let name = ''
        if (main.includes('#')) {
          const parts = main.split('#')
          main = parts[0]
          name = decodeURIComponent(parts[1] || '')
        }
        if (main.includes('?')) {
          main = main.split('?')[0]
        }
        const [uuid, hostPort] = main.split('@')
        const [server, port] = hostPort.split(':')
        return { protocol: 'VLESS', name, uuid, server, port }
      } catch {
        return null
      }
    }
    if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('socks5://')) {
      try {
        const u = new URL(url)
        return {
          protocol: u.protocol.replace(':', '').toUpperCase(),
          name: u.hash ? decodeURIComponent(u.hash.slice(1)) : '',
          server: u.hostname,
          port: u.port || (u.protocol === 'https:' ? '443' : '80'),
        }
      } catch {
        return null
      }
    }
    return null
  })

  watch(
    () => addForm.value.raw_url,
    (val) => {
      const trimmed = (val || '').trim()
      if (trimmed.includes('#') && !addForm.value.name) {
        try {
          const hashPart = trimmed.split('#')[1]
          if (hashPart) {
            addForm.value.name = decodeURIComponent(hashPart)
          }
        } catch {
          /* ignore */
        }
      }
    }
  )

  async function handleSaveNode(): Promise<void> {
    const raw = addForm.value.raw_url.trim()
    if (!raw) {
      ElMessage.warning('请输入节点链接或代理地址')
      return
    }

    adding.value = true
    try {
      const res = await api.addProxyNode({
        raw_url: raw,
        name: addForm.value.name.trim(),
        local_port: addForm.value.local_port || 10809,
      })
      ElMessage.success(`节点「${res.name}」已保存！内置 Xray 引擎已自动接管中转，导入即可直接使用！`)
      isAddDialogVisible.value = false
      await load()
    } catch (err) {
      ElMessage.error(describeError(err))
    } finally {
      adding.value = false
    }
  }

  // ------------------------------------------------------------------ 删除节点
  async function handleDeleteNode(node: ProxyNodeItem): Promise<void> {
    try {
      await ElMessageBox.confirm(
        `确定删除代理节点「${node.name}」吗？已绑定该节点的采集器将自动恢复为直连状态。`,
        '删除节点',
        { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
      )
      await api.deleteProxyNode(node.id)
      ElMessage.success('节点已删除')
      await load()
    } catch (err) {
      if (err !== 'cancel') {
        ElMessage.error(describeError(err))
      }
    }
  }

  // ------------------------------------------------------------------ 导出 Xray 配置弹窗（备用）
  const isXrayDialogVisible = ref(false)
  const xrayConfigJson = ref('')
  const currentExportNode = ref<ProxyNodeItem | null>(null)
  const xrayPort = ref(10809)
  const exporting = ref(false)

  async function openXrayDialog(node: ProxyNodeItem): Promise<void> {
    currentExportNode.value = node
    xrayPort.value = node.local_port || 10809
    isXrayDialogVisible.value = true
    await fetchXrayConfig()
  }

  async function fetchXrayConfig(): Promise<void> {
    if (!currentExportNode.value) return
    exporting.value = true
    try {
      const res = await api.exportNodeXray(currentExportNode.value.id, xrayPort.value, xrayPort.value - 1)
      xrayConfigJson.value = JSON.stringify(res, null, 2)
    } catch (err) {
      ElMessage.error(describeError(err))
    } finally {
      exporting.value = false
    }
  }

  async function copyXrayConfig(): Promise<void> {
    try {
      await navigator.clipboard.writeText(xrayConfigJson.value)
      ElMessage.success('Xray config.json 配置已成功复制到剪贴板！')
    } catch {
      ElMessage.info('复制失败，请手动全选复制')
    }
  }

  return {
    loading,
    nodesData,
    sites,
    engineStatus,
    engineActionLoading,
    testStates,
    nodes,
    bindings,
    totalNodes,
    vlessNodes,
    totalBindings,
    load,
    getBoundSites,
    getAvailableSitesForNode,
    handleInstallEngine,
    handleStartEngine,
    handleStopEngine,
    handleRestartEngine,
    handleUnbindSite,
    isBindDialogVisible,
    currentBindTargetNode,
    selectedSiteKeyToBind,
    bindSaving,
    openBindDialog,
    handleConfirmBind,
    handleInlineBind,
    handleTestNode,
    handleTestAllNodes,
    isAddDialogVisible,
    addMode,
    addForm,
    adding,
    openAddDialog,
    parsedPreview,
    handleSaveNode,
    handleDeleteNode,
    isXrayDialogVisible,
    xrayConfigJson,
    currentExportNode,
    xrayPort,
    exporting,
    openXrayDialog,
    fetchXrayConfig,
    copyXrayConfig,
  }
}
