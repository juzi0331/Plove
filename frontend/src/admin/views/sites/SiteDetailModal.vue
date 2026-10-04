<script setup lang="ts">
/**
 * SiteDetailModal - 统一卡片弹出式站点详细设置中心
 * 将分散的高级配置、分类与标签、广告清洗、采集器源码以及运维操作整合为多标签页弹窗，
 * 让用户点击卡片即可在统一面板中直观查看和编辑全部设置。
 */
import {
  Delete,
  Lightning,
  Plus,
  Right,
  TopRight,
  Upload,
} from '@element-plus/icons-vue'
import {
  ElAlert,
  ElButton,
  ElDialog,
  ElDivider,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElOption,
  ElOptionGroup,
  ElPopover,
  ElRadio,
  ElRadioGroup,
  ElSelect,
  ElSwitch,
  ElTabPane,
  ElTabs,
  ElTag,
} from 'element-plus'
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { describeError } from '@/api/http'
import { uploadCrawler } from '../../api'

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

import { adminPath } from '../../config'
import { ui } from '../../ui'

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

const router = useRouter()
const activeTab = ref('basic')

watch(
  () => props.initialTab,
  (val) => {
    if (val) activeTab.value = val
  },
  { immediate: true },
)

function goToProxyNodes(): void {
  emit('update:modelValue', false)
  void router.push(adminPath('/proxy-nodes'))
}

// 采集器源码在线上传与自定义版本号
const showCodeUpload = ref(false)
const modalUploadCode = ref('')
const modalCustomVersion = ref('')
const modalUploadOverwrite = ref(true)
const modalAutoBump = ref(false)
const modalUploading = ref(false)
const modalSelectedFileName = ref('')
const modalFileInputRef = ref<HTMLInputElement | null>(null)

function openModalUpload(): void {
  modalUploadCode.value = props.code || ''
  modalCustomVersion.value = ''
  modalUploadOverwrite.value = true
  modalAutoBump.value = false
  modalSelectedFileName.value = ''
  showCodeUpload.value = true
}

function triggerModalFileInput(): void {
  modalFileInputRef.value?.click()
}

function handleModalFileChange(e: Event): void {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  modalSelectedFileName.value = file.name
  const reader = new FileReader()
  reader.onload = (ev) => {
    modalUploadCode.value = (ev.target?.result as string) || ''
  }
  reader.readAsText(file)
}

async function handleModalSaveCrawler(): Promise<void> {
  if (ui.readOnly) {
    ElMessage.warning('演示模式只读，无法上传采集器')
    return
  }
  if (!props.site?.key) return
  if (!modalUploadCode.value.trim()) {
    ElMessage.warning('源码内容不能为空')
    return
  }

  modalUploading.value = true
  try {
    const res = await uploadCrawler({
      key: props.site.key,
      code: modalUploadCode.value,
      overwrite: modalUploadOverwrite.value,
      auto_bump_version: modalAutoBump.value,
      custom_version: modalCustomVersion.value.trim() || undefined,
    })
    ElMessage.success(res.message)
    showCodeUpload.value = false
    emit('crawlerUploaded')
  } catch (err) {
    ElMessage.error(describeError(err))
  } finally {
    modalUploading.value = false
  }
}
</script>

