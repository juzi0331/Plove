<script setup lang="ts">
import {
  ElCard,
  ElDivider,
  ElInputNumber,
  ElSwitch,
} from 'element-plus'
import type { WebhookConfigPayload } from '@/api/types'

const props = defineProps<{
  events: Required<WebhookConfigPayload>['events']
  readOnly: boolean
}>()
</script>

<template>
  <ElCard shadow="hover" class="events-card">
    <div class="event-rows-list">
      <div class="event-item-row">
        <div class="event-meta">
          <div class="event-name">内容源抓取连续异常与熔断警报</div>
          <div class="event-sub">当某个内容源在上游请求、DOM 解析中连续失败达到阈值，或触发自动熔断保护时立即向群内告警</div>
        </div>
        <div class="event-controls">
          <span class="threshold-label">连续失败阈值:</span>
          <ElInputNumber
            v-model="props.events.fail_threshold"
            :min="1"
            :max="10"
            size="small"
            :disabled="props.readOnly"
            style="width: 100px; margin-right: 16px;"
          />
          <ElSwitch
            v-model="props.events.circuit_break"
            :disabled="props.readOnly"
            inline-prompt
            active-text="开启"
            inactive-text="关闭"
          />
        </div>
      </div>

      <ElDivider style="margin: 12px 0;" />

      <div class="event-item-row">
        <div class="event-meta">
          <div class="event-name">代理节点离线与高延迟警报</div>
          <div class="event-sub">当绑定的 VLESS / HTTP 代理节点无法建立 TLS 握手或持续连接超时，自动推送运维提示</div>
        </div>
        <div class="event-controls">
          <ElSwitch
            v-model="props.events.proxy_offline"
            :disabled="props.readOnly"
            inline-prompt
            active-text="开启"
            inactive-text="关闭"
          />
        </div>
      </div>

      <ElDivider style="margin: 12px 0;" />

      <div class="event-item-row">
        <div class="event-meta">
          <div class="event-name">用户端激活码激活与绑定提醒</div>
          <div class="event-sub">当有新激活码首次在客户端激活并绑定设备时，推送设备型号、激活码前缀与有效时长信息</div>
        </div>
        <div class="event-controls">
          <ElSwitch
            v-model="props.events.code_activated"
            :disabled="props.readOnly"
            inline-prompt
            active-text="开启"
            inactive-text="关闭"
          />
        </div>
      </div>

      <ElDivider style="margin: 12px 0;" />

      <div class="event-item-row">
        <div class="event-meta">
          <div class="event-name">每日系统运行简报推送</div>
          <div class="event-sub">每日固定时间分发全站活跃设备数、今日总请求量与缓存截留率综合大盘简报</div>
        </div>
        <div class="event-controls">
          <ElSwitch
            v-model="props.events.daily_report"
            :disabled="props.readOnly"
            inline-prompt
            active-text="开启"
            inactive-text="关闭"
          />
        </div>
      </div>
    </div>
  </ElCard>
</template>
