<script setup lang="ts">
import { computed } from 'vue'
import { ElButton, ElCard, ElIcon, ElTag, ElTooltip } from 'element-plus'
import {
  Bell,
  Compass,
  Notification,
  Promotion,
  Setting,
} from '@element-plus/icons-vue'
import type { WebhookConfigPayload } from '@/api/types'

const props = defineProps<{
  events: Required<WebhookConfigPayload>['events']
  sendingEvent: string | null
  readOnly: boolean
}>()

const emit = defineEmits<{
  sendEvent: [eventType: string]
  openRules: []
  openCustomNotice: []
}>()

const activeCount = computed(() => {
  let count = 0
  const ev = props.events
  if (ev.circuit_break) count++
  if (ev.circuit_recover) count++
  if (ev.site_health_report) count++
  if (ev.code_activated) count++
  if (ev.device_conflict) count++
  if (ev.security_alert) count++
  if (ev.proxy_offline) count++
  if (ev.daily_report) count++
  if (ev.system_startup) count++
  return count
})

// 三大监控领域总览分组
const domainGroups = computed(() => [
  {
    title: '🧭 站点与健康巡检',
    badge: '3 项规则',
    desc: '聚合内容源全盘扫描、抓取熔断与探针自愈',
    items: [
      {
        key: 'site_health_report',
        name: '站点连通性巡检',
        active: !!props.events.site_health_report,
        icon: '🧭',
        highlight: true,
      },
      {
        key: 'circuit_break',
        name: '内容源熔断告警',
        active: !!props.events.circuit_break,
        icon: '🚨',
      },
      {
        key: 'circuit_recover',
        name: '探针自愈恢复',
        active: !!props.events.circuit_recover,
        icon: '❇️',
      },
    ],
  },
  {
    title: '🛡️ 安全风控与防刷',
    badge: '2 项规则',
    desc: '爆破限流阻断、同激活码多设备抢线顶号',
    items: [
      {
        key: 'security_alert',
        name: '接口防刷限流',
        active: !!props.events.security_alert,
        icon: '🛡️',
      },
      {
        key: 'device_conflict',
        name: '多设备抢线冲突',
        active: !!props.events.device_conflict,
        icon: '⚠️',
      },
    ],
  },
  {
    title: '🌐 集群与业务大盘',
    badge: '4 项规则',
    desc: '代理链路健康、激活码消耗、每日运营与服务启动',
    items: [
      {
        key: 'proxy_offline',
        name: '代理节点离线',
        active: !!props.events.proxy_offline,
        icon: '🌐',
      },
      {
        key: 'code_activated',
        name: '激活码绑定通知',
        active: !!props.events.code_activated,
        icon: '🎟️',
      },
      {
        key: 'daily_report',
        name: '每日运营简报',
        active: !!props.events.daily_report,
        icon: '📊',
      },
      {
        key: 'system_startup',
        name: '服务集群就绪',
        active: !!props.events.system_startup,
        icon: '🚀',
      },
    ],
  },
])
</script>

