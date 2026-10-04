<script setup lang="ts">
import { ElCard, ElIcon, ElRadioButton, ElRadioGroup } from 'element-plus'
import { Monitor, Tools } from '@element-plus/icons-vue'
import type { SystemMaintenancePayload, SystemNoticePayload } from '@/api/types'
import type { PreviewTab } from './useSystemNotice'

defineProps<{
  activeTab: PreviewTab
  noticeForm: SystemNoticePayload
  maintForm: SystemMaintenancePayload
}>()

const emit = defineEmits<{
  (e: 'update:activeTab', tab: PreviewTab): void
}>()
</script>

<template>
  <ElCard shadow="hover" class="module-card sandbox-card">
    <div class="card-top-bar">
      <div class="card-title-group">
        <div class="card-icon-box icon-box--primary">
          <ElIcon :size="20"><Monitor /></ElIcon>
        </div>
        <div>
          <div class="card-title">前台视觉所见即所得实时模拟沙盒 (Live Visual Sandbox)</div>
          <div class="card-subtitle">
            1:1 动态展示各场景在前台用户界面的呈现效果，所见即所得
          </div>
        </div>
      </div>

      <div class="sandbox-tabs">
        <ElRadioGroup :model-value="activeTab" size="small" @update:model-value="val => emit('update:activeTab', val as PreviewTab)">
          <ElRadioButton value="header_bar">顶部常驻横幅</ElRadioButton>
          <ElRadioButton value="banner">顶部跑马灯</ElRadioButton>
          <ElRadioButton value="modal">大厅居中强弹窗</ElRadioButton>
          <ElRadioButton value="float">右下角悬浮卡片</ElRadioButton>
          <ElRadioButton value="maintenance">全站维护锁屏</ElRadioButton>
        </ElRadioGroup>
      </div>
    </div>

    <!-- 实时沙盒渲染舞台 -->
    <div class="sandbox-stage">
      <!-- 1. 顶部常驻横幅预览 -->
      <div v-if="activeTab === 'header_bar'" class="stage-view">
        <div class="view-intro">
          <span class="view-tag">顶部常驻横幅效果</span>
          <span class="view-desc">
            置顶于网站导航栏，文字清晰平稳，适合通知或指引用户点击跳转
          </span>
        </div>

        <div class="preview-header-bar" :class="`preview-bar--${noticeForm.level || 'info'}`">
          <div class="preview-bar-inner">
            <span class="preview-bar-tag">公告</span>
            <span class="preview-bar-title">{{ noticeForm.title || '公告标题' }}</span>
            <span class="preview-bar-sep">—</span>
            <span class="preview-bar-content">{{ noticeForm.content || '请输入公告详细内容...' }}</span>
            <span v-if="noticeForm.action_text" class="preview-bar-action">
              {{ noticeForm.action_text }} &rarr;
            </span>
          </div>
          <span v-if="noticeForm.dismissible" class="preview-bar-close">✕</span>
        </div>

        <div class="fake-page-content">
          <div class="fake-nav-line" />
          <div class="fake-banner-card" />
          <div class="fake-grid-row">
            <div class="fake-card" />
            <div class="fake-card" />
            <div class="fake-card" />
            <div class="fake-card" />
          </div>
        </div>
      </div>

      <!-- 2. 顶部滚动跑马灯预览 -->
      <div v-if="activeTab === 'banner'" class="stage-view">
        <div class="view-intro">
          <span class="view-tag">顶部滚动走字跑马灯效果</span>
          <span class="view-desc">长文本平滑横向滚动走字，流媒体风格沉浸提示</span>
        </div>

        <div class="marquee-preview-bar" :class="`marquee--${noticeForm.level || 'info'}`">
          <div class="marquee-badge">系统广播</div>
          <div class="marquee-viewport">
            <div class="marquee-track">
              <span class="marquee-text">
                <strong>【{{ noticeForm.title || '系统广播' }}】</strong>
                {{ noticeForm.content || '暂无广播内容' }}
              </span>
            </div>
          </div>
          <span v-if="noticeForm.action_text" class="marquee-action-fake">
            {{ noticeForm.action_text }}
          </span>
          <span v-if="noticeForm.dismissible" class="marquee-close-fake">✕</span>
        </div>

        <div class="fake-page-content">
          <div class="fake-nav-line" />
          <div class="fake-banner-card" />
          <div class="fake-grid-row">
            <div class="fake-card" />
            <div class="fake-card" />
            <div class="fake-card" />
            <div class="fake-card" />
          </div>
        </div>
      </div>

      <!-- 3. 大厅居中强弹窗预览 -->
      <div v-if="activeTab === 'modal'" class="stage-view">
        <div class="view-intro">
          <span class="view-tag">大厅居中强弹窗 Modal 效果</span>
          <span class="view-desc">进站强提醒，半透明磨砂遮罩与高质感对话框</span>
        </div>

        <div class="modal-preview-stage">
          <div class="modal-box" :class="`modal--${noticeForm.level || 'info'}`">
            <div class="modal-header">
              <div class="modal-title-row">
                <span class="modal-level-badge">{{ (noticeForm.level || 'info').toUpperCase() }}</span>
                <span class="modal-title">{{ noticeForm.title || '公告标题' }}</span>
              </div>
              <span v-if="noticeForm.dismissible" class="modal-x">✕</span>
            </div>
            <div class="modal-content">
              {{ noticeForm.content || '请输入公告详细正文内容...' }}
            </div>
            <div class="modal-footer">
              <span v-if="noticeForm.action_text" class="modal-action-fake">
                {{ noticeForm.action_text }}
              </span>
              <span class="modal-btn-fake">我知道了</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 4. 右下角悬浮卡片预览 -->
      <div v-if="activeTab === 'float'" class="stage-view">
        <div class="view-intro">
          <span class="view-tag">右下角悬浮卡片效果</span>
          <span class="view-desc">常驻轻量气泡卡片，不遮挡主内容，优雅微交互</span>
        </div>

        <div class="float-preview-container">
          <div class="fake-page-content" style="opacity: 0.5;">
            <div class="fake-nav-line" />
            <div class="fake-banner-card" />
            <div class="fake-grid-row">
              <div class="fake-card" />
              <div class="fake-card" />
              <div class="fake-card" />
              <div class="fake-card" />
            </div>
          </div>

          <div class="float-preview-capsule" :class="`float--${noticeForm.level || 'info'}`">
            <div class="float-header">
              <div class="float-title-row">
                <span class="float-badge">站内通报</span>
                <span class="float-title">{{ noticeForm.title || '公告标题' }}</span>
              </div>
              <span v-if="noticeForm.dismissible" class="float-close">✕</span>
            </div>
            <div class="float-body">
              {{ noticeForm.content || '请输入公告详细内容...' }}
            </div>
            <div v-if="noticeForm.action_text" class="float-footer">
              <span class="float-btn-fake">{{ noticeForm.action_text }} &rarr;</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 5. 全站维护锁屏预览 -->
      <div v-if="activeTab === 'maintenance'" class="stage-view">
        <div class="view-intro">
          <span class="view-tag">全站停机维护全屏锁屏效果</span>
          <span class="view-desc">普通前台用户将被全面拦截并显示维护屏，管理后台持续放行</span>
        </div>

        <div class="lock-preview-stage">
          <div class="lock-icon-halo">
            <ElIcon :size="32" class="lock-spin-icon"><Tools /></ElIcon>
          </div>
          <div class="lock-title">SYSTEM MAINTENANCE</div>
          <div class="lock-badge">系统升级维护中</div>
          <div class="lock-message">
            {{ maintForm.message || '系统维护中，请稍后访问...' }}
          </div>
          <div class="lock-actions">
            <div class="lock-btn-fake">刷新页面重试</div>
            <div class="lock-btn-fake lock-btn-sub">管理后台通道</div>
          </div>
        </div>
      </div>
    </div>
  </ElCard>
</template>

<style scoped src="./system-notice.css"></style>
