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
  Lightning,
  Plus,
  Refresh,
} from '@element-plus/icons-vue'
import {
  ElButton,
  ElEmpty,
  ElIcon,
  ElMessage,
  ElSkeleton,
} from 'element-plus'

import PageHeader from '../components/PageHeader.vue'
import { useProxyNodes } from './proxy-nodes/useProxyNodes'
import EngineBanner from './proxy-nodes/EngineBanner.vue'
import NodeCard from './proxy-nodes/NodeCard.vue'
import AddNodeDialog from './proxy-nodes/AddNodeDialog.vue'
import ExportXrayDialog from './proxy-nodes/ExportXrayDialog.vue'
import BindSiteDialog from './proxy-nodes/BindSiteDialog.vue'

const {
  loading,
  sites,
  engineStatus,
  engineActionLoading,
  testStates,
  nodes,
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
} = useProxyNodes()

async function copyText(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动选择复制')
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

    <!-- 内置 Xray 引擎实时看板 -->
    <EngineBanner
      :engine-status="engineStatus"
      :engine-action-loading="engineActionLoading"
      @install="handleInstallEngine"
      @start="handleStartEngine"
      @stop="handleStopEngine"
      @restart="handleRestartEngine"
    />

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
          {{ engineStatus?.running ? '托管生效中' : (engineStatus?.installed ? '已就绪' : '待安装') }}
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
      <NodeCard
        v-for="node in nodes"
        :key="node.id"
        :node="node"
        :bound-sites="getBoundSites(node.id)"
        :available-sites="getAvailableSitesForNode(node.id)"
        :test-state="testStates[node.id]"
        @copy-text="copyText"
        @unbind-site="handleUnbindSite"
        @inline-bind="handleInlineBind"
        @open-bind-dialog="openBindDialog"
        @test-node="handleTestNode"
        @open-xray-dialog="openXrayDialog"
        @delete-node="handleDeleteNode"
      />
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

    <!-- 弹窗 1：添加节点 -->
    <AddNodeDialog
      v-model="isAddDialogVisible"
      v-model:add-mode="addMode"
      :add-form="addForm"
      :adding="adding"
      :parsed-preview="parsedPreview"
      @save="handleSaveNode"
    />

    <!-- 弹窗 2：导出 Xray 配置 (备用) -->
    <ExportXrayDialog
      v-model="isXrayDialogVisible"
      v-model:xray-port="xrayPort"
      :current-export-node="currentExportNode"
      :xray-config-json="xrayConfigJson"
      :exporting="exporting"
      @fetch-config="fetchXrayConfig"
      @copy="copyXrayConfig"
    />

    <!-- 弹窗 3：指派采集器到此节点 -->
    <BindSiteDialog
      v-model="isBindDialogVisible"
      v-model:selected-site-key-to-bind="selectedSiteKeyToBind"
      :current-bind-target-node="currentBindTargetNode"
      :sites="sites"
      :bind-saving="bindSaving"
      @confirm="handleConfirmBind"
    />
  </div>
</template>

<style>
@import './proxy-nodes/proxy-nodes.css';
</style>
