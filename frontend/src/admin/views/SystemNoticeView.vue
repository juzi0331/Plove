<script setup lang="ts">
/**
 * 全站公告与维护广播中心（模块化架构）：
 * 1. 停机维护闸门控制卡片（前台全屏拦截阻断，后台白名单放行）；
 * 2. 全站公告广播中心卡片（多渠道消息发布与总控）；
 * 3. 广播发布方式矩阵（支持 6 大公告场景切换）；
 * 4. 前台视觉所见即所得沙盒（NoticePreviewSandbox 组件）；
 * 5. 独立配置弹窗（MaintenanceConfigModal & NoticeConfigModal 组件）。
 */
import {
  ElButton,
  ElCard,
  ElIcon,
  ElSwitch,
  ElTag,
} from 'element-plus'
import {
  Bell,
  Check,
  Edit,
  Promotion,
  Refresh,
  Tools,
} from '@element-plus/icons-vue'

import { ui } from '@/admin/ui'
import { useSystemNotice } from './notice/useSystemNotice'
import NoticePreviewSandbox from './notice/NoticePreviewSandbox.vue'
import MaintenanceConfigModal from './notice/MaintenanceConfigModal.vue'
import NoticeConfigModal from './notice/NoticeConfigModal.vue'

const {
  loading,
  savingNotice,
  savingMaint,
  showMaintDialog,
  showNoticeDialog,
  activePreviewTab,
  noticeForm,
  maintForm,
  displayTypeOptions,
  currentDisplayOption,
  loadData,
  handleSaveNotice,
  handleQuickToggleNotice,
  handleSaveMaintenance,
  handleQuickToggleMaintenance,
  selectDisplayType,
  applyMaintTemplate,
  applyNoticeTemplate,
} = useSystemNotice()
</script>

