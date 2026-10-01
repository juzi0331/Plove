<script setup lang="ts">
/**
 * 统计卡：一个大数字 + 一行脚注。
 *
 * `tone` 只影响数字的颜色（warn / danger / good），**背景不变** ——
 * 一屏里五颜六色的卡片比全灰更难看。
 */
defineProps<{
  label: string
  value: string | number
  unit?: string
  foot?: string
  tone?: 'default' | 'warn' | 'danger' | 'good'
}>()
</script>

<template>
  <div class="a-card stat" :class="`stat--${tone ?? 'default'}`">
    <div class="stat__label">
      {{ label }}
      <slot name="badge" />
    </div>
    <div class="stat__value">
      {{ value }}<span v-if="unit" class="stat__unit">{{ unit }}</span>
    </div>
    <div v-if="foot || $slots.foot" class="stat__foot">
      <slot name="foot">{{ foot }}</slot>
    </div>
  </div>
</template>

<style scoped>
.stat {
  padding: 15px 16px;
}

.stat__label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--a-text-3);
  font-size: 12px;
}

.stat__value {
  margin-top: 8px;
  font-size: 22px;
  font-weight: 650;
  letter-spacing: 0.3px;
}

.stat__unit {
  margin-left: 4px;
  color: var(--a-text-3);
  font-size: 12px;
  font-weight: 400;
}

.stat__foot {
  margin-top: 8px;
  color: var(--a-text-3);
  font-size: 12px;
  line-height: 1.6;
}

.stat--warn .stat__value {
  color: var(--el-color-warning);
}

.stat--danger .stat__value {
  color: var(--el-color-danger);
}

.stat--good .stat__value {
  color: #2f9e6e;
}
</style>
