<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  ElAlert,
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElOption,
  ElSelect,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTag,
  ElMessage,
} from 'element-plus'
import {
  Delete,
  Edit,
  Link,
  Plus,
  Picture,
  RefreshLeft,
  VideoPlay,
} from '@element-plus/icons-vue'
import { ui } from '@/admin/ui'
import type { AdminSiteItem, ImageCdnPrefixRule } from '@/api/types'

const props = defineProps<{
  modelValue: boolean
  cdnRulesList: ImageCdnPrefixRule[]
  showCdnRuleEditDialog: boolean
  isEditingCdnRule: boolean
  cdnRuleForm: ImageCdnPrefixRule
  availableSites?: AdminSiteItem[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'update:showCdnRuleEditDialog', val: boolean): void
  (e: 'openAddCdnRule'): void
  (e: 'openEditCdnRule', row: ImageCdnPrefixRule, idx: number): void
  (e: 'saveCdnRule'): void
  (e: 'deleteCdnRule', idx: number): void
  (e: 'toggleCdnRule'): void
}>()

// ==========================================
// 常用预设快捷填入（支持动态增删与本地持久化）
// ==========================================
interface PresetItem {
  id: string
  name: string
  prefix: string
}

const DEFAULT_PRESETS: PresetItem[] = [
  { id: 'wsrv', name: 'wsrv.nl (推荐)', prefix: 'https://wsrv.nl/?url=' },
  { id: 'weserv', name: 'images.weserv.nl', prefix: 'https://images.weserv.nl/?url=' },
  { id: 'statically', name: 'statically.io', prefix: 'https://cdn.statically.io/img/' },
]

const STORAGE_KEY = 'plove_admin_cdn_prefix_presets'

function loadPresets(): PresetItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed) && parsed.length > 0) return parsed
    }
  } catch {}
  return [...DEFAULT_PRESETS]
}

const presets = ref<PresetItem[]>(loadPresets())

function savePresets(): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(presets.value))
  } catch {}
}

function applyPreset(item: PresetItem): void {
  props.cdnRuleForm.prefix = item.prefix
  testImageLoaded.value = false
  testImageError.value = false
  ElMessage.success(`已填入预设 [${item.name}]`)
}

function deletePreset(id: string): void {
  presets.value = presets.value.filter(p => p.id !== id)
  savePresets()
  ElMessage.info('已删除该预设')
}

function resetPresets(): void {
  presets.value = [...DEFAULT_PRESETS]
  savePresets()
  ElMessage.success('已恢复默认预设')
}

// 新增预设弹窗与表单
const showAddPresetDialog = ref(false)
const newPresetName = ref('')
const newPresetPrefix = ref('')

function openAddPresetDialog(): void {
  newPresetName.value = ''
  newPresetPrefix.value = props.cdnRuleForm.prefix || 'https://'
  showAddPresetDialog.value = true
}

function handleConfirmAddPreset(): void {
  const name = newPresetName.value.trim()
  const prefix = newPresetPrefix.value.trim()
  if (!name) {
    ElMessage.warning('请输入预设名称')
    return
  }
  if (!prefix) {
    ElMessage.warning('请输入代理前缀 URL')
    return
  }
  const id = `preset_${Date.now().toString(36)}`
  presets.value.push({ id, name, prefix })
  savePresets()
  showAddPresetDialog.value = false
  ElMessage.success(`已新增常用预设 [${name}]`)
}

// ==========================================
// 实时测试预览状态（编辑框内默认无内容）
// ==========================================
const testUrl = ref('')
const testImageLoaded = ref(false)
const testImageError = ref(false)

const previewWrappedUrl = computed(() => {
  const prefix = props.cdnRuleForm.prefix?.trim() || ''
  const url = testUrl.value.trim()
  if (!url || !prefix) return ''
  return `${prefix}${encodeURIComponent(url)}`
})

function handleImgLoad(): void {
  testImageLoaded.value = true
  testImageError.value = false
}

function handleImgError(): void {
  testImageLoaded.value = false
  testImageError.value = true
}
</script>

