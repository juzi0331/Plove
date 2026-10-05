<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  ElAlert,
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus'
import {
  Delete,
  Edit,
  Plus,
  Picture,
} from '@element-plus/icons-vue'
import { ui } from '@/admin/ui'
import type { ImageCdnPrefixRule } from '@/api/types'

const props = defineProps<{
  modelValue: boolean
  cdnRulesList: ImageCdnPrefixRule[]
  showCdnRuleEditDialog: boolean
  isEditingCdnRule: boolean
  cdnRuleForm: ImageCdnPrefixRule
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

// 实时测试预览状态
const testUrl = ref('https://vres.cyscyy.com/vod1/vod/cover/20261003/18/33/05/ef7c37cf022b3d955c176e01d07cf488.jpg')
const testImageLoaded = ref(false)
const testImageError = ref(false)

const previewWrappedUrl = computed(() => {
  const prefix = props.cdnRuleForm.prefix?.trim() || ''
  const url = testUrl.value.trim()
  if (!url || !prefix) return ''
  return `${prefix}${encodeURIComponent(url)}`
})

function applyPreset(prefixStr: string): void {
  props.cdnRuleForm.prefix = prefixStr
  testImageLoaded.value = false
  testImageError.value = false
}

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
      width="900px"
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

    <!-- 子弹窗: 新增/编辑规则 -->
    <ElDialog
      :model-value="props.showCdnRuleEditDialog"
      :title="props.isEditingCdnRule ? '编辑图床加速规则' : '添加图床加速规则'"
      width="640px"
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

          <ElFormItem label="限定适用站点 Key (可选)">
            <ElInput
              v-model="props.cdnRuleForm.site_key"
              placeholder="例如：www_ncat21_com"
            />
          </ElFormItem>
        </div>

        <ElFormItem label="代理前缀 *" required>
          <ElInput
            v-model="props.cdnRuleForm.prefix"
            placeholder="例如：https://wsrv.nl/?url="
          >
            <template #prepend>前缀</template>
          </ElInput>
          <div style="margin-top: 6px; display: flex; align-items: center; gap: 8px">
            <span style="font-size: 0.8rem; color: var(--el-text-color-secondary)">常用预设快捷填入：</span>
            <ElButton
              size="small"
              link
              type="primary"
              @click="applyPreset('https://wsrv.nl/?url=')"
            >
              wsrv.nl (推荐)
            </ElButton>
            <ElButton
              size="small"
              link
              type="primary"
              @click="applyPreset('https://images.weserv.nl/?url=')"
            >
              images.weserv.nl
            </ElButton>
          </div>
        </ElFormItem>

        <ElFormItem label="启用开关">
          <ElSwitch v-model="props.cdnRuleForm.enabled" active-text="生效中" inactive-text="已停用" />
        </ElFormItem>

        <!-- 实时测试与预览模块 -->
        <div style="background: var(--el-fill-color-light); border-radius: 8px; padding: 12px; margin-top: 8px">
          <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px; font-weight: 600; font-size: 0.88rem">
            <Picture style="width: 16px; height: 16px; color: var(--el-color-primary)" />
            <span>实时效果验证与预览</span>
          </div>

          <ElInput
            v-model="testUrl"
            size="small"
            placeholder="粘贴待测试的原图 URL"
            style="margin-bottom: 8px"
            @change="testImageLoaded = false; testImageError = false"
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
        </div>
      </ElForm>

      <template #footer>
        <ElButton @click="emit('update:showCdnRuleEditDialog', false)">取消</ElButton>
        <ElButton type="primary" :disabled="ui.readOnly" @click="emit('saveCdnRule')">保存规则</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.rule-modal-dialog :deep(.el-dialog__body) {
  padding-top: 10px;
}
</style>
