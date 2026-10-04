<script setup lang="ts">
/**
 * Plove Cloud Console - 探针与试播工作台
 *
 * 全面丰富化的多源在线测试中心：
 * 1. 单站深度探针：命令快速切换、自动智能串联测试（免手动输入 vod_id）；
 * 2. 常用预设快捷箱：首页片单即时嗅探、全量分类提取、首部影片详情穿透、真实视频流直放；
 * 3. 全站并发连通性体检矩阵：一键全源并发测速、健康评分对比；
 * 4. 视频流实时试播台：内置播放器、URL 分析与一键复制；
 * 5. 跨源并发搜索比对：多源横向对比返回耗时与匹配数量；
 * 6. 告别空白页面，整体采用卡片网格与专业边距排版。
 */
import {
  ElIcon,
  ElRadioButton,
  ElRadioGroup,
} from 'element-plus'
import { Aim } from '@element-plus/icons-vue'

import { usePlayground } from './playground/usePlayground'
import ProbeWorkflowSection from './playground/ProbeWorkflowSection.vue'
import ProbeResultPanel from './playground/ProbeResultPanel.vue'
import HealthMatrixPanel from './playground/HealthMatrixPanel.vue'
import AggregateSearchPanel from './playground/AggregateSearchPanel.vue'

const {
  activeTab,
  sites,
  probeForm,
  probing,
  probeResult,
  jsonTab,
  matrixList,
  matrixTesting,
  searchKw,
  searching,
  searchResult,
  previewItemList,
  handleRunProbe,
  handleQuickPreset,
  runFullMatrixTest,
  handleAggregateSearch,
  quickSearch,
  formatJson,
  copyText,
} = usePlayground()
</script>

<template>
  <div class="playground-page">
    <!-- 顶部工作台导航条 -->
    <div class="workbench-bar">
      <div class="workbench-header-text">
        <h1 class="workbench-title">探针与在线试播台</h1>
        <p class="workbench-desc">
          提供单站深度调试、全源并发连通性体检、HLS流媒体试播与跨源聚合搜索比对。
        </p>
      </div>
      <div class="workbench-tabs">
        <ElRadioGroup v-model="activeTab" size="default">
          <ElRadioButton value="probe">单站在线探针</ElRadioButton>
          <ElRadioButton value="matrix">全站并发连通性体检</ElRadioButton>
          <ElRadioButton value="search">跨源并发搜索比对</ElRadioButton>
        </ElRadioGroup>
      </div>
    </div>

    <!-- ==================== Tab 1: 单站在线探针 ==================== -->
    <div v-if="activeTab === 'probe'" class="tab-panel">
      <!-- 探针控制与体检工作流 -->
      <ProbeWorkflowSection
        :sites="sites"
        :form="probeForm"
        :probing="probing"
        @run-probe="handleRunProbe"
        @quick-preset="handleQuickPreset"
      />

      <!-- 探测结果展示区 -->
      <ProbeResultPanel
        v-if="probeResult"
        v-model:json-tab="jsonTab"
        :probe-result="probeResult"
        :preview-item-list="previewItemList"
        :format-json="formatJson"
        @copy="copyText"
      />

      <!-- 尚未探测时的就绪引导卡片 -->
      <div v-else class="ready-banner-card">
        <div class="ready-icon"><ElIcon :size="28"><Aim /></ElIcon></div>
        <div class="ready-title">在线探针控制台已就绪</div>
        <div class="ready-sub">点击上方「步骤 1 ~ 4」任一工作流卡片，即可一键对选定源站发起全自动穿透体检与在线播放测试。</div>
      </div>
    </div>

    <!-- ==================== Tab 2: 全站并发连通性体检矩阵 ==================== -->
    <HealthMatrixPanel
      v-else-if="activeTab === 'matrix'"
      :matrix-list="matrixList"
      :matrix-testing="matrixTesting"
      @run-test="runFullMatrixTest"
    />

    <!-- ==================== Tab 3: 跨源并发搜索比对 ==================== -->
    <AggregateSearchPanel
      v-else
      :search-kw="searchKw"
      :searching="searching"
      :search-result="searchResult"
      @update:search-kw="searchKw = $event"
      @search="handleAggregateSearch"
      @quick-search="quickSearch"
    />
  </div>
</template>

<style>
@import './playground/playground.css';
</style>
