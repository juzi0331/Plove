<script setup lang="ts">
/**
 * 站点管理（内容源）—— 全功能高级运维中心
 * 架构重构：按模块与单一职责拆分为独立组件与 composable 体系
 */

import { Connection, Refresh, Upload } from '@element-plus/icons-vue'
import { ElButton, ElSkeleton } from 'element-plus'
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import EmptyState from '../../components/EmptyState.vue'
import ErrorState from '../../components/ErrorState.vue'
import PageHeader from '../../components/PageHeader.vue'
import type { AdminSiteItem } from '@/api/types'
import { adminPath } from '../../config'
import SiteCards from './SiteCards.vue'
import SiteCrawlerUpload from './SiteCrawlerUpload.vue'
import SiteDetailModal from './SiteDetailModal.vue'
import { useCrawlerCode } from './useCrawlerCode'
import { useSiteAdvanced } from './useSiteAdvanced'
import { useSiteCategories } from './useSiteCategories'
import { useSiteDetailPolicy } from './useSiteDetailPolicy'
import { useSiteList } from './useSiteList'

const router = useRouter()

// 1. 站点列表与健康状态
const {
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
} = useSiteList()

// 2. 上传弹窗状态
const isUploadVisible = ref(false)

// 3. 源码查看
const {
  currentCode,
  currentCodeMtime,
  loadingCode,
  openCodeViewer,
} = useCrawlerCode()

// 4. 单站高级设置与缓存 TTL
const {
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
} = useSiteAdvanced(proxyNodes, getNodeById, load)

// 5. 分类与子分类规则
const {
  categoryLoading,
  categorySaving,
  categoryPayload,
  getSubInput,
  formatCategoryPreview,
  toggleSubCategoryHidden,
  openCategoryDrawer,
  addSubCategory,
  removeSubCategory,
  saveCategoryRules,
} = useSiteCategories()

// 6. 详情页展示与广告清洗策略
const {
  detailPolicyLoading,
  detailPolicySaving,
  detailPolicy,
  adPatternInput,
  newLineOrig,
  newLineAlias,
  openDetailPolicy,
  addAdPattern,
  removeAdPattern,
  addLineOverride,
  removeLineOverride,
  saveDetailPolicy,
} = useSiteDetailPolicy()

// 7. 统一卡片弹出式站点详细设置中心
const isDetailModalVisible = ref(false)
const selectedSite = ref<AdminSiteItem | null>(null)
const modalInitialTab = ref('basic')

function openSiteDetailModal(site: AdminSiteItem, tab = 'basic'): void {
  selectedSite.value = site
  modalInitialTab.value = tab
  isDetailModalVisible.value = true
  void openAdvanced(site)
  void openCategoryDrawer(site)
  void openDetailPolicy(site)
  void openCodeViewer(site)
}

async function handleModalDelete(): Promise<void> {
  if (!selectedSite.value) return
  isDetailModalVisible.value = false
  await deleteSite(selectedSite.value)
}

function handleModalMove(delta: number): void {
  if (!selectedSite.value) return
  const idx = sites.value.findIndex((s) => s.key === selectedSite.value?.key)
  if (idx !== -1) {
    move(idx, delta)
  }
}

function handleModalToggleEnabled(next: boolean): void {
  if (!selectedSite.value) return
  toggle(selectedSite.value, next)
  selectedSite.value.enabled = next
}

async function handleCrawlerUploaded(): Promise<void> {
  await load()
  if (selectedSite.value) {
    await openCodeViewer(selectedSite.value)
  }
}
</script>

