<script setup lang="ts">
/**
 * SiteDetailModal - 统一卡片弹出式站点详细设置中心（组件化架构）
 * 将基础与网络代理、分类与标签、广告清洗与线路、采集器源码以及运维操作
 * 拆解为独立的 Tab 子组件与外部样式表，主组件仅作为对话框与选项卡编排容器。
 */
import {
  ElDialog,
  ElTabPane,
  ElTabs,
  ElTag,
} from 'element-plus'
import { ref, watch } from 'vue'

import type {
  AdminSiteItem,
  CategoryRuleItem,
  ProxyNodeItem,
  SiteAdvancedSettingPayload,
  SiteCachePolicy,
  SiteCategoryRulePayload,
  SiteDetailPolicyPayload,
  SubCategoryItem,
} from '@/api/types'

import DetailBasicTab from './detail/DetailBasicTab.vue'
import DetailCategoryTab from './detail/DetailCategoryTab.vue'
import DetailPolicyTab from './detail/DetailPolicyTab.vue'
import DetailCodeTab from './detail/DetailCodeTab.vue'
import DetailOpsTab from './detail/DetailOpsTab.vue'

const props = defineProps<{
  modelValue: boolean
  site: AdminSiteItem | null
  initialTab?: string

  // 1. 基础与网络
  currentAdvanced: SiteAdvancedSettingPayload
  currentCachePolicy: SiteCachePolicy
  proxyNodes: ProxyNodeItem[]
  selectedProxyChoice: string
  selectedNode?: ProxyNodeItem
  advancedLoading: boolean
  advancedSaving: boolean
  testingNode: boolean
  formatNodeLabel: (node: ProxyNodeItem) => string

  // 2. 分类规则
  categoryPayload: SiteCategoryRulePayload
  categoryLoading: boolean
  categorySaving: boolean
  getSubInput: (tid: string) => { tid: string; name: string; custom_name?: string }
  formatCategoryPreview: (rawName: string, customName?: string) => string
  toggleSubCategoryHidden: (sub: SubCategoryItem) => void
  addSubCategory: (rule: CategoryRuleItem) => void
  removeSubCategory: (rule: CategoryRuleItem, sub: SubCategoryItem) => void

  // 3. 详情与广告清洗
  detailPolicy: SiteDetailPolicyPayload
  detailPolicyLoading: boolean
  detailPolicySaving: boolean
  adPatternInput: string
  newLineOrig: string
  newLineAlias: string

  // 4. 采集器源码
  code: string
  mtime: string
  loadingCode: boolean

  // 5. 排序与操作
  isFirst?: boolean
  isLast?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'update:adPatternInput', value: string): void
  (e: 'update:newLineOrig', value: string): void
  (e: 'update:newLineAlias', value: string): void
  (e: 'proxyChoiceChange', choice: string): void
  (e: 'testNode'): void
  (e: 'saveAdvanced'): void
  (e: 'saveCategory'): void
  (e: 'addAdPattern'): void
  (e: 'removeAdPattern', idx: number): void
  (e: 'addLineOverride'): void
  (e: 'removeLineOverride', orig: string): void
  (e: 'saveDetailPolicy'): void
  (e: 'move', delta: number): void
  (e: 'deleteSite'): void
  (e: 'toggleEnabled', next: boolean): void
  (e: 'crawlerUploaded'): void
}>()

const activeTab = ref('basic')

watch(
  () => props.initialTab,
  (val) => {
    if (val) activeTab.value = val
  },
  { immediate: true },
)
</script>

