<script setup lang="ts">
/**
 * 统一的页面头：标题 + 一句说明 + 右侧操作区。
 *
 * 每个页面都长得一样，是「不像手工作坊」的一半 —— 另一半是 theme.css 里的 token。
 */
defineProps<{
  title: string
  desc?: string
}>()
</script>

<template>
  <div class="a-head">
    <div>
      <h1 class="a-head__title">{{ title }}</h1>
      <p v-if="desc" class="a-head__desc">{{ desc }}</p>
    </div>
    <div class="a-actions">
      <slot name="actions" />
    </div>
  </div>
</template>
