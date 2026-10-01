<script setup lang="ts">
/**
 * 站点管理（内容源）—— 全功能高级运维中心
 *
 * 核心能力升级：
 * 1. 采集器脚本上传、静态安全审计与 meta 冒烟协议测试；
 * 2. 采集器源码在线查看与删除；
 * 3. 单站高级控制：自定义前台别名、站点角标、单站自定义超时（秒）；
 * 4. 站点分类与子分类控制：隐藏/显示、重命名、排序、二级子分类/标签增删；
 * 5. 详情页展示策略：牛皮癣广告正则清洗、线路名称别名映射、集数命名规则、兜底海报；
 * 6. 站点开关、排序与健康监控。
 */

import {
  Delete,
  Document,
  FolderOpened,
  Operation,
  Refresh,
  Setting,
  Upload,
  UploadFilled,
} from '@element-plus/icons-vue'
import {
  ElButton,
  ElCard,
  ElDialog,
  ElDivider,
  ElDrawer,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElPopover,
  ElRadio,
  ElRadioButton,
  ElRadioGroup,
  ElSelect,
  ElSkeleton,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTag,
  ElTooltip,
} from 'element-plus'
import { computed, onMounted, ref } from 'vue'

import { describeError } from '@/api/http'
import type {
  AdminSiteItem,
  AdminSiteListPayload,
  CategoryRuleItem,
  CrawlerValidateResult,
  SiteAdvancedSettingPayload,
  SiteCachePolicy,
  SiteCategoryRulePayload,
  SiteDetailPolicyPayload,
  SitePreheatDetail,
  SubCategoryItem,
} from '@/api/types'

import * as api from '../api'
import EmptyState from '../components/EmptyState.vue'
import ErrorState from '../components/ErrorState.vue'
import PageHeader from '../components/PageHeader.vue'
import { type TagType } from '../format'
import { ui } from '../ui'

const data = ref<AdminSiteListPayload | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const busyKey = ref<string | null>(null)
const viewMode = ref<'cards' | 'table'>('cards')

async function load(): Promise<void> {
  loading.value = true
  try {
    data.value = await api.listSites()
    error.value = null
  } catch (err) {
    error.value = describeError(err)
  } finally {
    loading.value = false
  }
}

onMounted(load)

const sites = computed(() => data.value?.sites ?? [])
const isEmpty = computed(() => !loading.value && !error.value && sites.value.length === 0)

// ------------------------------------------------------------------ 健康
const STATE: Record<string, { label: string; tag: TagType }> = {
  closed: { label: '正常', tag: 'success' },
  half_open: { label: '探测中', tag: 'warning' },
  open: { label: '已熔断', tag: 'danger' },
}

function healthState(site: AdminSiteItem): { label: string; tag: TagType } {
  if (!site.health.probed) return { label: '未探测', tag: 'info' }
  return STATE[site.health.state] ?? { label: site.health.state, tag: 'info' }
}

// ------------------------------------------------------------------ 开关
async function toggle(site: AdminSiteItem, next: boolean): Promise<void> {
  if (next === site.enabled) return

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
    const result = next ? await api.enableSite(site.key) : await api.disableSite(site.key)
    ElMessage.success(result.message)
    await load()
  } catch (err) {
    ElMessage.error(describeError(err))
  } finally {
    busyKey.value = null
  }
}

// ------------------------------------------------------------------ 顺序
const firstKey = computed(() => sites.value[0]?.key)
const lastKey = computed(() => sites.value[sites.value.length - 1]?.key)

async function move(index: number, delta: number): Promise<void> {
  const keys = sites.value.map((site) => site.key)
  const target = index + delta
  if (target < 0 || target >= keys.length) return

  const swapped = [...keys]
  ;[swapped[index], swapped[target]] = [swapped[target], swapped[index]]

  busyKey.value = keys[index]
  try {
    data.value = await api.orderSites(swapped)
    ElMessage.success('顺序已更新')
  } catch (err) {
    ElMessage.error(describeError(err))
    await load()
  } finally {
    busyKey.value = null
  }
}

// ================================================================== 1. 采集器上传与校验
const isUploadVisible = ref(false)
const uploadKey = ref('')
const uploadCode = ref('')
const uploadOverwrite = ref(false)
const validating = ref(false)
const uploading = ref(false)
const validateResult = ref<CrawlerValidateResult | null>(null)
const selectedFileName = ref('')
const selectedFileSize = ref(0)
const fileInputRef = ref<HTMLInputElement | null>(null)

