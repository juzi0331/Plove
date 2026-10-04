<script setup lang="ts">
import {
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElSwitch,
} from 'element-plus'
import type { SystemMaintenancePayload } from '@/api/types'

defineProps<{
  visible: boolean
  maintForm: SystemMaintenancePayload
  saving: boolean
  readOnly: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'save'): void
  (e: 'applyTemplate', type: 'network' | 'db' | 'cdn'): void
}>()
</script>

<template>
  <ElDialog
    :model-value="visible"
    title="配置全站停服维护闸门"
    width="640px"
    append-to-body
    destroy-on-close
    @update:model-value="val => emit('update:visible', val)"
  >
    <ElForm :model="maintForm" label-position="top">
      <ElFormItem label="全站停服维护总闸门">
        <div class="dialog-switch-row">
          <div>
            <div class="switch-row-title">紧急停机维护开关</div>
            <div class="switch-row-desc">
              开启后，所有普通前台路由（除 /admin 管理后台）一律展示维护锁屏
            </div>
          </div>
          <ElSwitch
            v-model="maintForm.enabled"
            :disabled="readOnly"
            active-text="开启维护"
            inactive-text="关闭"
          />
        </div>
      </ElFormItem>

      <ElFormItem label="常用维护模板快捷填充">
        <div class="template-btns-row">
          <ElButton size="small" @click="emit('applyTemplate', 'network')">机房网络升级</ElButton>
          <ElButton size="small" @click="emit('applyTemplate', 'db')">数据库容灾割接</ElButton>
          <ElButton size="small" @click="emit('applyTemplate', 'cdn')">高防 CDN 切换</ElButton>
        </div>
      </ElFormItem>

      <ElFormItem label="展示给前台用户的维护告示文案">
        <ElInput
          v-model="maintForm.message"
          type="textarea"
          :rows="4"
          placeholder="请输入维护原因与预计恢复时间文案..."
          :disabled="readOnly"
        />
      </ElFormItem>
    </ElForm>

    <template #footer>
      <div class="dialog-footer">
        <ElButton @click="emit('update:visible', false)">取消</ElButton>
        <ElButton
          :type="maintForm.enabled ? 'danger' : 'primary'"
          :loading="saving"
          :disabled="readOnly"
          @click="emit('save')"
        >
          保存并应用维护设置
        </ElButton>
      </div>
    </template>
  </ElDialog>
</template>

<style scoped src="./system-notice.css"></style>
