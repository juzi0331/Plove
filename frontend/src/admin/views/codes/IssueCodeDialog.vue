<script setup lang="ts">
import {
  ElButton,
  ElCol,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElOption,
  ElRow,
  ElSelect,
} from 'element-plus'
import { PRESETS } from './useCodes'

const props = defineProps<{
  modelValue: boolean
  issueBusy: boolean
  issueForm: {
    unit: 'days' | 'hours'
    amount: number
    count: number
    max_devices: number
    note: string
  }
  activePreset: string | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'applyPreset', preset: (typeof PRESETS)[number]): void
  (e: 'submit'): void
}>()
</script>

<template>
  <ElDialog
    :model-value="props.modelValue"
    title="发行新激活码"
    width="520px"
    destroy-on-close
    @update:model-value="emit('update:modelValue', $event)"
  >
    <ElForm label-position="top">
      <ElFormItem label="快捷时长预设">
        <div class="preset-btn-row">
          <ElButton
            v-for="p in PRESETS"
            :key="p.label"
            size="small"
            :type="props.activePreset === p.label ? 'primary' : 'default'"
            @click="emit('applyPreset', p)"
          >
            {{ p.label }}
          </ElButton>
        </div>
      </ElFormItem>

      <ElRow :gutter="16">
        <ElCol :xs="24" :sm="14">
          <ElFormItem label="自定义时长数值">
            <ElInputNumber v-model="props.issueForm.amount" :min="1" :max="10000" style="width: 100%" />
          </ElFormItem>
        </ElCol>
        <ElCol :xs="24" :sm="10">
          <ElFormItem label="单位">
            <ElSelect v-model="props.issueForm.unit" style="width: 100%">
              <ElOption label="天" value="days" />
              <ElOption label="小时" value="hours" />
            </ElSelect>
          </ElFormItem>
        </ElCol>
      </ElRow>

      <ElRow :gutter="16">
        <ElCol :xs="24" :sm="12">
          <ElFormItem label="生成数量">
            <ElInputNumber v-model="props.issueForm.count" :min="1" :max="100" style="width: 100%" />
          </ElFormItem>
        </ElCol>
        <ElCol :xs="24" :sm="12">
          <ElFormItem label="允许绑定设备数上限">
            <ElInputNumber v-model="props.issueForm.max_devices" :min="1" :max="10" style="width: 100%" />
          </ElFormItem>
        </ElCol>
      </ElRow>

      <ElFormItem label="备注（选填，方便后台识别）">
        <ElInput v-model="props.issueForm.note" placeholder="如：活动赠送、VIP客户、特定渠道" />
      </ElFormItem>
    </ElForm>

    <template #footer>
      <div class="dialog-footer">
        <ElButton @click="emit('update:modelValue', false)">取消</ElButton>
        <ElButton type="primary" :loading="props.issueBusy" @click="emit('submit')">
          生成激活码
        </ElButton>
      </div>
    </template>
  </ElDialog>
</template>
