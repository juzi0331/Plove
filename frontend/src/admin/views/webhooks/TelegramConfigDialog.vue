<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
  ElOption,
  ElOptionGroup,
  ElSelect,
  ElSwitch,
  ElTag,
} from 'element-plus'
import { CircleCheck, Promotion, Refresh, TopRight, WarningFilled } from '@element-plus/icons-vue'
import type { ProxyNodeItem, TelegramVerifyResult } from '@/api/types'
import { adminPath } from '../../config'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    draft: {
      bot_token: string
      chat_id: string
      proxy_url: string
      console_url?: string
      enabled: boolean
    }
    proxyNodes?: ProxyNodeItem[]
    verifyResult: TelegramVerifyResult | null
    verifying: boolean
    detectingChat?: boolean
    saving: boolean
    testing: boolean
    readOnly: boolean
  }>(),
  {
    proxyNodes: () => [],
    detectingChat: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  verify: []
  detectChat: []
  test: []
  save: []
}>()

const router = useRouter()

function fillCurrentOrigin(): void {
  if (typeof window !== 'undefined') {
    props.draft.console_url = window.location.origin
  }
}

// 代理模式选择
const proxyChoice = ref('')
const customProxyInput = ref('')

function syncProxyFromDraft(): void {
  const current = (props.draft.proxy_url || '').trim()
  if (!current) {
    proxyChoice.value = ''
    customProxyInput.value = ''
    return
  }
  if (current.toLowerCase() === 'direct') {
    proxyChoice.value = 'direct'
    customProxyInput.value = ''
    return
  }
  const matchedNode = (props.proxyNodes || []).find(
    (n) => n.proxy_url === current || n.id === current,
  )
  if (matchedNode) {
    proxyChoice.value = matchedNode.proxy_url
    customProxyInput.value = ''
  } else {
    proxyChoice.value = '__custom__'
    customProxyInput.value = current
  }
}

watch(
  () => [props.modelValue, props.draft.proxy_url, props.proxyNodes],
  () => {
    if (props.modelValue) {
      syncProxyFromDraft()
    }
  },
  { immediate: true },
)

function onProxyChoiceChange(val: string): void {
  if (val === '__custom__') {
    props.draft.proxy_url = customProxyInput.value.trim()
  } else {
    props.draft.proxy_url = val
  }
}

function onCustomProxyInput(val: string): void {
  customProxyInput.value = val
  if (proxyChoice.value === '__custom__') {
    props.draft.proxy_url = val.trim()
  }
}

function goToProxyNodes(): void {
  emit('update:modelValue', false)
  void router.push(adminPath('/proxy-nodes'))
}

function formatNodeLabel(node: ProxyNodeItem): string {
  const proto = (node.protocol || 'TCP').toUpperCase()
  const port = node.port ? `:${node.port}` : ''
  const srv = node.server ? ` (${node.server}${port})` : ''
  const ping = node.ping_ms ? ` - ${node.ping_ms}ms` : ''
  return `${node.name || '未命名节点'} [${proto}${srv}${ping}]`
}
</script>

