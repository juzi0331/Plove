<script setup lang="ts">
defineProps<{
  enabled?: boolean
  chatId?: string
  proxyUrl?: string
  activeEventsCount: number
}>()
</script>

<template>
  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-title">机器人运行状态</div>
      <div class="kpi-main">
        <span
          class="kpi-status-dot"
          :class="enabled ? 'dot-active' : 'dot-inactive'"
        />
        <span class="kpi-num-text">
          {{ enabled ? '已启用推送' : '未开启' }}
        </span>
      </div>
      <div class="kpi-desc">
        {{ enabled ? '全天候监听并推送关键告警' : '启用后将自动下发群消息' }}
      </div>
    </div>

    <div class="kpi-card">
      <div class="kpi-title">目标接收群组 / 频道</div>
      <div class="kpi-main">
        <span class="kpi-mono-val">
          {{ chatId || '未绑定 Chat ID' }}
        </span>
      </div>
      <div class="kpi-desc">管理员个人或超级群组 ID</div>
    </div>

    <div class="kpi-card">
      <div class="kpi-title">网络连接代理</div>
      <div class="kpi-main">
        <span class="kpi-mono-val">
          {{ proxyUrl || '自动继承本地代理池' }}
        </span>
      </div>
      <div class="kpi-desc">确保国内网络环境下 API 正常连通</div>
    </div>

    <div class="kpi-card">
      <div class="kpi-title">已订阅告警事件</div>
      <div class="kpi-main">
        <span class="kpi-num">{{ activeEventsCount }}</span>
        <span class="kpi-unit">/ 9 项</span>
      </div>
      <div class="kpi-desc">覆盖站点巡检、熔断自愈、抢线防刷等</div>
    </div>
  </div>
</template>
