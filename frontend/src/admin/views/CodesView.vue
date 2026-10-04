<script setup lang="ts">
/**
 * 激活码管理（卡片式模块架构）：
 * 1. 顶部激活码总控与批量发码卡片；
 * 2. 授权状态指标卡片（在用、未激活、到期、停用分布）；
 * 3. 激活码全功能卡片列表（包含行内一键复制、状态徽章、延长、停用/解封、彻底删除）；
 * 4. 绑定设备卡片式即时抽屉/弹窗（无需跳转新页面，直接在当前页面查看设备、踢下线或解绑释放名额）。
 */
import ErrorState from '../components/ErrorState.vue'
import PageHeader from '../components/PageHeader.vue'

import { useCodes } from './codes/useCodes'
import CodesSummaryCards from './codes/CodesSummaryCards.vue'
import CodesTable from './codes/CodesTable.vue'
import IssueCodeDialog from './codes/IssueCodeDialog.vue'
import ExtendCodeDialog from './codes/ExtendCodeDialog.vue'
import CodeDevicesDialog from './codes/CodeDevicesDialog.vue'

const {
  data,
  loading,
  error,
  search,
  page,
  pageSize,
  load,
  onSearch,
  onPageChange,
  onPageSizeChange,
  isEmpty,
  stats,
  rowClass,
  widthOf,
  onHeaderDragend,
  copyText,
  issueOpen,
  issueBusy,
  issueForm,
  issuedCodes,
  activePreset,
  applyPreset,
  submitIssue,
  toggleDisabled,
  extendOpen,
  extendBusy,
  extendHours,
  extendTarget,
  openExtend,
  submitExtend,
  handleDeleteCode,
  handleCleanupExpired,
  deviceDialogVisible,
  currentDeviceCode,
  devicesList,
  loadingDevices,
  openDevicesCard,
  loadDevices,
  handleKickDevice,
  handleUnbindDevice,
} = useCodes()
</script>

<template>
  <div class="codes-page">
    <PageHeader
      title="激活码管理"
      desc="全功能卡片式授权总控。支持生成多设备激活码、有效期延长、停用/解封，以及卡片内即时管控绑定设备与踢线，无需跳转页面。"
    />

    <ErrorState v-if="error" :message="error" @retry="load" />

    <!-- 顶部总控卡片矩阵 (发码卡片 + 状态指标卡片) -->
    <CodesSummaryCards
      :total-count="data?.total ?? 0"
      :search="search"
      :loading="loading"
      :stats="stats"
      :issued-codes="issuedCodes"
      @update:search="search = $event"
      @search="onSearch"
      @load="load"
      @open-issue="issueOpen = true"
      @cleanup-expired="handleCleanupExpired"
      @copy-text="copyText"
    />

    <!-- 数据列表卡片 -->
    <CodesTable
      :data="data"
      :loading="loading"
      :is-empty="isEmpty"
      :page="page"
      :page-size="pageSize"
      :row-class="rowClass"
      :width-of="widthOf"
      @header-dragend="onHeaderDragend"
      @copy-text="copyText"
      @open-devices-card="openDevicesCard"
      @open-extend="openExtend"
      @toggle-disabled="toggleDisabled"
      @delete-code="handleDeleteCode"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
      @open-issue="issueOpen = true"
    />

    <!-- 弹窗 1: 发码对话框 -->
    <IssueCodeDialog
      v-model="issueOpen"
      :issue-busy="issueBusy"
      :issue-form="issueForm"
      :active-preset="activePreset"
      @apply-preset="applyPreset"
      @submit="submitIssue"
    />

    <!-- 弹窗 2: 延长有效期对话框 -->
    <ExtendCodeDialog
      v-model="extendOpen"
      :extend-target="extendTarget"
      :extend-hours="extendHours"
      :extend-busy="extendBusy"
      @update:extend-hours="extendHours = $event"
      @submit="submitExtend"
    />

    <!-- 弹窗 3: 卡片式绑定设备即时管理 -->
    <CodeDevicesDialog
      v-model="deviceDialogVisible"
      :current-device-code="currentDeviceCode"
      :devices-list="devicesList"
      :loading-devices="loadingDevices"
      @refresh="currentDeviceCode && loadDevices(currentDeviceCode.id)"
      @kick-device="handleKickDevice"
      @unbind-device="handleUnbindDevice"
    />
  </div>
</template>

<style scoped src="./codes/codes.css"></style>