<template>
  <div class="system-notice-page">
    <!-- 顶栏标题 -->
    <div class="header-section">
      <div>
        <h2 class="title">全站公告与维护广播中心</h2>
        <p class="subtitle">
          统筹管理前台全站运行闸门。可一键开启全站停机维护，或发布前台大厅弹窗、顶部滚动跑马灯、静态通告横幅、右下角悬浮通知等多渠道广播。
        </p>
      </div>
      <div class="header-actions">
        <ElButton :icon="Refresh" :loading="loading" @click="loadData">刷新状态</ElButton>
      </div>
    </div>

    <!-- 核心板块卡片矩阵 (全卡片化设计) -->
    <div class="cards-grid">
      <!-- 卡片 1: 停机维护闸门控制卡片 -->
      <ElCard
        shadow="hover"
        class="module-card maint-card"
        :class="{ 'card--danger': maintForm.enabled }"
        @click="showMaintDialog = true"
      >
        <div class="card-top-bar">
          <div class="card-title-group">
            <div class="card-icon-box" :class="maintForm.enabled ? 'icon-box--danger' : 'icon-box--primary'">
              <ElIcon :size="20"><Tools /></ElIcon>
            </div>
            <div>
              <div class="card-title">全站停服维护闸门 (Maintenance Gateway)</div>
              <div class="card-subtitle">前台全屏拦截阻断，管理后台持续放行</div>
            </div>
          </div>
          <ElTag :type="maintForm.enabled ? 'danger' : 'success'" effect="dark" class="status-tag">
            {{ maintForm.enabled ? '全站维护中（前台已阻断）' : '正常对外运营中' }}
          </ElTag>
        </div>

        <div class="card-body-section">
          <div class="info-pill-grid">
            <div class="info-pill-item">
              <span class="pill-label">维护状态</span>
              <div class="pill-value-switch" @click.stop>
                <ElSwitch
                  v-model="maintForm.enabled"
                  :disabled="ui.readOnly || savingMaint"
                  active-text="开启维护"
                  inactive-text="正常运营"
                  @change="handleQuickToggleMaintenance"
                />
              </div>
            </div>

            <div class="info-pill-item">
              <span class="pill-label">后台放行</span>
              <ElTag size="small" type="success" effect="plain">白名单持续通行</ElTag>
            </div>

            <div class="info-pill-item pill-full">
              <span class="pill-label">展示文案摘要</span>
              <span class="pill-text-truncate" :title="maintForm.message">
                {{ maintForm.message || '未设置维护告示文案' }}
              </span>
            </div>
          </div>
        </div>

        <div class="card-footer-bar" @click.stop>
          <div class="footer-hint">
            <span v-if="maintForm.updated_at">更新于 {{ maintForm.updated_at }}</span>
            <span v-else>配置即时在前台生效</span>
          </div>
          <ElButton
            :type="maintForm.enabled ? 'danger' : 'default'"
            size="small"
            :icon="Edit"
            @click="showMaintDialog = true"
          >
            配置文案与锁屏预览
          </ElButton>
        </div>
      </ElCard>

      <!-- 卡片 2: 全站广播发布总控卡片 -->
      <ElCard
        shadow="hover"
        class="module-card broadcast-card"
        :class="{ 'card--active': noticeForm.enabled }"
        @click="showNoticeDialog = true"
      >
        <div class="card-top-bar">
          <div class="card-title-group">
            <div class="card-icon-box" :class="noticeForm.enabled ? 'icon-box--success' : 'icon-box--info'">
              <ElIcon :size="20"><Bell /></ElIcon>
            </div>
            <div>
              <div class="card-title">全站公告广播中心 (Broadcast Notice)</div>
              <div class="card-subtitle">向全站用户推送多渠道消息通告，支持即时生效</div>
            </div>
          </div>
          <ElTag :type="noticeForm.enabled ? 'success' : 'info'" effect="dark" class="status-tag">
            {{ noticeForm.enabled ? '广播生效中' : '广播已关闭' }}
          </ElTag>
        </div>

        <div class="card-body-section">
          <div class="info-pill-grid">
            <div class="info-pill-item">
              <span class="pill-label">广播状态</span>
              <div class="pill-value-switch" @click.stop>
                <ElSwitch
                  v-model="noticeForm.enabled"
                  :disabled="ui.readOnly || savingNotice"
                  active-text="开启"
                  inactive-text="关闭"
                  @change="handleQuickToggleNotice"
                />
              </div>
            </div>

            <div class="info-pill-item">
              <span class="pill-label">紧急级别</span>
              <ElTag
                size="small"
                :type="noticeForm.level === 'danger' ? 'danger' : noticeForm.level === 'warning' ? 'warning' : 'info'"
                effect="plain"
              >
                {{ noticeForm.level === 'danger' ? '紧急通告' : noticeForm.level === 'warning' ? '重要提醒' : '常规提示' }}
              </ElTag>
            </div>

            <div class="info-pill-item">
              <span class="pill-label">发布方式</span>
              <ElTag size="small" type="primary" effect="light">
                {{ currentDisplayOption.name }}
              </ElTag>
            </div>

            <div class="info-pill-item">
              <span class="pill-label">关闭权限</span>
              <ElTag size="small" :type="noticeForm.dismissible ? 'info' : 'warning'" effect="plain">
                {{ noticeForm.dismissible ? '允许手动关闭' : '强制驻留' }}
              </ElTag>
            </div>

            <div class="info-pill-item pill-full">
              <span class="pill-label">公告主标题</span>
              <span class="pill-text-truncate" :title="noticeForm.title">
                {{ noticeForm.title || '未配置标题' }}
              </span>
            </div>
          </div>
        </div>

        <div class="card-footer-bar" @click.stop>
          <div class="footer-hint">
            <span v-if="noticeForm.updated_at">最后发布：{{ noticeForm.updated_at }}</span>
            <span v-else>点击卡片修改内容</span>
          </div>
          <div class="card-footer-actions">
            <ElButton size="small" :icon="Edit" @click="showNoticeDialog = true">
              编辑内容与渠道
            </ElButton>
            <ElButton
              size="small"
              type="primary"
              :icon="Check"
              :loading="savingNotice"
              :disabled="ui.readOnly"
              @click="handleSaveNotice"
            >
              即刻发布广播
            </ElButton>
          </div>
        </div>
      </ElCard>
    </div>

    <!-- 卡片 3: 广播发布方式矩阵卡片 -->
    <ElCard shadow="hover" class="module-card channel-matrix-card">
      <div class="card-top-bar">
        <div class="card-title-group">
          <div class="card-icon-box icon-box--primary">
            <ElIcon :size="20"><Promotion /></ElIcon>
          </div>
          <div>
            <div class="card-title">广播发布方式矩阵 (Channels Matrix)</div>
            <div class="card-subtitle">
              支持 6 种丰富通知形式，点击可快速切换生效方式，并在下方沙盒中实时预览
            </div>
          </div>
        </div>
        <div class="flex-align">
          <span class="current-label">当前选定方式：</span>
          <ElTag type="success" effect="dark">{{ currentDisplayOption.name }}</ElTag>
        </div>
      </div>

      <div class="channel-grid">
        <div
          v-for="opt in displayTypeOptions"
          :key="opt.type"
          class="channel-box"
          :class="{ 'channel-box--active': noticeForm.display_type === opt.type }"
          @click="selectDisplayType(opt.type)"
        >
          <div class="channel-box-header">
            <div class="channel-name-row">
              <span class="channel-name">{{ opt.name }}</span>
              <span class="channel-tag">{{ opt.tag }}</span>
            </div>
            <span v-if="noticeForm.display_type === opt.type" class="channel-active-indicator">
              生效中
            </span>
          </div>

          <p class="channel-desc">{{ opt.desc }}</p>

          <div class="channel-features">
            <span v-for="f in opt.features" :key="f" class="feature-chip">{{ f }}</span>
          </div>
        </div>
      </div>

      <div class="card-footer-bar">
        <span class="footer-hint">切换发布方式后，点击下方「即刻发布广播」或弹窗内保存即可向前台全网推送</span>
        <ElButton
          type="primary"
          size="small"
          :loading="savingNotice"
          :disabled="ui.readOnly"
          @click="handleSaveNotice"
        >
          保存并应用当前方式
        </ElButton>
      </div>
    </ElCard>

    <!-- 卡片 4: 前台视觉所见即所得沙盒卡片 -->
    <NoticePreviewSandbox
      v-model:active-tab="activePreviewTab"
      :notice-form="noticeForm"
      :maint-form="maintForm"
    />

    <!-- 弹窗 1: 停机维护闸门详细配置弹窗 -->
    <MaintenanceConfigModal
      v-model:visible="showMaintDialog"
      :maint-form="maintForm"
      :saving="savingMaint"
      :read-only="ui.readOnly"
      @save="handleSaveMaintenance"
      @apply-template="applyMaintTemplate"
    />

    <!-- 弹窗 2: 全站广播公告详细配置弹窗 -->
    <NoticeConfigModal
      v-model:visible="showNoticeDialog"
      :notice-form="noticeForm"
      :saving="savingNotice"
      :read-only="ui.readOnly"
      @save="handleSaveNotice"
      @apply-template="applyNoticeTemplate"
    />
  </div>
</template>

<style>
@import './notice/system-notice.css';
</style>