<template>
  <ElDialog
    :model-value="modelValue"
    width="820px"
    class="site-detail-dialog"
    align-center
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
          <div v-loading="advancedLoading" class="tab-pane-content">
            <ElForm label-position="top">
              <div class="form-row-2">
                <ElFormItem label="用户端显示别名" style="flex: 1;">
                  <ElInput
                    v-model="currentAdvanced.custom_name"
                    placeholder="留空则显示脚本默认名称"
                    :disabled="ui.readOnly"
                  />
                </ElFormItem>

                <ElFormItem label="自定义角标（如 4K、蓝光、极速）" style="width: 240px;">
                  <ElInput
                    v-model="currentAdvanced.badge"
                    placeholder="留空无角标"
                    maxlength="10"
                    show-word-limit
                    :disabled="ui.readOnly"
                  />
                </ElFormItem>
              </div>

              <div class="form-row-2">
                <ElFormItem label="抓取请求超时 (秒)" style="flex: 1;">
                  <ElInputNumber
                    v-model="currentAdvanced.timeout_seconds"
                    :min="0"
                    :max="120"
                    :step="1"
                    :disabled="ui.readOnly"
                    style="width: 100%;"
                  />
                  <div class="form-item-tip">0 为使用系统默认超时（15 秒）</div>
                </ElFormItem>

                <ElFormItem label="运维备忘 / 站点特征说明" style="flex: 1;">
                  <ElInput
                    v-model="currentAdvanced.note"
                    placeholder="填写站长联系方式、接口特性等备忘"
                    :disabled="ui.readOnly"
                  />
                </ElFormItem>
              </div>

              <ElDivider content-position="left">爬虫网络代理与节点池指派</ElDivider>

              <ElFormItem label="网络请求通道指派">
                <div class="proxy-select-row">
                  <ElSelect
                    :model-value="selectedProxyChoice"
                    style="flex: 1;"
                    :disabled="ui.readOnly"
                    @update:model-value="(val) => emit('proxyChoiceChange', val)"
                  >
                    <ElOption label="直连源站（不使用代理中转，最快）" value="direct" />
                    <ElOptionGroup v-if="proxyNodes.length > 0" label="已配置代理节点池">
                      <ElOption
                        v-for="node in proxyNodes"
                        :key="node.id"
                        :label="formatNodeLabel(node)"
                        :value="node.id"
                      />
                    </ElOptionGroup>
                    <ElOption label="自定义本地 HTTP / SOCKS5 代理地址" value="custom" />
                  </ElSelect>

                  <ElButton
                    v-if="selectedNode"
                    :loading="testingNode"
                    :icon="Lightning"
                    @click="emit('testNode')"
                  >
                    节点测速
                  </ElButton>

                  <ElButton
                    link
                    type="primary"
                    :icon="TopRight"
                    @click="goToProxyNodes"
                  >
                    管理代理节点池 ({{ proxyNodes.length }})
                  </ElButton>
                </div>

                <div v-if="selectedNode" class="node-meta-banner">
                  <div><strong>服务器：</strong>{{ selectedNode.server }}:{{ selectedNode.port }}</div>
                  <div><strong>本地中转：</strong><code>{{ selectedNode.proxy_url }}</code></div>
                  <div v-if="selectedNode.protocol === 'vless'" class="xray-badge-text">
                    内置 Xray 核心引擎自动接管本地监听，免手动配置
                  </div>
                </div>

                <div v-if="selectedProxyChoice === 'custom'" style="margin-top: 10px;">
                  <ElInput
                    v-model="currentAdvanced.proxy_url"
                    placeholder="http://127.0.0.1:10809 或 socks5://127.0.0.1:10808"
                    :disabled="ui.readOnly"
                  />
                </div>
              </ElFormItem>

              <ElDivider content-position="left">单站独立内容缓存与 TTL (秒)</ElDivider>

              <div class="ttl-row">
                <ElFormItem label="首页 TTL">
                  <ElInputNumber
                    v-model="currentCachePolicy.home_ttl"
                    :min="0"
                    :max="86400"
                    :step="60"
                    placeholder="留空继承"
                    :disabled="ui.readOnly"
                    style="width: 100%;"
                  />
                </ElFormItem>
                <ElFormItem label="分类大厅 TTL">
                  <ElInputNumber
                    v-model="currentCachePolicy.category_ttl"
                    :min="0"
                    :max="86400"
                    :step="60"
                    placeholder="留空继承"
                    :disabled="ui.readOnly"
                    style="width: 100%;"
                  />
                </ElFormItem>
                <ElFormItem label="详情页 TTL">
                  <ElInputNumber
                    v-model="currentCachePolicy.detail_ttl"
                    :min="0"
                    :max="86400"
                    :step="60"
                    placeholder="留空继承"
                    :disabled="ui.readOnly"
                    style="width: 100%;"
                  />
                </ElFormItem>
              </div>
              <div class="form-item-tip">
                留空时自动继承系统全局默认缓存策略（首页 600s、分类 300s、详情 300s），输入 0 则单站禁用缓存。
              </div>

              <div class="pane-footer-actions">
                <ElButton
                  type="primary"
                  :loading="advancedSaving"
                  :disabled="ui.readOnly"
                  @click="emit('saveAdvanced')"
                >
                  保存基础与网络设置
                </ElButton>
              </div>
            </ElForm>
          </div>
        </ElTabPane>

        <!-- ==================== Tab 2: 分类与子分类规则 ==================== -->
        <ElTabPane label="分类规则" name="category">
          <div v-loading="categoryLoading" class="tab-pane-content">
            <ElAlert
              type="info"
              show-icon
              :closable="false"
              style="margin-bottom: 16px;"
            >
              您可以在此决定哪些分类在首页横向展示、屏蔽不需要的垃圾分类、重命名分类显示名称，或挂载二级子分类与筛选标签。
            </ElAlert>

            <div class="default-tid-bar">
              <span class="bar-label">用户端默认推荐主分类 TID：</span>
              <ElSelect
                v-model="categoryPayload.default_tid"
                placeholder="系统默认第一项"
                clearable
                style="width: 240px;"
              >
                <ElOption
                  v-for="r in (categoryPayload.rules || [])"
                  :key="r.tid"
                  :label="`${r.name} (TID: ${r.tid})`"
                  :value="r.tid"
                />
              </ElSelect>
            </div>

            <div v-if="!categoryPayload.rules || categoryPayload.rules.length === 0" class="empty-rules">
              <ElEmpty description="该采集器尚未返回任何分类数据，请先在探针中测试分类接口" />
            </div>

            <div v-else class="rules-list">
              <div
                v-for="rule in (categoryPayload.rules || [])"
                :key="rule.tid"
                class="category-rule-card"
                :class="{ 'is-hidden': rule.hidden }"
              >
                <div class="rule-card-header">
                  <div class="rule-title-group">
                    <span class="rule-tid-badge">TID: {{ rule.tid }}</span>
                    <span class="rule-orig-name">{{ rule.name }}</span>
                    <ElIcon v-if="rule.custom_name" :size="12"><Right /></ElIcon>
                    <span v-if="rule.custom_name" class="rule-preview-name">
                      {{ formatCategoryPreview(rule.name, rule.custom_name) }}
                    </span>
                  </div>

                  <div class="rule-switches">
                    <ElSwitch
                      v-model="rule.show_on_home"
                      active-text="首页横向展示"
                      size="small"
                      :disabled="rule.hidden || ui.readOnly"
                    />
                    <ElSwitch
                      v-model="rule.hidden"
                      active-text="屏蔽此分类"
                      size="small"
                      active-color="var(--el-color-danger)"
                      :disabled="ui.readOnly"
                    />
                  </div>
                </div>

                <div v-if="!rule.hidden" class="rule-body">
                  <div class="rule-inputs-row">
                    <ElInput
                      v-model="rule.custom_name"
                      placeholder="自定义别名（如：热播国产剧）"
                      size="small"
                      style="flex: 1;"
                      :disabled="ui.readOnly"
                    />
                    <span class="sub-count-tag">
                      子分类 ({{ rule.subcategories?.length || 0 }})
                    </span>
                  </div>

                  <!-- 二级子分类标签 -->
                  <div class="sub-categories-wrap">
                    <div
                      v-for="sub in (rule.subcategories || [])"
                      :key="sub.tid"
                      class="sub-pill"
                      :class="{ 'sub-pill--hidden': sub.hidden }"
                      :title="sub.hidden ? '点击解除屏蔽' : '点击屏蔽此子标签'"
                      @click="toggleSubCategoryHidden(sub)"
                    >
                      <span class="sub-pill-name">{{ sub.name }}</span>
                      <span
                        class="sub-pill-del"
                        title="删除子分类"
                        @click.stop="removeSubCategory(rule, sub)"
                      >
                        ×
                      </span>
                    </div>

                    <ElPopover placement="bottom-start" :width="280" trigger="click">
                      <template #reference>
                        <ElButton size="small" :icon="Plus" plain class="add-sub-btn">
                          添加子标签
                        </ElButton>
                      </template>
                      <div class="add-sub-popover">
                        <div class="popover-title">挂载子分类 / 过滤标签</div>
                        <ElInput
                          v-model="getSubInput(rule.tid).tid"
                          placeholder="子分类 TID（如 13）"
                          size="small"
                          style="margin-bottom: 8px;"
                        />
                        <ElInput
                          v-model="getSubInput(rule.tid).name"
                          placeholder="子分类名称（如 动作片）"
                          size="small"
                          style="margin-bottom: 8px;"
                        />
                        <ElButton
                          size="small"
                          type="primary"
                          style="width: 100%;"
                          @click="addSubCategory(rule)"
                        >
                          确认添加
                        </ElButton>
                      </div>
                    </ElPopover>
                  </div>
                </div>
              </div>
            </div>

            <div class="pane-footer-actions">
              <ElButton
                type="primary"
                :loading="categorySaving"
                :disabled="ui.readOnly"
                @click="emit('saveCategory')"
              >
                保存分类规则
              </ElButton>
            </div>
          </div>
        </ElTabPane>

        <!-- ==================== Tab 3: 广告清洗与线路别名 ==================== -->
        <ElTabPane label="广告与线路" name="policy">
          <div v-loading="detailPolicyLoading" class="tab-pane-content">
            <ElForm label-position="top" class="policy-clean-form">
              <!-- 板块 1: 牛皮癣广告过滤 -->
              <div class="policy-card-section">
                <div class="policy-card-header">
                  <div class="policy-card-title">牛皮癣广告清洗过滤</div>
                  <div class="policy-card-desc">
                    命中关键词或正则表达式将自动从剧名、备注与简介中剔除，保护播放端纯净体验
                  </div>
                </div>

                <div class="policy-card-body">
                  <div class="tags-editor-box">
                    <template v-if="(detailPolicy.ad_patterns || []).length > 0">
                      <ElTag
                        v-for="(pat, pIdx) in detailPolicy.ad_patterns"
                        :key="pIdx"
                        closable
                        type="danger"
                        effect="plain"
                        class="ad-tag"
                        @close="emit('removeAdPattern', pIdx)"
                      >
                        {{ pat }}
                      </ElTag>
                    </template>
                    <div v-else class="empty-policy-hint">
                      暂无过滤规则。在下方输入广告关键词或正则表达式添加规则
                    </div>
                  </div>

                  <div class="add-pattern-row">
                    <ElInput
                      :model-value="adPatternInput"
                      placeholder="输入广告关键词或正则（如：菠菜、TG频道、http://...）"
                      size="small"
                      style="flex: 1;"
                      :disabled="ui.readOnly"
                      @update:model-value="(val) => emit('update:adPatternInput', val)"
                      @keyup.enter="emit('addAdPattern')"
                    />
                    <ElButton
                      size="small"
                      type="primary"
                      plain
                      :icon="Plus"
                      :disabled="ui.readOnly"
                      @click="emit('addAdPattern')"
                    >
                      添加规则
                    </ElButton>
                  </div>
                </div>
              </div>

              <!-- 板块 2: 线路别名映射 -->
              <div class="policy-card-section">
                <div class="policy-card-header">
                  <div class="policy-card-title">线路名称友好别名映射</div>
                  <div class="policy-card-desc">
                    将源站原始线路名映射为直观别名（如：ffm3u8 ➔ 极速蓝光专线，kkm3u8 ➔ 4K超清专线）
                  </div>
                </div>

                <div class="policy-card-body">
                  <div class="line-overrides-box">
                    <template v-if="detailPolicy.line_name_overrides && Object.keys(detailPolicy.line_name_overrides).length > 0">
                      <div
                        v-for="(alias, orig) in detailPolicy.line_name_overrides"
                        :key="orig"
                        class="line-override-pill"
                      >
                        <code class="orig-code">{{ orig }}</code>
                        <span class="arrow">&rarr;</span>
                        <span class="alias-text">{{ alias }}</span>
                        <span
                          class="del-btn"
                          title="删除此映射"
                          @click="emit('removeLineOverride', String(orig))"
                        >
                          ✕
                        </span>
                      </div>
                    </template>
                    <div v-else class="empty-policy-hint">
                      暂无别名映射，线路将显示采集器原始名称
                    </div>
                  </div>

                  <div class="add-override-row">
                    <ElInput
                      :model-value="newLineOrig"
                      placeholder="原始线路名 (如 ffm3u8)"
                      size="small"
                      style="flex: 1;"
                      :disabled="ui.readOnly"
                      @update:model-value="(val) => emit('update:newLineOrig', val)"
                    />
                    <ElInput
                      :model-value="newLineAlias"
                      placeholder="前台显示别名 (如 极速蓝光专线)"
                      size="small"
                      style="flex: 1;"
                      :disabled="ui.readOnly"
                      @update:model-value="(val) => emit('update:newLineAlias', val)"
                    />
                    <ElButton
                      size="small"
                      type="primary"
                      plain
                      :icon="Plus"
                      :disabled="ui.readOnly"
                      @click="emit('addLineOverride')"
                    >
                      添加映射
                    </ElButton>
                  </div>
                </div>
              </div>

              <!-- 板块 3: 剧集标题规范化 -->
              <div class="policy-card-section">
                <div class="policy-card-header">
                  <div class="policy-card-title">集数标题自动规范化策略</div>
                  <div class="policy-card-desc">自动解析并格式化源站剧集标题序号</div>
                </div>
                <div class="policy-card-body">
                  <ElRadioGroup v-model="detailPolicy.ep_naming_rule" :disabled="ui.readOnly">
                    <ElRadio value="auto">智能提取（第01集、全集等）</ElRadio>
                    <ElRadio value="keep_raw">保持源站原始剧集文本</ElRadio>
                    <ElRadio value="numeric_only">纯序号提取（1, 2, 3...）</ElRadio>
                  </ElRadioGroup>
                </div>
              </div>

              <div class="pane-footer-actions">
                <ElButton
                  type="primary"
                  :loading="detailPolicySaving"
                  :disabled="ui.readOnly"
                  @click="emit('saveDetailPolicy')"
                >
                  保存广告清洗与线路策略
                </ElButton>
              </div>
            </ElForm>
          </div>
        </ElTabPane>

        <!-- ==================== Tab 4: 爬虫源码在线查看与上传 ==================== -->
        <ElTabPane label="采集器源码" name="code">
          <div v-loading="loadingCode" class="tab-pane-content">
            <div class="code-meta-bar">
              <div class="code-meta-left">
                <span>文件：<code>{{ site.key }}.py</code></span>
                <span v-if="mtime" style="margin-left: 12px;">最后修改：<strong class="a-mono">{{ mtime }}</strong></span>
              </div>
              <div class="code-meta-actions">
                <ElButton
                  size="small"
                  type="primary"
                  :icon="Upload"
                  :disabled="ui.readOnly"
                  @click="showCodeUpload ? (showCodeUpload = false) : openModalUpload()"
                >
                  {{ showCodeUpload ? '返回源码查看' : '上传/更新源码 (支持自定义版本)' }}
                </ElButton>
              </div>
            </div>

            <!-- 上传表单区 -->
            <div v-if="showCodeUpload" class="code-upload-panel">
              <input
                ref="modalFileInputRef"
                type="file"
                accept=".py"
                style="display: none;"
                @change="handleModalFileChange"
              />

              <div class="upload-tools-bar">
                <ElButton size="small" :icon="Upload" @click="triggerModalFileInput">
                  选择本地 .py 文件
                </ElButton>
                <span v-if="modalSelectedFileName" class="selected-file-text">
                  已选择：<strong>{{ modalSelectedFileName }}</strong>
                </span>

                <div class="version-input-box">
                  <span class="version-label">自定义版本号：</span>
                  <ElInput
                    v-model="modalCustomVersion"
                    placeholder="如 1.0.2 (选填，留空沿用原版)"
                    size="small"
                    style="width: 220px;"
                  />
                </div>
              </div>

              <ElInput
                v-model="modalUploadCode"
                type="textarea"
                :rows="12"
                placeholder="# 请在此粘贴或编辑 Python 采集器源码"
                class="upload-code-textarea"
              />

              <div class="upload-panel-actions">
                <ElSwitch
                  v-model="modalUploadOverwrite"
                  active-text="允许覆盖现有文件"
                  size="small"
                />
                <div style="display: flex; gap: 8px;">
                  <ElButton size="small" @click="showCodeUpload = false">取消</ElButton>
                  <ElButton
                    size="small"
                    type="primary"
                    :loading="modalUploading"
                    @click="handleModalSaveCrawler"
                  >
                    保存并部署更新
                  </ElButton>
                </div>
              </div>
            </div>

            <!-- 源码查看预览框 -->
            <pre v-else class="code-pre-box"><code>{{ code || '正在载入 Python 爬虫源代码...' }}</code></pre>
          </div>
        </ElTabPane>

        <!-- ==================== Tab 5: 排序与危险操作 ==================== -->
        <ElTabPane label="排序与操作" name="manage">
          <div class="tab-pane-content">
            <div class="manage-section">
              <div class="manage-title">站点在前台展示的位次排序</div>
              <p class="manage-desc">位次决定了该采集源在用户端首页、多源搜索结果以及线路选择时的优先级顺序。</p>
              <div class="manage-actions-row">
                <span class="a-muted" style="margin-right: 12px;">当前位次：{{ site.sort_order }}</span>
                <ElButton
                  size="small"
                  :disabled="ui.readOnly || isFirst"
                  @click="emit('move', -1)"
                >
                  ↑ 上移一位 (提升优先级)
                </ElButton>
                <ElButton
                  size="small"
                  :disabled="ui.readOnly || isLast"
                  @click="emit('move', 1)"
                >
                  ↓ 下移一位 (降低优先级)
                </ElButton>
              </div>
            </div>

            <ElDivider />

            <div class="manage-section">
              <div class="manage-title">启停状态控制</div>
              <p class="manage-desc">停用后，用户端将无法检索到该站影片，现有缓存将不再更新，但不影响采集器源码与配置持久化。</p>
              <ElSwitch
                :model-value="site.enabled"
                :disabled="ui.readOnly"
                active-text="启用站点"
                inactive-text="停用站点"
                @update:model-value="(val) => emit('toggleEnabled', Boolean(val))"
              />
            </div>

            <ElDivider />

            <div class="manage-section danger-zone">
              <div class="manage-title" style="color: var(--el-color-danger);">危险区域：删除采集器</div>
              <p class="manage-desc">删除采集器将从磁盘彻底移除 <code>{{ site.key }}.py</code> 脚本及该站的所有关联规则。此操作不可逆！</p>
              <ElButton
                type="danger"
                :icon="Delete"
                :disabled="ui.readOnly"
                @click="emit('deleteSite')"
              >
                彻底删除此采集器
              </ElButton>
            </div>
          </div>
        </ElTabPane>
      </ElTabs>
    </div>
  </ElDialog>
