<script setup lang="ts">
/**
 * 图片防盗链代理总控与解密配置：
 * 1. 全局海报防盗链中继总控（卡片展示，点击弹出配置详情，支持伪装/穿透）；
 * 2. 第三方源站加密海报动态解密配置（卡片展示，点击弹出规则管理弹窗，支持动态 AES-128 Key/IV、AI 导入与在线验证）。
 */
import {
  ElAlert,
  ElButton,
  ElCard,
  ElCol,
  ElDialog,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElRadio,
  ElRadioGroup,
  ElRow,
  ElSelect,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus'
import {
  Check,
  Delete,
  Edit,
  Key,
  MagicStick,
  Plus,
  Refresh,
  Setting,
  VideoPlay,
} from '@element-plus/icons-vue'
import { computed, onMounted, reactive, ref } from 'vue'

import {
  getImageProxyConfig,
  testDecryptImage,
  updateImageProxyConfig,
} from '@/admin/api'
import { ui } from '@/admin/ui'
import { useSitesStore } from '@/stores/sites'
import type {
  ImageDecryptionRule,
  ImageProxyConfig,
  TestDecryptResult,
} from '@/api/types'

const sitesStore = useSitesStore()

const loading = ref(false)
const savingConfig = ref(false)

const config = ref<ImageProxyConfig>({
  global_proxy_enabled: false,
  disk_cache_enabled: false,
  auto_strip_referer: true,
  custom_referer: '',
  cache_max_mb: 1024,
  decryption_rules: [],
})

const rulesList = computed(() => config.value.decryption_rules || [])

// 弹窗控制
const showGlobalProxyDialog = ref(false)
const showDecryptionDialog = ref(false)

// 密码显示/隐藏状态
const showSecret = reactive<Record<string, boolean>>({})
function toggleSecret(id?: string): void {
  if (id) {
    showSecret[id] = !showSecret[id]
  }
}
function maskSecret(val?: string): string {
  if (!val) return ''
  if (val.length <= 8) return '******'
  return val.slice(0, 3) + '****' + val.slice(-3)
}

function copyRuleKey(row: ImageDecryptionRule): void {
  const text = `Key: ${row.key}${row.iv ? '\nIV: ' + row.iv : ''}`
  void navigator.clipboard.writeText(text).then(() => {
    ElMessage.success('已复制 Key / IV 到剪贴板')
  })
}

// 规则编辑/新增弹窗状态
const showRuleDialog = ref(false)
const isEditing = ref(false)
const editingIndex = ref(-1)
const domainsInput = ref('')
const ruleForm = ref<ImageDecryptionRule>({
  id: '',
  name: '',
  site_key: '',
  match_domains: [],
  algorithm: 'AES-128-CBC',
  key: '',
  iv: '',
  is_hex: false,
  enabled: true,
})

function openAddRule(): void {
  isEditing.value = false
  editingIndex.value = -1
  ruleForm.value = {
    id: 'rule_' + Math.random().toString(36).substring(2, 9),
    name: '',
    site_key: '',
    match_domains: [],
    algorithm: 'AES-128-CBC',
    key: '',
    iv: '',
    is_hex: false,
    enabled: true,
  }
  domainsInput.value = ''
  inlineTestUrl.value = ''
  inlineTestResult.value = null
  showRuleDialog.value = true
}

function openEditRule(row: ImageDecryptionRule): void {
  isEditing.value = true
  const list = config.value.decryption_rules || []
  editingIndex.value = list.findIndex(r => r.id === row.id)
  ruleForm.value = JSON.parse(JSON.stringify(row))
  domainsInput.value = (row.match_domains || []).join(', ')
  inlineTestUrl.value = ''
  inlineTestResult.value = null
  showRuleDialog.value = true
}

function fillHuangguoaiSample(): void {
  ruleForm.value.name = '黄果艾加密封面 (wirqed.cn)'
  ruleForm.value.site_key = 'huangguoai_com'
  domainsInput.value = 'pic.wirqed.cn, wirqed.cn'
  ruleForm.value.algorithm = 'AES-128-CBC'
  ruleForm.value.key = 'f5d965df75336270'
  ruleForm.value.iv = '97b60394abc2fbe1'
  ruleForm.value.is_hex = false
  inlineTestUrl.value = 'https://pic.wirqed.cn/upload_01/upload/20260924/2026092411173970764.jpg?auth_key=1791087038-0-0-b93f245a9dc5c1483727b54bbf5f1804'
  ElMessage.info('已填入官方示例配置')
}

async function handleSaveRule(): Promise<void> {
  if (!ruleForm.value.key?.trim()) {
    ElMessage.warning('请输入解密密钥 Key')
    return
  }
  if (ruleForm.value.algorithm === 'AES-128-CBC' && !ruleForm.value.iv?.trim()) {
    ElMessage.warning('AES-128-CBC 模式必须填写 16 字节偏移量 IV')
    return
  }

  const domains = domainsInput.value
    .split(/[,，\s]+/)
    .map(d => d.trim())
    .filter(Boolean)
  ruleForm.value.match_domains = domains

  if (!config.value.decryption_rules) {
    config.value.decryption_rules = []
  }

  if (isEditing.value && editingIndex.value >= 0) {
    config.value.decryption_rules[editingIndex.value] = { ...ruleForm.value }
  } else {
    config.value.decryption_rules.push({ ...ruleForm.value })
  }

  showRuleDialog.value = false
  await handleSaveConfig()
  ElMessage.success('已保存站点图片解密规则并更新配置！')
}

async function handleDeleteRule(row: ImageDecryptionRule): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定删除解密规则【${row.name || row.id}】吗？删除后该图床图片可能无法解密。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
    })
    const list = config.value.decryption_rules || []
    config.value.decryption_rules = list.filter(r => r.id !== row.id)
    await handleSaveConfig()
    ElMessage.success('已删除解密规则')
  } catch {
    // cancel
  }
}

