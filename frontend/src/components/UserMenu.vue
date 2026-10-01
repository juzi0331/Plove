<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useDeviceStore } from '@/stores/device'
import { formatExpiry } from '@/utils/format'

const router = useRouter()
const device = useDeviceStore()
const isOpen = ref(false)
const menuRef = ref<HTMLElement | null>(null)

function toggle(): void {
  isOpen.value = !isOpen.value
  if (isOpen.value && device.activated) {
    void device.heartbeatOnce()
  }
}

function reActivate(): void {
  isOpen.value = false
  // 正确跳转到 activate 路由 (修复 H-1)
  void router.push({ name: 'activate' })
}

function onDocClick(e: MouseEvent): void {
  if (menuRef.value && !menuRef.value.contains(e.target as Node)) {
    isOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', onDocClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
})

defineExpose({
  close: () => { isOpen.value = false },
})
</script>

<template>
  <div ref="menuRef" class="nf-user-menu-wrap">
    <button
      class="nf-avatar-btn"
      :class="{ 'is-active': isOpen }"
      type="button"
      @click.stop="toggle"
      aria-label="查看會員權益與到期時間"
    >
      <!-- 官方原生高质感 Netflix Smiley 头像 (无外部依赖，零隐私风险) -->
      <div class="nf-avatar-box">
        <svg viewBox="0 0 32 32" width="32" height="32" class="nf-avatar-svg">
          <rect width="32" height="32" rx="5" fill="#E50914" />
          <circle cx="11" cy="12" r="2.2" fill="#FFFFFF" />
          <circle cx="21" cy="12" r="2.2" fill="#FFFFFF" />
          <path d="M10 18 Q16 25 22 18" stroke="#FFFFFF" stroke-width="2.2" stroke-linecap="round" fill="none" />
        </svg>
      </div>
      <span class="nf-avatar-caret" :class="{ 'is-rotated': isOpen }">▼</span>
    </button>

    <!-- 会员卡片弹窗 (点击头像出现真实到期时间) -->
    <Transition name="nf-dropdown">
      <div v-if="isOpen" class="nf-user-dropdown" @click.stop>
        <div class="nf-user-dropdown__header">
          <div class="nf-vip-badge">
            <span class="nf-vip-crown">👑</span>
            <span class="nf-vip-title">VIP 尊享會員</span>
          </div>
          <div class="nf-vip-device">
            <span class="nf-device-label">設備：</span>
            <span class="nf-device-val">{{ device.deviceName || '本機' }}</span>
          </div>
        </div>

        <!-- 到期时间核心展示区 (真实服务端数据) -->
        <div class="nf-user-dropdown__body">
          <div class="nf-expiry-row">
            <span class="nf-expiry-label">VIP 狀態</span>
            <span class="nf-expiry-val green">
              <span class="nf-status-dot" /> 正常生效中
            </span>
          </div>
          <div class="nf-expiry-row">
            <span class="nf-expiry-label">會員到期時間</span>
            <span class="nf-expiry-val highlight">{{ formatExpiry(device.expiresAt) }}</span>
          </div>
          <div class="nf-expiry-row">
            <span class="nf-expiry-label">剩餘天數</span>
            <span class="nf-expiry-val green">
              {{ device.daysLeft }} 天
              <small v-if="device.daysLeft <= 3 && device.daysLeft > 0" class="nf-expiry-warn">(即將到期)</small>
            </span>
          </div>
          <div class="nf-expiry-row">
            <span class="nf-expiry-label">精確剩餘</span>
            <span class="nf-expiry-val sub-time">{{ device.formattedRemainingTime }}</span>
          </div>
        </div>

        <!-- 底部操作按钮 -->
        <div class="nf-user-dropdown__footer">
          <button class="nf-renew-btn" type="button" @click="reActivate">
            更換卡密 / 續期
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.nf-user-menu-wrap {
  position: relative;
}

.nf-avatar-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 2px;
  border-radius: 6px;
  transition: transform 0.2s ease;
}

.nf-avatar-btn:hover,
.nf-avatar-btn.is-active {
  transform: scale(1.05);
}

.nf-avatar-box {
  width: 32px;
  height: 32px;
  border-radius: 5px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
  border: 1.5px solid transparent;
  transition: border-color 0.2s ease;
}

.nf-avatar-btn.is-active .nf-avatar-box,
.nf-avatar-btn:hover .nf-avatar-box {
  border-color: #e50914;
}

.nf-avatar-svg {
  display: block;
}

.nf-avatar-caret {
  font-size: 9px;
  color: #ffffff;
  transition: transform 0.2s ease;
}

.nf-avatar-caret.is-rotated {
  transform: rotate(180deg);
}

/* VIP 会员卡片弹层 (深黑质感毛玻璃) */
.nf-user-dropdown {
  position: absolute;
  top: calc(100% + 12px);
  right: 0;
  width: 280px;
  background: rgba(18, 18, 18, 0.96);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 10px;
  box-shadow: 0 20px 48px rgba(0, 0, 0, 0.9);
  backdrop-filter: blur(18px);
  z-index: 100;
  overflow: hidden;
  animation: nf-dropdown-fade 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.nf-user-dropdown__header {
  padding: 16px 16px 12px;
  background: linear-gradient(180deg, rgba(229, 9, 20, 0.15) 0%, transparent 100%);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.nf-vip-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.nf-vip-crown {
  font-size: 16px;
}

.nf-vip-title {
  font-size: 14px;
  font-weight: 700;
  color: #ffd700;
  letter-spacing: 0.5px;
}

.nf-vip-device {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.6);
}

.nf-user-dropdown__body {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.nf-expiry-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}

.nf-expiry-label {
  color: rgba(255, 255, 255, 0.6);
}

.nf-expiry-val {
  font-weight: 600;
  color: #ffffff;
}

.nf-expiry-val.highlight {
  color: #ffffff;
  font-family: monospace;
  font-size: 13px;
}

.nf-expiry-val.green {
  color: #46d369;
  display: flex;
  align-items: center;
}

.nf-status-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background-color: #46d369;
  box-shadow: 0 0 6px #46d369;
  margin-right: 5px;
}

.nf-expiry-val.sub-time {
  color: #ffd700;
  font-weight: 600;
  font-size: 12px;
}

.nf-expiry-warn {
  color: #ffaa00;
  font-size: 11px;
  margin-left: 4px;
}

.nf-user-dropdown__footer {
  padding: 10px 16px 14px;
}

.nf-renew-btn {
  width: 100%;
  padding: 8px 0;
  background: #e50914;
  color: #ffffff;
  border: none;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.nf-renew-btn:hover {
  background: #f40612;
}

@keyframes nf-dropdown-fade {
  from {
    opacity: 0;
    transform: translateY(-6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.nf-dropdown-enter-active,
.nf-dropdown-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.nf-dropdown-enter-from,
.nf-dropdown-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