</template>

<style scoped>
.modal-site-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding-right: 24px;
}

.site-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.site-modal-name {
  font-size: 19px;
  font-weight: 800;
  color: #0f172a;
}

html.dark .site-modal-name {
  color: #f8fafc;
}

.site-modal-key {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 12px;
  background: #f1f5f9;
  color: #475569;
  padding: 3px 8px;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
}

html.dark .site-modal-key {
  background: #1e293b;
  color: #cbd5e1;
  border-color: rgba(255, 255, 255, 0.1);
}

.site-modal-sub {
  font-size: 12.5px;
  color: #64748b;
  margin-top: 4px;
}

html.dark .site-modal-sub {
  color: #94a3b8;
}

.modal-tab-container {
  min-height: 420px;
}

.tab-pane-content {
  padding: 8px 4px 16px;
}

.form-row-2 {
  display: flex;
  gap: 16px;
  margin-bottom: 6px;
}

@media (max-width: 640px) {
  .form-row-2 {
    flex-direction: column;
  }
}

.form-item-tip {
  font-size: 12px;
  color: #64748b;
  margin-top: 5px;
  line-height: 1.4;
}

html.dark .form-item-tip {
  color: #94a3b8;
}

.proxy-select-row {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.node-meta-banner {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 14px;
  margin-top: 10px;
  font-size: 12.5px;
  line-height: 1.6;
  color: #334155;
}

html.dark .node-meta-banner {
  background: #1e293b;
  border-color: rgba(255, 255, 255, 0.1);
  color: #e2e8f0;
}

.xray-badge-text {
  color: #166534;
  font-weight: 600;
  margin-top: 2px;
}

html.dark .xray-badge-text {
  color: #34d399;
}

.ttl-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}