<template>
  <ElDialog
    :model-value="props.modelValue"
    width="640px"
    align-center
    append-to-body
    destroy-on-close
    class="submodal-dialog"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #header>
      <div class="submodal-header">
        <div class="submodal-icon-badge" style="background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);">
          <ElIcon :size="18"><Promotion /></ElIcon>
        </div>
        <div>
          <div class="submodal-title">Telegram 机器人参数配置</div>
          <div class="submodal-subtitle">配置 Telegram Bot API Token、网络代理穿透及目标频道会话</div>
        </div>
      </div>
    </template>

    <div class="dialog-body-wrap">
      <ElForm label-position="top" class="submodal-form">
        <!-- 1. Bot Token -->
        <div class="form-card-block">
          <div class="block-title">Bot 凭据与鉴权</div>
          <ElFormItem label="Telegram Bot Token *" required>
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
            <div class="form-hint" style="margin-top: 6px;">
              在 Telegram 中向 <strong>@BotFather</strong> 发送 <code>/newbot</code> 即可免费获取 API Token。
            </div>

            <!-- Token 校验回显卡片 -->
            <div
              v-if="props.verifyResult"
              class="verify-feedback-box"
              :class="props.verifyResult.ok ? 'verify-ok' : 'verify-fail'"
              style="margin-top: 8px;"
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
        </div>

        <!-- 2. 网络代理选择 -->
        <div class="form-card-block">
          <div class="block-title">网络连接代理 (Proxy)</div>
          <ElFormItem label="出口代理模式" style="margin-bottom: 0">
            <div class="proxy-select-container">
              <ElSelect
                :model-value="proxyChoice"
                placeholder="选择网络代理连接方式"
                style="width: 100%"
                :disabled="props.readOnly"
                @change="onProxyChoiceChange"
              >
                <ElOption label="🌐 自动继承本地默认代理池 (http://127.0.0.1:10809)" value="" />
                <ElOption label="⚡ 直连 (不通过任何代理，适用于海外服务器)" value="direct" />
                <ElOptionGroup
                  v-if="props.proxyNodes && props.proxyNodes.length > 0"
                  label="已添加的代理节点池"
                >
                  <ElOption
                    v-for="node in props.proxyNodes"
                    :key="node.id"
                    :label="formatNodeLabel(node)"
                    :value="node.proxy_url"
                  >
                    <div class="proxy-node-option-item">
                      <ElTag
                        size="small"
                        :type="node.protocol === 'vless' ? 'warning' : 'primary'"
                        effect="plain"
                      >
                        {{ (node.protocol || 'TCP').toUpperCase() }}
                      </ElTag>
                      <span class="node-name-text">{{ node.name }}</span>
                      <span class="node-url-text">{{ node.server }}:{{ node.port }}</span>
                      <ElTag v-if="node.ping_ms" size="small" type="success" effect="light">
                        {{ node.ping_ms }}ms
                      </ElTag>
                    </div>
                  </ElOption>
                </ElOptionGroup>
                <ElOption label="✏️ 自定义代理地址（手动输入 HTTP / SOCKS5）" value="__custom__" />
              </ElSelect>

              <!-- 手动输入自定义代理输入框 -->
              <transition name="el-fade-in-linear">
                <div v-if="proxyChoice === '__custom__'" class="custom-proxy-wrap" style="margin-top: 8px;">
                  <ElInput
                    :model-value="customProxyInput"
                    placeholder="例如：http://127.0.0.1:10809 或 socks5://127.0.0.1:10808"
                    :disabled="props.readOnly"
                    @input="onCustomProxyInput"
                  />
                </div>
              </transition>

              <div class="proxy-pool-manage-link" style="margin-top: 6px;">
                <ElButton
                  type="primary"
                  link
                  size="small"
                  :icon="TopRight"
                  @click="goToProxyNodes"
                >
                  前往代理节点池管理（添加多个 VLESS 节点 / 测速 / 导出）
                </ElButton>
              </div>
            </div>
            <div class="form-hint" style="margin-top: 6px;">
              国内服务器访问 Telegram 必须通过代理。支持直接下拉选择已配置的代理节点或手动填入。
            </div>
          </ElFormItem>
        </div>

        <!-- 3. Chat ID -->
        <div class="form-card-block">
          <div class="block-title">目标接收会话 (Target Chat)</div>
          <ElFormItem label="目标 Chat ID / Group ID *" required>
            <div class="chat-id-row">
              <ElInput
                v-model="props.draft.chat_id"
                placeholder="例如：123456789 (个人 ID) 或 -1001234567890 (群组 ID)"
                :disabled="props.readOnly"
              />
              <ElButton
                type="primary"
                plain
                :icon="Refresh"
                :loading="props.detectingChat"
                :disabled="!props.draft.bot_token || props.readOnly"
                @click="emit('detectChat')"
              >
                自动获取最新 Chat ID
              </ElButton>
            </div>

            <!-- 贴心的新手指引卡片 -->
            <div class="chat-guidance-card" style="margin-top: 8px;">
              <div class="guidance-line">
                <ElTag size="small" type="success" effect="light">💡 测试阶段无需建群</ElTag>
                <span class="guidance-text">
                  在 Telegram 中搜索你的机器人用户名
                  <strong v-if="props.verifyResult?.username">(@{{ props.verifyResult.username }})</strong>，
                  点击 <strong>【Start】</strong> 或给它发送任意一条消息（如 <code>hi</code>），然后点击上方
                  <strong>【自动获取最新 Chat ID】</strong> 即可一键填入管理员个人私聊 ID；亦可向官方 <code>@userinfobot</code> 发送消息直接查看个人 ID。
                </span>
              </div>
              <div class="guidance-line" style="margin-top: 8px;">
                <ElTag size="small" type="info" effect="plain">👥 运维群组推送</ElTag>
                <span class="guidance-text">
                  若需推送到群组，将机器人拉入群并设为管理员，在群里发一条消息后再点击 <strong>【自动获取最新 Chat ID】</strong> 即可抓取负数群组 ID。
                </span>
              </div>
            </div>
          </ElFormItem>
        </div>

        <!-- 4. 控制台直达地址 -->
        <div class="form-card-block">
          <div class="block-title">控制台直达与快捷入口 (可选)</div>
          <ElFormItem label="控制台直达地址" style="margin-bottom: 0">
            <div class="chat-id-row">
              <ElInput
                v-model="props.draft.console_url"
                placeholder="例如：http://localhost:4000 或 https://ops.yourdomain.com"
                :disabled="props.readOnly"
              />
              <ElButton
                type="primary"
                plain
                size="small"
                :disabled="props.readOnly"
                @click="fillCurrentOrigin"
              >
                填充当前网址
              </ElButton>
            </div>
            <div class="form-hint" style="margin-top: 6px;">
              配置后，Telegram 推送卡片下方将自动挂载【🎬 内容源管理】【🌐 代理节点池】等快捷直达按钮。
            </div>
          </ElFormItem>
        </div>
      </ElForm>
    </div>

    <template #footer>
      <div class="submodal-footer">
        <div class="footer-switch-box">
          <ElSwitch
            v-model="props.draft.enabled"
            :disabled="props.readOnly"
            active-text="机器人通道已生效"
            inactive-text="已关闭通道"
          />
        </div>
        <div class="footer-actions-box">
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
      </div>
    </template>
  </ElDialog>
</template>