<template>
  <div class="a-page">
    <PageHeader
      title="站点管理与控制中枢"
      desc="全功能控制：点击任意采集器卡片即可弹出详细设置（参数、代理节点、分类标签、广告过滤与源码浏览）。"
    >
      <template #actions>
        <ElButton :icon="Connection" @click="router.push(adminPath('/proxy-nodes'))">
          代理节点池 ({{ proxyNodes.length }})
        </ElButton>
        <ElButton type="primary" :icon="Upload" @click="isUploadVisible = true">
          上传采集器
        </ElButton>
        <ElButton :icon="Refresh" :loading="loading" @click="load">
          刷新
        </ElButton>
      </template>
    </PageHeader>

    <ErrorState v-if="error" :message="error" @retry="load" />

    <div v-if="loading && !data" class="a-card skeleton">
      <ElSkeleton :rows="5" animated />
    </div>

    <EmptyState
      v-else-if="isEmpty"
      title="当前系统未部署任何采集器"
      hint="点击右上角「上传采集器」立即部署一个新的 Python 采集器脚本。"
    />

    <SiteCards
      v-else
      :sites="sites"
      :busy-key="busyKey"
      :first-key="firstKey"
      :last-key="lastKey"
      :get-proxy-tooltip="getProxyTooltip"
      :get-bound-node-badge-text="getBoundNodeBadgeText"
      :health-state="healthState"
      @toggle-proxy="toggleSiteProxy"
      @toggle-enabled="toggle"
      @move="move"
      @open-detail="openSiteDetailModal"
      @open-advanced="openAdvanced"
      @open-category="openCategoryDrawer"
      @open-detail-policy="openDetailPolicy"
      @view-code="openCodeViewer"
      @delete-site="deleteSite"
    />

    <!-- 弹窗 1：上传采集器 -->
    <SiteCrawlerUpload
      v-model="isUploadVisible"
      @uploaded="load"
    />

    <!-- 统一弹出卡片：单站详细设置中心（点击卡片即打开，告别页面臃肿按钮！） -->
    <SiteDetailModal
      v-model="isDetailModalVisible"
      :site="selectedSite"
      :initial-tab="modalInitialTab"
      :current-advanced="currentAdvanced"
      :current-cache-policy="currentCachePolicy"
      :proxy-nodes="proxyNodes"
      :selected-proxy-choice="selectedProxyChoice"
      :selected-node="selectedNode"
      :advanced-loading="advancedLoading"
      :advanced-saving="advancedSaving"
      :testing-node="testingNode"
      :format-node-label="formatNodeLabel"
      :category-payload="categoryPayload"
      :category-loading="categoryLoading"
      :category-saving="categorySaving"
      :get-sub-input="getSubInput"
      :format-category-preview="formatCategoryPreview"
      :toggle-sub-category-hidden="toggleSubCategoryHidden"
      :add-sub-category="addSubCategory"
      :remove-sub-category="removeSubCategory"
      :detail-policy="detailPolicy"
      :detail-policy-loading="detailPolicyLoading"
      :detail-policy-saving="detailPolicySaving"
      :ad-pattern-input="adPatternInput"
      :new-line-orig="newLineOrig"
      :new-line-alias="newLineAlias"
      :code="currentCode"
      :mtime="currentCodeMtime"
      :loading-code="loadingCode"
      :is-first="selectedSite?.key === firstKey"
      :is-last="selectedSite?.key === lastKey"
      @update:ad-pattern-input="(val) => (adPatternInput = val)"
      @update:new-line-orig="(val) => (newLineOrig = val)"
      @update:new-line-alias="(val) => (newLineAlias = val)"
      @proxy-choice-change="onProxyChoiceChange"
      @test-node="testCurrentNode"
      @save-advanced="saveAdvanced"
      @save-category="saveCategoryRules"
      @add-ad-pattern="addAdPattern"
      @remove-ad-pattern="removeAdPattern"
      @add-line-override="addLineOverride"
      @remove-line-override="removeLineOverride"
      @save-detail-policy="saveDetailPolicy"
      @move="handleModalMove"
      @delete-site="handleModalDelete"
      @toggle-enabled="handleModalToggleEnabled"
      @crawler-uploaded="handleCrawlerUploaded"
    />
  </div>
</template>

<style>
@import './sites-view.css';
</style>