function triggerFileInput(): void {
  fileInputRef.value?.click()
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

function processFile(file: File): void {
  if (!file.name.endsWith('.py')) {
    ElMessage.warning('请选择 .py 格式的 Python 采集器脚本文件')
    return
  }
  selectedFileName.value = file.name
  selectedFileSize.value = file.size

  // 自动从文件名提取 key，如 xiaoyakankan.py -> xiaoyakankan
  const inferredKey = file.name.replace(/\.py$/i, '').trim()
  if (inferredKey && (!uploadKey.value || uploadKey.value === '')) {
    uploadKey.value = inferredKey
  }

  const reader = new FileReader()
  reader.onload = (event) => {
    const text = event.target?.result as string
    if (text) {
      uploadCode.value = text
      ElMessage.success(`已成功载入文件：${file.name}`)
      // 载入成功后，自动执行一次在线校验，给用户最直接的审计反馈
      handleValidateCrawler()
    }
  }
  reader.onerror = () => {
    ElMessage.error('读取文件内容失败，请重试')
  }
  reader.readAsText(file, 'utf-8')
}

function handleFileDrop(e: DragEvent): void {
  const files = e.dataTransfer?.files
  if (!files || files.length === 0) return
  processFile(files[0])
}

function handleFileChange(e: Event): void {
  const target = e.target as HTMLInputElement
  const files = target.files
  if (!files || files.length === 0) return
  processFile(files[0])
}

function clearSelectedFile(): void {
  selectedFileName.value = ''
  selectedFileSize.value = 0
  if (fileInputRef.value) fileInputRef.value.value = ''
}

function openUploadDialog(): void {
  uploadKey.value = ''
  uploadCode.value = ''
  uploadOverwrite.value = false
  validateResult.value = null
  selectedFileName.value = ''
  selectedFileSize.value = 0
  if (fileInputRef.value) fileInputRef.value.value = ''
  isUploadVisible.value = true
}

async function handleValidateCrawler(): Promise<void> {
  if (!uploadCode.value.trim()) {
    ElMessage.warning('请先输入或粘贴采集器 Python 源代码')
    return
  }
  validating.value = true
  validateResult.value = null
  try {
    const res = await api.validateCrawler({
      code: uploadCode.value,
      key: uploadKey.value.trim() || undefined,
    })
    validateResult.value = res
    if (res.valid) {
      ElMessage.success('语法与协议冒烟检查全部通过')
      if (!uploadKey.value && res.key) uploadKey.value = res.key
    } else {
      ElMessage.error(res.error || '校验失败')
    }
  } catch (err) {
    ElMessage.error(describeError(err))
  } finally {
    validating.value = false
  }
}

async function handleSaveCrawler(): Promise<void> {
  const key = uploadKey.value.trim()
  if (!key) {
    ElMessage.warning('请输入站点 key')
    return
  }
  if (!uploadCode.value.trim()) {
    ElMessage.warning('请输入采集器代码')
    return
  }

  uploading.value = true
  try {
    const res = await api.uploadCrawler({
      key,
      code: uploadCode.value,
      overwrite: uploadOverwrite.value,
    })
    ElMessage.success(res.message)
    isUploadVisible.value = false
    await load()
  } catch (err) {
    ElMessage.error(describeError(err))
  } finally {
    uploading.value = false
  }
}

// ================================================================== 2. 源码查看与删除
const isCodeViewerVisible = ref(false)
const currentCode = ref('')
const currentCodeKey = ref('')
const currentCodeMtime = ref('')
const loadingCode = ref(false)

async function viewCrawlerCode(site: AdminSiteItem): Promise<void> {
  currentCodeKey.value = site.key
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

async function handleDeleteCrawler(key: string): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确定彻底删除采集器 ${key}.py 吗？删除后此内容源将从系统完全下线。`,
      '警告：删除采集器',
      { type: 'error', confirmButtonText: '确认删除', cancelButtonText: '取消' },
    )
    await api.deleteCrawler(key)
    ElMessage.success(`已删除采集器 ${key}`)
    await load()
  } catch (err) {
    if (err !== 'cancel') {
      ElMessage.error(describeError(err))
    }
  }
}

// ================================================================== 3. 单站高级控制
const isAdvancedVisible = ref(false)
const advancedLoading = ref(false)
const advancedSaving = ref(false)
const currentAdvanced = ref<SiteAdvancedSettingPayload>({
  key: '',
  custom_name: '',
  badge: '',
  timeout_seconds: 0,
  note: '',
})
const currentCachePolicy = ref<SiteCachePolicy>({
  home_ttl: null,
  category_ttl: null,
  detail_ttl: null,
})
const siteActionLoading = ref(false)

async function openAdvanced(site: AdminSiteItem): Promise<void> {
  currentAdvanced.value = {
    key: site.key,
    custom_name: '',
    badge: '',
    timeout_seconds: 0,
    note: site.note || '',
  }
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
    }
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
    await Promise.all([
      api.updateSiteAdvanced(currentAdvanced.value.key, {
        custom_name: currentAdvanced.value.custom_name,
        badge: currentAdvanced.value.badge,
        timeout_seconds: currentAdvanced.value.timeout_seconds,
        note: currentAdvanced.value.note,
      }),
      api.updateSiteCachePolicy(currentAdvanced.value.key, currentCachePolicy.value),
    ])
    ElMessage.success('单站配置与缓存策略已保存')
    isAdvancedVisible.value = false
    await load()
  } catch (err) {
    ElMessage.error(describeError(err))
  } finally {
    advancedSaving.value = false
  }
}

async function handleClearSiteCacheQuick(key: string): Promise<void> {
  siteActionLoading.value = true
  try {
    const res = await api.clearCache(key)
    ElMessage.success(res.message)
  } catch (err) {
    ElMessage.error(describeError(err))
  } finally {
    siteActionLoading.value = false
  }
}

const isPreheatReportVisible = ref(false)
const preheatReport = ref<SitePreheatDetail | null>(null)

async function handlePreheatSiteQuick(key: string): Promise<void> {
  siteActionLoading.value = true
  try {
    const res = await api.preheatCache(key)
    if (res.details && res.details.length > 0) {
      preheatReport.value = res.details[0]
      isPreheatReportVisible.value = true
      ElMessage.success(`预热成功！已拉取 ${res.details[0].categories_count} 个分类与 ${res.details[0].recommend_count} 部推荐影片`)
    } else {
      ElMessage.success(`预热完成（${res.elapsed_ms}ms），首页数据已装入缓存`)
    }
  } catch (err) {
    ElMessage.error(describeError(err))
  } finally {
    siteActionLoading.value = false
  }
}

// ================================================================== 4. 分类与子分类控制
const isCategoryDrawerVisible = ref(false)
const categoryLoading = ref(false)
const categorySaving = ref(false)
const categoryPayload = ref<SiteCategoryRulePayload>({
  site_key: '',
  rules: [],
  default_tid: null,
})

// 为每个分类维护新增子分类的临时输入
const subCatInputs = ref<Record<string, { tid: string; name: string; custom_name?: string }>>({})

function getSubInput(tid: string): { tid: string; name: string; custom_name?: string } {
  if (!subCatInputs.value[tid]) {
    subCatInputs.value[tid] = { tid: '', name: '', custom_name: '' }
  }
  return subCatInputs.value[tid]!
}

function formatCategoryPreview(rawName: string, customName?: string): string {
  if (!customName || !customName.trim()) {
    return rawName
  }
  let c = customName.trim()
  if ((c.startsWith('(') && c.endsWith(')')) || (c.startsWith('（') && c.endsWith('）'))) {
    c = c.slice(1, -1).trim()
  }
  if (!c) return rawName
  return `${rawName}（${c}）`
}

function toggleSubCategoryHidden(sub: SubCategoryItem): void {
  sub.hidden = !sub.hidden
}

async function openCategoryDrawer(site: AdminSiteItem): Promise<void> {
  categoryPayload.value = {
    site_key: site.key,
    rules: [],
    default_tid: null,
  }
  subCatInputs.value = {}
  isCategoryDrawerVisible.value = true
  categoryLoading.value = true
  try {
    const res = await api.getSiteCategories(site.key)
    categoryPayload.value = {
      site_key: res.site_key,
      rules: (res.rules ?? []).map((r) => ({
        ...r,
        subcategories: (r.subcategories ?? []).map((s) => ({
          ...s,
          custom_name: s.custom_name ?? '',
          hidden: !!s.hidden,
        })),
      })),
      default_tid: res.default_tid ?? null,
    }
  } catch (err) {
    ElMessage.error(describeError(err))
  } finally {
    categoryLoading.value = false
  }
}

function addSubCategory(rule: CategoryRuleItem): void {
  const input = getSubInput(rule.tid)
  if (!input.tid.trim() || !input.name.trim()) {
    ElMessage.warning('请输入子分类 ID 与名称')
    return
  }
  rule.subcategories ??= []
  if (rule.subcategories.some((s) => s.tid === input.tid.trim())) {
    ElMessage.warning('子分类 ID 已存在')
    return
  }
  rule.subcategories.push({
    tid: input.tid.trim(),
    name: input.name.trim(),
    custom_name: input.custom_name?.trim() || '',
    hidden: false,
  })
  input.tid = ''
  input.name = ''
  input.custom_name = ''
}

function removeSubCategory(rule: CategoryRuleItem, sub: SubCategoryItem): void {
  if (!rule.subcategories) return
  rule.subcategories = rule.subcategories.filter((s) => s.tid !== sub.tid)
}

async function saveCategoryRules(): Promise<void> {
  categorySaving.value = true
  try {
    await api.updateSiteCategories(categoryPayload.value.site_key, {
      rules: categoryPayload.value.rules,
      default_tid: categoryPayload.value.default_tid,
    })
    ElMessage.success('分类与子分类规则已保存')
    isCategoryDrawerVisible.value = false
  } catch (err) {
    ElMessage.error(describeError(err))
  } finally {
    categorySaving.value = false
  }
}

// ================================================================== 5. 详情页展示策略
const isDetailPolicyVisible = ref(false)
const detailPolicyLoading = ref(false)
const detailPolicySaving = ref(false)
const detailPolicy = ref<SiteDetailPolicyPayload>({
  site_key: '',
  ad_patterns: [],
  line_name_overrides: {},
  ep_naming_rule: 'auto',
  default_poster: '',
  hide_fields: [],
})

const adPatternInput = ref('')
const newLineOrig = ref('')
const newLineAlias = ref('')

async function openDetailPolicy(site: AdminSiteItem): Promise<void> {
  detailPolicy.value = {
    site_key: site.key,
    ad_patterns: [],
    line_name_overrides: {},
    ep_naming_rule: 'auto',
    default_poster: '',
    hide_fields: [],
  }
  adPatternInput.value = ''
  newLineOrig.value = ''
  newLineAlias.value = ''
  isDetailPolicyVisible.value = true
  detailPolicyLoading.value = true
  try {
    const res = await api.getSiteDetailPolicy(site.key)
    detailPolicy.value = {
      site_key: res.site_key,
      ad_patterns: res.ad_patterns ?? [],
      line_name_overrides: res.line_name_overrides ?? {},
      ep_naming_rule: res.ep_naming_rule ?? 'auto',
      default_poster: res.default_poster ?? '',
      hide_fields: res.hide_fields ?? [],
    }
  } catch (err) {
    ElMessage.error(describeError(err))
  } finally {
    detailPolicyLoading.value = false
  }
}

function addAdPattern(): void {
  const val = adPatternInput.value.trim()
  if (!val) return
  detailPolicy.value.ad_patterns ??= []
  if (!detailPolicy.value.ad_patterns.includes(val)) {
    detailPolicy.value.ad_patterns.push(val)
  }
  adPatternInput.value = ''
}

function removeAdPattern(idx: number): void {
  detailPolicy.value.ad_patterns?.splice(idx, 1)
}

function addLineOverride(): void {
  const orig = newLineOrig.value.trim()
  const alias = newLineAlias.value.trim()
  if (!orig || !alias) {
    ElMessage.warning('请输入原始线路名与映射别名')
    return
  }
  detailPolicy.value.line_name_overrides ??= {}
  detailPolicy.value.line_name_overrides[orig] = alias
  newLineOrig.value = ''
  newLineAlias.value = ''
}

function removeLineOverride(orig: string): void {
  if (!detailPolicy.value.line_name_overrides) return
  delete detailPolicy.value.line_name_overrides[orig]
}

async function saveDetailPolicy(): Promise<void> {
  detailPolicySaving.value = true
  try {
    await api.updateSiteDetailPolicy(detailPolicy.value.site_key, {
      ad_patterns: detailPolicy.value.ad_patterns,
      line_name_overrides: detailPolicy.value.line_name_overrides,
      ep_naming_rule: detailPolicy.value.ep_naming_rule,
      default_poster: detailPolicy.value.default_poster,
      hide_fields: detailPolicy.value.hide_fields,
    })
    ElMessage.success('详情页显示策略已保存')
    isDetailPolicyVisible.value = false
  } catch (err) {
    ElMessage.error(describeError(err))
  } finally {
    detailPolicySaving.value = false
  }
}
</script>

<template>
  <div class="a-page">
    <PageHeader
      title="站点管理与控制中枢"
      desc="全功能控制：采集器脚本上传与热插拔、单站别名/角标/超时、分类与子分类控制、详情页广告清洗与线路别名映射。"
    >
      <template #actions>
        <ElRadioGroup v-model="viewMode" size="small" style="margin-right: 8px">
          <ElRadioButton value="cards">
            <span>卡片视图</span>
          </ElRadioButton>
          <ElRadioButton value="table">
            <span>表格视图</span>
          </ElRadioButton>
        </ElRadioGroup>
        <ElButton type="primary" :icon="Upload" @click="openUploadDialog">
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

    <div v-else class="sites-container">
      <!-- 模式 1: 现代化立体卡片网格 -->
      <div v-if="viewMode === 'cards'" class="site-cards-grid">
        <ElCard
          v-for="(site, index) in sites"
          :key="site.key"
          shadow="hover"
          class="site-card"
          :class="{ 'site-card--disabled': !site.enabled, 'site-card--open': site.health.state === 'open' }"
        >
          <!-- 卡片顶栏 -->
          <div class="site-card-header">
            <div class="site-title-box">
              <span class="site-name" :title="site.name">{{ site.name }}</span>
              <code class="site-key-badge">{{ site.key }}</code>
              <ElTag v-if="site.mode === 'proxy'" size="small" type="warning" effect="plain" class="mini-tag">
                反代
              </ElTag>
              <ElTag v-if="site.version" size="small" type="info" effect="plain" class="mini-badge">
                v{{ site.version }}
              </ElTag>
            </div>
            <div class="site-switch-box">
              <ElTooltip :content="site.enabled ? '已启用（用户端可见）' : '已停用（用户端不可见）'" placement="top">
                <ElSwitch
                  :model-value="site.enabled"
                  size="small"
                  :loading="busyKey === site.key"
                  :disabled="ui.readOnly"
                  @update:model-value="(val) => toggle(site, Boolean(val))"
                />
              </ElTooltip>
            </div>
          </div>

          <!-- 卡片状态与排序 -->
          <div class="site-meta-bar">
            <div class="status-indicator">
              <ElTag :type="healthState(site).tag" size="small" effect="light">
                {{ healthState(site).label }}
              </ElTag>
              <span v-if="site.health.failures" class="fail-text">
                失败 {{ site.health.failures }}/{{ site.health.fail_threshold }}
              </span>
              <span v-if="site.health.retry_after" class="retry-text">
                熔断中，约 {{ Math.ceil(site.health.retry_after) }}s 后试探
              </span>
            </div>

            <!-- 排序控制 -->
            <div class="order-control">
              <span class="a-muted order-label">位次 {{ site.sort_order }}</span>
              <ElButton
                link
                size="small"
                :disabled="ui.readOnly || site.key === firstKey"
                title="上移"
                @click="move(index, -1)"
              >
                ↑
              </ElButton>
              <ElButton
                link
                size="small"
                :disabled="ui.readOnly || site.key === lastKey"
                title="下移"
                @click="move(index, 1)"
              >
                ↓
              </ElButton>
            </div>
          </div>

          <!-- 能力清单 -->
          <div class="capabilities-box">
            <div class="cap-title a-muted">支持能力：</div>
            <div class="cap-tags">
              <ElTag
                v-for="cap in site.capabilities"
                :key="cap"
                size="small"
                class="cap-tag"
                effect="plain"
              >
                {{ cap }}
              </ElTag>
            </div>
          </div>

          <!-- 运维备忘 -->
          <div v-if="site.note" class="site-note-text" :title="site.note">
            {{ site.note }}
          </div>

          <ElDivider style="margin: 12px 0 10px 0" />

          <!-- 一站式运维操作栏：彻底合并单站预热、清空与配置 -->
          <div class="site-card-actions">
            <!-- 预热该源 -->
            <ElButton
              size="small"
              type="primary"
              plain
              :loading="siteActionLoading"
              title="立即抓取该站首页推荐影视与分类，秒级落入缓存并弹出成果战报"
              @click="handlePreheatSiteQuick(site.key)"
            >
              预热首页
            </ElButton>

            <!-- 清空该源缓存 -->
            <ElButton
              size="small"
              type="danger"
              plain
              :loading="siteActionLoading"
              title="仅清空该站的首页、分类与详情缓存条目"
              @click="handleClearSiteCacheQuick(site.key)"
            >
              清空缓存
            </ElButton>

            <!-- 单站高级配置 -->
            <ElButton
              size="small"
              :icon="Setting"
              @click="openAdvanced(site)"
            >
              设置
            </ElButton>

            <!-- 分类与子分类 -->
            <ElButton
              size="small"
              :icon="FolderOpened"
              @click="openCategoryDrawer(site)"
            >
              分类
            </ElButton>

            <!-- 详情页展示策略 -->
            <ElButton
              size="small"
              :icon="Operation"
              @click="openDetailPolicy(site)"
            >
              清洗
            </ElButton>

            <!-- 源码 -->
            <ElButton
              size="small"
              link
              :icon="Document"
              @click="viewCrawlerCode(site)"
            >
              源码
            </ElButton>

            <!-- 删除采集器 -->
            <ElButton
              size="small"
              link
              type="danger"
              :icon="Delete"
              :disabled="ui.readOnly"
              @click="handleDeleteCrawler(site.key)"
            />
          </div>
        </ElCard>
      </div>

      <!-- 模式 2: 表格视图 -->
      <ElTable v-else :data="sites" size="default" class="sites-table" row-key="key">
        <!-- 顺序 -->
        <ElTableColumn label="顺序" width="100" align="center">
          <template #default="{ row, $index }">
            <div class="order-cell">
              <ElButton
                link
                size="small"
                :disabled="ui.readOnly || row.key === firstKey"
                title="上移"
                @click="move($index, -1)"
              >
                ↑
              </ElButton>
              <ElButton
                link
                size="small"
                :disabled="ui.readOnly || row.key === lastKey"
                title="下移"
                @click="move($index, 1)"
              >
                ↓
              </ElButton>
              <span class="a-muted order-num">{{ row.sort_order }}</span>
            </div>
          </template>
        </ElTableColumn>

        <!-- 站点信息（支持自定义别名与角标徽章） -->
        <ElTableColumn label="站点源" min-width="190">
          <template #default="{ row }">
            <div class="site-name-wrap">
              <span class="a-mono site-key">{{ row.key }}</span>
              <ElTag v-if="row.mode === 'proxy'" size="small" type="warning" effect="plain" class="mini-tag">
                反代
              </ElTag>
            </div>
            <div class="site-display-title">
              {{ row.name }}
            </div>
            <div v-if="row.note" class="a-muted site-note">
              {{ row.note }}
            </div>
          </template>
        </ElTableColumn>

        <!-- 用户可见 -->
        <ElTableColumn label="客户端可见" width="110" align="center">
          <template #default="{ row }">
            <ElTooltip :content="row.enabled ? '已启用（用户端正常可见）' : '已停用（用户端不可见）'" placement="top">
              <ElSwitch
                :model-value="row.enabled"
                size="small"
                :loading="busyKey === row.key"
                :disabled="ui.readOnly"
                @update:model-value="(value) => toggle(row as AdminSiteItem, Boolean(value))"
              />
            </ElTooltip>
          </template>
        </ElTableColumn>

        <!-- 健康度 -->
        <ElTableColumn label="健康状态" width="110" align="center">
          <template #default="{ row }">
            <ElTag :type="healthState(row as AdminSiteItem).tag" size="small" effect="light">
              {{ healthState(row as AdminSiteItem).label }}
            </ElTag>
            <div v-if="row.health.failures" class="a-muted sub-text">
              失败 {{ row.health.failures }}/{{ row.health.fail_threshold }}
            </div>
          </template>
        </ElTableColumn>

        <!-- 能力 -->
        <ElTableColumn label="能力清单" min-width="180">
          <template #default="{ row }">
            <div class="cap-tags">
              <ElTag v-for="item in row.capabilities" :key="item" size="small" class="cap-tag" effect="plain">
                {{ item }}
              </ElTag>
            </div>
          </template>
        </ElTableColumn>

        <!-- 核心操作控制栏 -->
        <ElTableColumn label="高级控制与策略" min-width="320" align="right">
          <template #default="{ row }">
            <div class="actions-group">
              <!-- 单站高级配置 -->
              <ElButton
                size="small"
                :icon="Setting"
                @click="openAdvanced(row as AdminSiteItem)"
              >
                单站设置
              </ElButton>

              <!-- 站点分类控制 -->
              <ElButton
                size="small"
                type="primary"
                plain
                :icon="FolderOpened"
                @click="openCategoryDrawer(row as AdminSiteItem)"
              >
                分类控制
              </ElButton>

              <!-- 详情页策略 -->
              <ElButton
                size="small"
                type="success"
                plain
                :icon="Operation"
                @click="openDetailPolicy(row as AdminSiteItem)"
              >
                详情策略
              </ElButton>

              <!-- 源码查看 -->
              <ElButton
                size="small"
                link
                :icon="Document"
                @click="viewCrawlerCode(row as AdminSiteItem)"
              >
                源码
              </ElButton>

              <!-- 删除采集器 -->
              <ElButton
                size="small"
                link
                type="danger"
                :icon="Delete"
                :disabled="ui.readOnly"
                @click="handleDeleteCrawler(row.key)"
              />
            </div>
          </template>
        </ElTableColumn>
      </ElTable>
    </div>

    <!-- ================================================================ 弹窗 1：上传采集器 -->
    <ElDialog
      v-model="isUploadVisible"
      title="部署 / 上传 Python 采集器脚本"
      width="780px"
      destroy-on-close
    >
      <ElForm label-position="top">
        <!-- 本地文件选择与拖拽上传区域 -->
        <div
          class="file-upload-dropzone"
          @dragover.prevent
          @drop.prevent="handleFileDrop"
          @click="triggerFileInput"
        >
          <input
            ref="fileInputRef"
            type="file"
            accept=".py"
            style="display: none;"
            @change="handleFileChange"
          />
          <div class="dropzone-content">
            <el-icon class="dropzone-icon"><UploadFilled /></el-icon>
            <div class="dropzone-text">
              <strong>点击选择本地 .py 文件</strong> 或直接拖拽文件到这里
            </div>
            <div class="dropzone-sub">
              选择后将自动提取站点 Key、载入完整源代码并自动执行全链路安全冒烟校验
            </div>
          </div>
          <div v-if="selectedFileName" class="selected-file-badge" @click.stop>
            <span class="file-name-tag">
              📄 已载入文件：<strong>{{ selectedFileName }}</strong>（{{ formatFileSize(selectedFileSize) }}）
            </span>
            <ElButton size="small" type="primary" link @click.stop="triggerFileInput">更换文件</ElButton>
            <ElButton size="small" type="danger" link @click.stop="clearSelectedFile">清除</ElButton>
          </div>
        </div>

        <ElFormItem label="站点 Key（英文小写下划线，对应 crawler/sites/<key>.py）" required>
          <ElInput v-model="uploadKey" placeholder="如：my_vod_site" />
        </ElFormItem>

        <ElFormItem label="采集器 Python 源代码（支持上方直接选文件载入，或在此手动粘贴与微调）" required>
          <ElInput
            v-model="uploadCode"
            type="textarea"
            :rows="14"
            placeholder="# 请在此粘贴完整的 Python 采集器脚本（必须遵循 Plove 命令行信封协议）"
            class="code-textarea"
          />
        </ElFormItem>

        <!-- 校验反馈区域 -->
        <div v-if="validateResult" class="validate-box" :class="{ 'is-ok': validateResult.valid, 'is-fail': !validateResult.valid }">
          <div class="val-title">
            {{ validateResult.valid ? '语法与协议审计通过' : '校验失败' }}
          </div>
          <div v-if="validateResult.error" class="val-err">
            {{ validateResult.error }}
          </div>
          <div v-if="validateResult.meta" class="val-meta">
            站点名称：<strong>{{ validateResult.meta.name }}</strong> | 模式：{{ validateResult.meta.mode }} | 能力：{{ (validateResult.meta.capabilities || []).join(', ') }}
          </div>
        </div>

        <ElFormItem>
          <div class="upload-options">
            <ElSwitch v-model="uploadOverwrite" active-text="允许覆盖已有文件" />
          </div>
        </ElFormItem>
      </ElForm>

      <template #footer>
        <div class="dialog-footer">
          <ElButton :loading="validating" @click="handleValidateCrawler">
            在线校验 (AST + 冒烟测试)
          </ElButton>
          <ElButton @click="isUploadVisible = false">取消</ElButton>
          <ElButton type="primary" :loading="uploading" @click="handleSaveCrawler">
            确认落盘部署
          </ElButton>
        </div>
      </template>
    </ElDialog>

    <!-- ================================================================ 弹窗 2：单站高级设置 -->
    <ElDialog
      v-model="isAdvancedVisible"
      :title="`单站高级控制 · ${currentAdvanced.key}`"
      width="560px"
      destroy-on-close
    >
      <div v-loading="advancedLoading">
        <ElForm label-position="top">
          <ElFormItem label="客户端显示别名（自定义对外站名，留空则使用源站原名）">
            <ElInput v-model="currentAdvanced.custom_name" placeholder="如：VIP蓝光秒播站" />
          </ElFormItem>

          <ElFormItem label="站点角标 / 徽章（如：4K, 极速, 推荐, 备用）">
            <ElInput v-model="currentAdvanced.badge" placeholder="如：4K极速" />
          </ElFormItem>

          <ElFormItem label="单站独立超时秒数（0 表示使用系统全局默认 20s/25s）">
            <ElInputNumber v-model="currentAdvanced.timeout_seconds" :min="0" :max="120" :step="1" />
            <span class="a-muted desc-hint">秒（慢速站可适当放宽，极速站可配置短超时以快速熔断）</span>
          </ElFormItem>

          <ElFormItem label="运维备注说明">
            <ElInput v-model="currentAdvanced.note" type="textarea" :rows="2" placeholder="填写备忘信息" />
          </ElFormItem>

          <ElDivider content-position="left">该站点独立缓存存活时间 (TTL)</ElDivider>

          <div class="cache-policy-grid">
            <ElFormItem label="首页缓存秒数">
              <ElInputNumber
                v-model="currentCachePolicy.home_ttl"
                :min="0"
                :max="86400"
                placeholder="默认 600s (0不缓存)"
                style="width: 100%"
              />
            </ElFormItem>

            <ElFormItem label="分类列表秒数">
              <ElInputNumber
                v-model="currentCachePolicy.category_ttl"
                :min="0"
                :max="86400"
                placeholder="默认 300s (0不缓存)"
                style="width: 100%"
              />
            </ElFormItem>

            <ElFormItem label="影视详情秒数">
              <ElInputNumber
                v-model="currentCachePolicy.detail_ttl"
                :min="0"
                :max="86400"
                placeholder="默认 300s (0不缓存)"
                style="width: 100%"
              />
            </ElFormItem>

            <ElFormItem label="封面/简介长效静态缓存">
              <ElInputNumber
                v-model="currentCachePolicy.long_term_static_ttl"
                :min="0"
                :max="2592000"
                :step="3600"
                placeholder="默认 86400s (24小时)"
                style="width: 100%"
              />
            </ElFormItem>
          </div>

          <div class="cache-policy-tip">
            <strong>静态元数据长效化建议</strong>：海报封面图片 URL、剧情简介、演职员等信息极少失效，推荐保持 86400 秒（24小时）乃至更高，可大幅降低源站爬虫频次并显著提升前台秒开速度。
          </div>

          <div class="site-cache-actions">
            <ElButton
              size="small"
              type="primary"
              plain
              :loading="siteActionLoading"
              @click="handlePreheatSiteQuick(currentAdvanced.key)"
            >
              立即预热该源首页并查看战报
            </ElButton>
            <ElButton
              size="small"
              type="danger"
              plain
              :loading="siteActionLoading"
              @click="handleClearSiteCacheQuick(currentAdvanced.key)"
            >
              清空该源所有缓存
            </ElButton>
          </div>
        </ElForm>
      </div>

      <template #footer>
        <ElButton @click="isAdvancedVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="advancedSaving" @click="saveAdvanced">
          保存配置
        </ElButton>
      </template>
    </ElDialog>

    <!-- ================================================================ 弹窗：单站首页预热战报报告 -->
    <ElDialog
      v-model="isPreheatReportVisible"
      :title="`预热成效成果报告 · ${preheatReport?.site_name ?? preheatReport?.site}`"
      width="680px"
      destroy-on-close
    >
      <div v-if="preheatReport" class="preheat-report-box">
        <div class="report-meta-row">
          <div class="meta-item">
            <span class="meta-label">目标站点：</span>
            <span class="meta-val font-mono">{{ preheatReport.site_name }} ({{ preheatReport.site }})</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">预热抓取耗时：</span>
            <span class="meta-val text-green font-bold">{{ preheatReport.elapsed_ms }} ms</span>
          </div>
        </div>

        <ElDivider content-position="left">
          成功装载并落入缓存的分类列表 ({{ preheatReport.categories_count }} 个)
        </ElDivider>
        <div class="cat-tags-wrap">
          <ElTag
            v-for="cat in preheatReport.categories ?? []"
            :key="cat"
            size="small"
            effect="plain"
            type="info"
          >
            {{ cat }}
          </ElTag>
          <span v-if="!preheatReport.categories?.length" class="a-muted">无单独分类返回</span>
        </div>

        <ElDivider content-position="left">
          成功预热的精选推荐片单 ({{ preheatReport.recommend_count }} 部)
        </ElDivider>
        <div class="rec-titles-wrap">
          <div
            v-for="(title, idx) in preheatReport.recommend_titles ?? []"
            :key="idx"
            class="title-badge"
          >
            <span class="badge-idx">{{ idx + 1 }}.</span>
            <span class="badge-text" :title="title">{{ title }}</span>
          </div>
          <span v-if="!preheatReport.recommend_titles?.length" class="a-muted">无推荐影片返回</span>
        </div>

        <template v-if="preheatReport.sample_posters?.length">
          <ElDivider content-position="left">抽样海报缩略图预览</ElDivider>
          <div class="sample-posters-grid">
            <div
              v-for="(img, idx) in preheatReport.sample_posters"
              :key="idx"
              class="poster-preview-card"
            >
              <img :src="img" alt="封面" loading="lazy" />
            </div>
          </div>
        </template>
      </div>

      <template #footer>
        <ElButton type="primary" @click="isPreheatReportVisible = false">已知晓关闭</ElButton>
      </template>
    </ElDialog>

    <!-- ================================================================ 抽屉 3：站点分类与子分类控制 -->
    <ElDrawer
      v-model="isCategoryDrawerVisible"
      :title="`分类与子分类控制 · ${categoryPayload.site_key}`"
      size="720px"
      destroy-on-close
    >
      <div v-loading="categoryLoading" class="category-drawer-content">
        <div class="drawer-tip">
          源站分类由爬虫返回。您可以在此<strong>屏蔽敏感/不需要的分类</strong>、<strong>重命名分类名称</strong>，或<strong>挂载二级子分类与筛选标签</strong>。
        </div>

        <div class="default-tid-bar">
          <span class="bar-label">默认推荐分类 TID：</span>
          <ElSelect v-model="categoryPayload.default_tid" placeholder="默认全部" clearable style="width: 220px;">
            <ElOption
              v-for="r in categoryPayload.rules"
              :key="r.tid"
              :label="`${r.custom_name || r.name} (${r.tid})`"
              :value="r.tid"
            />
          </ElSelect>
        </div>

        <ElDivider />

        <div class="rules-list">
          <div
            v-for="rule in categoryPayload.rules"
            :key="rule.tid"
            class="rule-card"
            :class="{ 'is-hidden': rule.hidden }"
          >
            <div class="rule-header">
              <div class="rule-title-area">
                <span class="cat-tid a-mono">#{{ rule.tid }}</span>
                <span class="cat-raw-name">{{ rule.name }}</span>
                <ElTag v-if="rule.hidden" type="danger" size="small">已隐藏</ElTag>
              </div>

              <div class="rule-actions">
                <ElSwitch
                  v-model="rule.hidden"
                  active-text="屏蔽"
                  inactive-text="展示"
                  :active-value="true"
                  :inactive-value="false"
                  size="small"
                />
              </div>
            </div>

            <div v-if="!rule.hidden" class="rule-body">
              <div class="rule-row">
                <span class="label">前台别名：</span>
                <ElInput v-model="rule.custom_name" placeholder="留空保持原名" size="small" style="width: 170px;" clearable />
                <span class="cat-preview-text">
                  前台显示：<strong :class="{ 'has-custom': !!rule.custom_name?.trim() }">{{ formatCategoryPreview(rule.name, rule.custom_name) }}</strong>
                </span>

                <span class="label ml">排序权重：</span>
                <ElInputNumber v-model="rule.sort_order" size="small" :step="1" style="width: 110px;" />
              </div>

              <!-- 二级子分类标签 -->
              <div class="subcategories-wrap">
                <div class="sub-label-row">
                  <span class="sub-label">二级子分类/筛选标签：</span>
                  <span class="sub-tip-desc">（点击胶囊切换显隐：变红即隐藏；点击 ✏️ 可重命名）</span>
                </div>
                <div class="sub-tags">
                  <div
                    v-for="sub in (rule.subcategories || [])"
                    :key="sub.tid"
                    class="sub-item-pill"
                    :class="{ 'is-hidden': sub.hidden }"
                  >
                    <div
                      class="sub-tag-body"
                      :title="sub.hidden ? '当前已隐藏（前台不展示），点击恢复展示' : '当前正常展示，点击切换为隐藏（变红）'"
                      @click="toggleSubCategoryHidden(sub)"
                    >
                      <span class="sub-status-dot" :class="sub.hidden ? 'dot-danger' : 'dot-success'" />
                      <span class="sub-title" :style="{ textDecoration: sub.hidden ? 'line-through' : 'none' }">
                        {{ formatCategoryPreview(sub.name, sub.custom_name) }}
                      </span>
                      <span class="sub-tid">#{{ sub.tid }}</span>
                      <span v-if="sub.hidden" class="sub-hidden-label">已隐藏</span>
                    </div>

                    <!-- 重命名二级分类 popover -->
                    <ElPopover trigger="click" :width="280" placement="top">
                      <template #reference>
                        <button class="sub-icon-btn edit-btn" type="button" title="重命名二级分类" @click.stop>
                          ✏️
                        </button>
                      </template>
                      <div class="sub-popover-content">
                        <div class="popover-title">重命名二级分类</div>
                        <div class="popover-orig">原名：{{ sub.name }} (#{{ sub.tid }})</div>
                        <ElInput
                          v-model="sub.custom_name"
                          placeholder="前台别名（留空保持原名）"
                          size="small"
                          clearable
                        />
                        <div class="popover-preview">
                          前台显示：<strong>{{ formatCategoryPreview(sub.name, sub.custom_name) }}</strong>
                        </div>
                      </div>
                    </ElPopover>

                    <!-- 彻底删除按钮 -->
                    <button
                      class="sub-icon-btn remove-btn"
                      type="button"
                      title="从列表中彻底移除该子分类"
                      @click.stop="removeSubCategory(rule, sub)"
                    >
                      ×
                    </button>
                  </div>
                  <span v-if="!(rule.subcategories && rule.subcategories.length)" class="a-muted no-sub">无子分类</span>
                </div>

                <!-- 添加子分类 -->
                <div class="add-sub-box">
                  <ElInput
                    v-model="getSubInput(rule.tid).tid"
                    placeholder="子分类 TID"
                    size="small"
                    style="width: 100px;"
                  />
                  <ElInput
                    v-model="getSubInput(rule.tid).name"
                    placeholder="分类原名"
                    size="small"
                    style="width: 120px;"
                  />
                  <ElInput
                    v-model="getSubInput(rule.tid).custom_name"
                    placeholder="别名（选填）"
                    size="small"
                    style="width: 110px;"
                  />
                  <ElButton
                    size="small"
                    type="primary"
                    plain
                    @click="addSubCategory(rule)"
                  >
                    添加子分类
                  </ElButton>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="drawer-footer">
          <ElButton @click="isCategoryDrawerVisible = false">取消</ElButton>
          <ElButton type="primary" :loading="categorySaving" @click="saveCategoryRules">
            保存分类配置
          </ElButton>
        </div>
      </template>
    </ElDrawer>

    <!-- ================================================================ 弹窗 4：详情页清洗策略 -->
    <ElDialog
      v-model="isDetailPolicyVisible"
      :title="`详情页展示与清洗策略 · ${detailPolicy.site_key}`"
      width="680px"
      destroy-on-close
    >
      <div v-loading="detailPolicyLoading">
        <ElForm label-position="top">
          <!-- 广告清洗黑名单 -->
          <ElFormItem label="牛皮癣广告过滤（命中关键词或正则将自动从剧名、备注与简介中剔除）">
            <div class="tags-editor">
              <ElTag
                v-for="(pat, pIdx) in (detailPolicy.ad_patterns || [])"
                :key="pIdx"
                closable
                type="danger"
                effect="plain"
                class="pat-tag"
                @close="removeAdPattern(pIdx)"
              >
                {{ pat }}
              </ElTag>
            </div>
            <div class="add-pat-row">
              <ElInput
                v-model="adPatternInput"
                placeholder="输入广告词或正则，如：关注公众号|最新无删减"
                size="small"
                @keyup.enter="addAdPattern"
              />
              <ElButton size="small" type="primary" @click="addAdPattern">添加过滤词</ElButton>
            </div>
          </ElFormItem>

          <ElDivider />

          <!-- 线路别名映射 -->
          <ElFormItem label="线路名称别名映射（将难看源站线路重命名为高大上专线）">
            <div class="overrides-table">
              <div
                v-for="(alias, orig) in (detailPolicy.line_name_overrides || {})"
                :key="orig"
                class="override-row"
              >
                <span class="a-mono orig-name">{{ orig }}</span>
                <span class="arrow">&rarr;</span>
                <span class="alias-name">{{ alias }}</span>
                <ElButton link type="danger" size="small" @click="removeLineOverride(String(orig))">删除</ElButton>
              </div>
              <div v-if="!Object.keys(detailPolicy.line_name_overrides || {}).length" class="a-muted no-sub">
                未配置映射（保持源站原样）
              </div>
            </div>
            <div class="add-line-row">
              <ElInput v-model="newLineOrig" placeholder="源站线路名（如 lzm3u8）" size="small" style="width: 200px;" />
              <ElInput v-model="newLineAlias" placeholder="映射别名（如 超清极速专线）" size="small" style="width: 220px;" />
              <ElButton size="small" type="primary" @click="addLineOverride">添加映射</ElButton>
            </div>
          </ElFormItem>

          <ElDivider />

          <!-- 集数命名 -->
          <ElFormItem label="剧集名称格式化规则">
            <ElRadioGroup v-model="detailPolicy.ep_naming_rule">
              <ElRadio value="auto">智能清洗（剔除重复剧名与长前缀，推荐）</ElRadio>
              <ElRadio value="standard">强制统一（统一格式化为「第 N 集」）</ElRadio>
              <ElRadio value="raw">原始名称（完全保留源站输出）</ElRadio>
            </ElRadioGroup>
          </ElFormItem>

          <!-- 兜底海报 -->
          <ElFormItem label="兜底海报 URL（海报为空或源站防盗链失效时兜底展示）">
            <ElInput v-model="detailPolicy.default_poster" placeholder="https://.../fallback_poster.jpg" />
          </ElFormItem>
        </ElForm>
      </div>

      <template #footer>
        <ElButton @click="isDetailPolicyVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="detailPolicySaving" @click="saveDetailPolicy">
          保存策略
        </ElButton>
      </template>
    </ElDialog>

    <!-- ================================================================ 抽屉 5：源码查看 -->
    <ElDrawer
      v-model="isCodeViewerVisible"
      :title="`采集器源码查看 · ${currentCodeKey}.py`"
      size="800px"
      destroy-on-close
    >
      <div v-loading="loadingCode" class="code-viewer-container">
        <div class="code-meta-bar">
          最后更新时间：<span class="a-mono">{{ currentCodeMtime || '—' }}</span>
        </div>
        <pre class="code-pre"><code>{{ currentCode }}</code></pre>
      </div>
    </ElDrawer>
  </div>
</template>

<style scoped>
.sites-container {
  margin-top: 16px;
  background: var(--a-card-bg, #fff);
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
}

.sites-table {
  border-radius: 8px;
}

.order-cell {
  display: flex;
  align-items: center;
  justify-content: center;
}

.order-num {
  font-size: 11px;
  margin-left: 4px;
}

.site-name-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
}

.site-key {
  font-weight: 600;
  font-size: 14px;
}

.mini-tag {
  font-size: 10px;
  height: 18px;
  padding: 0 4px;
}

.site-display-title {
  font-size: 12px;
  color: var(--el-text-color-regular);
  margin-top: 2px;
}

.site-note {
  font-size: 11px;
  margin-top: 2px;
}

.sub-text {
  font-size: 11px;
  margin-top: 2px;
}

.cap-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.cap-tag {
  margin: 0;
}

.actions-group {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

/* 校验反馈 */
.validate-box {
  margin-bottom: 16px;
  padding: 12px;
  border-radius: 6px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color);
}

.validate-box.is-ok {
  background: var(--el-color-success-light-9);
  border-color: var(--el-color-success-light-5);
  color: var(--el-color-success-dark-2);
}

.validate-box.is-fail {
  background: var(--el-color-danger-light-9);
  border-color: var(--el-color-danger-light-5);
  color: var(--el-color-danger-dark-2);
}

.val-title {
  font-weight: 600;
  margin-bottom: 4px;
}

.val-err {
  font-size: 13px;
  color: var(--el-color-danger);
}

.val-meta {
  font-size: 12px;
  margin-top: 4px;
}

.code-textarea :deep(textarea) {
  font-family: monospace;
  font-size: 13px;
  line-height: 1.5;
  background: var(--el-fill-color-light);
}

.file-upload-dropzone {
  border: 1px dashed var(--el-border-color);
  border-radius: 8px;
  background-color: var(--el-fill-color-blank);
  text-align: center;
  padding: 14px 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  margin-bottom: 14px;
}

.file-upload-dropzone:hover {
  border-color: var(--el-color-primary);
  background-color: var(--el-color-primary-light-9);
}

.dropzone-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.dropzone-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  margin-bottom: 4px;
  color: var(--el-color-primary);
}

.dropzone-icon :deep(svg),
.dropzone-icon svg {
  width: 26px !important;
  height: 26px !important;
  max-width: 26px !important;
  max-height: 26px !important;
}

.dropzone-text {
  font-size: 13px;
  color: var(--el-text-color-regular);
  margin-bottom: 2px;
}

.dropzone-text strong {
  color: var(--el-color-primary);
}

.dropzone-sub {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

.selected-file-badge {
  margin-top: 10px;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-lighter);
  padding: 4px 12px;
  border-radius: 14px;
  font-size: 12px;
}

.file-name-tag strong {
  color: var(--el-color-primary);
}

.upload-options {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.desc-hint {
  margin-left: 8px;
  font-size: 12px;
}

/* 分类抽屉 */
.drawer-tip {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
  margin-bottom: 12px;
}

.default-tid-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.bar-label {
  font-size: 13px;
  font-weight: 500;
}

.rules-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: calc(100vh - 220px);
  overflow-y: auto;
  padding-right: 6px;
}

.rule-card {
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
  transition: all 0.2s;
}

.rule-card.is-hidden {
  opacity: 0.6;
  background: var(--el-fill-color-light);
}

.rule-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.rule-title-area {
  display: flex;
  align-items: center;
  gap: 8px;
}

.cat-tid {
  font-size: 12px;
  color: var(--el-color-primary);
  font-weight: bold;
}

.cat-raw-name {
  font-weight: 500;
}

.rule-body {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--el-border-color-lighter);
}

.rule-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.rule-row .label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.rule-row .ml {
  margin-left: 12px;
}

.subcategories-wrap {
  margin-top: 8px;
  padding: 8px 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
}

.cat-preview-text {
  margin-left: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.cat-preview-text strong {
  color: var(--el-text-color-primary);
}

.cat-preview-text strong.has-custom {
  color: #409eff;
}

.sub-label-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.sub-label {
  font-size: 12px;
  font-weight: 500;
}

.sub-tip-desc {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

.sub-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.sub-item-pill {
  display: inline-flex;
  align-items: center;
  background: #ffffff;
  border: 1px solid #dcdfe6;
  border-radius: 16px;
  padding: 2px 6px 2px 10px;
  font-size: 12px;
  color: #303133;
  transition: all 0.2s ease;
  user-select: none;
}

.sub-item-pill:hover {
  border-color: #c0c4cc;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
}

/* 隐藏状态：变红 */
.sub-item-pill.is-hidden {
  background: #fef0f0;
  border-color: #fde2e2;
  color: #f56c6c;
}

.sub-tag-body {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  padding: 2px 0;
}

.sub-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
}

.dot-success {
  background-color: #67c23a;
  box-shadow: 0 0 4px rgba(103, 194, 58, 0.4);
}

.dot-danger {
  background-color: #f56c6c;
  box-shadow: 0 0 4px rgba(245, 108, 108, 0.4);
}

.sub-title {
  font-weight: 500;
}

.sub-tid {
  color: #909399;
  font-size: 11px;
}

.sub-hidden-label {
  background: #f56c6c;
  color: #fff;
  font-size: 10px;
  border-radius: 4px;
  padding: 0 4px;
  margin-left: 2px;
}

.sub-icon-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 2px 4px;
  margin-left: 4px;
  font-size: 12px;
  opacity: 0.65;
  transition: opacity 0.2s;
  border-radius: 50%;
}

.sub-icon-btn:hover {
  opacity: 1;
}

.sub-icon-btn.remove-btn {
  font-size: 14px;
  font-weight: bold;
  color: #909399;
}

.sub-icon-btn.remove-btn:hover {
  color: #f56c6c;
}

.sub-popover-content {
  font-size: 12px;
}

.popover-title {
  font-weight: 600;
  margin-bottom: 6px;
  color: #303133;
}

.popover-orig {
  color: #909399;
  margin-bottom: 8px;
}

.popover-preview {
  margin-top: 8px;
  color: #606266;
}

.popover-preview strong {
  color: #409eff;
}

.no-sub {
  font-size: 12px;
}

.add-sub-box {
  display: flex;
  gap: 6px;
}

/* 详情策略 */
.tags-editor {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.pat-tag {
  margin: 0;
}

.add-pat-row {
  display: flex;
  gap: 8px;
  width: 100%;
}

.overrides-table {
  background: var(--el-fill-color-light);
  padding: 8px 12px;
  border-radius: 6px;
  margin-bottom: 8px;
}

.override-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 0;
  font-size: 13px;
}

.arrow {
  color: var(--el-text-color-secondary);
}

.alias-name {
  color: var(--el-color-primary);
  font-weight: 500;
}

.add-line-row {
  display: flex;
  gap: 8px;
}

/* 源码查看 */
.code-viewer-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.code-meta-bar {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}

.code-pre {
  margin: 0;
  padding: 16px;
  background: var(--el-fill-color-dark, #1e1e1e);
  color: var(--el-text-color-primary, #e0e0e0);
  border-radius: 8px;
  overflow: auto;
  font-family: monospace;
  font-size: 13px;
  line-height: 1.5;
  flex: 1;
}

.cache-policy-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.cache-policy-tip {
  margin-top: 10px;
  padding: 8px 12px;
  background: rgba(59, 130, 246, 0.08);
  border-radius: 6px;
  font-size: 12px;
  color: var(--a-text-2);
  line-height: 1.5;
}

.site-cache-actions {
  display: flex;
  gap: 10px;
  margin-top: 12px;
}

.preheat-report-box {
  padding: 4px 8px;
}

.report-meta-row {
  display: flex;
  justify-content: space-between;
  background: var(--el-fill-color-light);
  padding: 10px 14px;
  border-radius: 6px;
  font-size: 13px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.meta-label {
  color: var(--a-text-2);
}

.cat-tags-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.rec-titles-wrap {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 8px;
}

.title-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--el-fill-color-lighter);
  border: 1px solid var(--el-border-color-lighter);
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 12.5px;
}

.badge-idx {
  color: var(--el-color-primary);
  font-weight: 600;
  flex-shrink: 0;
}

.badge-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sample-posters-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.poster-preview-card {
  aspect-ratio: 2/3;
  border-radius: 6px;
  overflow: hidden;
  background: #000;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.poster-preview-card img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* 现代化卡片网格系统 */
.site-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 16px;
  margin-top: 14px;
}

.site-card {
  border-radius: 10px;
  border: 1px solid var(--el-border-color-lighter);
  transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
  background: var(--el-fill-color-blank);
}

.site-card:hover {
  transform: translateY(-2px);
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.08);
}

.site-card--disabled {
  opacity: 0.65;
  background: var(--el-fill-color-lighter);
}

.site-card--open {
  border-color: var(--el-color-danger-light-3);
}

.site-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.site-title-box {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.site-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.site-key-badge {
  font-family: ui-monospace, SFMono-Regular, monospace;
  font-size: 12px;
  background: var(--el-fill-color-light);
  padding: 1px 6px;
  border-radius: 4px;
  color: var(--el-color-primary);
}

.mini-badge {
  font-size: 11px;
  height: 20px;
  line-height: 20px;
  padding: 0 6px;
}

.site-meta-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
}

.fail-text {
  font-size: 11.5px;
  color: var(--el-color-danger);
}

.retry-text {
  font-size: 11.5px;
  color: var(--el-color-warning);
}

.order-control {
  display: flex;
  align-items: center;
  gap: 4px;
}

.order-label {
  font-size: 12px;
}

.capabilities-box {
  margin-top: 10px;
}

.cap-title {
  font-size: 11.5px;
  margin-bottom: 4px;
}

.site-note-text {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-light);
  padding: 4px 8px;
  border-radius: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.site-card-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
</style>