<template>
  <ElCard shadow="hover" class="ops-hub-card">
    <template #header>
      <div class="hub-header">
        <div class="header-left">
          <div class="hub-icon-wrapper">
            <ElIcon :size="20"><Bell /></ElIcon>
          </div>
          <div class="header-text">
            <div class="hub-title-row">
              <span class="hub-title">自动化告警与运维推送中心</span>
              <ElTag size="small" type="success" effect="light" round>
                监控就绪 {{ activeCount }} / 9 项
              </ElTag>
            </div>
            <div class="hub-desc">
              覆盖站点健康巡检、抓取熔断自愈、接口防刷限流与集群运行大盘，支持一键弹窗管理与独立模拟测试
            </div>
          </div>
        </div>

        <div class="header-actions">
          <!-- 站点连通性巡检快捷触发 -->
          <ElTooltip
            content="立即汇总所有添加站点的启用状态、健康度与代理模式，推送到 Telegram"
            placement="top"
            :show-after="300"
          >
            <ElButton
              type="success"
              plain
              :icon="Compass"
              :loading="props.sendingEvent === 'site_health_report'"
              :disabled="props.readOnly"
              class="action-btn"
              @click="emit('sendEvent', 'site_health_report')"
            >
              站点连通性巡检推送
            </ElButton>
          </ElTooltip>

          <!-- 发送自定义广播弹窗按钮 -->
          <ElButton
            type="primary"
            plain
            :icon="Notification"
            :disabled="props.readOnly"
            class="action-btn"
            @click="emit('openCustomNotice')"
          >
            发送自定义广播
          </ElButton>

          <!-- 告警规则弹窗管理按钮 -->
          <ElButton
            type="primary"
            :icon="Setting"
            :disabled="props.readOnly"
            class="action-btn"
            @click="emit('openRules')"
          >
            告警订阅规则与测试
          </ElButton>
        </div>
      </div>
    </template>

    <!-- 三大领域全景总览面板 -->
    <div class="domains-overview-grid">
      <div
        v-for="grp in domainGroups"
        :key="grp.title"
        class="domain-column"
      >
        <div class="domain-header">
          <div class="domain-title-box">
            <span class="domain-title">{{ grp.title }}</span>
            <ElTag size="small" type="info" effect="plain">{{ grp.badge }}</ElTag>
          </div>
          <div class="domain-desc">{{ grp.desc }}</div>
        </div>

        <div class="domain-chips-list">
          <div
            v-for="item in grp.items"
            :key="item.key"
            class="event-status-chip"
            :class="{
              'chip-active': item.active,
              'chip-inactive': !item.active,
              'chip-highlight': item.highlight,
            }"
          >
            <div class="chip-main">
              <span class="chip-icon">{{ item.icon }}</span>
              <span class="chip-name">{{ item.name }}</span>
            </div>
            <div class="chip-tail">
              <span
                class="status-dot"
                :class="item.active ? 'dot-on' : 'dot-off'"
              />
              <ElTooltip
                :content="`即时模拟【${item.name}】向 Telegram 发送测试卡片`"
                placement="top"
                :show-after="200"
              >
                <button
                  type="button"
                  class="chip-test-btn"
                  :disabled="props.readOnly || props.sendingEvent === item.key"
                  @click="emit('sendEvent', item.key)"
                >
                  <ElIcon :size="12"><Promotion /></ElIcon>
                </button>
              </ElTooltip>
            </div>
          </div>
        </div>
      </div>
    </div>
  </ElCard>
</template>

<style scoped>
.ops-hub-card {
  border-radius: 12px;
  border: 1px solid var(--a-border, #e2e8f0);
  background: var(--a-card, #ffffff);
  margin-bottom: 20px;
}

.hub-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.hub-icon-wrapper {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: #f0f9ff;
  color: #0284c7;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #bae6fd;
}

.header-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.hub-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.hub-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--a-text, #0f172a);
}

.hub-desc {
  font-size: 12.5px;
  color: var(--a-text-2, #64748b);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.action-btn {
  font-weight: 600;
}

/* 领域总览网格 */
.domains-overview-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

@media (max-width: 900px) {
  .domains-overview-grid {
    grid-template-columns: 1fr;
  }
}

.domain-column {
  background: var(--a-bg-subtle, #f8fafc);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: 10px;
  padding: 14px 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.domain-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-bottom: 8px;
  border-bottom: 1px dashed var(--a-border, #e2e8f0);
}

.domain-title-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.domain-title {
  font-size: 13.5px;
  font-weight: 700;
  color: var(--a-text, #0f172a);
}

.domain-desc {
  font-size: 11.5px;
  color: var(--a-text-2, #64748b);
  line-height: 1.4;
}

.domain-chips-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.event-status-chip {
  background: var(--a-card, #ffffff);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: 8px;
  padding: 8px 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  transition: all 0.15s ease;
}

.event-status-chip:hover {
  border-color: #38bdf8;
  box-shadow: 0 2px 6px rgba(2, 132, 199, 0.06);
}

.chip-highlight {
  border-color: #86efac;
  background: #f0fdf4;
}

.chip-highlight:hover {
  border-color: #22c55e;
}

.chip-inactive {
  opacity: 0.65;
}

.chip-main {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--a-text, #1e293b);
}

.chip-icon {
  font-size: 15px;
  line-height: 1;
}

.chip-tail {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.dot-on {
  background: #22c55e;
  box-shadow: 0 0 6px #22c55e;
}

.dot-off {
  background: #94a3b8;
}

.chip-test-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  color: #64748b;
  padding: 3px 5px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}

.chip-test-btn:hover {
  color: #0284c7;
  background: #e0f2fe;
}
</style>
