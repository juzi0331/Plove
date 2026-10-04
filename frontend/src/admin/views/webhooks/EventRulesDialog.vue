<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  ElButton,
  ElDialog,
  ElIcon,
  ElInputNumber,
  ElRadioButton,
  ElRadioGroup,
  ElSwitch,
  ElTag,
  ElTooltip,
} from 'element-plus'
import { Promotion, Setting } from '@element-plus/icons-vue'
import type { WebhookConfigPayload } from '@/api/types'

type SubscribableEventKey =
  | 'site_health_report'
  | 'circuit_break'
  | 'circuit_recover'
  | 'proxy_offline'
  | 'code_activated'
  | 'device_conflict'
  | 'security_alert'
  | 'daily_report'
  | 'system_startup'

interface EventRuleItem {
  key: SubscribableEventKey
  icon: string
  name: string
  category: 'site' | 'security' | 'cluster'
  tag: string
  tagType: 'danger' | 'success' | 'warning' | 'primary' | 'info'
  desc: string
  hasThreshold?: boolean
}

const props = defineProps<{
  modelValue: boolean
  events: Required<WebhookConfigPayload>['events']
  sendingEvent: string | null
  saving: boolean
  readOnly: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  sendEvent: [eventType: string]
  save: []
}>()

const categoryFilter = ref<'all' | 'site' | 'security' | 'cluster'>('all')

const allEventRules: EventRuleItem[] = [
  {
    key: 'site_health_report',
    icon: '🧭',
    name: '站点清单与连通性自检报告',
    category: 'site',
    tag: '站点巡检',
    tagType: 'success',
    desc: '自动巡检系统接入的全部内容源，汇总站点启用状态、熔断保护健康度与网络代理模式，推送到 Telegram。',
  },
  {
    key: 'circuit_break',
    icon: '🚨',
    name: '内容源抓取连续异常与熔断',
    category: 'site',
    tag: '稳定性',
    tagType: 'danger',
    desc: '当某个内容源在上游请求、DOM 解析中连续失败达到设定阈值时，自动进入熔断保护并向 Telegram 推送告警。',
    hasThreshold: true,
  },
  {
    key: 'circuit_recover',
    icon: '❇️',
    name: '内容源探针自愈恢复通知',
    category: 'site',
    tag: '自愈恢复',
    tagType: 'success',
    desc: '处于熔断冷却的内容源在半开探测中请求成功、熔断解除并恢复正常可用时，即时下发源站健康恢复通知。',
  },
  {
    key: 'proxy_offline',
    icon: '🌐',
    name: '代理节点离线与高延迟警报',
    category: 'cluster',
    tag: '网络链路',
    tagType: 'warning',
    desc: '当绑定的 VLESS / HTTP 代理节点无法建立 TLS 握手或持续连接超时，自动推送运维提示并告警异常节点。',
  },
  {
    key: 'code_activated',
    icon: '🎟️',
    name: '用户端激活码首次激活提醒',
    category: 'cluster',
    tag: '用户业务',
    tagType: 'primary',
    desc: '当有新激活码首次在客户端激活并绑定设备时，推送设备型号、脱敏激活码与有效时长等动态信息。',
  },
  {
    key: 'device_conflict',
    icon: '⚠️',
    name: '同码多设备抢线冲突下线告警',
    category: 'security',
    tag: '账号安全',
    tagType: 'danger',
    desc: '某一激活码已有设备在线，又有新设备接入顶替并踢掉旧设备时触发通知，防范激活码违规外泄共享与倒卖。',
  },
  {
    key: 'security_alert',
    icon: '🛡️',
    name: '接口防刷与高频限流安全告警',
    category: 'security',
    tag: '风控拦截',
    tagType: 'danger',
    desc: '当客户端高频爆破激活码或恶意探测触发频控限制（HTTP 429）被系统临时封禁时，推送来源 IP 告警。',
  },
  {
    key: 'daily_report',
    icon: '📊',
    name: '每日系统运行与运营简报',
    category: 'cluster',
    tag: '运营日报',
    tagType: 'info',
    desc: '每日固定时间汇总全站活跃设备数、激活码消耗、聚合内容源健康度等核心运行大盘指标。',
  },
  {
    key: 'system_startup',
    icon: '🚀',
    name: 'Plove 服务集群就绪与重启通知',
    category: 'cluster',
    tag: '集群运维',
    tagType: 'success',
    desc: '当后端服务重新启动、数据库连接就绪、后台守护进程与看门狗加载完成时下发集群状态通知。',
  },
]

const filteredRules = computed(() => {
  if (categoryFilter.value === 'all') return allEventRules
  return allEventRules.filter((r) => r.category === categoryFilter.value)
})

const activeCount = computed(() => {
  let count = 0
  const ev = props.events
  for (const r of allEventRules) {
    if (ev[r.key]) count++
  }
  return count
})
</script>

