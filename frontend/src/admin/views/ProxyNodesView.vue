<script setup lang="ts">
/**
 * 网络代理节点池管理中心 (Proxy Nodes Center) & 内置 Xray 引擎管理
 *
 * 功能：
 * 1. 集中管理多个 VLESS / HTTP / SOCKS5 代理节点；
 * 2. 内置 Xray-core 核心引擎，自动接管 VLESS 节点在本地开放独立端口中转，开箱即用；
 * 3. 快速解析并校验 vless:// 协议链接（支持 Reality、TLS、WS、gRPC 等）；
 * 4. 实时节点连通性测速与延迟反馈；
 * 5. 采集器适配器与代理节点一对一指派与解绑；
 * 6. 可选备用：导出标准 Xray-core client config.json（用于外部设备或备用排查）。
 */
import {
  Connection,
  CopyDocument,
  Cpu,
  Delete,
  Download,
  Lightning,
  Plus,
  Refresh,
  RefreshRight,
  VideoPause,
  VideoPlay,
} from '@element-plus/icons-vue'
import {
  ElButton,
  ElCard,
  ElCol,
  ElDialog,
  ElDivider,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElRow,
  ElSelect,
  ElSkeleton,
  ElTabPane,
  ElTabs,
  ElTag,
} from 'element-plus'
import { computed, onMounted, ref } from 'vue'

import { describeError } from '@/api/http'
import type {
  AdminSiteItem,
  ProxyEngineStatusPayload,
  ProxyNodeItem,
  ProxyNodeListPayload,
  ProxyTestResult,
} from '@/api/types'

import * as api from '../api'
import PageHeader from '../components/PageHeader.vue'

async function copyText(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动选择复制')
  }
}

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
    ElMessage.success('内置 Xray 引擎已成功启动')
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
    ElMessage.info('内置 Xray 引擎已停止')
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
    ElMessage.success('内置 Xray 引擎已重新加载配置并重启')
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

// 快速解析预览
const parsedPreview = computed(() => {
  const url = addForm.value.raw_url.trim()
  if (!url.startsWith('vless://')) return null
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
    return { name, uuid, server, port }
  } catch {
    return null
  }
})

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
</script>

