<script setup lang="ts">
import { Delete } from '@element-plus/icons-vue'
import {
  ElButton,
  ElDivider,
  ElSwitch,
} from 'element-plus'

import type { AdminSiteItem } from '@/api/types'
import { ui } from '@/admin/ui'

defineProps<{
  site: AdminSiteItem
  isFirst?: boolean
  isLast?: boolean
}>()

const emit = defineEmits<{
  (e: 'move', offset: number): void
  (e: 'toggleEnabled', val: boolean): void
  (e: 'deleteSite'): void
}>()
</script>

<template>
  <div class="tab-pane-content">
    <div class="manage-section">
      <div class="manage-title">站点在前台展示的位次排序</div>
      <p class="manage-desc">位次决定了该采集源在用户端首页、多源搜索结果以及线路选择时的优先级顺序。</p>
      <div class="manage-actions-row">
        <span class="a-muted" style="margin-right: 12px;">当前位次：{{ site.sort_order }}</span>
        <ElButton
          size="small"
          :disabled="ui.readOnly || isFirst"
          @click="emit('move', -1)"
        >
          ↑ 上移一位 (提升优先级)
        </ElButton>
        <ElButton
          size="small"
          :disabled="ui.readOnly || isLast"
          @click="emit('move', 1)"
        >
          ↓ 下移一位 (降低优先级)
        </ElButton>
      </div>
    </div>

    <ElDivider />

    <div class="manage-section">
      <div class="manage-title">启停状态控制</div>
      <p class="manage-desc">停用后，用户端将无法检索到该站影片，现有缓存将不再更新，但不影响采集器源码与配置持久化。</p>
      <ElSwitch
        :model-value="site.enabled"
        :disabled="ui.readOnly"
        active-text="启用站点"
        inactive-text="停用站点"
        @update:model-value="(val) => emit('toggleEnabled', Boolean(val))"
      />
    </div>

    <ElDivider />

    <div class="manage-section danger-zone">
      <div class="manage-title" style="color: var(--el-color-danger);">危险区域：删除采集器</div>
      <p class="manage-desc">删除采集器将从磁盘彻底移除 <code>{{ site.key }}.py</code> 脚本及该站的所有关联规则。此操作不可逆！</p>
      <ElButton
        type="danger"
        :icon="Delete"
        :disabled="ui.readOnly"
        @click="emit('deleteSite')"
      >
        彻底删除此采集器
      </ElButton>
    </div>
  </div>
</template>

<style scoped src="./site-detail-modal.css"></style>