@media (max-width: 640px) {
  .ttl-row {
    grid-template-columns: 1fr;
  }
}

.pane-footer-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #f1f5f9;
}

html.dark .pane-footer-actions {
  border-top-color: rgba(255, 255, 255, 0.08);
}

/* 分类规则卡片 */
.default-tid-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
  background: #f8fafc;
  padding: 10px 16px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  color: #0f172a;
}

html.dark .default-tid-bar {
  background: #1a2236;
  border-color: rgba(255, 255, 255, 0.08);
  color: #f8fafc;
}

.bar-label {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
}

html.dark .bar-label {
  color: #f8fafc;
}

.rules-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 480px;
  overflow-y: auto;
  padding-right: 6px;
}

.category-rule-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 16px;
  transition: all 0.2s ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

html.dark .category-rule-card {
  background: #182238;
  border-color: rgba(255, 255, 255, 0.08);
}

.category-rule-card.is-hidden {
  opacity: 0.6;
  border-color: rgba(239, 68, 68, 0.3);
}

.rule-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
}

.rule-title-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.rule-tid-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  background: #f1f5f9;
  color: #475569;
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid #e2e8f0;
}

html.dark .rule-tid-badge {
  background: #1e293b;
  color: #cbd5e1;
  border-color: rgba(255, 255, 255, 0.1);
}