<template>
  <div class="a-page proxy-page">
    <PageHeader
      title="网络代理节点池 & 内置 Xray 核心引擎"
      desc="内置 Xray-core 独立内核，导入 vless:// 节点后全自动在本地开放端口托管中转，直接开箱即用；无需繁琐导出或手动配置。"
    >
      <template #actions>
        <ElButton type="primary" :icon="Plus" @click="openAddDialog">
          添加代理节点
        </ElButton>
        <ElButton :icon="Lightning" @click="handleTestAllNodes">
          全节点并发测速
        </ElButton>
        <ElButton :icon="Refresh" :loading="loading" @click="load">
          刷新
        </ElButton>
      </template>
    </PageHeader>

    <!-- ========================================================== 内置 Xray 引擎实时看板 -->
    <div class="engine-banner" :class="{ 'engine-banner--running': engineStatus?.running, 'engine-banner--stopped': engineStatus && !engineStatus.running && engineStatus.installed, 'engine-banner--uninstalled': engineStatus && !engineStatus.installed }">
      <div class="engine-banner-left">
        <div class="engine-icon-box">
          <ElIcon :size="24"><Cpu /></ElIcon>
        </div>
        <div class="engine-meta">
          <div class="engine-title-row">
            <span class="engine-title">内置 Xray-core 转发守护引擎</span>
            <ElTag
              v-if="engineStatus?.running"
              size="small"
              type="success"
              effect="dark"
              class="engine-badge"
            >
              🟢 运行中 (PID {{ engineStatus.pid }})
            </ElTag>
            <ElTag
              v-else-if="engineStatus?.installed"
              size="small"
              type="info"
              effect="plain"
              class="engine-badge"
            >
              ⚪ 已就绪 (未运行)
            </ElTag>
            <ElTag
              v-else
              size="small"
              type="warning"
              effect="dark"
              class="engine-badge"
            >
              🟡 未安装内核
            </ElTag>

            <span v-if="engineStatus?.version" class="engine-version a-muted">
              版本: {{ engineStatus.version }}
            </span>
          </div>

          <div class="engine-desc">
            <template v-if="engineStatus?.running">
              ✨ <strong>直接可用保障</strong>：内置 Xray 引擎已自动开启并在本地监听端口
              <code>{{ engineStatus.managed_ports.length > 0 ? engineStatus.managed_ports.join(', ') : '10809' }}</code>，所有导入的 VLESS 节点免配置即可直接被采集器使用！
            </template>
            <template v-else-if="engineStatus?.installed">
              💡 Xray 核心引擎已在服务器就绪。导入 VLESS 节点或点击右侧「启动引擎」，系统将自动接管多端口代理转发。
            </template>
            <template v-else>
              ⚠️ 当前服务器尚未检测到 Xray 独立内核。点击右侧<strong>「一键安装 Xray 核心」</strong>，系统将全自动下载适配内核，让您导入的 VLESS 节点无需任何手动配置直接生效！
            </template>
          </div>
        </div>
      </div>

      <div class="engine-banner-right">
        <!-- 未安装时提供一键安装 -->
        <ElButton
          v-if="engineStatus && !engineStatus.installed"
          type="primary"
          :icon="Lightning"
          :loading="engineActionLoading"
          @click="handleInstallEngine"
        >
          ⚡ 一键安装 Xray 核心
        </ElButton>

        <!-- 已安装但未运行时提供启动 -->
        <ElButton
          v-else-if="engineStatus && !engineStatus.running"
          type="success"
          :icon="VideoPlay"
          :loading="engineActionLoading"
          @click="handleStartEngine"
        >
          启动 Xray 引擎
        </ElButton>

        <!-- 运行中提供重启和停止 -->
        <template v-else-if="engineStatus?.running">
          <ElButton
            size="small"
            :icon="RefreshRight"
            :loading="engineActionLoading"
            @click="handleRestartEngine"
          >
            重启/热重载
          </ElButton>
          <ElButton
            size="small"
            type="danger"
            plain
            :icon="VideoPause"
            :loading="engineActionLoading"
            @click="handleStopEngine"
          >
            停止
          </ElButton>
        </template>
      </div>
    </div>

    <!-- 顶部概览仪表盘 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-val">{{ totalNodes }}</div>
        <div class="stat-label">已配置节点数</div>
      </div>
      <div class="stat-card">
        <div class="stat-val stat-val--vless">{{ vlessNodes }}</div>
        <div class="stat-label">VLESS 节点 (内置直接转发)</div>
      </div>
      <div class="stat-card">
        <div class="stat-val stat-val--bound">{{ totalBindings }}</div>
        <div class="stat-label">已绑定采集器数</div>
      </div>
      <div class="stat-card">
        <div class="stat-val stat-val--ready">
          {{ engineStatus?.running ? '🟢 托管生效中' : (engineStatus?.installed ? '⚪ 已就绪' : '🟡 待安装') }}
        </div>
        <div class="stat-label">内置 Xray 状态</div>
      </div>
    </div>

    <!-- 骨架屏 -->
    <div v-if="loading && nodes.length === 0" class="a-card skeleton">
      <ElSkeleton :rows="6" animated />
    </div>

    <!-- 空状态 -->
    <div v-else-if="nodes.length === 0" class="empty-box">
      <ElEmpty description="暂无代理节点，点击上方「添加代理节点」直接粘贴 vless:// 链接或本地代理地址" />
    </div>

    <!-- 节点网格卡片 -->
    <div v-else class="nodes-grid">
      <ElCard
        v-for="node in nodes"
        :key="node.id"
        shadow="hover"
        class="node-card"
        :class="{ 'node-card--vless': node.protocol === 'vless' }"
      >
        <!-- 节点头部 -->
        <div class="node-header">
          <div class="node-title-box">
            <ElTag
              size="small"
              :type="node.protocol === 'vless' ? 'success' : 'warning'"
              effect="dark"
              class="proto-tag"
            >
              {{ node.protocol.toUpperCase() }}
            </ElTag>
            <span class="node-name" :title="node.name">{{ node.name }}</span>
            <ElTag v-if="node.security && node.security !== 'none'" size="small" type="info" effect="plain">
              {{ node.security }}
            </ElTag>
          </div>

          <!-- 测速结果显示 -->
          <div class="node-status-indicator">
            <span v-if="testStates[node.id]?.loading" class="status-loading a-muted">
              测速中...
            </span>
            <span
              v-else-if="testStates[node.id]?.result?.ok"
              class="status-badge status-badge--ok"
            >
              🟢 {{ testStates[node.id]?.result?.duration_ms }}ms
            </span>
            <span
              v-else-if="testStates[node.id]?.result"
              class="status-badge status-badge--fail"
              :title="testStates[node.id]?.result?.message"
            >
              🔴 连接失败
            </span>
          </div>
        </div>

        <!-- 节点核心参数 -->
        <div class="node-details">
          <div class="detail-row">
            <span class="detail-label">远端服务器：</span>
            <code class="detail-val">{{ node.server ? `${node.server}:${node.port}` : '本地监听' }}</code>
          </div>

          <div class="detail-row">
            <span class="detail-label">爬虫本地中转：</span>
            <code class="detail-val copyable" title="点击复制" @click="copyText(node.proxy_url)">
              {{ node.proxy_url }}
            </code>
            <ElTag v-if="node.protocol === 'vless'" size="small" type="success" effect="light" style="margin-left: 4px">
              内置 Xray 直达
            </ElTag>
          </div>

          <div v-if="node.network_type" class="detail-row">
            <span class="detail-label">传输协议：</span>
            <span class="detail-val">{{ node.network_type }}</span>
          </div>

          <!-- 绑定的采集器 (修复直连仍显示使用的 Bug，并支持一键解绑与指派) -->
          <div class="detail-row bound-row">
            <span class="detail-label">正在使用此节点的适配器：</span>
            <div class="bound-tags">
              <template v-if="getBoundSites(node.id).length > 0">
                <ElTag
                  v-for="s in getBoundSites(node.id)"
                  :key="s.key"
                  size="small"
                  type="success"
                  effect="light"
                  closable
                  class="bound-tag"
                  title="点击 × 切换为直连模式"
                  @close="handleUnbindSite(s.key, s.name)"
                >
                  {{ s.name }} ({{ s.key }})
                </ElTag>
              </template>
              <span v-else class="a-muted no-bound-hint">暂无适配器使用 (直连保护中)</span>

              <ElButton
                size="small"
                link
                type="primary"
                :icon="Plus"
                style="font-size: 11.5px; padding: 0 4px; margin-left: 4px;"
                @click="openBindDialog(node)"
              >
                指派采集器
              </ElButton>
            </div>
          </div>
        </div>

        <ElDivider style="margin: 12px 0 10px 0" />

        <!-- 操作栏 -->
        <div class="node-actions">
          <ElButton
            size="small"
            type="primary"
            :loading="testStates[node.id]?.loading"
            :icon="Lightning"
            @click="handleTestNode(node)"
          >
            连通性测速
          </ElButton>

          <!-- 导出作为备用工具，不再强求用户手动运行 -->
          <ElButton
            v-if="node.protocol === 'vless'"
            size="small"
            plain
            :icon="Download"
            title="备用：如果需要在外部或其它设备独立运行 Xray，可在此导出 config.json"
            @click="openXrayDialog(node)"
          >
            导出备用配置
          </ElButton>

          <div style="flex: 1" />

          <ElButton
            size="small"
            link
            type="danger"
            :icon="Delete"
            @click="handleDeleteNode(node)"
          >
            删除
          </ElButton>
        </div>
      </ElCard>
    </div>

    <!-- 底部使用说明卡片 -->
    <div class="guide-box">
      <div class="guide-title">
        <ElIcon style="margin-right: 6px;"><Connection /></ElIcon>
        <strong>内置 Xray 核心运行机制与节点指派说明</strong>
      </div>
      <div class="guide-content">
        <p>1. <strong>免配置导入直接用</strong>：直接粘贴 <code>vless://...</code> 节点字符串，系统由<strong>内置 Xray 核心引擎</strong>在本地自动分配独立端口（如 10809、10810）实现直接中转，无需任何手动导出或外部终端执行！</p>
        <p>2. <strong>采集器单站独立绑定</strong>：在卡片上的<strong>「指派采集器」</strong>或进入<strong>「内容源管理 ➔ 高级设置」</strong>中选择对应节点即可绑定；选择“直连源站”的采集器绝不走代理，单站绝对隔离！</p>
        <p>3. <strong>一键测速检验</strong>：点击卡片上的「连通性测速」，系统将通过内置 Xray 引擎向国际网络发起真实 HTTP 探针并实时反馈连通延迟。</p>
      </div>
    </div>

    <!-- ========================================================== 弹窗 1：添加节点 -->
    <ElDialog
      v-model="isAddDialogVisible"
      title="添加代理节点"
      width="640px"
      align-center
      destroy-on-close
    >
      <ElTabs v-model="addMode">
        <ElTabPane label="VLESS 链接导入 (内置 Xray 直接驱动)" name="vless">
          <div style="background: var(--el-fill-color-light); border-radius: 8px; padding: 10px 14px; margin-bottom: 14px; font-size: 12.5px; color: var(--el-text-color-regular);">
            🚀 <strong>开箱即用说明</strong>：系统内置 Xray 核心引擎。添加后，系统将自动在本地开放独立 HTTP 端口为您托管中转，无需再手动导出配置！
          </div>

          <ElForm label-position="top">
            <ElFormItem label="VLESS 节点连接串 (以 vless:// 开头)" required>
              <ElInput
                v-model="addForm.raw_url"
                type="textarea"
                :rows="4"
                placeholder="vless://uuid@server:port?type=tcp&security=reality&pbk=...#香港高速节点"
              />
            </ElFormItem>

            <!-- 动态解析预览 -->
            <div v-if="parsedPreview" class="preview-box">
              <div class="preview-title">✨ 已识别节点参数：</div>
              <div class="preview-items">
                <div><strong>备注：</strong>{{ parsedPreview.name || '默认' }}</div>
                <div><strong>服务器：</strong>{{ parsedPreview.server }}:{{ parsedPreview.port }}</div>
                <div><strong>UUID：</strong>{{ parsedPreview.uuid }}</div>
              </div>
            </div>

            <ElRow :gutter="16">
              <ElCol :span="14">
                <ElFormItem label="自定义节点备注名称（选填，留空自动提取 # 备注）">
                  <ElInput v-model="addForm.name" placeholder="如：自建香港高速专线" />
                </ElFormItem>
              </ElCol>
              <ElCol :span="10">
                <ElFormItem label="内置 Xray 托管端口">
                  <ElInputNumber v-model="addForm.local_port" :min="1024" :max="65535" style="width: 100%" />
                </ElFormItem>
              </ElCol>
            </ElRow>
          </ElForm>
        </ElTabPane>

        <ElTabPane label="常规 HTTP / SOCKS5 代理" name="http">
          <ElForm label-position="top">
            <ElFormItem label="代理服务器完整 URL" required>
              <ElInput
                v-model="addForm.raw_url"
                placeholder="如 http://192.168.31.5:10809 或 http://127.0.0.1:7890"
              />
            </ElFormItem>

            <ElFormItem label="节点备注名称">
              <ElInput v-model="addForm.name" placeholder="如：本地 Clash 代理" />
            </ElFormItem>
          </ElForm>
        </ElTabPane>
      </ElTabs>

      <template #footer>
        <ElButton @click="isAddDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="adding" @click="handleSaveNode">
          确认添加并启动
        </ElButton>
      </template>
    </ElDialog>

    <!-- ========================================================== 弹窗 2：导出 Xray 配置 (备用) -->
    <ElDialog
      v-model="isXrayDialogVisible"
      :title="`Xray-core 配置文件 (备用) · ${currentExportNode?.name}`"
      width="680px"
      align-center
    >
      <div v-loading="exporting">
        <div class="xray-desc">
          💡 系统默认已通过<strong>内置 Xray 引擎</strong>在本机自动托管运行此节点。此配置生成器仅供您备份或在外部独立机器上执行：
        </div>

        <div class="xray-port-bar">
          <span class="port-label">修改本地 HTTP 映射端口：</span>
          <ElInputNumber
            v-model="xrayPort"
            :min="1024"
            :max="65535"
            size="small"
            @change="fetchXrayConfig"
          />
        </div>

        <div class="code-wrapper">
          <pre class="json-code"><code>{{ xrayConfigJson }}</code></pre>
        </div>
      </div>

      <template #footer>
        <ElButton :icon="CopyDocument" type="primary" @click="copyXrayConfig">
          一键复制 config.json
        </ElButton>
        <ElButton @click="isXrayDialogVisible = false">关闭</ElButton>
      </template>
    </ElDialog>

    <!-- ========================================================== 弹窗 3：指派采集器到此节点 -->
    <ElDialog
      v-model="isBindDialogVisible"
      :title="`指派采集器到「${currentBindTargetNode?.name}」`"
      width="480px"
      align-center
    >
      <div style="margin-bottom: 14px; font-size: 13.5px; color: var(--el-text-color-primary);">
        选择要将网络请求通道指派给此节点的采集器适配器：
      </div>
      <ElSelect
        v-model="selectedSiteKeyToBind"
        placeholder="请选择要绑定的采集器"
        style="width: 100%"
        filterable
      >
        <ElOption
          v-for="s in sites"
          :key="s.key"
          :label="`${s.name} (${s.key})`"
          :value="s.key"
        >
          <div style="display: flex; justify-content: space-between; align-items: center">
            <span>{{ s.name }} ({{ s.key }})</span>
            <ElTag v-if="s.proxy_enabled && s.proxy_node_id === currentBindTargetNode?.id" size="small" type="success">
              当前已绑定
            </ElTag>
            <ElTag v-else-if="!s.proxy_enabled" size="small" type="info">
              当前直连
            </ElTag>
          </div>
        </ElOption>
      </ElSelect>

      <template #footer>
        <ElButton @click="isBindDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="bindSaving" @click="handleConfirmBind">
          确认绑定指派
        </ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.proxy-page {
  padding-bottom: 40px;
}

