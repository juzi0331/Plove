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
import { adminPath } from '../../config'
import SiteAdvancedSettings from './SiteAdvancedSettings.vue'
import SiteCards from './SiteCards.vue'
import SiteCategoryRules from './SiteCategoryRules.vue'
import SiteCrawlerCode from './SiteCrawlerCode.vue'
import SiteCrawlerUpload from './SiteCrawlerUpload.vue'
import SiteDetailPolicy from './SiteDetailPolicy.vue'
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
  isCodeViewerVisible,
  currentCodeKey,
  currentCode,
  currentCodeMtime,
  loadingCode,
  openCodeViewer,
} = useCrawlerCode()

// 4. 单站高级设置与缓存 TTL
const {
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
} = useSiteAdvanced(proxyNodes, getNodeById, load)

// 5. 分类与子分类规则
const {
  isCategoryDrawerVisible,
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
  isDetailPolicyVisible,
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
</script>

<template>
  <div class="a-page">
    <PageHeader
      title="站点管理与控制中枢"
      desc="全功能控制：采集器脚本上传与热插拔、单站别名/角标/超时、分类与子分类控制、详情页广告清洗与线路别名映射。"
    >
      <template #actions>
        <ElButton :icon="Connection" @click="router.push(adminPath('/proxy-nodes'))">
          🌐 代理节点池 ({{ proxyNodes.length }})
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

    <!-- 抽屉 2：源码查看 -->
    <SiteCrawlerCode
      v-model="isCodeViewerVisible"
      :site-key="currentCodeKey"
      :code="currentCode"
      :mtime="currentCodeMtime"
      :loading="loadingCode"
    />

    <!-- 弹窗 3：单站高级设置 -->
    <SiteAdvancedSettings
      v-model="isAdvancedVisible"
      :current-advanced="currentAdvanced"
      :current-cache-policy="currentCachePolicy"
      :proxy-nodes="proxyNodes"
      :selected-proxy-choice="selectedProxyChoice"
      :selected-node="selectedNode"
      :advanced-loading="advancedLoading"
      :advanced-saving="advancedSaving"
      :testing-node="testingNode"
      :format-node-label="formatNodeLabel"
      @proxy-choice-change="onProxyChoiceChange"
      @test-node="testCurrentNode"
      @save="saveAdvanced"
    />

    <!-- 抽屉 4：分类与子分类规则 -->
    <SiteCategoryRules
      v-model="isCategoryDrawerVisible"
      :category-payload="categoryPayload"
      :category-loading="categoryLoading"
      :category-saving="categorySaving"
      :get-sub-input="getSubInput"
      :format-category-preview="formatCategoryPreview"
      :toggle-sub-category-hidden="toggleSubCategoryHidden"
      :add-sub-category="addSubCategory"
      :remove-sub-category="removeSubCategory"
      @save="saveCategoryRules"
    />

    <!-- 弹窗 5：详情页策略 -->
    <SiteDetailPolicy
      v-model="isDetailPolicyVisible"
      v-model:ad-pattern-input="adPatternInput"
      v-model:new-line-orig="newLineOrig"
      v-model:new-line-alias="newLineAlias"
      :detail-policy="detailPolicy"
      :detail-policy-loading="detailPolicyLoading"
      :detail-policy-saving="detailPolicySaving"
      @add-ad-pattern="addAdPattern"
      @remove-ad-pattern="removeAdPattern"
      @add-line-override="addLineOverride"
      @remove-line-override="removeLineOverride"
      @save="saveDetailPolicy"
    />
  </div>
</template>

<style>
@import './sites-view.css';
</style>
