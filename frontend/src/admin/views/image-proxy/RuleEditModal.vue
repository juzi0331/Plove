<script setup lang="ts">
import {
  ElAlert,
  ElButton,
  ElCol,
  ElDialog,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
  ElOption,
  ElRadio,
  ElRadioGroup,
  ElRow,
  ElSelect,
  ElSwitch,
} from 'element-plus'
import { Lock } from '@element-plus/icons-vue'
import { ui } from '@/admin/ui'
import { useSitesStore } from '@/stores/sites'
import type { ImageDecryptionRule, TestDecryptResult } from '@/api/types'

const sitesStore = useSitesStore()

const props = defineProps<{
  modelValue: boolean
  isEditing: boolean
  ruleForm: ImageDecryptionRule
  domainsInput: string
  inlineTestUrl: string
  inlineTesting: boolean
  inlineTestResult: TestDecryptResult | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'update:domainsInput', val: string): void
  (e: 'update:inlineTestUrl', val: string): void
  (e: 'fillHuangguoaiSample'): void
  (e: 'runInlineTest'): void
  (e: 'save'): void
}>()
</script>

<template>
  <ElDialog
    :model-value="props.modelValue"
    width="680px"
    align-center
    append-to-body
    destroy-on-close
    class="submodal-dialog"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #header>
      <div class="submodal-header">
        <div class="submodal-icon-badge" :class="props.isEditing ? 'is-edit' : 'is-add'">
          <ElIcon :size="18"><Lock /></ElIcon>
        </div>
        <div>
          <div class="submodal-title">{{ props.isEditing ? '编辑图片解密规则' : '添加站点图片解密规则' }}</div>
          <div class="submodal-subtitle">配置 AES 等加密图床的密钥算法并支持实时解密验证</div>
        </div>
      </div>
    </template>
    <ElForm :model="props.ruleForm" label-position="top">
      <ElRow :gutter="16">
        <ElCol :span="14">
          <ElFormItem label="规则名称 / 备注" required>
            <ElInput v-model="props.ruleForm.name" placeholder="例如：黄果艾加密封面 (wirqed.cn)" />
          </ElFormItem>
        </ElCol>
        <ElCol :span="10">
          <ElFormItem label="关联目标站点（选填）">
            <ElSelect
              v-model="props.ruleForm.site_key"
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
          :model-value="props.domainsInput"
          placeholder="例如：pic.wirqed.cn, wirqed.cn（留空则对该站点的所有图片生效）"
          @update:model-value="emit('update:domainsInput', $event)"
        />
      </ElFormItem>

      <ElRow :gutter="16">
        <ElCol :span="12">
          <ElFormItem label="解密算法" required>
            <ElRadioGroup v-model="props.ruleForm.algorithm">
              <ElRadio value="AES-128-CBC">AES-128-CBC (最常见)</ElRadio>
              <ElRadio value="AES-128-ECB">AES-128-ECB</ElRadio>
            </ElRadioGroup>
          </ElFormItem>
        </ElCol>
        <ElCol :span="12">
          <ElFormItem label="密钥格式">
            <ElSwitch
              v-model="props.ruleForm.is_hex"
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
              v-model="props.ruleForm.key"
              placeholder="例如：f5d965df75336270"
              clearable
            />
          </ElFormItem>
        </ElCol>
        <ElCol :span="12">
          <ElFormItem
            label="偏移量 IV"
            :required="props.ruleForm.algorithm === 'AES-128-CBC'"
          >
            <ElInput
              v-model="props.ruleForm.iv"
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
          <ElButton link size="small" type="primary" @click="emit('fillHuangguoaiSample')">
            填入官方范例
          </ElButton>
        </div>
        <div class="inline-test-input-row">
          <ElInput
            :model-value="props.inlineTestUrl"
            size="small"
            placeholder="输入加密图片 URL 进行实时解密测试（若图床开启动态鉴权请粘贴包含 ?auth_key= 的完整地址）"
            clearable
            @update:model-value="emit('update:inlineTestUrl', $event)"
          />
          <ElButton
            size="small"
            type="warning"
            :loading="props.inlineTesting"
            @click="emit('runInlineTest')"
          >
            验证密钥
          </ElButton>
        </div>

        <div v-if="props.inlineTestResult" class="inline-test-result">
          <ElAlert
            :type="props.inlineTestResult.success ? 'success' : 'error'"
            :closable="false"
            show-icon
          >
            <template #title>
              <span>{{ props.inlineTestResult.message }}</span>
            </template>
          </ElAlert>
          <div v-if="props.inlineTestResult.preview_data_url" class="inline-preview-wrap">
            <img :src="props.inlineTestResult.preview_data_url" alt="解密预览" class="inline-img" />
            <div class="inline-img-meta">
              <div>格式: <b>{{ props.inlineTestResult.mime_type }}</b></div>
              <div>大小: <b>{{ (((props.inlineTestResult.size_bytes || 0)) / 1024).toFixed(1) }} KB</b></div>
              <div>耗时: <b>{{ props.inlineTestResult.elapsed_ms }} ms</b></div>
            </div>
          </div>
        </div>
      </div>
    </ElForm>

    <template #footer>
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <ElSwitch
          v-model="props.ruleForm.enabled"
          active-text="启用规则"
          inactive-text="关闭"
        />
        <div>
          <ElButton @click="emit('update:modelValue', false)">取消</ElButton>
          <ElButton type="primary" :disabled="ui.readOnly" @click="emit('save')">
            保存规则
          </ElButton>
        </div>
      </div>
    </template>
  </ElDialog>
</template>
