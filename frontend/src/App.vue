<script setup lang="ts">
/**
 * 根组件横切关注点：
 * 1. 登录会话与互踢治理（SESSION_KICKED 对话框）；
 * 2. 全站系统状态感知（停服维护模式全屏拦截、大厅重要弹窗 Modal、顶部走字跑马灯）；
 * 3. 全局海报防盗链中继开关同步。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ADMIN_BASE_PATH, adminPath } from '@/admin/config'
import { getPublicSystemStatus } from '@/api/client'
import type { SystemNoticePayload, SystemStatusPayload } from '@/api/types'
import { useDeviceStore } from '@/stores/device'
import { setGlobalImageProxy } from '@/utils/format'

const device = useDeviceStore()
const router = useRouter()
const route = useRoute()

const isAdminRoute = computed(() => route.path.startsWith(ADMIN_BASE_PATH) || route.path.startsWith('/admin'))

// ------------------------------------------------------------------ 互踢对话框
const showKicked = computed({
  get: () => device.kicked && !isAdminRoute.value,
  set: (value: boolean) => {
    if (!value) device.dismissKicked()
  },
})

async function continueHere(): Promise<void> {
  const ok = await device.resume()
  if (!ok) {
    device.forget()
    await router.push({ name: 'activate' })
  }
}

async function goActivate(): Promise<void> {
  device.forget()
  await router.push({ name: 'activate' })
}

// ------------------------------------------------------------------ 全站状态与广播
const sysStatus = ref<SystemStatusPayload | null>(null)
const bannerDismissed = ref(false)
const showModalNotice = ref(false)

const activeNotice = computed<SystemNoticePayload | null>(() => {
  if (sysStatus.value?.notice?.enabled) {
    return sysStatus.value.notice
  }
  return null
})

const showBannerNotice = computed(() => {
  if (isAdminRoute.value || bannerDismissed.value) return false
  const n = activeNotice.value
  if (!n) return false
  return n.display_type === 'banner' || n.display_type === 'both'
})

async function fetchStatus(): Promise<void> {
  try {
    const res = await getPublicSystemStatus()
    sysStatus.value = res
    setGlobalImageProxy(Boolean(res.image_proxy_enabled))
    // 首次弹窗策略：若公告为 modal 或 both，且本次会话未关闭过
    if (res.notice?.enabled && (res.notice.display_type === 'modal' || res.notice.display_type === 'both')) {
      const seenKey = `plove_notice_seen_${res.notice.title || 'default'}`
      if (!sessionStorage.getItem(seenKey)) {
        showModalNotice.value = true
      }
    }
  } catch {
    // 静默降级
  }
}

function handleDismissModal(): void {
  showModalNotice.value = false
  if (activeNotice.value?.title) {
    sessionStorage.setItem(`plove_notice_seen_${activeNotice.value.title}`, 'true')
  }
}

function handleDismissBanner(): void {
  bannerDismissed.value = true
}

function handleReload(): void {
  window.location.reload()
}

function goAdmin(): void {
  void router.push(adminPath())
}

onMounted(() => {
  void fetchStatus()
})

watch(
  () => route.path,
  () => {
    // 路由切换时轻量同步
    void fetchStatus()
  },
)
</script>

<template>
  <div class="app-root">
    <!-- 1. 全站停机维护全屏拦截 (仅对普通前台路由生效，管理后台始终放行) -->
    <div
      v-if="sysStatus?.maintenance && !isAdminRoute"
      class="maintenance-overlay"
    >
      <div class="maintenance-box">
        <div class="maint-icon-wrap">
          <div class="maint-halo" />
          <div class="maint-icon">⚠️</div>
        </div>
        <div class="maint-title-en">SYSTEM MAINTENANCE</div>
        <h1 class="maint-title">系统升级维护中</h1>
        <p class="maint-msg">
          {{ sysStatus?.maintenance_message || '为了提供更稳定优质的影音播放体验，系统正在进行机房网络升级，请稍后访问。' }}
        </p>
        <div class="maint-actions">
          <button class="maint-btn-reload" @click="handleReload">
            刷新页面重试
          </button>
          <button class="maint-btn-admin" @click="goAdmin">
            管理后台通道
          </button>
        </div>
        <div class="maint-footer">PLOVE STREAMING NETWORK &copy; 2026</div>
      </div>
    </div>

    <!-- 2. 正常路由渲染 -->
    <template v-else>
      <!-- 顶部跑马灯通知条 -->
      <div
        v-if="showBannerNotice && activeNotice"
        class="global-marquee-banner"
        :class="`marquee-level--${activeNotice.level || 'info'}`"
      >
        <div class="marquee-icon-badge">📢 系统广播</div>
        <div class="marquee-scroller-viewport">
          <div class="marquee-scroller-track">
            <span class="marquee-scroller-item">
              <strong>【{{ activeNotice.title }}】</strong>
              {{ activeNotice.content }}
            </span>
          </div>
        </div>
        <button
          v-if="activeNotice.dismissible"
          class="marquee-close-btn"
          title="关闭通知"
          @click="handleDismissBanner"
        >
          ✕
        </button>
      </div>

      <router-view />

      <!-- 3. 大厅重要通知强弹窗 Modal -->
      <div
        v-if="showModalNotice && activeNotice && !isAdminRoute"
        class="modal-backdrop"
      >
        <div class="modal-dialog-card" :class="`modal-border--${activeNotice.level || 'info'}`">
          <div class="modal-dialog-header">
            <div class="modal-badge-row">
              <span class="modal-badge-tag">{{ (activeNotice.level || 'INFO').toUpperCase() }}</span>
              <h3 class="modal-heading">{{ activeNotice.title || '系统重要通知' }}</h3>
            </div>
            <button
              v-if="activeNotice.dismissible"
              class="modal-close-icon"
              @click="handleDismissModal"
            >
              ✕
            </button>
          </div>
          <div class="modal-dialog-body">
            <p>{{ activeNotice.content }}</p>
          </div>
          <div class="modal-dialog-footer">
            <button class="modal-btn-confirm" @click="handleDismissModal">
              我知道了
            </button>
          </div>
        </div>
      </div>
    </template>

    <!-- 4. 被踢互踢提示对话框 -->
    <van-dialog
      v-model:show="showKicked"
      title="已在别的设备上使用"
      confirm-button-text="在此设备继续"
      cancel-button-text="去激活页"
      show-cancel-button
      @confirm="continueHere"
      @cancel="goActivate"
    >
      <p style="padding: 16px; margin: 0; line-height: 1.6">
        这个激活码同一时间只能一台设备在线。你现在这台被另一台顶掉了。
        <br />
        <br />
        点「在此设备继续」会把在线的那台顶下来，那台会被提示。
      </p>
    </van-dialog>
  </div>
</template>

<style scoped>
.app-root {
  min-height: 100vh;
  position: relative;
}

/* 停机维护全屏阻断 */
.maintenance-overlay {
  position: fixed;
  inset: 0;
  z-index: 99999;
  background: radial-gradient(circle at center, #1e1b4b 0%, #030712 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  color: #ffffff;
}

.maintenance-box {
  max-width: 520px;
  width: 100%;
  text-align: center;
  background: rgba(255, 255, 255, 0.03);
  backdrop-filter: blur(24px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  padding: 48px 32px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.8);
}

.maint-icon-wrap {
  position: relative;
  width: 72px;
  height: 72px;
  margin: 0 auto 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.maint-halo {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: rgba(239, 68, 68, 0.2);
  animation: pulse-ring 2s infinite ease-out;
}

@keyframes pulse-ring {
  0% { transform: scale(0.8); opacity: 0.8; }
  100% { transform: scale(1.6); opacity: 0; }
}

.maint-icon {
  font-size: 36px;
  position: relative;
  z-index: 2;
}

.maint-title-en {
  font-family: monospace;
  font-size: 13px;
  letter-spacing: 3px;
  color: #f87171;
  margin-bottom: 6px;
}

.maint-title {
  margin: 0 0 16px;
  font-size: 26px;
  font-weight: 800;
  color: #ffffff;
}

.maint-msg {
  font-size: 14px;
  line-height: 1.6;
  color: #94a3b8;
  margin: 0 0 32px;
}

.maint-actions {
  display: flex;
  gap: 16px;
  justify-content: center;
  flex-wrap: wrap;
}

.maint-btn-reload {
  background: #e50914;
  color: #ffffff;
  border: none;
  font-size: 14px;
  font-weight: 700;
  padding: 12px 28px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s ease;
}

.maint-btn-reload:hover {
  background: #f40612;
}

.maint-btn-admin {
  background: rgba(255, 255, 255, 0.08);
  color: #cbd5e1;
  border: 1px solid rgba(255, 255, 255, 0.15);
  font-size: 14px;
  font-weight: 600;
  padding: 12px 24px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.maint-btn-admin:hover {
  background: rgba(255, 255, 255, 0.15);
  color: #ffffff;
}

.maint-footer {
  margin-top: 36px;
  font-family: monospace;
  font-size: 11px;
  color: #475569;
}

/* 顶部跑马灯 Banner */
.global-marquee-banner {
  position: relative;
  z-index: 1000;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  font-size: 13px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.marquee-level--info {
  background: linear-gradient(90deg, #0369a1 0%, #0284c7 100%);
  color: #ffffff;
}

.marquee-level--warning {
  background: linear-gradient(90deg, #b45309 0%, #d97706 100%);
  color: #ffffff;
}

.marquee-level--danger {
  background: linear-gradient(90deg, #b91c1c 0%, #dc2626 100%);
  color: #ffffff;
}

.marquee-icon-badge {
  font-size: 12px;
  font-weight: 700;
  background: rgba(0, 0, 0, 0.25);
  padding: 2px 8px;
  border-radius: 4px;
  white-space: nowrap;
}

.marquee-scroller-viewport {
  flex: 1;
  overflow: hidden;
  white-space: nowrap;
}

.marquee-scroller-track {
  display: inline-block;
  animation: roll-track 20s linear infinite;
}

@keyframes roll-track {
  0% { transform: translateX(100%); }
  100% { transform: translateX(-100%); }
}

.marquee-scroller-item {
  display: inline-block;
}

.marquee-close-btn {
  background: none;
  border: none;
  color: #ffffff;
  font-size: 14px;
  cursor: pointer;
  opacity: 0.8;
  padding: 0 4px;
}

.marquee-close-btn:hover {
  opacity: 1;
}

/* 大厅弹窗 Modal */
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.modal-dialog-card {
  max-width: 440px;
  width: 100%;
  background: #14171f;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 20px 48px rgba(0, 0, 0, 0.8);
  display: flex;
  flex-direction: column;
  gap: 16px;
  animation: modal-pop 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes modal-pop {
  from { transform: scale(0.92); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}

.modal-border--info {
  border: 1px solid rgba(56, 189, 248, 0.4);
}

.modal-border--warning {
  border: 1px solid rgba(245, 158, 11, 0.4);
}

.modal-border--danger {
  border: 1px solid rgba(239, 68, 68, 0.5);
}

.modal-dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-badge-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.modal-badge-tag {
  font-size: 10px;
  font-weight: 800;
  background: rgba(255, 255, 255, 0.12);
  color: #ffffff;
  padding: 2px 6px;
  border-radius: 4px;
}

.modal-heading {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: #ffffff;
}

.modal-close-icon {
  background: none;
  border: none;
  color: #94a3b8;
  font-size: 16px;
  cursor: pointer;
}

.modal-dialog-body {
  font-size: 14px;
  line-height: 1.6;
  color: #cbd5e1;
  background: rgba(255, 255, 255, 0.03);
  padding: 16px;
  border-radius: 10px;
}

.modal-dialog-body p {
  margin: 0;
}

.modal-dialog-footer {
  display: flex;
  justify-content: flex-end;
}

.modal-btn-confirm {
  background: #e50914;
  color: #ffffff;
  border: none;
  font-size: 13px;
  font-weight: 700;
  padding: 8px 22px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s ease;
}

.modal-btn-confirm:hover {
  background: #f40612;
}
</style>
