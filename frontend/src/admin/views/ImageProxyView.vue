<script setup lang="ts">
/**
 * 图片防盗链代理总控与解密配置：
 * 1. 全局海报防盗链中继总控（卡片展示，点击弹出配置详情，支持伪装/穿透）；
 * 2. 第三方源站加密海报动态解密配置（卡片展示，点击弹出规则管理弹窗，支持动态 AES-128 Key/IV、AI 导入与在线验证）。
 */
import {
  ElButton,
  ElCard,
  ElIcon,
  ElSwitch,
  ElTag,
} from 'element-plus'
import {
  Key,
  MagicStick,
  Plus,
  Promotion,
  Refresh,
  Setting,
} from '@element-plus/icons-vue'
import { onMounted } from 'vue'

import { ui } from '@/admin/ui'
import { useImageProxy } from './image-proxy/useImageProxy'
import GlobalProxyDialog from './image-proxy/GlobalProxyDialog.vue'
import DecryptionRulesDialog from './image-proxy/DecryptionRulesDialog.vue'
import CdnPrefixDialog from './image-proxy/CdnPrefixDialog.vue'

const {
  loading,
  savingConfig,
  config,
  rulesList,
  showGlobalProxyDialog,
  showDecryptionDialog,
  showSecret,
  toggleSecret,
  copyRuleKey,
  showRuleDialog,
  isEditing,
  domainsInput,
  ruleForm,
  openAddRule,
  openEditRule,
  fillHuangguoaiSample,
  handleSaveRule,
  handleDeleteRule,
  handleToggleRule,
  inlineTestUrl,
  inlineTesting,
  inlineTestResult,
  runInlineTest,
  showAiImportDialog,
  aiImportText,
  openAiImport,
  handleParseAiJson,
  showTestModal,
  testModalRule,
  testModalUrl,
  testModalLoading,
  testModalResult,
  openTestRuleModal,
  runModalTest,
  loadData,
  handleSaveConfig,
  handleSaveConfigAndCloseDialog,
  // CDN 前缀规则
  cdnRulesList,
  showCdnPrefixDialog,
  showCdnRuleEditDialog,
  isEditingCdnRule,
  cdnRuleForm,
  openAddCdnRule,
  openEditCdnRule,
  handleSaveCdnRule,
  handleDeleteCdnRule,
  handleToggleCdnRule,
} = useImageProxy()

onMounted(() => {
  void loadData()
})
</script>

