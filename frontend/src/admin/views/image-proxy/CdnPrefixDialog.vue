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
  Plus,
  Picture,
  RefreshLeft,
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
    <!-- 主弹窗: 图床加速与代理前缀规则列表 -->
    <ElDialog
      :model-value="props.modelValue"
      title="图床加速与代理前缀路由"
      width="920px"
      append-to-body
      class="rule-modal-dialog"
      @update:model-value="(val: boolean) => emit('update:modelValue', val)"
    >
      <ElAlert
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 1.25rem"
      >
        <template #title>
          <span style="font-weight: 600">解决海外图床被墙、丢包或防盗链破图</span>
        </template>
        为特定站点或域名指定免费公共边缘 CDN 反代（如 <code>https://wsrv.nl/?url=</code>），由 Cloudflare 全球边缘节点高速拉取并缓存海报，<b>完全不消耗本地服务器流量与 CPU</b>。
      </ElAlert>

      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem">
        <span style="font-weight: 600; font-size: 0.95rem">
          已配置规则 ({{ props.cdnRulesList.length }})
        </span>
        <ElButton
          type="primary"
          :icon="Plus"
          size="small"
          :disabled="ui.readOnly"
          @click="emit('openAddCdnRule')"
        >
          添加加速前缀规则
        </ElButton>
      </div>

      <ElTable :data="props.cdnRulesList" stripe style="width: 100%" empty-text="暂无代理前缀规则，点击右上角添加">
        <ElTableColumn prop="name" label="规则名称" min-width="140">
          <template #default="{ row }">
            <span style="font-weight: 600">{{ row.name }}</span>
          </template>
        </ElTableColumn>

        <ElTableColumn label="匹配条件" min-width="170">
          <template #default="{ row }">
            <div style="display: flex; flex-direction: column; gap: 4px">
              <span v-if="row.site_key">
                站点: <ElTag size="small" type="info">{{ row.site_key }}</ElTag>
              </span>
              <span v-if="row.match_domain">
                域名: <code style="font-size: 0.82rem; background: var(--el-fill-color-light); padding: 2px 4px; border-radius: 4px">{{ row.match_domain }}</code>
              </span>
              <span v-if="!row.site_key && !row.match_domain" style="color: var(--el-text-color-secondary); font-size: 0.85rem">
                全局匹配
              </span>
            </div>
          </template>
        </ElTableColumn>

        <ElTableColumn prop="prefix" label="代理前缀" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <code style="color: var(--el-color-primary); font-weight: 600">{{ row.prefix }}</code>
          </template>
        </ElTableColumn>

        <ElTableColumn label="启用状态" width="100" align="center">
          <template #default="{ row }">
            <ElSwitch
              v-model="row.enabled"
              size="small"
              :disabled="ui.readOnly"
              @change="emit('toggleCdnRule')"
            />
          </template>
        </ElTableColumn>

        <ElTableColumn label="操作" width="130" align="center">
          <template #default="{ row, $index }">
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
          </template>
        </ElTableColumn>
      </ElTable>

      <template #footer>
        <ElButton @click="emit('update:modelValue', false)">关闭</ElButton>
      </template>
    </ElDialog>

    <!-- 子弹窗 1: 新增/编辑规则 -->
    <ElDialog
      :model-value="props.showCdnRuleEditDialog"
      :title="props.isEditingCdnRule ? '编辑图床加速规则' : '添加图床加速规则'"
      width="660px"
      append-to-body
      @update:model-value="(val: boolean) => emit('update:showCdnRuleEditDialog', val)"
    >
      <ElForm label-position="top">
        <ElFormItem label="规则名称 *" required>
          <ElInput
            v-model="props.cdnRuleForm.name"
            placeholder="例如：网飞猫图床加速、海外源站封面代理"
          />
        </ElFormItem>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px">
          <ElFormItem label="匹配域名特征 (可选)">
            <ElInput
              v-model="props.cdnRuleForm.match_domain"
              placeholder="例如：vres.cyscyy.com"
            />
          </ElFormItem>

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
        </div>

        <ElFormItem label="代理前缀 *" required>
          <ElInput
            v-model="props.cdnRuleForm.prefix"
            placeholder="例如：https://wsrv.nl/?url="
          >
            <template #prepend>前缀</template>
          </ElInput>

          <!-- 常用预设快捷填入（支持增加/删除） -->
          <div style="margin-top: 8px; width: 100%">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px">
              <span style="font-size: 0.8rem; color: var(--el-text-color-secondary)">
                常用预设快捷填入（点击即可填入，支持添加与删除）：
              </span>
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

            <div style="display: flex; flex-wrap: wrap; gap: 8px; align-items: center">
              <ElTag
                v-for="p in presets"
                :key="p.id"
                closable
                type="info"
                effect="plain"
                class="preset-item-tag"
                style="cursor: pointer; user-select: none"
                @click="applyPreset(p)"
                @close="deletePreset(p.id)"
              >
                <span>{{ p.name }}</span>
              </ElTag>
            </div>
          </div>
        </ElFormItem>

        <ElFormItem label="启用开关">
          <ElSwitch v-model="props.cdnRuleForm.enabled" active-text="生效中" inactive-text="已停用" />
        </ElFormItem>

        <!-- 实时测试与预览模块（编辑框内默认无内容） -->
        <div style="background: var(--el-fill-color-light); border-radius: 8px; padding: 12px; margin-top: 8px">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px">
            <div style="display: flex; align-items: center; gap: 6px; font-weight: 600; font-size: 0.88rem">
              <Picture style="width: 16px; height: 16px; color: var(--el-color-primary)" />
              <span>实时效果验证与预览</span>
            </div>
            <ElButton
              v-if="testUrl"
              size="small"
              link
              type="info"
              @click="testUrl = ''; testImageLoaded = false; testImageError = false"
            >
              清空
            </ElButton>
          </div>

          <ElInput
            v-model="testUrl"
            size="small"
            placeholder="粘贴待测试的原图 URL 进行实时加载验证"
            clearable
            style="margin-bottom: 8px"
            @input="testImageLoaded = false; testImageError = false"
          />

          <div v-if="previewWrappedUrl" style="display: flex; gap: 12px; align-items: center">
            <div style="width: 70px; height: 95px; border-radius: 4px; overflow: hidden; background: #000; display: flex; align-items: center; justify-content: center; border: 1px solid var(--el-border-color)">
              <img
                :src="previewWrappedUrl"
                alt="测试预览"
                style="width: 100%; height: 100%; object-fit: cover"
                @load="handleImgLoad"
                @error="handleImgError"
              />
            </div>
            <div style="flex: 1; font-size: 0.8rem">
              <div style="color: var(--el-text-color-secondary); margin-bottom: 4px">包装后的中继请求地址：</div>
              <code style="word-break: break-all; color: var(--el-color-primary); font-size: 0.78rem">{{ previewWrappedUrl }}</code>
              <div style="margin-top: 6px">
                <ElTag v-if="testImageLoaded" size="small" type="success">✓ 加载成功（秒开可用）</ElTag>
                <ElTag v-else-if="testImageError" size="small" type="danger">✕ 加载失败，请检查 URL 或前缀</ElTag>
                <ElTag v-else size="small" type="info">加载中...</ElTag>
              </div>
            </div>
          </div>
          <div v-else style="padding: 10px 0; text-align: center; color: var(--el-text-color-secondary); font-size: 0.8rem">
            输入或粘贴待测试的图片链接，即可验证代理前缀的穿透与加速效果
          </div>
        </div>
      </ElForm>

      <template #footer>
        <ElButton @click="emit('update:showCdnRuleEditDialog', false)">取消</ElButton>
        <ElButton type="primary" :disabled="ui.readOnly" @click="emit('saveCdnRule')">保存规则</ElButton>
      </template>
    </ElDialog>

    <!-- 子弹窗 2: 增加预设弹窗 -->
    <ElDialog
      v-model="showAddPresetDialog"
      title="增加常用代理前缀预设"
      width="460px"
      append-to-body
    >
      <ElForm label-position="top">
        <ElFormItem label="预设名称 *" required>
          <ElInput
            v-model="newPresetName"
            placeholder="例如：自建 Cloudflare Worker、海外公共节点"
          />
        </ElFormItem>
        <ElFormItem label="代理前缀 URL *" required>
          <ElInput
            v-model="newPresetPrefix"
            placeholder="例如：https://my-proxy.workers.dev/?url="
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="showAddPresetDialog = false">取消</ElButton>
        <ElButton type="primary" @click="handleConfirmAddPreset">保存预设</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.rule-modal-dialog :deep(.el-dialog__body) {
  padding-top: 10px;
}
.preset-item-tag:hover {
  border-color: var(--el-color-primary);
  color: var(--el-color-primary);
}
</style>
