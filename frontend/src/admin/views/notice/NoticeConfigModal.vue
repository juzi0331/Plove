<script setup lang="ts">
import {
  ElButton,
  ElCol,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElOption,
  ElRadio,
  ElRadioGroup,
  ElRow,
  ElSelect,
  ElSwitch,
} from 'element-plus'
import type { SystemNoticePayload } from '@/api/types'
import { displayTypeOptions } from './useSystemNotice'

defineProps<{
  visible: boolean
  noticeForm: SystemNoticePayload
  saving: boolean
  readOnly: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'save'): void
  (e: 'applyTemplate', type: 'upgrade' | 'mirror' | 'speed'): void
}>()
</script>

<template>
  <ElDialog
    :model-value="visible"
    title="配置全站广播公告"
    width="680px"
    append-to-body
    destroy-on-close
    @update:model-value="val => emit('update:visible', val)"
  >
    <ElForm :model="noticeForm" label-position="top">
      <ElFormItem label="全站广播总开关">
        <div class="dialog-switch-row">
          <div>
            <div class="switch-row-title">广播发布状态</div>
            <div class="switch-row-desc">开启后立即在前台按照指定渠道进行展示</div>
          </div>
          <ElSwitch
            v-model="noticeForm.enabled"
            :disabled="readOnly"
            active-text="广播生效"
            inactive-text="关闭"
          />
        </div>
      </ElFormItem>

      <ElRow :gutter="16">
        <ElCol :xs="24" :sm="15">
          <ElFormItem label="公告主标题">
            <ElInput
              v-model="noticeForm.title"
              placeholder="如：全站蓝光超清解析核心升级公告"
              :disabled="readOnly"
            />
          </ElFormItem>
        </ElCol>

        <ElCol :xs="24" :sm="9">
          <ElFormItem label="紧急级别">
            <ElSelect v-model="noticeForm.level" style="width: 100%" :disabled="readOnly">
              <ElOption label="常规提示 (Info 蓝/绿)" value="info" />
              <ElOption label="重要提醒 (Warning 琥珀橙)" value="warning" />
              <ElOption label="紧急通告 (Danger 警示红)" value="danger" />
            </ElSelect>
          </ElFormItem>
        </ElCol>
      </ElRow>

      <ElFormItem label="发布渠道与展示形式">
        <ElRadioGroup v-model="noticeForm.display_type" :disabled="readOnly" class="dialog-radio-grid">
          <ElRadio
            v-for="opt in displayTypeOptions"
            :key="opt.type"
            :value="opt.type"
            border
            class="dialog-radio-item"
          >
            {{ opt.name }}
          </ElRadio>
        </ElRadioGroup>
      </ElFormItem>

      <ElFormItem label="常用公告模板快捷填充">
        <div class="template-btns-row">
          <ElButton size="small" @click="emit('applyTemplate', 'upgrade')">影视全新升级</ElButton>
          <ElButton size="small" @click="emit('applyTemplate', 'mirror')">备用发布页通知</ElButton>
          <ElButton size="small" @click="emit('applyTemplate', 'speed')">线路优化提示</ElButton>
        </div>
      </ElFormItem>

      <ElFormItem label="公告详细正文内容">
        <ElInput
          v-model="noticeForm.content"
          type="textarea"
          :rows="4"
          placeholder="请输入公告正文详细内容..."
          :disabled="readOnly"
        />
      </ElFormItem>

      <ElRow :gutter="16">
        <ElCol :xs="24" :sm="10">
          <ElFormItem label="行动引导按钮文案（选填）">
            <ElInput
              v-model="noticeForm.action_text"
              placeholder="如：查看详情 / 立即加群"
              :disabled="readOnly"
            />
          </ElFormItem>
        </ElCol>

        <ElCol :xs="24" :sm="14">
          <ElFormItem label="引导跳转链接 URL（选填）">
            <ElInput
              v-model="noticeForm.action_url"
              placeholder="如：https://...（用户点击按钮跳转）"
              :disabled="readOnly"
            />
          </ElFormItem>
        </ElCol>
      </ElRow>

      <ElFormItem label="交互权限控制">
        <div class="dialog-switch-row">
          <div>
            <div class="switch-row-title">允许用户手动点击关闭</div>
            <div class="switch-row-desc">关闭后不再遮挡用户视线，保持前台清爽</div>
          </div>
          <ElSwitch v-model="noticeForm.dismissible" :disabled="readOnly" />
        </div>
      </ElFormItem>
    </ElForm>

    <template #footer>
      <div class="dialog-footer">
        <ElButton @click="emit('update:visible', false)">取消</ElButton>
        <ElButton
          type="primary"
          :loading="saving"
          :disabled="readOnly"
          @click="emit('save')"
        >
          保存并立即向前台广播
        </ElButton>
      </div>
    </template>
  </ElDialog>
</template>

<style scoped src="./system-notice.css"></style>