<template>
  <ElDialog
    :model-value="props.modelValue"
    title="告警事件触发与订阅规则配置"
    width="920px"
    class="event-rules-modal"
    destroy-on-close
    append-to-body
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="rules-dialog-content">
      <!-- 顶部说明与筛选胶囊 -->
      <div class="dialog-banner">
        <div class="banner-left">
          <div class="banner-title">
            <ElIcon class="banner-icon"><Setting /></ElIcon>
            <span>系统监控订阅中心</span>
            <ElTag size="small" type="primary" effect="dark" round>
              已订阅 {{ activeCount }} / {{ allEventRules.length }} 项
            </ElTag>
          </div>
          <div class="banner-subtitle">
            配置 9 大核心监控规则的自动推送开关与熔断阈值。每个事件均支持随时点击【发送测试】验证 Telegram 实际呈现。
          </div>
        </div>

        <div class="filter-radio-group">
          <ElRadioGroup v-model="categoryFilter" size="small">
            <ElRadioButton label="all">全部 (9)</ElRadioButton>
            <ElRadioButton label="site">站点与健康 (3)</ElRadioButton>
            <ElRadioButton label="security">安全与风控 (2)</ElRadioButton>
            <ElRadioButton label="cluster">集群与业务 (4)</ElRadioButton>
          </ElRadioGroup>
        </div>
      </div>

      <!-- 规则卡片网格 -->
      <div class="rules-dialog-grid">
        <div
          v-for="card in filteredRules"
          :key="card.key"
          class="rule-box"
          :class="{ 'rule-box-inactive': !props.events[card.key] }"
        >
          <!-- 头部: 图标 + 标题 + 标签 -->
          <div class="rule-box-header">
            <div class="rule-box-title">
              <span class="rule-box-icon">{{ card.icon }}</span>
              <span class="rule-box-name">{{ card.name }}</span>
            </div>
            <ElTag size="small" :type="card.tagType as any" effect="light">
              {{ card.tag }}
            </ElTag>
          </div>

          <!-- 描述 -->
          <div class="rule-box-desc">
            {{ card.desc }}
          </div>

          <!-- 阈值调节器（熔断规则） -->
          <div v-if="card.hasThreshold" class="rule-threshold-bar">
            <span class="threshold-label">连续失败阈值:</span>
            <ElInputNumber
              v-model="props.events.fail_threshold"
              :min="1"
              :max="10"
              size="small"
              :disabled="props.readOnly"
              style="width: 96px;"
            />
            <span class="threshold-unit">次失败进入熔断</span>
          </div>

          <!-- 卡片底栏: 开启开关 + 手动发送测试按钮 -->
          <div class="rule-box-footer">
            <div class="switch-box">
              <ElSwitch
                v-model="props.events[card.key]"
                :disabled="props.readOnly"
                inline-prompt
                active-text="开启"
                inactive-text="关闭"
              />
            </div>

            <ElTooltip
              content="模拟该事件触发，立即向 Telegram 发送真实富文本卡片"
              placement="top"
              :show-after="300"
            >
              <ElButton
                type="primary"
                plain
                size="small"
                :icon="Promotion"
                :loading="props.sendingEvent === card.key"
                :disabled="props.readOnly"
                class="send-test-btn"
                @click="emit('sendEvent', card.key)"
              >
                发送测试
              </ElButton>
            </ElTooltip>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <div class="footer-tip">
          💡 修改订阅规则与阈值后，请点击「保存规则设置」应用到服务
        </div>
        <div class="footer-btns">
          <ElButton @click="emit('update:modelValue', false)">关闭</ElButton>
          <ElButton
            type="primary"
            :loading="props.saving"
            :disabled="props.readOnly"
            @click="emit('save')"
          >
            保存规则设置
          </ElButton>
        </div>
      </div>
    </template>
  </ElDialog>
</template>

<style scoped>
.rules-dialog-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-height: 70vh;
  overflow-y: auto;
  padding-right: 4px;
}

.dialog-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding: 14px 16px;
  background: var(--a-bg-subtle, #f8fafc);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: 10px;
}

.banner-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.banner-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 700;
  color: var(--a-text, #0f172a);
}

.banner-icon {
  font-size: 16px;
  color: #0284c7;
}

.banner-subtitle {
  font-size: 12px;
  color: var(--a-text-2, #64748b);
}

/* 规则网格: 双列 */
.rules-dialog-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

@media (max-width: 720px) {
  .rules-dialog-grid {
    grid-template-columns: 1fr;
  }
}

.rule-box {
  background: var(--a-card, #ffffff);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: 10px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}

.rule-box:hover {
  border-color: #38bdf8;
  box-shadow: 0 4px 12px rgba(2, 132, 199, 0.08);
  transform: translateY(-1px);
}

.rule-box-inactive {
  opacity: 0.65;
  background: var(--a-bg-subtle, #f8fafc);
  filter: grayscale(0.2);
}

.rule-box-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.rule-box-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.rule-box-icon {
  font-size: 18px;
  line-height: 1;
  flex-shrink: 0;
}

.rule-box-name {
  font-size: 13.5px;
  font-weight: 700;
  color: var(--a-text, #0f172a);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rule-box-desc {
  font-size: 12px;
  line-height: 1.55;
  color: var(--a-text-2, #64748b);
  margin-bottom: 12px;
  min-height: 38px;
}

.rule-threshold-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #fef2f2;
  border: 1px dashed #fca5a5;
  border-radius: 6px;
  padding: 6px 10px;
  margin-bottom: 12px;
}

.threshold-label {
  font-size: 11.5px;
  color: #991b1b;
  font-weight: 600;
}

.threshold-unit {
  font-size: 11.5px;
  color: #991b1b;
}

.rule-box-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 10px;
  border-top: 1px solid var(--a-border-subtle, #f1f5f9);
}

.send-test-btn {
  font-size: 11.5px;
  height: 28px;
  padding: 0 10px;
}

.dialog-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.footer-tip {
  font-size: 12px;
  color: var(--a-text-2, #64748b);
}

.footer-btns {
  display: flex;
  gap: 8px;
}
</style>
