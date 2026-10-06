<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useSitesStore } from '@/stores/sites'

const emit = defineEmits<{
  (e: 'change', key: string): void
}>()

const router = useRouter()
const route = useRoute()
const sites = useSitesStore()
const isOpen = ref(false)
const selectorRef = ref<HTMLElement | null>(null)

function toggle(): void {
  isOpen.value = !isOpen.value
}

function selectSite(key: string): void {
  if (key === sites.currentKey) {
    isOpen.value = false
    return
  }
  sites.select(key)
  isOpen.value = false
  emit('change', key)
  showToast(`已切換至片源：${sites.current?.name ?? key}`)

  // 若当前在分类页或详情页等非首页路由，切源后默认平滑返回大厅首页，防止分类/影片ID跨源404
  if (route.name !== 'home') {
    void router.push({ name: 'home' })
  }
}

function onDocClick(e: MouseEvent): void {
  if (selectorRef.value && !selectorRef.value.contains(e.target as Node)) {
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
  open: () => { isOpen.value = true },
  close: () => { isOpen.value = false },
  toggle: () => { isOpen.value = !isOpen.value },
})
</script>

<template>
  <div ref="selectorRef" class="nf-site-selector-wrap">
    <button
      class="nf-switch-pill"
      :class="{ 'is-active': isOpen }"
      type="button"
      @click.stop="toggle"
      aria-label="切換片源線路"
    >
      <span class="nf-switch-dot" />
      <span class="nf-switch-name">{{ sites.current?.name || '極速專線' }}</span>
      <span v-if="sites.current?.badge" class="nf-switch-badge">{{ sites.current.badge }}</span>
      <span class="nf-switch-arrow" :class="{ 'is-rotated': isOpen }">▾</span>
    </button>

    <!-- 下拉选择面板 -->
    <Transition name="nf-dropdown">
      <div v-if="isOpen" class="nf-site-dropdown" @click.stop>
        <div class="nf-site-dropdown__header">
          <span class="nf-site-dropdown__title">切換片源線路</span>
          <span class="nf-site-dropdown__count">{{ sites.sites.length }} 個站點</span>
        </div>
        <div class="nf-site-dropdown__list">
          <button
            v-for="(site, idx) in sites.sites"
            :key="site.key"
            class="nf-site-option"
            :class="{ 'is-current': site.key === sites.currentKey }"
            type="button"
            @click="selectSite(site.key)"
          >
            <div class="nf-site-option__left">
              <span class="nf-site-option__dot" />
              <div class="nf-site-option__meta">
                <div class="nf-site-option__title-row">
                  <span class="nf-site-option__name">{{ site.name || `極速專線 ${idx + 1}` }}</span>
                  <span v-if="site.badge" class="nf-site-option__tag">{{ site.badge }}</span>
                </div>
                <span class="nf-site-option__key">線路標識: {{ site.badge || `NODE-${idx + 1}` }}</span>
              </div>
            </div>
            <span v-if="site.key === sites.currentKey" class="nf-site-option__badge">✓ 當前在線</span>
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.nf-site-selector-wrap {
  position: relative;
}

.nf-switch-pill {
  display: flex;
  align-items: center;
  gap: 7px;
  background: rgba(45, 45, 45, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 16px;
  padding: 5px 12px;
  color: #ffffff;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.25s ease;
  user-select: none;
}

.nf-switch-pill:hover,
.nf-switch-pill.is-active {
  background: rgba(229, 9, 20, 0.9);
  border-color: rgba(255, 255, 255, 0.3);
  box-shadow: 0 2px 10px rgba(229, 9, 20, 0.4);
}

.nf-switch-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background-color: #46d369;
  box-shadow: 0 0 6px #46d369;
}

.nf-switch-name {
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}

.nf-switch-badge {
  font-size: 10px;
  line-height: 1.2;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(229, 9, 20, 0.85);
  color: #ffffff;
  font-weight: 600;
  letter-spacing: 0.3px;
  white-space: nowrap;
}

.nf-switch-arrow {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.7);
  transition: transform 0.25s ease;
}

.nf-switch-arrow.is-rotated {
  transform: rotate(180deg);
}

.nf-site-dropdown {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  width: 260px;
  background: rgba(20, 20, 20, 0.96);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 8px;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.85);
  backdrop-filter: blur(16px);
  z-index: 100;
  overflow: hidden;
  animation: nf-dropdown-fade 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.nf-site-dropdown__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.nf-site-dropdown__title {
  font-size: 13px;
  font-weight: 700;
  color: #e5e5e5;
}

.nf-site-dropdown__count {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
}

.nf-site-dropdown__list {
  padding: 6px;
  max-height: 280px;
  overflow-y: auto;
}

.nf-site-option {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  text-align: left;
  transition: background-color 0.2s ease;
}

.nf-site-option:hover {
  background: rgba(255, 255, 255, 0.1);
}

.nf-site-option.is-current {
  background: rgba(229, 9, 20, 0.18);
  border: 1px solid rgba(229, 9, 20, 0.4);
}

.nf-site-option__left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.nf-site-option__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #46d369;
}

.nf-site-option__meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nf-site-option__title-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.nf-site-option__name {
  font-size: 13px;
  color: #ffffff;
  font-weight: 500;
}

.nf-site-option__tag {
  font-size: 9px;
  line-height: 1.2;
  padding: 1px 5px;
  border-radius: 3px;
  background: rgba(229, 9, 20, 0.22);
  border: 1px solid rgba(229, 9, 20, 0.55);
  color: #ff5e62;
  font-weight: 600;
  white-space: nowrap;
}

.nf-site-option__key {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.45);
}

.nf-site-option__badge {
  font-size: 11px;
  font-weight: 600;
  color: #e50914;
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