<template>
  <div class="proxy-page">
    <!-- 顶栏标题 -->
    <div class="header-section">
      <div>
        <h2 class="title">图片防盗链代理</h2>
        <p class="subtitle">
          解决第三方影视站/图床开启防盗链导致前台海报 403 破图问题。支持 Referer 伪装与穿透，以及第三方源站加密海报动态流式解密。
        </p>
      </div>
      <div class="header-actions">
        <ElButton :icon="Refresh" :loading="loading" @click="loadData">刷新状态</ElButton>
      </div>
    </div>

    <!-- 核心板块卡片矩阵 (全卡片化设计) -->
    <div class="cards-grid">
      <!-- 卡片 1: 全局海报防盗链中继总控 -->
      <ElCard shadow="hover" class="module-card relay-card" @click="showGlobalProxyDialog = true">
        <div class="card-top-bar">
          <div class="card-title-group">
            <div class="card-icon-box relay-icon">
              <ElIcon :size="20"><Setting /></ElIcon>
            </div>
            <div>
              <div class="card-title">全局海报防盗链中继总控</div>
              <div class="card-subtitle">前台全站海报统一代理中继，彻底解决 403 破图</div>
            </div>
          </div>
          <ElTag :type="config.global_proxy_enabled ? 'success' : 'info'" effect="dark" class="status-tag">
            {{ config.global_proxy_enabled ? '全局中继已生效' : '原图直连（未开启）' }}
          </ElTag>
        </div>

        <div class="card-body-section">
          <div class="info-pill-grid">
            <div class="info-pill-item">
              <span class="pill-label">中继状态</span>
              <div class="pill-value-switch" @click.stop>
                <ElSwitch
                  v-model="config.global_proxy_enabled"
                  :disabled="ui.readOnly"
                  active-text="开启"
                  inactive-text="关闭"
                  @change="handleSaveConfig"
                />
              </div>
            </div>

            <div class="info-pill-item">
              <span class="pill-label">Referer 策略</span>
              <ElTag
                size="small"
                :type="config.auto_strip_referer ? 'success' : 'info'"
                effect="plain"
                class="pill-tag"
              >
                {{ config.auto_strip_referer ? '伪装' : '穿透' }}
              </ElTag>
            </div>

            <div class="info-pill-item">
              <span class="pill-label">伪装 Referer</span>
              <span class="pill-value-text" :title="config.custom_referer || '自动同源 (Host)'">
                {{ config.custom_referer ? config.custom_referer : '自动同源 (Host)' }}
              </span>
            </div>
          </div>
        </div>

        <div class="card-bottom-bar">
          <span class="card-hint-text">点击卡片查看与调整中继详情参数</span>
          <ElButton
            type="primary"
            link
            :icon="Setting"
            @click.stop="showGlobalProxyDialog = true"
          >
            配置详情 →
          </ElButton>
        </div>
      </ElCard>

      <!-- 卡片 2: 第三方源站加密海报动态解密配置 -->
      <ElCard shadow="hover" class="module-card decrypt-card" @click="showDecryptionDialog = true">
        <div class="card-top-bar">
          <div class="card-title-group">
            <div class="card-icon-box decrypt-icon">
              <ElIcon :size="20"><Key /></ElIcon>
            </div>
            <div>
              <div class="card-title">第三方源站加密海报动态解密配置</div>
              <div class="card-subtitle">支持 AES-128 等前端加密海报流式解密，无需修改源码</div>
            </div>
          </div>
          <ElTag type="warning" effect="dark" class="status-tag">
            {{ rulesList.filter(r => r.enabled).length }} / {{ rulesList.length }} 规则生效中
          </ElTag>
        </div>

        <div class="card-body-section">
          <div class="info-pill-grid">
            <div class="info-pill-item">
              <span class="pill-label">已配置规则</span>
              <span class="pill-value-number">{{ rulesList.length }} <small>条</small></span>
            </div>

            <div class="info-pill-item">
              <span class="pill-label">算法支持</span>
              <span class="pill-value-text">AES-128-CBC / ECB</span>
            </div>

            <div class="info-pill-item">
              <span class="pill-label">特征站点/图床</span>
              <span class="pill-value-text">
                {{ rulesList.length > 0 ? (rulesList[0].site_key || rulesList[0].match_domains?.[0] || '通用图床') : '暂无规则' }}
                <span v-if="rulesList.length > 1" style="opacity: 0.6;"> +{{ rulesList.length - 1 }}</span>
              </span>
            </div>
          </div>
        </div>

        <div class="card-bottom-bar">
          <div class="quick-btn-group" @click.stop>
            <ElButton
              size="small"
              type="warning"
              plain
              :icon="MagicStick"
              @click.stop="openAiImport"
            >
              AI 导入
            </ElButton>
            <ElButton
              size="small"
              type="primary"
              plain
              :icon="Plus"
              :disabled="ui.readOnly"
              @click.stop="openAddRule"
            >
              添加规则
            </ElButton>
          </div>
          <ElButton
            type="primary"
            link
            @click.stop="showDecryptionDialog = true"
          >
            管理解密规则 →
          </ElButton>
        </div>
      </ElCard>

      <!-- 卡片 3: 图床加速与代理前缀路由 (CDN Prefix Relay) -->
      <ElCard shadow="hover" class="module-card cdn-card" @click="showCdnPrefixDialog = true">
        <div class="card-top-bar">
          <div class="card-title-group">
            <div class="card-icon-box cdn-icon" style="background: rgba(14, 165, 233, 0.12); color: #0ea5e9">
              <ElIcon :size="20"><Promotion /></ElIcon>
            </div>
            <div>
              <div class="card-title">图床加速与代理前缀路由</div>
              <div class="card-subtitle">按站点/域名指定免费边缘 CDN 反代（如 wsrv.nl），解决被墙与丢包破图</div>
            </div>
          </div>
          <ElTag type="success" effect="dark" class="status-tag">
            {{ cdnRulesList.filter(r => r.enabled).length }} / {{ cdnRulesList.length }} 规则生效中
          </ElTag>
        </div>

        <div class="card-body-section">
          <div class="info-pill-grid">
            <div class="info-pill-item">
              <span class="pill-label">已配置规则</span>
              <span class="pill-value-number">{{ cdnRulesList.length }} <small>条</small></span>
            </div>

            <div class="info-pill-item">
              <span class="pill-label">边缘加速支持</span>
              <span class="pill-value-text">wsrv.nl / weserv</span>
            </div>

            <div class="info-pill-item">
              <span class="pill-label">特征站点/图床</span>
              <span class="pill-value-text">
                {{ cdnRulesList.length > 0 ? (cdnRulesList[0].site_key || cdnRulesList[0].match_domain || '网飞猫') : '暂无规则' }}
                <span v-if="cdnRulesList.length > 1" style="opacity: 0.6;"> +{{ cdnRulesList.length - 1 }}</span>
              </span>
            </div>
          </div>
        </div>

        <div class="card-bottom-bar">
          <ElButton
            size="small"
            type="primary"
            plain
            :icon="Plus"
            :disabled="ui.readOnly"
            @click.stop="openAddCdnRule"
          >
            添加加速规则
          </ElButton>
          <ElButton
            type="primary"
            link
            @click.stop="showCdnPrefixDialog = true"
          >
            管理加速路由 →
          </ElButton>
        </div>
      </ElCard>
    </div>

    <!-- 弹窗 1: 全局海报防盗链中继总控详情 -->
    <GlobalProxyDialog
      v-model="showGlobalProxyDialog"
      :config="config"
      :saving-config="savingConfig"
      @save="handleSaveConfigAndCloseDialog"
    />

    <!-- 弹窗 2: 第三方源站加密海报动态解密配置详情管理 -->
    <DecryptionRulesDialog
      v-model="showDecryptionDialog"
      :rules-list="rulesList"
      :show-secret="showSecret"
      :show-rule-dialog="showRuleDialog"
      :is-editing="isEditing"
      :rule-form="ruleForm"
      :domains-input="domainsInput"
      :inline-test-url="inlineTestUrl"
      :inline-testing="inlineTesting"
      :inline-test-result="inlineTestResult"
      :show-ai-import-dialog="showAiImportDialog"
      :ai-import-text="aiImportText"
      :show-test-modal="showTestModal"
      :test-modal-rule="testModalRule"
      :test-modal-url="testModalUrl"
      :test-modal-loading="testModalLoading"
      :test-modal-result="testModalResult"
      @update:show-rule-dialog="showRuleDialog = $event"
      @update:domains-input="domainsInput = $event"
      @update:inline-test-url="inlineTestUrl = $event"
      @update:show-ai-import-dialog="showAiImportDialog = $event"
      @update:ai-import-text="aiImportText = $event"
      @update:show-test-modal="showTestModal = $event"
      @update:test-modal-url="testModalUrl = $event"
      @open-add-rule="openAddRule"
      @open-edit-rule="openEditRule"
      @delete-rule="handleDeleteRule"
      @toggle-rule="handleToggleRule"
      @toggle-secret="toggleSecret"
      @copy-rule-key="copyRuleKey"
      @fill-huangguoai-sample="fillHuangguoaiSample"
      @save-rule="handleSaveRule"
      @run-inline-test="runInlineTest"
      @open-ai-import="openAiImport"
      @parse-ai-json="handleParseAiJson"
      @open-test-rule-modal="openTestRuleModal"
      @run-modal-test="runModalTest"
    />

    <!-- 弹窗 3: 图床加速与代理前缀管理弹窗 -->
    <CdnPrefixDialog
      v-model="showCdnPrefixDialog"
      :cdn-rules-list="cdnRulesList"
      :show-cdn-rule-edit-dialog="showCdnRuleEditDialog"
      :is-editing-cdn-rule="isEditingCdnRule"
      :cdn-rule-form="cdnRuleForm"
      @update:show-cdn-rule-edit-dialog="showCdnRuleEditDialog = $event"
      @open-add-cdn-rule="openAddCdnRule"
      @open-edit-cdn-rule="openEditCdnRule"
      @save-cdn-rule="handleSaveCdnRule"
      @delete-cdn-rule="handleDeleteCdnRule"
      @toggle-cdn-rule="handleToggleCdnRule"
    />
  </div>
</template>

<style>
@import './image-proxy/image-proxy.css';
</style>
