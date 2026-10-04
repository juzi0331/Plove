<script setup lang="ts">
import {
  ElButton,
  ElCard,
  ElIcon,
  ElInput,
  ElTag,
} from 'element-plus'
import {
  CopyDocument,
  Plus,
  Refresh,
  Search,
  Tickets,
} from '@element-plus/icons-vue'
import { ui } from '@/admin/ui'

const props = defineProps<{
  totalCount: number
  search: string
  loading: boolean
  stats: {
    active: number
    unactivated: number
    expired: number
    disabled: number
  }
  issuedCodes: string[]
}>()

const emit = defineEmits<{
  (e: 'update:search', val: string): void
  (e: 'search'): void
  (e: 'load'): void
  (e: 'openIssue'): void
  (e: 'cleanupExpired'): void
  (e: 'copyText', text: string, success: string): void
}>()
</script>

<template>
  <div class="cards-grid">
    <!-- 卡片 1: 发码与快速控制中心 -->
    <ElCard shadow="hover" class="module-card">
      <div class="card-top-bar">
        <div class="card-title-group">
          <div class="card-icon-box icon-box--primary">
            <ElIcon :size="20"><Tickets /></ElIcon>
          </div>
          <div>
            <div class="card-title">激活码总控与操作</div>
            <div class="card-subtitle">支持批量生成、有效期时长预设与条件检索</div>
          </div>
        </div>
        <ElTag type="primary" effect="dark" class="status-tag">
          共 {{ props.totalCount }} 个激活码
        </ElTag>
      </div>

      <div class="card-body-section">
        <div class="control-row">
          <ElInput
            :model-value="props.search"
            placeholder="搜索激活码或备注关键词..."
            size="small"
            clearable
            :prefix-icon="Search"
            style="max-width: 320px;"
            @update:model-value="emit('update:search', $event)"
            @keyup.enter="emit('search')"
            @clear="emit('search')"
          />
          <ElButton size="small" :icon="Search" @click="emit('search')">搜索</ElButton>
          <ElButton size="small" :icon="Refresh" :loading="props.loading" @click="emit('load')">刷新</ElButton>
        </div>
      </div>

      <div class="card-footer-bar">
        <span class="footer-hint">支持单台或多设备共用同一激活码</span>
        <div class="card-footer-actions">
          <ElButton
            size="small"
            type="danger"
            plain
            :disabled="ui.readOnly"
            @click="emit('cleanupExpired')"
          >
            清理失效码
          </ElButton>
          <ElButton
            size="small"
            type="primary"
            :icon="Plus"
            :disabled="ui.readOnly"
            @click="emit('openIssue')"
          >
            发行新码
          </ElButton>
        </div>
      </div>
    </ElCard>

    <!-- 卡片 2: 授权状态指标卡片 -->
    <ElCard shadow="hover" class="module-card">
      <div class="card-top-bar">
        <div class="card-title-group">
          <div class="card-icon-box icon-box--success">
            <ElIcon :size="20"><Tickets /></ElIcon>
          </div>
          <div>
            <div class="card-title">当前状态指标</div>
            <div class="card-subtitle">在用、未激活、过期及封禁激活码实时统计</div>
          </div>
        </div>
      </div>

      <div class="card-body-section">
        <div class="stats-pills-grid">
          <div class="stat-pill-box">
            <span class="stat-pill-label">在用激活中</span>
            <span class="stat-pill-value stat-active">{{ props.stats.active }}</span>
          </div>
          <div class="stat-pill-box">
            <span class="stat-pill-label">未激活</span>
            <span class="stat-pill-value stat-unactivated">{{ props.stats.unactivated }}</span>
          </div>
          <div class="stat-pill-box">
            <span class="stat-pill-label">已过期</span>
            <span class="stat-pill-value stat-expired">{{ props.stats.expired }}</span>
          </div>
          <div class="stat-pill-box">
            <span class="stat-pill-label">已停用/封禁</span>
            <span class="stat-pill-value stat-disabled">{{ props.stats.disabled }}</span>
          </div>
        </div>
      </div>

      <div class="card-footer-bar">
        <span class="footer-hint">
          {{ props.issuedCodes.length > 0 ? `最新发出 ${props.issuedCodes.length} 个码（点击复制）：` : '激活码时长自首次使用设备绑定起算' }}
        </span>
        <div v-if="props.issuedCodes.length > 0" class="issued-codes-box">
          <span
            v-for="c in props.issuedCodes"
            :key="c"
            class="issued-code-chip"
            title="点击复制此码"
            @click="emit('copyText', c, `已复制激活码: ${c}`)"
          >
            {{ c }}
          </span>
          <ElButton
            size="small"
            link
            type="primary"
            :icon="CopyDocument"
            @click="emit('copyText', props.issuedCodes.join('\n'), '已复制全部新发行激活码')"
          >
            复制全部
          </ElButton>
        </div>
      </div>
    </ElCard>
  </div>
</template>
