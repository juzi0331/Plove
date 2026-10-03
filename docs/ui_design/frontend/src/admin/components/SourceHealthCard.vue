<script setup lang="ts">
/**
 * 一个源的健康卡片（总览页用）。
 *
 * 为什么从表格里搬出来：源的四个状态（没探测 / 正常 / 探测中 / 熔断）
 * 用表格读要"一行行看数字"，用卡片可以做到**一眼扫过** ——
 * 而"为什么这个源没内容了"正是要回答这个问题。
 *
 * 冷却倒计时每秒自己跳一次，不用父组件驱动。
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

/**
 * retry_after 是"响应那一刻还剩多少秒"，不是绝对时刻。
 * 所以每次它变化（每次刷新拿到新值）就重算一个 deadline，
 * 倒计时用 deadline - now —— 直接减"挂载以来的时间"会在刷新时重复扣。
 */
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

const state = computed<{ label: string; tag: TagType }>(() => {
  // 没取过 meta 的源单独标出来：它的 state 也是 closed、failures 也是 0，
  // 和"一直很正常"长得一模一样。
  if (!props.health.probed) return { label: '未探测', tag: 'info' }
  if (props.health.state === 'open') return { label: '已熔断', tag: 'danger' }
  if (props.health.state === 'half_open') return { label: '探测中', tag: 'warning' }
  return { label: '正常', tag: 'success' }
})
</script>

<template>
  <div class="a-card site" :class="{ 'site--down': health.state === 'open' && health.probed }">
    <div class="site__head">
      <span class="site__name">{{ health.site }}</span>
      <ElTag :type="state.tag" size="small" effect="light" round>{{ state.label }}</ElTag>
    </div>

    <div class="site__rows">
      <div class="site__row">
        <span class="a-muted">连续失败</span>
        <span>{{ health.failures }} / {{ health.fail_threshold }}</span>
      </div>
      <div class="site__row">
        <span class="a-muted">冷却剩余</span>
        <span v-if="cooldown !== null" class="site__countdown">{{ cooldown }}s</span>
        <span v-else>—</span>
      </div>
      <div class="site__row">
        <span class="a-muted">并发上限</span>
        <span>
          {{ health.max_concurrency }}
          <span v-if="health.global_limit" class="a-muted">（全站 {{ health.global_limit }}）</span>
        </span>
      </div>
      <div class="site__row">
        <span class="a-muted">半开探针</span>
        <span>{{ health.probing ? '正在试探' : '—' }}</span>
      </div>
    </div>

    <p v-if="!health.probed" class="site__foot">这台机器上还没人用过它，状态不代表源站正常。</p>
  </div>
</template>

<style scoped>
.site {
  padding: 14px 16px;
}

.site--down {
  border-color: var(--a-danger-border);
}

.site__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.site__name {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-weight: 650;
  font-size: 14px;
}

.site__rows {
  margin-top: 10px;
  display: grid;
  gap: 6px;
}

.site__row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  font-size: 12.5px;
}

.site__countdown {
  color: var(--el-color-warning);
  font-variant-numeric: tabular-nums;
}

.site__foot {
  margin: 10px 0 0;
  color: var(--a-text-3);
  font-size: 12px;
}
</style>