.rule-orig-name {
  font-weight: 700;
  font-size: 14px;
  color: #0f172a;
}

html.dark .rule-orig-name {
  color: #f8fafc;
}

.rule-preview-name {
  color: #4f46e5;
  font-size: 13px;
  font-weight: 600;
}

html.dark .rule-preview-name {
  color: #818cf8;
}

.rule-switches {
  display: flex;
  align-items: center;
  gap: 14px;
}

.rule-body {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #e2e8f0;
}

html.dark .rule-body {
  border-top-color: rgba(255, 255, 255, 0.1);
}

.rule-inputs-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.sub-count-tag {
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
}

.sub-categories-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.sub-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #f8fafc;
  border: 1px solid #cbd5e1;
  color: #334155;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
}

html.dark .sub-pill {
  background: #1f293d;
  border-color: rgba(255, 255, 255, 0.12);
  color: #e2e8f0;
}

.sub-pill:hover {
  border-color: #4f46e5;
  color: #4f46e5;
}

.sub-pill--hidden {
  text-decoration: line-through;
  opacity: 0.5;
}

.sub-pill-del {
  color: #94a3b8;
  font-weight: bold;
}

.sub-pill-del:hover {
  color: #ef4444;
}

.add-sub-popover {
  padding: 4px;
}

