<script setup lang="ts">
import {
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInputNumber,
} from 'element-plus'

const props = defineProps<{
  modelValue: boolean
  extendTarget: { id: number; code: string; started: boolean } | null
  extendHours: number
  extendBusy: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'update:extendHours', val: number): void
  (e: 'submit'): void
}>()
</script>

<template>
  <ElDialog
    :model-value="props.modelValue"
    :title="`延长激活码有效期 · ${props.extendTarget?.code || ''}`"
    width="440px"
    align-center
    append-to-body
    destroy-on-close
    class="submodal-dialog"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <ElForm label-position="top">
      <ElFormItem label="延长时长（小时）">
        <ElInputNumber
          :model-value="props.extendHours"
          :min="1"
          :max="87600"
          style="width: 100%"
          @update:model-value="emit('update:extendHours', $event as number)"
        />
      </ElFormItem>
      <p class="a-muted" style="font-size: 12px; margin: 0;">
        {{
          props.extendTarget?.started
            ? '该码已激活使用中：将在现有到期时间的基础上向后顺延指定小时数。'
            : '该码尚未激活：将在首次激活后的总可用时长中追加指定小时数。'
        }}
      </p>
    </ElForm>
    <template #footer>
      <div class="dialog-footer">
        <ElButton @click="emit('update:modelValue', false)">取消</ElButton>
        <ElButton type="primary" :loading="props.extendBusy" @click="emit('submit')">
          确认延长
        </ElButton>
      </div>
    </template>
  </ElDialog>
</template>
