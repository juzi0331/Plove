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
import { CircleCheck, WarningFilled } from '@element-plus/icons-vue'
import type { TelegramVerifyResult } from '@/api/types'

const props = defineProps<{
  modelValue: boolean
  draft: {
    bot_token: string
    chat_id: string
    proxy_url: string
    enabled: boolean
  }
  verifyResult: TelegramVerifyResult | null
  verifying: boolean
  saving: boolean
  testing: boolean
  readOnly: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  verify: []
  test: []
  save: []
}>()
</script>

<template>
  <ElDialog
    :model-value="props.modelValue"
    title="Telegram 机器人参数配置"
    width="560px"
    append-to-body
    destroy-on-close
    class="bot-config-dialog"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="dialog-body-wrap">
      <ElForm label-position="top" class="config-modal-form">
        <!-- 1. Bot Token -->
        <ElFormItem label="Telegram Bot Token">
          <div class="token-input-row">
            <ElInput
              v-model="props.draft.bot_token"
              placeholder="例如：123456789:AAFxz_SAMPLE_TOKEN"
              type="password"
              show-password
              :disabled="props.readOnly"
            />
            <ElButton
              type="primary"
              plain
              :loading="props.verifying"
              :disabled="!props.draft.bot_token || props.readOnly"
              @click="emit('verify')"
            >
              验证 Token
            </ElButton>
          </div>
          <div class="form-hint">
            向 Telegram 中的 <strong>@BotFather</strong> 发起 <code>/newbot</code> 即可免费获取 API Token
          </div>

          <!-- Token 校验回显卡片 -->
          <div
            v-if="props.verifyResult"
            class="verify-feedback-box"
            :class="props.verifyResult.ok ? 'verify-ok' : 'verify-fail'"
          >
            <ElIcon :size="15">
              <CircleCheck v-if="props.verifyResult.ok" />
              <WarningFilled v-else />
            </ElIcon>
            <div v-if="props.verifyResult.ok" class="feedback-text">
              机器人验证成功：<strong>{{ props.verifyResult.first_name }}</strong>
              <span v-if="props.verifyResult.username"> (@{{ props.verifyResult.username }})</span>
            </div>
            <div v-else class="feedback-text">
              {{ props.verifyResult.error }}
            </div>
          </div>
        </ElFormItem>

        <!-- 2. Chat ID -->
        <ElFormItem label="目标 Chat ID / Group ID">
          <ElInput
            v-model="props.draft.chat_id"
            placeholder="例如：-1001234567890 或管理员个人 ID"
            :disabled="props.readOnly"
          />
          <div class="form-hint">
            接收告警的管理员个人 ID 或 Telegram 群组的负数 ID（需先将机器人拉入群中并设为管理员）
          </div>
        </ElFormItem>

        <!-- 3. 网络代理 -->
        <ElFormItem label="网络连接代理 (Proxy URL，可选)">
          <ElInput
            v-model="props.draft.proxy_url"
            placeholder="例如：http://127.0.0.1:10809 或留空自动继承代理池"
            :disabled="props.readOnly"
          />
          <div class="form-hint">
            在国内服务器环境下必须通过 HTTP / SOCKS5 代理方可访问 Telegram。留空将自动继承本地代理节点池。
          </div>
        </ElFormItem>

        <!-- 4. 启用开关 -->
        <ElFormItem label="启用状态">
          <div class="switch-line">
            <span class="switch-hint">开启后当系统事件发生时将自动向此 Telegram 发送告警</span>
            <ElSwitch
              v-model="props.draft.enabled"
              :disabled="props.readOnly"
              inline-prompt
              active-text="开启"
              inactive-text="关闭"
            />
          </div>
        </ElFormItem>
      </ElForm>
    </div>

    <template #footer>
      <div class="dialog-footer-actions">
        <ElButton @click="emit('update:modelValue', false)">取消</ElButton>
        <ElButton
          type="success"
          plain
          :loading="props.testing"
          :disabled="!props.draft.bot_token || !props.draft.chat_id"
          @click="emit('test')"
        >
          即时发送测试
        </ElButton>
        <ElButton
          type="primary"
          :loading="props.saving"
          :disabled="props.readOnly"
          @click="emit('save')"
        >
          保存配置
        </ElButton>
      </div>
    </template>
  </ElDialog>
</template>