/* 内置 Xray 引擎看板 */
.engine-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  background: var(--el-fill-color-blank);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  padding: 16px 20px;
  margin-bottom: 20px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04);
  transition: all 0.25s ease;
}

.engine-banner--running {
  border-left: 4px solid var(--el-color-success);
  background: linear-gradient(to right, rgba(16, 185, 129, 0.04), transparent);
}

.engine-banner--stopped {
  border-left: 4px solid #94a3b8;
}

.engine-banner--uninstalled {
  border-left: 4px solid var(--el-color-warning);
  background: linear-gradient(to right, rgba(234, 179, 8, 0.04), transparent);
}

.engine-banner-left {
  display: flex;
  align-items: center;
  gap: 14px;
  flex: 1;
  min-width: 280px;
}

.engine-icon-box {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  background: var(--el-fill-color-light);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--el-color-primary);
  flex-shrink: 0;
}

.engine-banner--running .engine-icon-box {
  color: var(--el-color-success);
  background: rgba(16, 185, 129, 0.12);
}

.engine-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.engine-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.engine-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.engine-version {
  font-size: 12px;
  margin-left: 4px;
}

.engine-desc {
  font-size: 12.5px;
  color: var(--el-text-color-regular);
  line-height: 1.5;
}

.engine-desc code {
  background: var(--el-fill-color-light);
  padding: 1px 6px;
  border-radius: 4px;
  color: var(--el-color-primary);
  font-family: ui-monospace, monospace;
}