<template>
  <ElDialog
    :model-value="modelValue"
    width="820px"
    class="site-detail-dialog"
    align-center
    append-to-body
    destroy-on-close
    @update:model-value="(val) => emit('update:modelValue', val)"
  >
    <!-- 自定义弹窗顶栏 -->
    <template #header>
      <div v-if="site" class="modal-site-header">
        <div class="header-left">
          <div class="site-title-row">
            <span class="site-modal-name">{{ currentAdvanced.custom_name || site.name }}</span>
            <code class="site-modal-key">{{ site.key }}</code>
            <ElTag v-if="site.mode === 'proxy'" size="small" type="warning" effect="plain">
              反代
            </ElTag>
            <ElTag v-if="site.version" size="small" type="info" effect="plain">
              v{{ site.version }}
            </ElTag>
            <ElTag :type="site.enabled ? 'success' : 'info'" size="small" effect="dark">
              {{ site.enabled ? '用户端已启用' : '已停用' }}
            </ElTag>
          </div>
          <div class="site-modal-sub">
            支持能力：{{ site.capabilities?.join(' · ') || '全功能' }}
          </div>
        </div>
      </div>
    </template>

    <div v-if="site" class="modal-tab-container">
      <ElTabs v-model="activeTab" class="site-config-tabs">
        <!-- ==================== Tab 1: 基础参数与网络代理 ==================== -->
        <ElTabPane label="基础与网络" name="basic">
          <DetailBasicTab
            :current-advanced="currentAdvanced"
            :current-cache-policy="currentCachePolicy"
            :proxy-nodes="proxyNodes"
            :selected-proxy-choice="selectedProxyChoice"
            :selected-node="selectedNode"
            :advanced-loading="advancedLoading"
            :advanced-saving="advancedSaving"
            :testing-node="testingNode"
            :format-node-label="formatNodeLabel"
            @proxy-choice-change="(val) => emit('proxyChoiceChange', val)"
            @test-node="emit('testNode')"
            @save-advanced="emit('saveAdvanced')"
            @close-modal="emit('update:modelValue', false)"
          />
        </ElTabPane>

        <!-- ==================== Tab 2: 分类与子分类规则 ==================== -->
        <ElTabPane label="分类规则" name="category">
          <DetailCategoryTab
            :category-payload="categoryPayload"
            :category-loading="categoryLoading"
            :category-saving="categorySaving"
            :get-sub-input="getSubInput"
            :format-category-preview="formatCategoryPreview"
            :toggle-sub-category-hidden="toggleSubCategoryHidden"
            :add-sub-category="addSubCategory"
            :remove-sub-category="removeSubCategory"
            @save-category="emit('saveCategory')"
          />
        </ElTabPane>

        <!-- ==================== Tab 3: 广告清洗与线路别名 ==================== -->
        <ElTabPane label="广告与线路" name="policy">
          <DetailPolicyTab
            :detail-policy="detailPolicy"
            :detail-policy-loading="detailPolicyLoading"
            :detail-policy-saving="detailPolicySaving"
            :ad-pattern-input="adPatternInput"
            :new-line-orig="newLineOrig"
            :new-line-alias="newLineAlias"
            @remove-ad-pattern="(idx) => emit('removeAdPattern', idx)"
            @update:ad-pattern-input="(val) => emit('update:adPatternInput', val)"
            @add-ad-pattern="emit('addAdPattern')"
            @remove-line-override="(orig) => emit('removeLineOverride', orig)"
            @update:new-line-orig="(val) => emit('update:newLineOrig', val)"
            @update:new-line-alias="(val) => emit('update:newLineAlias', val)"
            @add-line-override="emit('addLineOverride')"
            @save-detail-policy="emit('saveDetailPolicy')"
          />
        </ElTabPane>

        <!-- ==================== Tab 4: 爬虫源码在线查看与上传 ==================== -->
        <ElTabPane label="采集器源码" name="code">
          <DetailCodeTab
            :site="site"
            :code="code"
            :mtime="mtime"
            :loading-code="loadingCode"
            @crawler-uploaded="emit('crawlerUploaded')"
          />
        </ElTabPane>

        <!-- ==================== Tab 5: 排序与危险操作 ==================== -->
        <ElTabPane label="排序与操作" name="manage">
          <DetailOpsTab
            :site="site"
            :is-first="isFirst"
            :is-last="isLast"
            @move="(delta) => emit('move', delta)"
            @toggle-enabled="(next) => emit('toggleEnabled', next)"
            @delete-site="emit('deleteSite')"
          />
        </ElTabPane>
      </ElTabs>
    </div>
  </ElDialog>
</template>

<style scoped src="./detail/site-detail-modal.css"></style>
<style src="./detail/site-detail-dialog.css"></style>