.popover-title {
  font-weight: 700;
  font-size: 13px;
  margin-bottom: 8px;
  color: #0f172a;
}

/* 广告清洗与线路别名卡片化排版 */
.policy-clean-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
}

.policy-card-section {
  background: var(--el-fill-color-light, #f8fafc);
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
  box-sizing: border-box;
}

html.dark .policy-card-section {
  background: #1a2236;
  border-color: rgba(255, 255, 255, 0.12);
}

.policy-card-header {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.policy-card-title {
  font-size: 13.5px;
  font-weight: 700;
  color: var(--a-text, #1e293b);
}

html.dark .policy-card-title {
  color: #f8fafc;
}

.policy-card-desc {
  font-size: 11.5px;
  color: #64748b;
  line-height: 1.4;
}

html.dark .policy-card-desc {
  color: #94a3b8;
}

.policy-card-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.tags-editor-box,
.line-overrides-box {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  min-height: 38px;
  padding: 6px 10px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  width: 100%;
  box-sizing: border-box;
}

html.dark .tags-editor-box,
html.dark .line-overrides-box {
  background: #111827;
  border-color: rgba(255, 255, 255, 0.1);
}

.empty-policy-hint {
  font-size: 12px;
  color: #94a3b8;
  padding: 4px 2px;
}

.add-pattern-row,
.add-override-row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}

.line-override-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #f1f5f9;
  border: 1px solid #cbd5e1;
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 12px;
  color: #334155;
}

html.dark .line-override-pill {
  background: #1e293b;
  border-color: rgba(255, 255, 255, 0.12);
  color: #e2e8f0;
}

.orig-code {
  font-family: 'JetBrains Mono', monospace;
  color: #475569;
  font-weight: 600;
}

html.dark .orig-code {
  color: #cbd5e1;
}

.arrow {
  color: #94a3b8;
}

.alias-text {
  font-weight: 700;
  color: #4f46e5;
}

html.dark .alias-text {
  color: #818cf8;
}

.del-btn {
  color: #94a3b8;
  cursor: pointer;
  font-weight: bold;
  margin-left: 4px;
}

.del-btn:hover {
  color: #ef4444;
}

/* 源码预览与上传面板 */
.code-meta-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  font-size: 12.5px;
  color: #475569;
  gap: 12px;
  flex-wrap: wrap;
}