<template>
  <div>
    <!-- 主弹窗: 图床加速与代理前缀规则列表 (与第三方解密弹窗完全一致的 1180px 现代风格) -->
    <ElDialog
      :model-value="props.modelValue"
      title="图床加速与代理前缀路由配置"
      width="1180px"
      align-center
      append-to-body
      destroy-on-close
      class="rule-modal-dialog"
      @update:model-value="(val: boolean) => emit('update:modelValue', val)"
    >
      <ElAlert
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px;"
      >
        为特定站点或域名指定免费公共边缘 CDN 反代（如 <code>https://wsrv.nl/?url=</code>），由 Cloudflare 全球边缘节点高速拉取并缓存海报，<b>完全不消耗本地服务器流量与 CPU</b>。
      </ElAlert>

      <div class="decryption-toolbar">
        <div class="toolbar-left">
          <span class="toolbar-title">加速规则列表</span>
          <ElTag size="small" type="info" effect="plain">{{ props.cdnRulesList.length }} 条规则</ElTag>
        </div>
        <div class="toolbar-actions">
          <ElButton
            type="primary"
            :icon="Plus"
            :disabled="ui.readOnly"
            @click="emit('openAddCdnRule')"
          >
            添加加速前缀规则
          </ElButton>
        </div>
      </div>

      <div class="decryption-table-wrap">
        <ElTable :data="props.cdnRulesList" stripe style="width: 100%" empty-text="暂无代理前缀规则，点击右上角添加">
          <ElTableColumn prop="name" label="规则名称" min-width="170">
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

          <ElTableColumn prop="match_domain" label="匹配图床域名" min-width="170">
            <template #default="{ row }">
              <div v-if="row.match_domain" class="tags-cluster">
                <ElTag size="small" effect="plain">{{ row.match_domain }}</ElTag>
              </div>
              <span v-else style="color: var(--a-text-3, #94a3b8); font-size: 12px;">该站点全部图片</span>
            </template>
          </ElTableColumn>

          <ElTableColumn prop="prefix" label="代理前缀" min-width="240">
            <template #default="{ row }">
              <code class="cipher-val" style="color: #4f46e5; font-weight: 600;">{{ row.prefix }}</code>
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
                @change="emit('toggleCdnRule')"
              />
            </template>
          </ElTableColumn>

          <ElTableColumn label="操作" min-width="180" width="180" align="center">
            <template #default="{ row, $index }">
              <div class="table-ops-group">
                <ElButton
                  type="primary"
                  link
                  size="small"
                  :icon="VideoPlay"
                  @click="emit('openEditCdnRule', row as ImageCdnPrefixRule, $index)"
                >
                  验证
                </ElButton>
                <ElButton
                  type="primary"
                  link
                  size="small"
                  :icon="Edit"
                  :disabled="ui.readOnly"
                  @click="emit('openEditCdnRule', row as ImageCdnPrefixRule, $index)"
                >
                  编辑
                </ElButton>
                <ElButton
                  type="danger"
                  link
                  size="small"
                  :icon="Delete"
                  :disabled="ui.readOnly"
                  @click="emit('deleteCdnRule', $index)"
                >
                  删除
                </ElButton>
              </div>
            </template>
          </ElTableColumn>
        </ElTable>
      </div>

      <template #footer>
        <ElButton @click="emit('update:modelValue', false)">关闭</ElButton>
      </template>
    </ElDialog>

    <!-- 子弹窗 1: 新增/编辑规则 (现代化卡片风二级弹窗) -->
    <ElDialog
      :model-value="props.showCdnRuleEditDialog"
      width="680px"
      align-center
      append-to-body
      destroy-on-close
      class="submodal-dialog"
      @update:model-value="(val: boolean) => emit('update:showCdnRuleEditDialog', val)"
    >
      <template #header>
        <div class="submodal-header">
          <div class="submodal-icon-badge" :class="props.isEditingCdnRule ? 'is-edit' : 'is-add'">
            <ElIcon :size="18"><Link /></ElIcon>
          </div>
          <div>
            <div class="submodal-title">{{ props.isEditingCdnRule ? '编辑图床加速规则' : '添加图床加速规则' }}</div>
            <div class="submodal-subtitle">配置指定站点或图片域名的免费 CDN 边缘代理路由</div>
          </div>
        </div>
      </template>

      <ElForm label-position="top" class="submodal-form">
        <!-- 卡片 1: 规则匹配特征 -->
        <div class="form-card-block">
          <div class="block-title">基本匹配设置</div>
          <ElFormItem label="规则名称 *" required>
            <ElInput
              v-model="props.cdnRuleForm.name"
              placeholder="例如：网飞猫图床加速、海外源站封面代理"
            />
          </ElFormItem>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px">
            <ElFormItem label="限定适用站点 (可选)">
              <ElSelect
                v-model="props.cdnRuleForm.site_key"
                placeholder="留空为全局通用；或选择适配站点"
                clearable
                filterable
                allow-create
                default-first-option
                style="width: 100%"
              >
                <ElOption
                  v-for="site in props.availableSites || []"
                  :key="site.key"
                  :label="`${site.name} (${site.key})`"
                  :value="site.key"
                >
                  <div style="display: flex; justify-content: space-between; align-items: center">
                    <span style="font-weight: 500">{{ site.name }}</span>
                    <span style="color: var(--el-text-color-secondary); font-size: 0.82rem; margin-left: 12px">{{ site.key }}</span>
                  </div>
                </ElOption>
              </ElSelect>
            </ElFormItem>

            <ElFormItem label="匹配图床域名特征 (可选)">
              <ElInput
                v-model="props.cdnRuleForm.match_domain"
                placeholder="例如：vres.cyscyy.com"
              />
            </ElFormItem>
          </div>
        </div>

        <!-- 卡片 2: 代理前缀与预设快捷填充 -->
        <div class="form-card-block">
          <div class="block-title">CDN 代理路由前缀</div>
          <ElFormItem label="代理前缀 URL *" required>
            <ElInput
              v-model="props.cdnRuleForm.prefix"
              placeholder="例如：https://wsrv.nl/?url="
            >
              <template #prepend>代理前缀</template>
            </ElInput>

            <!-- 常用预设快捷填入（胶囊徽章风格） -->
            <div class="preset-capsule-bar">
              <div class="preset-capsule-header">
                <span class="preset-header-hint">常用预设快捷填入（点击自动填充）：</span>
                <div style="display: flex; gap: 8px">
                  <ElButton
                    size="small"
                    link
                    type="primary"
                    :icon="Plus"
                    @click="openAddPresetDialog"
                  >
                    增加预设
                  </ElButton>
                  <ElButton
                    size="small"
                    link
                    type="info"
                    :icon="RefreshLeft"
                    title="恢复系统默认预设"
                    @click="resetPresets"
                  >
                    恢复默认
                  </ElButton>
                </div>
              </div>

              <div class="preset-capsule-list">
                <ElTag
                  v-for="p in presets"
                  :key="p.id"
                  closable
                  type="info"
                  effect="plain"
                  class="preset-item-tag"
                  @click="applyPreset(p)"
                  @close="deletePreset(p.id)"
                >
                  <span>{{ p.name }}</span>
                </ElTag>
              </div>
            </div>
          </ElFormItem>
        </div>

        <!-- 卡片 3: 实时效果验证与预览沙盒 -->
        <div class="sandbox-card-block">
          <div class="sandbox-header">
            <div class="sandbox-title-wrap">
              <span class="sandbox-pulse-dot" />
              <ElIcon :size="15" color="#10b981"><Picture /></ElIcon>
              <span class="sandbox-title">实时效果验证与沙盒预览</span>
            </div>
            <ElButton
              v-if="testUrl"
              size="small"
              link
              type="info"
              @click="testUrl = ''; testImageLoaded = false; testImageError = false"
            >
              清空测试
            </ElButton>
          </div>

          <ElInput
            v-model="testUrl"
            size="small"
            placeholder="粘贴待测试的原图 URL 进行实时加载验证"
            clearable
            style="margin-bottom: 10px"
            @input="testImageLoaded = false; testImageError = false"
          />

          <div v-if="previewWrappedUrl" class="sandbox-preview-result">
            <div class="sandbox-poster-wrap">
              <img
                :src="previewWrappedUrl"
                alt="测试预览"
                class="sandbox-poster-img"
                @load="handleImgLoad"
                @error="handleImgError"
              />
            </div>
            <div class="sandbox-info-wrap">
              <div class="sandbox-req-label">包装后的中继请求地址：</div>
              <code class="sandbox-url-code">{{ previewWrappedUrl }}</code>
              <div style="margin-top: 8px">
                <ElTag v-if="testImageLoaded" size="small" type="success" effect="dark">✓ 加载成功（秒开可用）</ElTag>
                <ElTag v-else-if="testImageError" size="small" type="danger" effect="dark">✕ 加载失败，请检查 URL 或前缀</ElTag>
                <ElTag v-else size="small" type="info">边缘请求加载中...</ElTag>
              </div>
            </div>
          </div>
          <div v-else class="sandbox-empty-tip">
            输入或粘贴待测试的图片链接，系统将自动拼接前缀并实时渲染预览
          </div>
        </div>
      </ElForm>

      <template #footer>
        <div class="submodal-footer">
          <div class="footer-switch-box">
            <ElSwitch
              v-model="props.cdnRuleForm.enabled"
              active-text="规则已启用"
              inactive-text="已停用"
            />
          </div>
          <div class="footer-actions-box">
            <ElButton @click="emit('update:showCdnRuleEditDialog', false)">取消</ElButton>
            <ElButton type="primary" :disabled="ui.readOnly" @click="emit('saveCdnRule')">
              保存规则
            </ElButton>
          </div>
        </div>
      </template>
    </ElDialog>

    <!-- 子弹窗 2: 增加预设弹窗 (现代化卡片风) -->
    <ElDialog
      v-model="showAddPresetDialog"
      width="480px"
      align-center
      append-to-body
      destroy-on-close
      class="submodal-dialog"
    >
      <template #header>
        <div class="submodal-header">
          <div class="submodal-icon-badge is-add">
            <ElIcon :size="18"><Plus /></ElIcon>
          </div>
          <div>
            <div class="submodal-title">增加常用代理前缀预设</div>
            <div class="submodal-subtitle">保存到本地预设库，方便以后一键快捷填入</div>
          </div>
        </div>
      </template>

      <ElForm label-position="top" class="submodal-form" style="padding: 10px 0 0 0">
        <div class="form-card-block">
          <ElFormItem label="预设名称 *" required>
            <ElInput
              v-model="newPresetName"
              placeholder="例如：自建 Cloudflare Worker、海外公共节点"
            />
          </ElFormItem>
          <ElFormItem label="代理前缀 URL *" required style="margin-bottom: 0">
            <ElInput
              v-model="newPresetPrefix"
              placeholder="例如：https://my-proxy.workers.dev/?url="
            />
          </ElFormItem>
        </div>
      </ElForm>

      <template #footer>
        <div class="dialog-footer-right">
          <ElButton @click="showAddPresetDialog = false">取消</ElButton>
          <ElButton type="primary" @click="handleConfirmAddPreset">保存预设</ElButton>
        </div>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.rule-modal-dialog :deep(.el-dialog__body) {
  padding-top: 10px;
}