.engine-banner-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 统计卡片 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  background: var(--el-fill-color-blank);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  padding: 16px 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.stat-val {
  font-size: 26px;
  font-weight: 800;
  color: var(--el-text-color-primary);
  line-height: 1.2;
}

.stat-val--vless {
  color: var(--el-color-success);
}

.stat-val--bound {
  color: var(--el-color-primary);
}

.stat-val--ready {
  color: #6366f1;
}

.stat-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-top: 6px;
}

/* 节点网格卡片 */
.nodes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 18px;
}

.node-card {
  border-radius: 12px;
  transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
  background: var(--el-fill-color-blank);
}

.node-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
}

.node-card--vless {
  border-top: 3px solid var(--el-color-success);
}

.node-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.node-title-box {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  overflow: hidden;
}

.proto-tag {
  font-weight: 700;
  letter-spacing: 0.5px;
}

.node-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.node-details {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;
}

.detail-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.detail-label {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  flex-shrink: 0;
}

.detail-val {
  font-family: ui-monospace, SFMono-Regular, monospace;
  font-size: 12px;
  color: var(--el-text-color-primary);
}

.detail-val.copyable {
  cursor: pointer;
  background: var(--el-fill-color-light);
  padding: 1px 6px;
  border-radius: 4px;
}