html.dark .code-meta-bar {
  color: #cbd5e1;
}

.code-meta-left {
  display: flex;
  align-items: center;
}

.code-upload-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 14px;
}

.upload-tools-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.selected-file-text {
  font-size: 12px;
  color: #38bdf8;
}

.version-input-box {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}

.version-label {
  font-size: 12px;
  color: #94a3b8;
}

.upload-code-textarea :deep(.el-textarea__inner) {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 12.5px;
  line-height: 1.5;
  background: #0f172a;
  color: #f1f5f9;
  border-color: #334155;
}

.upload-panel-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.code-pre-box {
  background: #0f172a;
  color: #f1f5f9;
  border: 1px solid #1e293b;
  border-radius: 8px;
  padding: 16px;
  max-height: 480px;
  overflow: auto;
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 12.5px;
  line-height: 1.5;
}

/* 排序与危险操作 */
.manage-section {
  padding: 10px 0;
}

.manage-title {
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 4px;
  color: #0f172a;
}

html.dark .manage-title {
  color: #f8fafc;
}

.manage-desc {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 12px;
}

html.dark .manage-desc {
  color: #94a3b8;
}

.manage-actions-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>

<!-- 全局重载针对 teleport 到 body 的站点详细设置弹窗，确保文字极致清晰、零遮挡 -->
<style>
.site-detail-dialog {
  border-radius: 16px !important;
  overflow: hidden;
  box-shadow: 0 25px 50px -12px rgba(15, 23, 42, 0.25) !important;
  border: 1px solid #e2e8f0 !important;
}

/* 浅色主题（默认） */
.site-detail-dialog .el-dialog__header {
  background: #ffffff !important;
  border-bottom: 1px solid #f1f5f9 !important;
  padding: 18px 24px !important;
  margin-right: 0 !important;
}

.site-detail-dialog .el-dialog__body {
  background: #ffffff !important;
  color: #0f172a !important;
  padding: 20px 24px !important;
}

/* 标签页高对比度 */
.site-detail-dialog .el-tabs__nav-wrap::after {
  background-color: #f1f5f9 !important;
  height: 2px !important;
}

.site-detail-dialog .el-tabs__item {
  color: #475569 !important;
  font-size: 14px !important;
  font-weight: 600 !important;
  padding: 0 16px !important;
  transition: color 0.15s ease;
}

.site-detail-dialog .el-tabs__item:hover {
  color: #0f172a !important;
}

.site-detail-dialog .el-tabs__item.is-active {
  color: #4f46e5 !important;
  font-weight: 700 !important;
}

.site-detail-dialog .el-tabs__active-bar {
  background-color: #4f46e5 !important;
  height: 2.5px !important;
  border-radius: 2px !important;
}

/* 表单 Label 极致清晰黑字，彻底解决看不清的问题 */
.site-detail-dialog .el-form-item__label {
  color: #0f172a !important;
  font-size: 13.5px !important;
  font-weight: 600 !important;
  padding-bottom: 6px !important;
  line-height: 1.4 !important;
}

/* 输入框清爽白色背景、清晰边框与深色文字 */
.site-detail-dialog .el-input__wrapper,
.site-detail-dialog .el-textarea__inner {
  background-color: #ffffff !important;
  box-shadow: 0 0 0 1px #cbd5e1 inset !important;
  border-radius: 8px !important;
  transition: all 0.15s ease;
}

.site-detail-dialog .el-input__wrapper:hover,
.site-detail-dialog .el-textarea__inner:hover {
  box-shadow: 0 0 0 1px #94a3b8 inset !important;
}

.site-detail-dialog .el-input__wrapper.is-focus,
.site-detail-dialog .el-textarea__inner:focus {
  box-shadow: 0 0 0 1.5px #4f46e5 inset, 0 0 0 3px rgba(79, 70, 229, 0.12) !important;
}

