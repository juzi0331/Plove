<script setup lang="ts">
/**
 * 错误态：错在哪 + 一个重试按钮。
 *
 * 比 ElMessage 好用的地方：它**留在页面上**，不会因为 3 秒没人看就消失，
 * 而"源站超时"这种错往往要盯着看第二遍。
 */
import { ElButton } from 'element-plus'

defineProps<{
  message: string
  hint?: string
}>()

defineEmits<{ retry: [] }>()
</script>

<template>
  <div class="a-card error">
    <div class="error__row">
      <div>
        <div class="error__title">{{ message }}</div>
        <div v-if="hint" class="error__hint">{{ hint }}</div>
      </div>
      <ElButton size="small" @click="$emit('retry')">重试</ElButton>
    </div>
  </div>
</template>

<style scoped>
.error {
  padding: 14px 16px;
  border-color: var(--a-danger-border);
  background: var(--a-danger-bg);
  margin-bottom: 14px;
}

.error__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.error__title {
  color: var(--el-color-danger);
  font-weight: 600;
  font-size: 13px;
}

.error__hint {
  margin-top: 4px;
  color: var(--a-text-3);
  font-size: 12px;
}
</style>
