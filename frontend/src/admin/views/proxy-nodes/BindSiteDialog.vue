<script setup lang="ts">
import {
  ElButton,
  ElDialog,
  ElOption,
  ElSelect,
  ElTag,
} from 'element-plus'
import type { AdminSiteItem, ProxyNodeItem } from '@/api/types'

const props = defineProps<{
  modelValue: boolean
  currentBindTargetNode: ProxyNodeItem | null
  selectedSiteKeyToBind: string
  sites: AdminSiteItem[]
  bindSaving: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'update:selectedSiteKeyToBind', val: string): void
  (e: 'confirm'): void
}>()
</script>

<template>
  <ElDialog
    :model-value="props.modelValue"
    :title="`指派采集器到「${props.currentBindTargetNode?.name || ''}」`"
    width="480px"
    align-center
    append-to-body
    destroy-on-close
    class="submodal-dialog"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div style="margin-bottom: 14px; font-size: 13.5px; color: var(--el-text-color-primary);">
      选择要将网络请求通道指派给此节点的采集器适配器：
    </div>
    <ElSelect
      :model-value="props.selectedSiteKeyToBind"
      placeholder="请选择要绑定的采集器"
      style="width: 100%"
      filterable
      @update:model-value="emit('update:selectedSiteKeyToBind', $event)"
    >
      <ElOption
        v-for="s in props.sites"
        :key="s.key"
        :label="`${s.name} (${s.key})`"
        :value="s.key"
      >
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>{{ s.name }} ({{ s.key }})</span>
          <ElTag v-if="s.proxy_enabled && s.proxy_node_id === props.currentBindTargetNode?.id" size="small" type="success">
            当前已绑定
          </ElTag>
          <ElTag v-else-if="!s.proxy_enabled" size="small" type="info">
            当前直连
          </ElTag>
        </div>
      </ElOption>
    </ElSelect>

    <template #footer>
      <ElButton @click="emit('update:modelValue', false)">取消</ElButton>
      <ElButton type="primary" :loading="props.bindSaving" @click="emit('confirm')">
        确认绑定指派
      </ElButton>
    </template>
  </ElDialog>
</template>
