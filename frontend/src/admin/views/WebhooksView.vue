<script setup lang="ts">
/**
 * WebhooksView - Telegram 告警与通知机器人管理中心
 *
 * 专注于 Telegram 官方 Bot 自动化推送：
 * 1. Bot Token 校验与机器人信息拉取 (getMe)
 * 2. 目标 Chat ID / 频道群组配置
 * 3. HTTP / SOCKS5 代理穿透支持 (适应国内环境)
 * 4. 弹出式参数配置卡片 (Dialog 模态设计)
 * 5. 核心告警规则订阅矩阵 (源站熔断、代理离线、激活码使用、每日简报)
 * 6. 一键连通性测试与投递日志审计
 */
import { Check, Promotion, Refresh } from '@element-plus/icons-vue'
import { ElButton, ElIcon, ElSkeleton, ElTag } from 'element-plus'

import { ui } from '../ui'
import { useWebhooks } from './webhooks/useWebhooks'
import WebhooksKpiGrid from './webhooks/WebhooksKpiGrid.vue'
import TelegramBotCard from './webhooks/TelegramBotCard.vue'
import WebhookEventsCard from './webhooks/WebhookEventsCard.vue'
import WebhookLogsTable from './webhooks/WebhookLogsTable.vue'
import TelegramConfigDialog from './webhooks/TelegramConfigDialog.vue'
import EventRulesDialog from './webhooks/EventRulesDialog.vue'
import CustomNoticeDialog from './webhooks/CustomNoticeDialog.vue'

const {
  loading,
  saving,
  testing,
  verifying,
  detectingChat,
  clearingLogs,
  configDialogVisible,
  rulesDialogVisible,
  customNoticeDialogVisible,
  proxyNodes,
  config,
  editDraft,
  verifyResult,
  logs,
  activeEventsCount,
  lastLog,
  sendingEvent,
  sendingCustomNotice,
  customNoticeDraft,
  loadData,
  handleSave,
  openConfigDialog,
  handleVerifyToken,
  handleDetectChat,
  saveDialogConfig,
  handleTest,
  handleClearLogs,
  handleSendEvent,
  handleSendCustomNotice,
} = useWebhooks()
</script>

<template>
  <div class="a-page webhooks-page">
    <!-- 顶部状态大屏 (统一样式标准) -->
    <div class="dash-hero">
      <div class="dash-hero-info">
        <div class="hero-badge">
          <span class="hero-pulse" :class="{ 'is-maint': !config.telegram.enabled }" />
          <span>{{ config.telegram.enabled ? 'Telegram 机器人推送生效中' : '机器人通道已停用' }}</span>
        </div>
        <h1 class="hero-title">Telegram 机器人告警中心</h1>
        <p class="hero-desc">
          配置 Telegram 官方告警机器人通道。当源站采集熔断、代理离线或激活码兑换时，实时向 Telegram 频道或运维群组推送告警。
        </p>
      </div>

      <div class="dash-hero-actions">
        <ElTag :type="config.telegram.enabled ? 'success' : 'info'" effect="light" size="default" style="font-weight: 600;">
          {{ config.telegram.enabled ? '● 机器人已在线' : '● 通道待启动' }}
        </ElTag>
        <ElButton
          :icon="Refresh"
          :loading="loading"
          @click="loadData"
        >
          刷新
        </ElButton>
        <ElButton
          type="primary"
          :icon="Check"
          :loading="saving"
          :disabled="ui.readOnly"
          @click="handleSave"
        >
          保存全部配置
        </ElButton>
      </div>
    </div>

    <!-- 骨架屏加载状态 -->
    <div v-if="loading && !config.telegram.chat_id && logs.length === 0" class="a-card skeleton">
      <ElSkeleton :rows="6" animated />
    </div>

    <template v-else>
      <!-- 顶部核心指标看板 -->
      <WebhooksKpiGrid
        :enabled="config.telegram.enabled"
        :chat-id="config.telegram.chat_id"
        :proxy-url="config.telegram.proxy_url"
        :active-events-count="activeEventsCount"
      />

      <!-- Telegram 核心卡片展示 -->
      <div class="section-title-bar">
        <div class="title-with-icon">
          <ElIcon :size="16"><Promotion /></ElIcon>
          <span>Telegram 机器人核心通道</span>
        </div>
      </div>

      <TelegramBotCard
        :telegram="config.telegram"
        :last-log="lastLog"
        :testing="testing"
        :read-only="ui.readOnly"
        @open-config="openConfigDialog"
        @save="handleSave"
        @test="handleTest"
      />

      <!-- 自动化告警规则与运维推送中心 -->
      <WebhookEventsCard
        :events="config.events"
        :sending-event="sendingEvent"
        :read-only="ui.readOnly"
        @send-event="handleSendEvent"
        @open-rules="rulesDialogVisible = true"
        @open-custom-notice="customNoticeDialogVisible = true"
      />

      <!-- 投递审计日志 -->
      <WebhookLogsTable
        :logs="logs"
        :clearing="clearingLogs"
        :read-only="ui.readOnly"
        @clear="handleClearLogs"
      />
    </template>

    <!-- 弹出式参数配置卡片 -->
    <TelegramConfigDialog
      v-model="configDialogVisible"
      :draft="editDraft"
      :proxy-nodes="proxyNodes"
      :verify-result="verifyResult"
      :verifying="verifying"
      :detecting-chat="detectingChat"
      :saving="saving"
      :testing="testing"
      :read-only="ui.readOnly"
      @verify="handleVerifyToken"
      @detect-chat="handleDetectChat"
      @test="handleTest"
      @save="saveDialogConfig"
    />

    <!-- 弹出式告警规则与手动测试模态弹窗 -->
    <EventRulesDialog
      v-model="rulesDialogVisible"
      :events="config.events"
      :sending-event="sendingEvent"
      :saving="saving"
      :read-only="ui.readOnly"
      @send-event="handleSendEvent"
      @save="handleSave"
    />

    <!-- 弹出式自定义即时广播模态弹窗 -->
    <CustomNoticeDialog
      v-model="customNoticeDialogVisible"
      :draft="customNoticeDraft"
      :sending="sendingCustomNotice"
      :read-only="ui.readOnly"
      @send="handleSendCustomNotice"
    />
  </div>
</template>

<style>
@import './webhooks/webhooks.css';
</style>