.detail-val.copyable:hover {
  color: var(--el-color-primary);
}

.bound-row {
  align-items: flex-start;
  margin-top: 4px;
}

.bound-tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.bound-tag {
  font-size: 11px;
}

.no-bound-hint {
  font-size: 11.5px;
}

.node-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-badge--ok {
  font-size: 12px;
  font-weight: 700;
  color: var(--el-color-success);
}

.status-badge--fail {
  font-size: 12px;
  font-weight: 700;
  color: var(--el-color-danger);
}

.guide-box {
  margin-top: 36px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  padding: 20px 24px;
}

.guide-title {
  display: flex;
  align-items: center;
  font-size: 15px;
  color: var(--el-text-color-primary);
  margin-bottom: 12px;
}

.guide-content p {
  margin: 6px 0;
  font-size: 13px;
  color: var(--el-text-color-regular);
  line-height: 1.6;
}

.guide-content code {
  background: var(--el-fill-color-blank);
  padding: 1px 6px;
  border-radius: 4px;
  font-family: ui-monospace, SFMono-Regular, monospace;
  color: var(--el-color-primary);
}

.preview-box {
  background: var(--el-color-success-light-9);
  border: 1px solid var(--el-color-success-light-5);
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 16px;
}

.preview-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--el-color-success);
  margin-bottom: 4px;
}

.preview-items {
  font-size: 12px;
  color: var(--el-text-color-primary);
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-family: ui-monospace, monospace;
}

.xray-desc {
  font-size: 13px;
  color: var(--el-text-color-regular);
  line-height: 1.6;
  margin-bottom: 14px;
}

.xray-port-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.port-label {
  font-size: 13px;
}

.code-wrapper {
  max-height: 380px;
  overflow-y: auto;
  border-radius: 8px;
  background: #1e1e2e;
}

.json-code {
  margin: 0;
  padding: 14px 18px;
  color: #cdd6f4;
  font-family: ui-monospace, SFMono-Regular, monospace;
  font-size: 12px;
  line-height: 1.5;
}
</style>