.decryption-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--el-text-color-primary, #0f172a);
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.decryption-table-wrap {
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--el-border-color-lighter, #f1f5f9);
}

.rule-name-text {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.rule-id-text {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
}

.tags-cluster {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.cipher-val {
  background: var(--el-fill-color-light, #f8fafc);
  padding: 3px 6px;
  border-radius: 4px;
  font-size: 12px;
  word-break: break-all;
}

.table-ops-group {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.preset-item-tag:hover {
  border-color: var(--el-color-primary);
  color: var(--el-color-primary);
}

/* ==========================================
   二级弹窗现代高级卡片规范 (Submodal Styling)
   ========================================== */
.submodal-dialog :deep(.el-dialog__header) {
  padding: 18px 24px 14px;
  margin-right: 0;
  border-bottom: 1px solid var(--el-border-color-lighter, #f1f5f9);
}

.submodal-dialog :deep(.el-dialog__body) {
  padding: 16px 24px;
}

.submodal-dialog :deep(.el-dialog__footer) {
  padding: 14px 24px;
  border-top: 1px solid var(--el-border-color-lighter, #f1f5f9);
  background: var(--el-fill-color-blank);
}

.submodal-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.submodal-icon-badge {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
  box-shadow: 0 2px 8px rgba(79, 70, 229, 0.3);
  flex-shrink: 0;
}

.submodal-icon-badge.is-edit {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.3);
}

.submodal-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--el-text-color-primary, #0f172a);
}

.submodal-subtitle {
  font-size: 12px;
  color: var(--el-text-color-secondary, #64748b);
  margin-top: 2px;
}

.form-card-block {
  background: var(--el-fill-color-light, #f8fafc);
  border: 1px solid var(--el-border-color-lighter, #e2e8f0);
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 12px;
}

.block-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--el-text-color-regular, #475569);
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.preset-capsule-bar {
  margin-top: 10px;
  width: 100%;
}

.preset-capsule-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.preset-header-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.preset-capsule-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

/* 实时预览沙盒卡片 */
.sandbox-card-block {
  background: var(--el-bg-color-overlay, #ffffff);
  border: 1px solid var(--el-border-color, #e2e8f0);
  border-radius: 8px;
  padding: 14px 16px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.03);
}

.sandbox-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.sandbox-title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sandbox-pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10b981;
}

.sandbox-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.sandbox-preview-result {
  display: flex;
  gap: 14px;
  align-items: center;
  background: var(--el-fill-color-light, #f8fafc);
  border: 1px solid var(--el-border-color-lighter, #f1f5f9);
  border-radius: 8px;
  padding: 10px;
}

.sandbox-poster-wrap {
  width: 68px;
  height: 92px;
  border-radius: 6px;
  overflow: hidden;
  background: #0f172a;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--el-border-color);
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.sandbox-poster-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.sandbox-info-wrap {
  flex: 1;
  min-width: 0;
}

.sandbox-req-label {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
}

.sandbox-url-code {
  display: block;
  word-break: break-all;
  color: #4f46e5;
  font-size: 11px;
  font-weight: 600;
  background: rgba(79, 70, 229, 0.06);
  padding: 4px 8px;
  border-radius: 4px;
}

.sandbox-empty-tip {
  padding: 14px 0;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

/* 底部操作与开关一体化 */
.submodal-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.footer-switch-box {
  display: flex;
  align-items: center;
}

.footer-actions-box,
.dialog-footer-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
</style>
