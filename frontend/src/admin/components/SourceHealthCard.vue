<script setup lang="ts">
/**
 * 现代内容源健康状态卡片
 *
 * 1. 实时倒计时器，自动刷新冷却时间；
 * 2. 状态脉冲呼吸灯（正常 / 探测中 / 熔断 / 未探测）；
 * 3. 规整的指标信息行与高质感边框。
 */
import { ElTag } from 'element-plus'
import { computed, onUnmounted, ref, watch } from 'vue'

import type { SiteHealth } from '@/api/types'
import { type TagType } from '../format'

const props = defineProps<{ health: SiteHealth }>()

const now = ref(Date.now())
const timer = window.setInterval(() => {
  now.value = Date.now()
}, 1000)
onUnmounted(() => window.clearInterval(timer))

const deadline = ref<number | null>(null)
watch(
  () => props.health.retry_after,
  (remain) => {
    deadline.value = remain ? Date.now() + remain * 1000 : null
  },
  { immediate: true },
)

const cooldown = computed(() => {
  if (deadline.value === null) return null
  return Math.max(0, Math.ceil((deadline.value - now.value) / 1000))
})

const state = computed<{ label: string; tag: TagType; pulse: 'good' | 'warn' | 'danger' | 'info' }>(() => {
  if (!props.health.probed) return { label: '未探测', tag: 'info', pulse: 'info' }
  if (props.health.state === 'open') return { label: '已熔断', tag: 'danger', pulse: 'danger' }
  if (props.health.state === 'half_open') return { label: '探测中', tag: 'warning', pulse: 'warn' }
  return { label: '正常服务', tag: 'success', pulse: 'good' }
})
</script>

<template>
  <div class="a-card site-card" :class="`site-card--${state.pulse}`">
    <div class="site-card__head">
      <div class="site-card__title-box">
        <span class="status-dot" :class="`status-dot--${state.pulse}`" />
        <span class="site-card__name">{{ health.site }}</span>
      </div>
      <ElTag :type="state.tag" size="small" effect="light" round>{{ state.label }}</ElTag>
    </div>

    <div class="site-card__grid">
      <div class="stat-pill">
        <span class="pill-label">连续失败</span>
        <span class="pill-val font-mono" :class="{ 'text-danger': health.failures > 0 }">
          {{ health.failures }} / {{ health.fail_threshold }}
        </span>
      </div>

      <div class="stat-pill">
        <span class="pill-label">冷却倒计</span>
        <span v-if="cooldown !== null" class="pill-val text-warn font-mono">{{ cooldown }}s</span>
        <span v-else class="pill-val text-muted">—</span>
      </div>

      <div class="stat-pill">
        <span class="pill-label">并发限制</span>
        <span class="pill-val font-mono">{{ health.max_concurrency }}</span>
      </div>

      <div class="stat-pill">
        <span class="pill-label">探针状态</span>
        <span class="pill-val" :class="health.probing ? 'text-warn' : 'text-muted'">
          {{ health.probing ? '试探中' : '静默' }}
        </span>
      </div>
    </div>

    <p v-if="!health.probed" class="site-card__foot">当前节点尚未向该源发起过请求，状态不代表源站连通性。</p>
  </div>
</template>

<style scoped>
.site-card {
  padding: 16px 18px;
  background: var(--a-card);
  border: 1px solid var(--a-border);
  border-radius: var(--a-radius);
  transition: all 0.25s ease;
}

.site-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--a-shadow-1);
}

.site-card--danger {
  border-color: var(--a-danger-border);
  background: var(--a-danger-bg);
}

.site-card--warn {
  border-color: var(--a-warn-border);
}

.site-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.site-card__title-box {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-dot--good {
  background: #10b981;
  box-shadow: 0 0 6px rgba(16, 185, 129, 0.6);
}

.status-dot--warn {
  background: #f59e0b;
  box-shadow: 0 0 6px rgba(245, 158, 11, 0.6);
}

.status-dot--danger {
  background: #ef4444;
  box-shadow: 0 0 6px rgba(239, 68, 68, 0.6);
}

.status-dot--info {
  background: #94a3b8;
}

.site-card__name {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  font-size: 14.5px;
  color: var(--a-text);
}

.site-card__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.stat-pill {
  display: flex;
  flex-direction: column;
  gap: 2px;
  background: var(--a-bg-subtle);
  padding: 6px 10px;
  border-radius: 6px;
  border: 1px solid var(--a-border);
}

.pill-label {
  font-size: 11px;
  color: var(--a-text-3);
}

.pill-val {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--a-text);
}

.font-mono {
  font-family: 'JetBrains Mono', monospace;
}

.text-danger {
  color: var(--el-color-danger);
}

.text-warn {
  color: var(--el-color-warning);
}

.text-muted {
  color: var(--a-text-3);
}

.site-card__foot {
  margin: 10px 0 0;
  color: var(--a-text-3);
  font-size: 11.5px;
  line-height: 1.5;
}
</style>
