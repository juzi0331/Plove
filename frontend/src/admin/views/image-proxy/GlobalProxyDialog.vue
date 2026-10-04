<script setup lang="ts">
import {
  ElAlert,
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElRadio,
  ElRadioGroup,
  ElSwitch,
} from 'element-plus'
import { Check } from '@element-plus/icons-vue'
import { ui } from '@/admin/ui'
import type { ImageProxyConfig } from '@/api/types'

const props = defineProps<{
  modelValue: boolean
  config: ImageProxyConfig
  savingConfig: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'save'): void
}>()
</script>

<template>
  <ElDialog
    :model-value="props.modelValue"
    title="全局海报防盗链中继总控详情"
    width="640px"
    destroy-on-close
    @update:model-value="emit('update:modelValue', $event)"
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
        <ElButton @click="emit('update:modelValue', false)">取消</ElButton>
        <ElButton
          type="primary"
          :icon="Check"
          :loading="savingConfig"
          :disabled="ui.readOnly"
          @click="emit('save')"
        >
          保存并应用配置
        </ElButton>
      </div>
    </template>
  </ElDialog>
</template>
