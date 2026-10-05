<script setup lang="ts">
import {
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
  ElSwitch,
} from 'element-plus'
import { Tools } from '@element-plus/icons-vue'
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
    width="640px"
    align-center
    append-to-body
    destroy-on-close
    class="submodal-dialog"
    @update:model-value="val => emit('update:visible', val)"
  >
    <template #header>
      <div class="submodal-header">
        <div class="submodal-icon-badge" :class="maintForm.enabled ? 'is-danger' : 'is-edit'">
          <ElIcon :size="18"><Tools /></ElIcon>
        </div>
        <div>
          <div class="submodal-title">配置全站停服维护闸门</div>
          <div class="submodal-subtitle">开启后拦截普通前台路由展示锁屏，管理后台白名单放行</div>
        </div>
      </div>
    </template>

    <ElForm :model="maintForm" label-position="top" class="submodal-form">
      <div class="form-card-block">
        <div class="block-title">常用维护模板快捷填充</div>
        <div class="template-btns-row">
          <ElButton size="small" @click="emit('applyTemplate', 'network')">机房网络升级</ElButton>
          <ElButton size="small" @click="emit('applyTemplate', 'db')">数据库容灾割接</ElButton>
          <ElButton size="small" @click="emit('applyTemplate', 'cdn')">高防 CDN 切换</ElButton>
        </div>
      </div>

      <div class="form-card-block">
        <div class="block-title">展示给前台用户的维护告示文案</div>
        <ElFormItem style="margin-bottom: 0">
          <ElInput
            v-model="maintForm.message"
            type="textarea"
            :rows="4"
            placeholder="请输入维护原因与预计恢复时间文案..."
            :disabled="readOnly"
          />
        </ElFormItem>
      </div>
    </ElForm>

    <template #footer>
      <div class="submodal-footer">
        <div class="footer-switch-box">
          <ElSwitch
            v-model="maintForm.enabled"
            :disabled="readOnly"
            active-text="开启全站维护"
            inactive-text="正常运营"
          />
        </div>
        <div class="footer-actions-box">
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
      </div>
    </template>
  </ElDialog>
</template>

<style scoped src="./system-notice.css"></style>
