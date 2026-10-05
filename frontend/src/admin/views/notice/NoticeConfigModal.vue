<script setup lang="ts">
import {
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
import { Bell } from '@element-plus/icons-vue'
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
    width="700px"
    align-center
    append-to-body
    destroy-on-close
    class="submodal-dialog"
    @update:model-value="val => emit('update:visible', val)"
  >
    <template #header>
      <div class="submodal-header">
        <div class="submodal-icon-badge" :class="noticeForm.enabled ? 'is-success' : 'is-edit'">
          <ElIcon :size="18"><Bell /></ElIcon>
        </div>
        <div>
          <div class="submodal-title">配置全站广播公告</div>
          <div class="submodal-subtitle">按指定渠道向前台实时发布大厅弹窗、顶部跑马灯、通告横幅</div>
        </div>
      </div>
    </template>

    <ElForm :model="noticeForm" label-position="top" class="submodal-form">
      <!-- 卡片 1: 标题与级别 -->
      <div class="form-card-block">
        <div class="block-title">公告基础信息</div>
        <ElRow :gutter="14">
          <ElCol :xs="24" :sm="15">
            <ElFormItem label="公告主标题 *" required>
              <ElInput
                v-model="noticeForm.title"
                placeholder="如：全站蓝光超清解析核心升级公告"
                :disabled="readOnly"
              />
            </ElFormItem>
          </ElCol>

          <ElCol :xs="24" :sm="9">
            <ElFormItem label="紧急程度级别">
              <ElSelect v-model="noticeForm.level" style="width: 100%" :disabled="readOnly">
                <ElOption label="常规提示 (Info 蓝/绿)" value="info" />
                <ElOption label="重要提醒 (Warning 琥珀橙)" value="warning" />
                <ElOption label="紧急通告 (Danger 警示红)" value="danger" />
              </ElSelect>
            </ElFormItem>
          </ElCol>
        </ElRow>

        <ElFormItem label="常用公告模板快捷填充" style="margin-bottom: 0">
          <div class="template-btns-row">
            <ElButton size="small" @click="emit('applyTemplate', 'upgrade')">影视全新升级</ElButton>
            <ElButton size="small" @click="emit('applyTemplate', 'mirror')">备用发布页通知</ElButton>
            <ElButton size="small" @click="emit('applyTemplate', 'speed')">线路优化提示</ElButton>
          </div>
        </ElFormItem>
      </div>

      <!-- 卡片 2: 发布渠道与展示形式 -->
      <div class="form-card-block">
        <div class="block-title">展示形态与渠道</div>
        <ElFormItem style="margin-bottom: 0">
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
      </div>

      <!-- 卡片 3: 公告详细正文内容 -->
      <div class="form-card-block">
        <div class="block-title">公告正文与操作引导</div>
        <ElFormItem label="公告详细正文内容 *" required>
          <ElInput
            v-model="noticeForm.content"
            type="textarea"
            :rows="3"
            placeholder="请输入公告正文详细内容..."
            :disabled="readOnly"
          />
        </ElFormItem>

        <ElRow :gutter="14">
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
                placeholder="如：https://...（用户点击跳转）"
                :disabled="readOnly"
              />
            </ElFormItem>
          </ElCol>
        </ElRow>

        <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 4px">
          <span style="font-size: 12px; color: var(--el-text-color-secondary)">允许前台用户手动关闭/折叠该公告：</span>
          <ElSwitch v-model="noticeForm.dismissible" :disabled="readOnly" active-text="允许手动关闭" inactive-text="常驻显示" />
        </div>
      </div>
    </ElForm>

    <template #footer>
      <div class="submodal-footer">
        <div class="footer-switch-box">
          <ElSwitch
            v-model="noticeForm.enabled"
            :disabled="readOnly"
            active-text="广播发布生效"
            inactive-text="已关闭广播"
          />
        </div>
        <div class="footer-actions-box">
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
      </div>
    </template>
  </ElDialog>
</template>