.site-detail-dialog .el-input__inner,
.site-detail-dialog .el-textarea__inner {
  color: #0f172a !important;
  font-size: 13.5px !important;
}

.site-detail-dialog .el-input__inner::placeholder,
.site-detail-dialog .el-textarea__inner::placeholder {
  color: #94a3b8 !important;
}

.site-detail-dialog .el-input-number__decrease,
.site-detail-dialog .el-input-number__increase {
  background-color: #f8fafc !important;
  color: #475569 !important;
  border-color: #cbd5e1 !important;
}

.site-detail-dialog .el-input-number__decrease:hover,
.site-detail-dialog .el-input-number__increase:hover {
  color: #4f46e5 !important;
}

.site-detail-dialog .el-select__wrapper {
  background-color: #ffffff !important;
  box-shadow: 0 0 0 1px #cbd5e1 inset !important;
  border-radius: 8px !important;
}

.site-detail-dialog .el-select__wrapper.is-focused {
  box-shadow: 0 0 0 1.5px #4f46e5 inset, 0 0 0 3px rgba(79, 70, 229, 0.12) !important;
}

.site-detail-dialog .el-select__placeholder {
  color: #94a3b8 !important;
}

.site-detail-dialog .el-select__selected-item {
  color: #0f172a !important;
  font-weight: 500;
}

/* 分割线标题 */
.site-detail-dialog .el-divider--horizontal {
  border-top: 1px solid #e2e8f0 !important;
  margin: 24px 0 18px !important;
}

.site-detail-dialog .el-divider__text {
  background-color: #ffffff !important;
  color: #4f46e5 !important;
  font-weight: 700 !important;
  font-size: 13px !important;
  padding: 0 12px !important;
}

/* 开关与单选标签 */
.site-detail-dialog .el-switch__label {
  color: #475569 !important;
  font-size: 13px !important;
}

.site-detail-dialog .el-switch__label.is-active {
  color: #4f46e5 !important;
  font-weight: 600 !important;
}

.site-detail-dialog .el-radio__label {
  color: #334155 !important;
  font-size: 13px !important;
}

.site-detail-dialog .el-radio.is-checked .el-radio__label {
  color: #4f46e5 !important;
  font-weight: 600 !important;
}

/* ==================== 深色模式适配 ==================== */
html.dark .site-detail-dialog {
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
  background: #131b2e !important;
}

html.dark .site-detail-dialog .el-dialog__header {
  background: #172138 !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08) !important;
}

html.dark .site-detail-dialog .el-dialog__body {
  background: #131b2e !important;
  color: #f1f5f9 !important;
}

html.dark .site-detail-dialog .el-tabs__nav-wrap::after {
  background-color: rgba(255, 255, 255, 0.08) !important;
}

html.dark .site-detail-dialog .el-tabs__item {
  color: #94a3b8 !important;
}

html.dark .site-detail-dialog .el-tabs__item:hover {
  color: #f8fafc !important;
}

html.dark .site-detail-dialog .el-tabs__item.is-active {
  color: #818cf8 !important;
}

html.dark .site-detail-dialog .el-tabs__active-bar {
  background-color: #818cf8 !important;
}

html.dark .site-detail-dialog .el-form-item__label {
  color: #f1f5f9 !important;
}

html.dark .site-detail-dialog .el-input__wrapper,
html.dark .site-detail-dialog .el-textarea__inner,
html.dark .site-detail-dialog .el-select__wrapper {
  background-color: #1a2236 !important;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.12) inset !important;
}

html.dark .site-detail-dialog .el-input__wrapper:hover,
html.dark .site-detail-dialog .el-textarea__inner:hover {
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.25) inset !important;
}

html.dark .site-detail-dialog .el-input__inner,
html.dark .site-detail-dialog .el-textarea__inner,
html.dark .site-detail-dialog .el-select__selected-item {
  color: #f8fafc !important;
}

html.dark .site-detail-dialog .el-input-number__decrease,
html.dark .site-detail-dialog .el-input-number__increase {
  background-color: #222d45 !important;
  color: #cbd5e1 !important;
  border-color: rgba(255, 255, 255, 0.12) !important;
}

html.dark .site-detail-dialog .el-divider--horizontal {
  border-top-color: rgba(255, 255, 255, 0.08) !important;
}

html.dark .site-detail-dialog .el-divider__text {
  background-color: #131b2e !important;
  color: #818cf8 !important;
}

html.dark .site-detail-dialog .el-switch__label {
  color: #94a3b8 !important;
}

html.dark .site-detail-dialog .el-switch__label.is-active {
  color: #818cf8 !important;
}

html.dark .site-detail-dialog .el-radio__label {
  color: #cbd5e1 !important;
}

html.dark .site-detail-dialog .el-radio.is-checked .el-radio__label {
  color: #818cf8 !important;
}
</style>