async function handleToggleRule(): Promise<void> {
  await handleSaveConfig()
}

// 弹窗现场验证 (Inline Test)
const inlineTestUrl = ref('')
const inlineTesting = ref(false)
const inlineTestResult = ref<TestDecryptResult | null>(null)

async function runInlineTest(): Promise<void> {
  let url = inlineTestUrl.value.trim().replace(/^['"`]+|['"`]+$/g, '')
  if (!url) {
    ElMessage.warning('请输入待测试的加密图片链接')
    return
  }
  if (url.startsWith('//')) {
    url = 'https:' + url
  } else if (!url.startsWith('http://') && !url.startsWith('https://') && !url.includes('://')) {
    url = 'https://' + url
  }
  inlineTestUrl.value = url
  inlineTesting.value = true
  inlineTestResult.value = null
  try {
    const domains = domainsInput.value.split(/[,，\s]+/).map(d => d.trim()).filter(Boolean)
    const tempRule: ImageDecryptionRule = {
      ...ruleForm.value,
      match_domains: domains,
    }
    const res = await testDecryptImage({
      url,
      site_key: ruleForm.value.site_key,
      rule: tempRule,
    })
    inlineTestResult.value = res
    if (res.success) {
      ElMessage.success('验证成功！' + res.message)
    } else {
      ElMessage.error(res.message)
    }
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '测试解密请求失败')
  } finally {
    inlineTesting.value = false
  }
}

// AI 逆向结果一键智能导入
const showAiImportDialog = ref(false)
const aiImportText = ref('')

function openAiImport(): void {
  aiImportText.value = ''
  showAiImportDialog.value = true
}

function handleParseAiJson(): void {
  const raw = aiImportText.value.trim()
  if (!raw) {
    ElMessage.warning('请粘贴 AI 逆向输出的 JSON 块或文本')
    return
  }

  let parsed: any = null
  const jsonBlock = raw.match(/```(?:json)?\s*([\s\S]*?)\s*```/)
  const candidate = jsonBlock ? jsonBlock[1].trim() : raw

  try {
    parsed = JSON.parse(candidate)
  } catch {
    parsed = {}
    const mKey = raw.match(/["']?key["']?\s*[:=]\s*["']([a-zA-Z0-9_\-+=/]{16,64})["']/i)
    const mIv = raw.match(/["']?iv["']?\s*[:=]\s*["']([a-zA-Z0-9_\-+=/]{16,64})["']/i)
    const mSite = raw.match(/["']?site_key["']?\s*[:=]\s*["']([a-zA-Z0-9_]+)["']/i)
    const mName = raw.match(/["']?name["']?\s*[:=]\s*["']([^"']+)["']/i)
    const mAlgo = raw.match(/["']?algorithm["']?\s*[:=]\s*["'](AES-128-(?:CBC|ECB))["']/i)
    if (mKey) parsed.key = mKey[1]
    if (mIv) parsed.iv = mIv[1]
    if (mSite) parsed.site_key = mSite[1]
    if (mName) parsed.name = mName[1]
    if (mAlgo) parsed.algorithm = mAlgo[1]
  }

  if (!parsed || !parsed.key) {
    ElMessage.error('未能从粘贴内容中识别到有效的 Key 密钥，请检查内容')
    return
  }

  isEditing.value = false
  editingIndex.value = -1
  ruleForm.value = {
    id: 'rule_' + Math.random().toString(36).substring(2, 9),
    name: parsed.name || (parsed.site_key ? `${parsed.site_key}加密封面` : 'AI 逆向新规则'),
    site_key: parsed.site_key || '',
    match_domains: Array.isArray(parsed.match_domains) ? parsed.match_domains : [],
    algorithm: parsed.algorithm || 'AES-128-CBC',
    key: parsed.key || '',
    iv: parsed.iv || '',
    is_hex: Boolean(parsed.is_hex),
    enabled: true,
  }
  domainsInput.value = (ruleForm.value.match_domains || []).join(', ')
  inlineTestUrl.value = ''
  inlineTestResult.value = null

  showAiImportDialog.value = false
  showRuleDialog.value = true
  ElMessage.success('已成功提取 AI 密钥！请核对参数并进行解密测试')
}

// 独立解密测试弹窗
const showTestModal = ref(false)
const testModalRule = ref<ImageDecryptionRule | null>(null)
const testModalUrl = ref('')
const testModalLoading = ref(false)
const testModalResult = ref<TestDecryptResult | null>(null)

function openTestRuleModal(row: ImageDecryptionRule): void {
  testModalRule.value = row
  testModalResult.value = null
  if (row.match_domains && row.match_domains.some(d => d.includes('wirqed.cn'))) {
    testModalUrl.value = 'https://pic.wirqed.cn/upload_01/upload/20260924/2026092411173970764.jpg?auth_key=1791087038-0-0-b93f245a9dc5c1483727b54bbf5f1804'
  } else {
    testModalUrl.value = ''
  }
  showTestModal.value = true
}

async function runModalTest(): Promise<void> {
  let url = testModalUrl.value.trim().replace(/^['"`]+|['"`]+$/g, '')
  if (!url) {
    ElMessage.warning('请输入待测试的加密图片链接')
    return
  }
  if (url.startsWith('//')) {
    url = 'https:' + url
  } else if (!url.startsWith('http://') && !url.startsWith('https://') && !url.includes('://')) {
    url = 'https://' + url
  }
  testModalUrl.value = url
  testModalLoading.value = true
  testModalResult.value = null
  try {
    const res = await testDecryptImage({
      url,
      site_key: testModalRule.value?.site_key,
      rule: testModalRule.value || undefined,
    })
    testModalResult.value = res
    if (res.success) {
      ElMessage.success('解密成功！')
    } else {
      ElMessage.error(res.message)
    }
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '测试解密请求异常')
  } finally {
    testModalLoading.value = false
  }
}

function onCopyRule(row: any): void {
  copyRuleKey(row as ImageDecryptionRule)
}

function onTestRule(row: any): void {
  openTestRuleModal(row as ImageDecryptionRule)
}

function onEditRule(row: any): void {
  openEditRule(row as ImageDecryptionRule)
}

function onDeleteRule(row: any): void {
  void handleDeleteRule(row as ImageDecryptionRule)
}

async function loadData(): Promise<void> {
  loading.value = true
  try {
    const cfg = await getImageProxyConfig()
    config.value = cfg
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '加载图片代理配置失败')
  } finally {
    loading.value = false
  }
}

async function handleSaveConfig(): Promise<void> {
  savingConfig.value = true
  try {
    config.value.disk_cache_enabled = false
    const res = await updateImageProxyConfig(config.value)
    config.value = res
    ElMessage.success(
      res.global_proxy_enabled
        ? '已开启全局海报防盗链中继：前台所有海报自动经由服务端代理'
        : '已保存防盗链设置（当前处于原图直连模式）'
    )
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '保存配置失败')
  } finally {
    savingConfig.value = false
  }
}

async function handleSaveConfigAndCloseDialog(): Promise<void> {
  await handleSaveConfig()
  showGlobalProxyDialog.value = false
}

onMounted(() => {
  void loadData()
})
</script>

<template>
  <div class="proxy-page">
    <!-- 顶栏标题 -->
    <div class="header-section">
      <div>
        <h2 class="title">图片防盗链代理</h2>
        <p class="subtitle">
          解决第三方影视站/图床开启防盗链导致前台海报 403 破图问题。支持 Referer 伪装与穿透，以及第三方源站加密海报动态流式解密。
        </p>
      </div>
      <div class="header-actions">
        <ElButton :icon="Refresh" :loading="loading" @click="loadData">刷新状态</ElButton>
      </div>
    </div>

    <!-- 核心板块卡片矩阵 (全卡片化设计) -->
    <div class="cards-grid">
      <!-- 卡片 1: 全局海报防盗链中继总控 -->
      <ElCard shadow="hover" class="module-card relay-card" @click="showGlobalProxyDialog = true">
        <div class="card-top-bar">
          <div class="card-title-group">
            <div class="card-icon-box relay-icon">
              <ElIcon :size="20"><Setting /></ElIcon>
            </div>
            <div>
              <div class="card-title">全局海报防盗链中继总控</div>
              <div class="card-subtitle">前台全站海报统一代理中继，彻底解决 403 破图</div>
            </div>
          </div>
          <ElTag :type="config.global_proxy_enabled ? 'success' : 'info'" effect="dark" class="status-tag">
            {{ config.global_proxy_enabled ? '全局中继已生效' : '原图直连（未开启）' }}
          </ElTag>
        </div>

        <div class="card-body-section">
          <div class="info-pill-grid">
            <div class="info-pill-item">
              <span class="pill-label">中继状态</span>
              <div class="pill-value-switch" @click.stop>
                <ElSwitch
                  v-model="config.global_proxy_enabled"
                  :disabled="ui.readOnly"
                  active-text="开启"
                  inactive-text="关闭"
                  @change="handleSaveConfig"
                />
              </div>
            </div>

            <div class="info-pill-item">
              <span class="pill-label">Referer 策略</span>
              <ElTag
                size="small"
                :type="config.auto_strip_referer ? 'success' : 'info'"
                effect="plain"
                class="pill-tag"
              >
                {{ config.auto_strip_referer ? '伪装' : '穿透' }}
              </ElTag>
            </div>

            <div class="info-pill-item">
              <span class="pill-label">伪装 Referer</span>
              <span class="pill-value-text" :title="config.custom_referer || '自动同源 (Host)'">
                {{ config.custom_referer ? config.custom_referer : '自动同源 (Host)' }}
              </span>
            </div>
          </div>
        </div>

        <div class="card-bottom-bar">
          <span class="card-hint-text">点击卡片查看与调整中继详情参数</span>
          <ElButton
            type="primary"
            link
            :icon="Setting"
            @click.stop="showGlobalProxyDialog = true"
          >
            配置详情 →
          </ElButton>
        </div>
      </ElCard>

      <!-- 卡片 2: 第三方源站加密海报动态解密配置 -->
      <ElCard shadow="hover" class="module-card decrypt-card" @click="showDecryptionDialog = true">
        <div class="card-top-bar">
          <div class="card-title-group">
            <div class="card-icon-box decrypt-icon">
              <ElIcon :size="20"><Key /></ElIcon>
            </div>
            <div>
              <div class="card-title">第三方源站加密海报动态解密配置</div>
              <div class="card-subtitle">支持 AES-128 等前端加密海报流式解密，无需修改源码</div>
            </div>
          </div>
          <ElTag type="warning" effect="dark" class="status-tag">
            {{ rulesList.filter(r => r.enabled).length }} / {{ rulesList.length }} 规则生效中
          </ElTag>
        </div>

        <div class="card-body-section">
          <div class="info-pill-grid">
            <div class="info-pill-item">
              <span class="pill-label">已配置规则</span>
              <span class="pill-value-number">{{ rulesList.length }} <small>条</small></span>
            </div>

            <div class="info-pill-item">
              <span class="pill-label">算法支持</span>
              <span class="pill-value-text">AES-128-CBC / ECB</span>
            </div>

            <div class="info-pill-item">
              <span class="pill-label">特征站点/图床</span>
              <span class="pill-value-text">
                {{ rulesList.length > 0 ? (rulesList[0].site_key || rulesList[0].match_domains?.[0] || '通用图床') : '暂无规则' }}
                <span v-if="rulesList.length > 1" style="opacity: 0.6;"> +{{ rulesList.length - 1 }}</span>
              </span>
            </div>
          </div>
        </div>

        <div class="card-bottom-bar">
          <div class="quick-btn-group" @click.stop>
            <ElButton
              size="small"
              type="warning"
              plain
              :icon="MagicStick"
              @click.stop="openAiImport"
            >
              AI 导入
            </ElButton>
            <ElButton
              size="small"
              type="primary"
              plain
              :icon="Plus"
              :disabled="ui.readOnly"
              @click.stop="openAddRule"
            >
              添加规则
            </ElButton>
          </div>
          <ElButton
            type="primary"
            link
            @click.stop="showDecryptionDialog = true"
          >
            管理解密规则 →
          </ElButton>
        </div>
      </ElCard>
    </div>

    <!-- 弹窗 1: 全局海报防盗链中继总控详情 -->
    <ElDialog
      v-model="showGlobalProxyDialog"
      title="全局海报防盗链中继总控详情"
      width="640px"
      destroy-on-close
    >
      <ElAlert
        type="info"
        show-icon
        :closable="false"
        style="margin-bottom: 20px;"
      >
        <template #title>
          <span style="font-weight: 600;">关于图片防盗链机制说明：</span>
        </template>
        开启「全局海报防盗链中继」后，<strong>前台全站（首页、分类大厅、详情页）的所有影视海报将自动通过本站代理中继</strong>，
        服务端会自动剥离敏感请求头、并按设定伪装或穿透 Referer。<strong>无需为任何单部影片单独设置！</strong>
      </ElAlert>

      <ElForm :model="config" label-position="top">
        <div class="detail-switch-row">
          <div class="switch-info">
            <div class="switch-title">全局开启海报防盗链中继</div>
            <div class="switch-desc">
              开启后，前台影视海报均通过 <code>/api/v1/proxy/image</code> 中继加速，彻底杜绝 403 破图
            </div>
          </div>
          <ElSwitch
            v-model="config.global_proxy_enabled"
            :disabled="ui.readOnly"
            active-text="开启"
            inactive-text="关闭"
          />
        </div>

        <ElFormItem label="Referer 处理策略" style="margin-top: 18px;">
          <ElRadioGroup v-model="config.auto_strip_referer" :disabled="ui.readOnly">
            <ElRadio :value="true">
              <span style="font-weight: 600;">伪装</span>
              <span class="radio-desc">（自动将 Referer 伪装为源站域名，突破大多数防盗链白名单机制）</span>
            </ElRadio>
            <ElRadio :value="false">
              <span style="font-weight: 600;">穿透</span>
              <span class="radio-desc">（直接穿透，不伪造 Referer 请求头）</span>
            </ElRadio>
          </ElRadioGroup>
        </ElFormItem>

        <ElFormItem label="自定义全局伪装 Referer（选填）" style="margin-top: 18px;">
          <ElInput
            v-model="config.custom_referer"
            placeholder="留空时自动提取图片 URL 的 host 域名作为同源 Referer"
            :disabled="ui.readOnly"
            clearable
          />
        </ElFormItem>
      </ElForm>

      <template #footer>
        <div class="dialog-footer">
          <ElButton @click="showGlobalProxyDialog = false">取消</ElButton>
          <ElButton
            type="primary"
            :icon="Check"
            :loading="savingConfig"
            :disabled="ui.readOnly"
            @click="handleSaveConfigAndCloseDialog"
          >
            保存并应用配置
          </ElButton>
        </div>
      </template>
    </ElDialog>

    <!-- 弹窗 2: 第三方源站加密海报动态解密配置详情管理 -->
    <ElDialog
      v-model="showDecryptionDialog"
      title="第三方源站加密海报动态解密配置"
      width="1180px"
      destroy-on-close
    >
      <ElAlert
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px;"
      >
        当源站（如黄果艾、新抓取站点）对海报进行了 AES-128 等前端加密时，在此配置对应密钥与图床域名，系统自动流式解密，无需修改任何 Python 源码。
      </ElAlert>

      <div class="decryption-toolbar">
        <div class="toolbar-left">
          <span class="toolbar-title">解密规则列表</span>
          <ElTag size="small" type="info" effect="plain">{{ rulesList.length }} 条规则</ElTag>
        </div>
        <div class="toolbar-actions">
          <ElButton
            type="warning"
            plain
            :icon="MagicStick"
            @click="openAiImport"
          >
            一键导入 AI 逆向结果
          </ElButton>
          <ElButton
            type="primary"
            :icon="Plus"
            :disabled="ui.readOnly"
            @click="openAddRule"
          >
            添加解密规则
          </ElButton>
        </div>
      </div>

      <div class="decryption-table-wrap">
        <ElTable :data="rulesList" stripe style="width: 100%" empty-text="暂无解密规则，点击上方按钮添加或一键导入">
          <ElTableColumn prop="name" label="规则名称" min-width="160">
            <template #default="{ row }">
              <span class="rule-name-text">{{ row.name || '未命名规则' }}</span>
              <div v-if="row.id" class="rule-id-text">ID: {{ row.id }}</div>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="site_key" label="适用站点" min-width="130" align="center">
            <template #default="{ row }">
              <ElTag v-if="row.site_key" type="success" size="small">{{ row.site_key }}</ElTag>
              <ElTag v-else type="info" size="small">全站匹配</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="match_domains" label="匹配图床域名" min-width="160">
            <template #default="{ row }">
              <div v-if="row.match_domains && row.match_domains.length > 0" class="tags-cluster">
                <ElTag v-for="d in row.match_domains" :key="d" size="small" effect="plain">{{ d }}</ElTag>
              </div>
              <span v-else style="color: var(--a-text-3, #94a3b8); font-size: 12px;">该站点全部图片</span>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="algorithm" label="解密算法" min-width="140" align="center">
            <template #default="{ row }">
              <ElTag size="small" effect="dark" type="warning" class="algo-tag">{{ row.algorithm || 'AES-128-CBC' }}</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn label="密钥 (Key / IV)" min-width="230">
            <template #default="{ row }">
              <div class="cipher-keys-display">
                <div class="cipher-row">
                  <span class="cipher-label">Key:</span>
                  <code class="cipher-val" :title="row.key">{{ showSecret[row.id] ? row.key : maskSecret(row.key) }}</code>
                </div>
                <div v-if="row.iv" class="cipher-row">
                  <span class="cipher-label">IV:</span>
                  <code class="cipher-val" :title="row.iv">{{ showSecret[row.id] ? row.iv : maskSecret(row.iv) }}</code>
                </div>
                <div class="cipher-actions">
                  <ElButton
                    link
                    type="primary"
                    size="small"
                    @click="toggleSecret(row.id)"
                  >
                    {{ showSecret[row.id] ? '隐藏' : '显示' }}
                  </ElButton>
                  <ElButton
                    link
                    type="primary"
                    size="small"
                    @click="onCopyRule(row)"
                  >
                    复制
                  </ElButton>
                </div>
              </div>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="enabled" label="状态" width="85" align="center">
            <template #default="{ row }">
              <ElSwitch
                v-model="row.enabled"
                :disabled="ui.readOnly"
                inline-prompt
                active-text="开"
                inactive-text="关"
                @change="handleToggleRule"
              />
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" min-width="195" width="195" align="center">
            <template #default="{ row }">
              <div class="table-ops-group">
                <ElButton
                  size="small"
                  type="primary"
                  link
                  :icon="VideoPlay"
                  @click="onTestRule(row)"
                >
                  验证
                </ElButton>
                <ElButton
                  size="small"
                  type="primary"
                  link
                  :icon="Edit"
                  :disabled="ui.readOnly"
                  @click="onEditRule(row)"
                >
                  编辑
                </ElButton>
                <ElButton
                  size="small"
                  type="danger"
                  link
                  :icon="Delete"
                  :disabled="ui.readOnly"
                  @click="onDeleteRule(row)"
                >
                  删除
                </ElButton>
              </div>
            </template>
          </ElTableColumn>
        </ElTable>
      </div>

      <template #footer>
        <ElButton @click="showDecryptionDialog = false">关闭</ElButton>
      </template>
    </ElDialog>

    <!-- 子弹窗 1: 添加/编辑解密规则 -->
    <ElDialog
      v-model="showRuleDialog"
      :title="isEditing ? '编辑图片解密规则' : '添加站点图片解密规则'"
      width="680px"
      destroy-on-close
    >
      <ElForm :model="ruleForm" label-position="top">
        <ElRow :gutter="16">
          <ElCol :span="14">
            <ElFormItem label="规则名称 / 备注" required>
              <ElInput v-model="ruleForm.name" placeholder="例如：黄果艾加密封面 (wirqed.cn)" />
            </ElFormItem>
          </ElCol>
          <ElCol :span="10">
            <ElFormItem label="关联目标站点（选填）">
              <ElSelect
                v-model="ruleForm.site_key"
                filterable
                allow-create
                default-first-option
                clearable
                placeholder="选择已有站点或输入 key"
                style="width: 100%"
              >
                <ElOption
                  v-for="s in sitesStore.sites"
                  :key="s.key"
                  :label="`${s.name} (${s.key})`"
                  :value="s.key"
                />
              </ElSelect>
            </ElFormItem>
          </ElCol>
        </ElRow>

        <ElFormItem label="匹配加密图床域名（特征白名单，多个用逗号隔开）">
          <ElInput
            v-model="domainsInput"
            placeholder="例如：pic.wirqed.cn, wirqed.cn（留空则对该站点的所有图片生效）"
          />
        </ElFormItem>

        <ElRow :gutter="16">
          <ElCol :span="12">
            <ElFormItem label="解密算法" required>
              <ElRadioGroup v-model="ruleForm.algorithm">
                <ElRadio value="AES-128-CBC">AES-128-CBC (最常见)</ElRadio>
                <ElRadio value="AES-128-ECB">AES-128-ECB</ElRadio>
              </ElRadioGroup>
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem label="密钥格式">
              <ElSwitch
                v-model="ruleForm.is_hex"
                active-text="Hex 十六进制编码"
                inactive-text="普通 UTF-8 字符串"
              />
            </ElFormItem>
          </ElCol>
        </ElRow>

        <ElRow :gutter="16">
          <ElCol :span="12">
            <ElFormItem label="解密密钥 Key" required>
              <ElInput
                v-model="ruleForm.key"
                placeholder="例如：f5d965df75336270"
                clearable
              />
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem
              label="偏移量 IV"
              :required="ruleForm.algorithm === 'AES-128-CBC'"
            >
              <ElInput
                v-model="ruleForm.iv"
                placeholder="例如：97b60394abc2fbe1 (CBC模式需16字符)"
                clearable
              />
            </ElFormItem>
          </ElCol>
        </ElRow>

        <!-- 现场快速测试验证沙盒 -->
        <div class="inline-test-box">
          <div class="inline-test-header">
            <span>现场验证此规则（推荐）</span>
            <ElButton link size="small" type="primary" @click="fillHuangguoaiSample">
              填入官方范例
            </ElButton>
          </div>
          <div class="inline-test-input-row">
            <ElInput
              v-model="inlineTestUrl"
              size="small"
              placeholder="输入加密图片 URL 进行实时解密测试（若图床开启动态鉴权请粘贴包含 ?auth_key= 的完整地址）"
              clearable
            />
            <ElButton
              size="small"
              type="warning"
              :loading="inlineTesting"
              @click="runInlineTest"
            >
              验证密钥
            </ElButton>
          </div>

          <div v-if="inlineTestResult" class="inline-test-result">
            <ElAlert
              :type="inlineTestResult.success ? 'success' : 'error'"
              :closable="false"
              show-icon
            >
              <template #title>
                <span>{{ inlineTestResult.message }}</span>
              </template>
            </ElAlert>
            <div v-if="inlineTestResult.preview_data_url" class="inline-preview-wrap">
              <img :src="inlineTestResult.preview_data_url" alt="解密预览" class="inline-img" />
              <div class="inline-img-meta">
                <div>格式: <b>{{ inlineTestResult.mime_type }}</b></div>
                <div>大小: <b>{{ (((inlineTestResult.size_bytes || 0)) / 1024).toFixed(1) }} KB</b></div>
                <div>耗时: <b>{{ inlineTestResult.elapsed_ms }} ms</b></div>
              </div>
            </div>
          </div>
        </div>
      </ElForm>

      <template #footer>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <ElSwitch
            v-model="ruleForm.enabled"
            active-text="启用规则"
            inactive-text="关闭"
          />
          <div>
            <ElButton @click="showRuleDialog = false">取消</ElButton>
            <ElButton type="primary" :disabled="ui.readOnly" @click="handleSaveRule">
              保存规则
            </ElButton>
          </div>
        </div>
      </template>
    </ElDialog>

    <!-- 子弹窗 2: AI 逆向结果一键智能导入 -->
    <ElDialog
      v-model="showAiImportDialog"
      title="粘贴导入 AI 逆向输出的解密配置"
      width="600px"
    >
      <ElAlert
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 12px;"
      >
        将 ChatGPT / DeepSeek / Claude 回复给您的 JSON 配置块或包含 key/iv 的文本直接粘贴在下方，系统会自动识别提取并为您填好表单！
      </ElAlert>
      <ElInput
        v-model="aiImportText"
        type="textarea"
        :rows="8"
        placeholder='示例直接粘贴：
{
  "site_key": "my_new_site",
  "match_domains": ["pic.example.com"],
  "algorithm": "AES-128-CBC",
  "key": "f5d965df75336270",
  "iv": "97b60394abc2fbe1"
}'
      />
      <template #footer>
        <ElButton @click="showAiImportDialog = false">取消</ElButton>
        <ElButton type="primary" :icon="MagicStick" @click="handleParseAiJson">
          智能解析并填入规则
        </ElButton>
      </template>
    </ElDialog>

    <!-- 子弹窗 3: 独立解密在线测试 -->
    <ElDialog
      v-model="showTestModal"
      :title="`解密验证: ${testModalRule?.name || testModalRule?.id}`"
      width="600px"
    >
      <div v-if="testModalRule" class="modal-rule-info">
        <div class="info-row">
          <span>所属站点:</span>
          <b>{{ testModalRule.site_key || '通用' }}</b>
        </div>
        <div class="info-row">
          <span>算法 / Key:</span>
          <code>{{ testModalRule.algorithm }} | {{ testModalRule.key }}</code>
        </div>
      </div>

      <div style="margin-top: 14px;">
        <ElFormItem label="待验证的图片 URL">
          <div style="display: flex; gap: 8px; width: 100%;">
            <ElInput
              v-model="testModalUrl"
              placeholder="输入目标加密图床图片 URL（若图床开启鉴权需带完整 ?auth_key= 等参数）"
              clearable
            />
            <ElButton
              type="primary"
              :loading="testModalLoading"
              :icon="VideoPlay"
              @click="runModalTest"
            >
              执行解密
            </ElButton>
          </div>
        </ElFormItem>
      </div>

      <div v-if="testModalResult" style="margin-top: 14px;">
        <ElAlert
          :type="testModalResult.success ? 'success' : 'error'"
          :closable="false"
          show-icon
        >
          <template #title>
            <span>{{ testModalResult.message }}</span>
          </template>
        </ElAlert>

        <div v-if="testModalResult.preview_data_url" class="test-modal-preview">
          <img :src="testModalResult.preview_data_url" alt="解密成功预览" class="modal-preview-img" />
          <div class="modal-preview-meta">
            <div>MIME 类型: <b>{{ testModalResult.mime_type }}</b></div>
            <div>图片大小: <b>{{ (((testModalResult.size_bytes || 0)) / 1024).toFixed(1) }} KB</b></div>
            <div>解密耗时: <b>{{ testModalResult.elapsed_ms }} ms</b></div>
          </div>
        </div>
      </div>

      <template #footer>
        <ElButton @click="showTestModal = false">关闭</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.proxy-page {
  padding: 24px 32px;
  max-width: 1440px;
  margin: 0 auto;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
}

.header-section {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 4px;
}

.title {
  margin: 0 0 6px;
  font-size: 20px;
  font-weight: 700;
  color: var(--a-text, #1e293b);
}

.subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--a-text-2, #64748b);
  line-height: 1.6;
}

/* 卡片栅格 */
.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(440px, 1fr));
  gap: 20px;
  width: 100%;
}

.module-card {
  border-radius: var(--a-radius, 10px);
  border: 1px solid var(--a-border, #e2e8f0);
  background: var(--a-card, #ffffff);
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  display: flex;
  flex-direction: column;
}

.module-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  border-color: var(--el-color-primary-light-5, #93c5fd);
}

.card-top-bar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}

.card-title-group {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.card-icon-box {
  width: 38px;
  height: 38px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.relay-icon {
  background: rgba(16, 185, 129, 0.12);
  color: #059669;
}

.decrypt-icon {
  background: rgba(217, 119, 6, 0.12);
  color: #d97706;
}

.card-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--a-text, #1e293b);
  margin-bottom: 4px;
}

.card-subtitle {
  font-size: 12px;
  color: var(--a-text-2, #64748b);
  line-height: 1.5;
}

.status-tag {
  font-weight: 600;
  border-radius: 6px;
  flex-shrink: 0;
}

.card-body-section {
  flex: 1;
  margin-bottom: 16px;
}

.info-pill-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  background: var(--a-bg-subtle, #f8fafc);
  padding: 12px 14px;
  border-radius: 8px;
  border: 1px solid var(--a-border, #e2e8f0);
}

.info-pill-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.pill-label {
  font-size: 11px;
  color: var(--a-text-3, #94a3b8);
  font-weight: 500;
}

.pill-value-switch {
  display: inline-flex;
  align-items: center;
}

.pill-tag {
  align-self: flex-start;
  font-size: 12px;
}

.pill-value-text {
  font-size: 12px;
  color: var(--a-text, #1e293b);
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pill-value-number {
  font-size: 16px;
  font-weight: 700;
  color: var(--el-color-primary, #3b82f6);
}

.pill-value-number small {
  font-size: 11px;
  font-weight: normal;
  color: var(--a-text-3, #94a3b8);
}

.card-bottom-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 14px;
  border-top: 1px solid var(--a-border, #f1f5f9);
}

.card-hint-text {
  font-size: 12px;
  color: var(--a-text-3, #94a3b8);
}

.quick-btn-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 详情弹窗 */
.detail-switch-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--a-bg-subtle, #f8fafc);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: 8px;
  padding: 16px;
}

.switch-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-right: 16px;
}

.switch-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--a-text, #1e293b);
}

.switch-desc {
  font-size: 12px;
  color: var(--a-text-2, #64748b);
  line-height: 1.5;
}

.radio-desc {
  font-size: 12px;
  color: var(--a-text-2, #64748b);
  font-weight: normal;
}

/* 解密管理弹窗与工具栏 */
.decryption-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 14px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--a-text, #1e293b);
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: nowrap;
  flex-shrink: 0;
}

.rule-name-text {
  font-weight: 600;
  display: block;
  word-break: break-word;
}

.rule-id-text {
  font-size: 11px;
  color: var(--a-text-3, #94a3b8);
  font-family: monospace;
  margin-top: 2px;
}

.tags-cluster {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.algo-tag {
  font-family: monospace;
  font-weight: 600;
  letter-spacing: 0.5px;
  white-space: nowrap;
}

.cipher-keys-display {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.cipher-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.cipher-label {
  color: var(--a-text-3, #94a3b8);
  font-weight: 600;
  width: 28px;
  flex-shrink: 0;
}

.cipher-val {
  background: var(--a-bg, #f1f5f9);
  padding: 1px 6px;
  border-radius: 4px;
  font-family: monospace;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cipher-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-top: 2px;
}

.cipher-actions .el-button {
  padding: 0;
  height: auto;
  font-size: 12px;
}

.cipher-actions .el-button + .el-button {
  margin-left: 0;
}

.table-ops-group {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  white-space: nowrap;
  flex-wrap: nowrap;
}

.table-ops-group .el-button {
  padding: 4px 4px;
}

.table-ops-group .el-button + .el-button {
  margin-left: 0;
}

.decryption-table-wrap {
  overflow-x: auto;
  border-radius: 8px;
}

.inline-test-box {
  margin-top: 16px;
  padding: 12px 14px;
  background: var(--a-bg-subtle, #f8fafc);
  border: 1px dashed var(--a-border, #e2e8f0);
  border-radius: 8px;
}

.inline-test-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  font-weight: 600;
  color: var(--a-text, #1e293b);
  margin-bottom: 8px;
}

.inline-test-input-row {
  display: flex;
  gap: 8px;
}

.inline-test-result {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.inline-preview-wrap {
  display: flex;
  align-items: center;
  gap: 14px;
  background: #ffffff;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid var(--a-border, #e2e8f0);
}

.inline-img {
  width: 60px;
  height: 84px;
  object-fit: cover;
  border-radius: 4px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.inline-img-meta {
  font-size: 12px;
  color: var(--a-text-2, #64748b);
  line-height: 1.6;
}

.modal-rule-info {
  background: var(--a-bg-subtle, #f8fafc);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: 6px;
  padding: 10px 14px;
}

.info-row {
  font-size: 13px;
  display: flex;
  gap: 8px;
  margin-bottom: 4px;
}

.test-modal-preview {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 16px;
  background: #ffffff;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--a-border, #e2e8f0);
}

.modal-preview-img {
  width: 90px;
  height: 126px;
  object-fit: cover;
  border-radius: 6px;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.12);
}

.modal-preview-meta {
  font-size: 13px;
  color: var(--a-text-2, #64748b);
  line-height: 1.8;
}

@media (max-width: 768px) {
  .proxy-page {
    padding: 16px;
  }
  .cards-grid {
    grid-template-columns: 1fr;
  }
  .info-pill-grid {
    grid-template-columns: 1fr;
  }
}
</style>
