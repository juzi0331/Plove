<script setup lang="ts">
/**
 * 相对时间：「3 分钟前」，鼠标悬停看绝对时间。
 *
 * 为什么值得单独一个组件：后台到处都是时间（最后出现、首次激活、上次预热），
 * 人读时间的第一反应是"多久以前"，不是"2026-09-30 14:03"。
 * `title` 里放绝对时间，需要精确值时不缺。
 *
 * 自己每 30 秒重算一次 —— 不用父组件驱动，也就不会每个页面各写一遍定时器。
 */
import { computed, onUnmounted, ref } from 'vue'

import { formatDateTime } from '../format'

const props = defineProps<{ value: string | null | undefined }>()

const now = ref(Date.now())
const timer = window.setInterval(() => {
  now.value = Date.now()
}, 30000)
onUnmounted(() => window.clearInterval(timer))

const absolute = computed(() => formatDateTime(props.value ?? null))

const relative = computed(() => {
  if (!props.value) return '—'
  const time = new Date(props.value).getTime()
  if (Number.isNaN(time)) return '—'
  const diff = Math.floor((now.value - time) / 1000)
  if (diff < 0) return absolute.value // 未来时间（时钟偏差）直接给绝对时间，别编造
  if (diff < 45) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  if (diff < 86400 * 30) return `${Math.floor(diff / 86400)} 天前`
  return absolute.value
})
</script>

<template>
  <span :title="absolute">{{ relative }}</span>
</template>
