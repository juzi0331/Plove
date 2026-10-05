import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  getImageProxyConfig,
  testDecryptImage,
  updateImageProxyConfig,
} from '@/admin/api'
import type {
  ImageCdnPrefixRule,
  ImageDecryptionRule,
  ImageProxyConfig,
  TestDecryptResult,
} from '@/api/types'

export function useImageProxy() {
  const loading = ref(false)
  const savingConfig = ref(false)

  const config = ref<ImageProxyConfig>({
    global_proxy_enabled: false,
    disk_cache_enabled: false,
    auto_strip_referer: true,
    custom_referer: '',
    cache_max_mb: 1024,
    decryption_rules: [],
    cdn_prefix_rules: [],
  })

  const rulesList = computed(() => config.value.decryption_rules || [])
  const cdnRulesList = computed(() => config.value.cdn_prefix_rules || [])

  // 弹窗控制
  const showGlobalProxyDialog = ref(false)
  const showDecryptionDialog = ref(false)
  const showCdnPrefixDialog = ref(false)

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
        ElMessage.success('解密测试成功！')
      } else {
        ElMessage.error(res.message)
      }
    } catch (err) {
      ElMessage.error(err instanceof Error ? err.message : '解密请求失败')
    } finally {
      testModalLoading.value = false
    }
  }

  // CDN 前缀规则编辑/管理状态
  const showCdnRuleEditDialog = ref(false)
  const isEditingCdnRule = ref(false)
  const editingCdnRuleIndex = ref(-1)
  const cdnRuleForm = ref<ImageCdnPrefixRule>({
    id: '',
    name: '',
    site_key: '',
    match_domain: '',
    prefix: 'https://wsrv.nl/?url=',
    enabled: true,
  })

  function openAddCdnRule(): void {
    isEditingCdnRule.value = false
    editingCdnRuleIndex.value = -1
    cdnRuleForm.value = {
      id: `prefix_${Date.now().toString(36)}`,
      name: '',
      site_key: '',
      match_domain: '',
      prefix: 'https://wsrv.nl/?url=',
      enabled: true,
    }
    showCdnRuleEditDialog.value = true
  }

  function openEditCdnRule(row: ImageCdnPrefixRule, idx: number): void {
    isEditingCdnRule.value = true
    editingCdnRuleIndex.value = idx
    cdnRuleForm.value = { ...row }
    showCdnRuleEditDialog.value = true
  }

  async function handleSaveCdnRule(): Promise<void> {
    if (!cdnRuleForm.value.name.trim()) {
      ElMessage.warning('请输入规则名称')
      return
    }
    if (!cdnRuleForm.value.prefix.trim()) {
      ElMessage.warning('请输入代理前缀（如 https://wsrv.nl/?url=）')
      return
    }
    const rules = [...(config.value.cdn_prefix_rules || [])]
    if (isEditingCdnRule.value && editingCdnRuleIndex.value >= 0) {
      rules[editingCdnRuleIndex.value] = { ...cdnRuleForm.value }
    } else {
      rules.push({ ...cdnRuleForm.value })
    }
    config.value.cdn_prefix_rules = rules
    await handleSaveConfig()
    showCdnRuleEditDialog.value = false
    ElMessage.success('图床加速前缀规则已保存')
  }

  async function handleDeleteCdnRule(idx: number): Promise<void> {
    try {
      await ElMessageBox.confirm('确定要删除该条图床加速规则吗？', '提示', {
        type: 'warning',
      })
      const rules = [...(config.value.cdn_prefix_rules || [])]
      rules.splice(idx, 1)
      config.value.cdn_prefix_rules = rules
      await handleSaveConfig()
      ElMessage.success('已删除规则')
    } catch {
      // 用户取消
    }
  }

  async function handleToggleCdnRule(): Promise<void> {
    await handleSaveConfig()
  }

  async function loadData(): Promise<void> {
    loading.value = true
    try {
      const cfg = await getImageProxyConfig()
      config.value = {
        global_proxy_enabled: Boolean(cfg.global_proxy_enabled),
        disk_cache_enabled: Boolean(cfg.disk_cache_enabled),
        auto_strip_referer: cfg.auto_strip_referer !== false,
        custom_referer: cfg.custom_referer || '',
        cache_max_mb: cfg.cache_max_mb || 1024,
        decryption_rules: cfg.decryption_rules || [],
        cdn_prefix_rules: cfg.cdn_prefix_rules || [
          {
            id: 'rule_ncat21',
            name: '网飞猫图床加速',
            site_key: 'www_ncat21_com',
            match_domain: 'vres.cyscyy.com',
            prefix: 'https://wsrv.nl/?url=',
            enabled: true,
          },
        ],
        updated_at: cfg.updated_at,
      }
    } catch (err) {
      ElMessage.error(err instanceof Error ? err.message : '获取图片防盗链配置失败')
    } finally {
      loading.value = false
    }
  }

  async function handleSaveConfig(): Promise<void> {
    savingConfig.value = true
    try {
      const payload: ImageProxyConfig = {
        global_proxy_enabled: Boolean(config.value.global_proxy_enabled),
        disk_cache_enabled: Boolean(config.value.disk_cache_enabled),
        auto_strip_referer: Boolean(config.value.auto_strip_referer),
        custom_referer: config.value.custom_referer?.trim() || '',
        cache_max_mb: config.value.cache_max_mb || 1024,
        decryption_rules: config.value.decryption_rules || [],
        cdn_prefix_rules: config.value.cdn_prefix_rules || [],
      }
      const updated = await updateImageProxyConfig(payload)
      config.value = { ...config.value, ...updated }
      ElMessage.success(
        config.value.global_proxy_enabled
          ? '防盗链设置已保存！前台全站海报已进入统一中继防盗链模式'
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

  return {
    loading,
    savingConfig,
    config,
    rulesList,
    showGlobalProxyDialog,
    showDecryptionDialog,
    showSecret,
    toggleSecret,
    maskSecret,
    copyRuleKey,
    showRuleDialog,
    isEditing,
    editingIndex,
    domainsInput,
    ruleForm,
    openAddRule,
    openEditRule,
    fillHuangguoaiSample,
    handleSaveRule,
    handleDeleteRule,
    handleToggleRule,
    inlineTestUrl,
    inlineTesting,
    inlineTestResult,
    runInlineTest,
    showAiImportDialog,
    aiImportText,
    openAiImport,
    handleParseAiJson,
    showTestModal,
    testModalRule,
    testModalUrl,
    testModalLoading,
    testModalResult,
    openTestRuleModal,
    runModalTest,
    // CDN 前缀规则
    cdnRulesList,
    showCdnPrefixDialog,
    showCdnRuleEditDialog,
    isEditingCdnRule,
    editingCdnRuleIndex,
    cdnRuleForm,
    openAddCdnRule,
    openEditCdnRule,
    handleSaveCdnRule,
    handleDeleteCdnRule,
    handleToggleCdnRule,
    loadData,
    handleSaveConfig,
    handleSaveConfigAndCloseDialog,
  }
}
