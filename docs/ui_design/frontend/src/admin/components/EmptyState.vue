<script setup lang="ts">
/**
 * 空状态：说清"为什么空"，并给一个下一步按钮。
 *
 * 一个空表格看起来像"坏了"；一句「还没有激活码 → 去发码」才是完整的答案。
 */
import { ElEmpty } from 'element-plus'

defineProps<{
  title?: string
  hint?: string
}>()
</script>

<template>
  <div class="a-card empty">
    <ElEmpty :description="title ?? '暂无数据'">
      <p v-if="hint" class="a-note">{{ hint }}</p>
      <slot name="action" />
    </ElEmpty>
  </div>
</template>

<style scoped>
.empty {
  padding: 26px 16px;
}
</style>
