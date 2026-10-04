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
import { ElButton, ElIcon, ElSkeleton } from 'element-plus'

import PageHeader from '../components/PageHeader.vue'
import { ui } from '../ui'
import { useWebhooks } from './webhooks/useWebhooks'
import WebhooksKpiGrid from './webhooks/WebhooksKpiGrid.vue'
import TelegramBotCard from './webhooks/TelegramBotCard.vue'
import WebhookEventsCard from './webhooks/WebhookEventsCard.vue'
import WebhookLogsTable from './webhooks/WebhookLogsTable.vue'
import TelegramConfigDialog from './webhooks/TelegramConfigDialog.vue'

const {
  loading,
  saving,
  testing,
  verifying,
  clearingLogs,
  configDialogVisible,
  config,
  editDraft,
  verifyResult,
  logs,
  activeEventsCount,
  lastLog,
  loadData,
  handleSave,
  openConfigDialog,
  handleVerifyToken,
  saveDialogConfig,
  handleTest,
  handleClearLogs,
} = useWebhooks()
</script>

<template>
  <div class="a-page webhooks-page">
    <PageHeader
      title="Telegram 机器人"
      desc="配置 Telegram 官方告警机器人通道。当源站采集熔断、代理离线或激活码兑换时，实时向 Telegram 频道或运维群组推送告警。"
    >
      <template #actions>
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
      </template>
    </PageHeader>

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

      <!-- 告警订阅事件规则设置 -->
      <div class="section-title-bar" style="margin-top: 24px;">
        <div class="title-with-icon">
          <ElIcon :size="16"><Promotion /></ElIcon>
          <span>系统事件与告警触发订阅规则</span>
        </div>
      </div>

      <WebhookEventsCard
        :events="config.events"
        :read-only="ui.readOnly"
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
      :verify-result="verifyResult"
      :verifying="verifying"
      :saving="saving"
      :testing="testing"
      :read-only="ui.readOnly"
      @verify="handleVerifyToken"
      @test="handleTest"
      @save="saveDialogConfig"
    />
  </div>
</template>

<style>
@import './webhooks/webhooks.css';
</style>
