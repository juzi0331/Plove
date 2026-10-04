<script setup lang="ts">
import {
  Delete,
  Download,
  Lightning,
  Plus,
} from '@element-plus/icons-vue'
import {
  ElButton,
  ElCard,
  ElDivider,
  ElOption,
  ElSelect,
  ElTag,
} from 'element-plus'
import type {
  AdminSiteItem,
  ProxyNodeItem,
  ProxyTestResult,
} from '@/api/types'

const props = defineProps<{
  node: ProxyNodeItem
  boundSites: AdminSiteItem[]
  availableSites: AdminSiteItem[]
  testState?: { loading: boolean; result?: ProxyTestResult }
}>()

const emit = defineEmits<{
  (e: 'copyText', text: string): void
  (e: 'unbindSite', siteKey: string, siteName: string): void
  (e: 'inlineBind', nodeId: string, siteKey: string): void
  (e: 'openBindDialog', node: ProxyNodeItem): void
  (e: 'testNode', node: ProxyNodeItem): void
  (e: 'openXrayDialog', node: ProxyNodeItem): void
  (e: 'deleteNode', node: ProxyNodeItem): void
}>()
</script>

<template>
  <ElCard
    class="node-card"
    :class="{ 'node-card--vless': props.node.protocol === 'vless' }"
    shadow="hover"
  >
    <!-- 卡片头部 -->
    <div class="node-header">
      <div class="node-title-box">
        <ElTag
          :type="props.node.protocol === 'vless' ? 'success' : 'primary'"
          effect="dark"
          size="small"
          class="proto-tag"
        >
          {{ props.node.protocol.toUpperCase() }}
        </ElTag>
        <span class="node-name" :title="props.node.name">{{ props.node.name }}</span>
      </div>

      <!-- 测速延迟标签 / 状态徽章 -->
      <div v-if="props.testState?.result" class="node-status-tag">
        <span v-if="props.testState.result.ok" class="status-badge--ok">
          {{ props.testState.result.duration_ms }}ms
        </span>
        <span v-else class="status-badge--fail" :title="props.testState.result.message">
          连接失败
        </span>
      </div>
    </div>

    <!-- 节点参数详情 -->
    <div class="node-details">
      <!-- VLESS 模式下高亮展示托管本地端口 -->
      <div v-if="props.node.protocol === 'vless'" class="detail-row">
        <span class="detail-label">本地托管中转：</span>
        <code
          class="detail-val copyable"
          title="点击复制此地址"
          @click="emit('copyText', props.node.proxy_url)"
        >
          {{ props.node.proxy_url }}
        </code>
      </div>

      <!-- 远程服务器信息 -->
      <div v-if="props.node.server" class="detail-row">
        <span class="detail-label">远程服务器：</span>
        <span class="detail-val">{{ props.node.server }}:{{ props.node.port }}</span>
      </div>

      <!-- 普通 HTTP/SOCKS 代理直连信息 -->
      <div v-else class="detail-row">
        <span class="detail-label">代理地址：</span>
        <code
          class="detail-val copyable"
          title="点击复制此地址"
          @click="emit('copyText', props.node.proxy_url)"
        >
          {{ props.node.proxy_url }}
        </code>
      </div>

      <!-- 绑定采集器列表 -->
      <div class="detail-row bound-row">
        <span class="detail-label">已绑定采集器：</span>
        <div class="bound-tags">
          <template v-if="props.boundSites.length > 0">
            <ElTag
              v-for="s in props.boundSites"
              :key="s.key"
              size="small"
              type="info"
              closable
              class="bound-tag"
              @close="emit('unbindSite', s.key, s.name)"
            >
              {{ s.name }}
            </ElTag>
          </template>
          <span v-else class="detail-label no-bound-hint">
            暂无采集器指派至此节点
          </span>

          <!-- 快速内联指派采集器 -->
          <ElSelect
            v-if="props.availableSites.length > 0"
            size="small"
            placeholder="+ 指派"
            style="width: 90px; margin-left: 4px;"
            @change="emit('inlineBind', props.node.id, $event as string)"
          >
            <ElOption
              v-for="s in props.availableSites"
              :key="s.key"
              :label="s.name"
              :value="s.key"
            />
          </ElSelect>
          <ElButton
            v-else
            size="small"
            link
            type="primary"
            :icon="Plus"
            style="font-size: 11.5px; padding: 0 4px; margin-left: 4px;"
            title="打开弹窗指派"
            @click="emit('openBindDialog', props.node)"
          >
            指派
          </ElButton>
        </div>
      </div>
    </div>

    <ElDivider style="margin: 12px 0 10px 0" />

    <!-- 操作栏 -->
    <div class="node-actions">
      <ElButton
        size="small"
        type="primary"
        :loading="props.testState?.loading"
        :icon="Lightning"
        @click="emit('testNode', props.node)"
      >
        连通性测速
      </ElButton>

      <!-- 导出作为备用工具，不再强求用户手动运行 -->
      <ElButton
        v-if="props.node.protocol === 'vless'"
        size="small"
        plain
        :icon="Download"
        title="备用：如果需要在外部或其它设备独立运行 Xray，可在此导出 config.json"
        @click="emit('openXrayDialog', props.node)"
      >
        导出备用配置
      </ElButton>

      <div style="flex: 1" />

      <ElButton
        size="small"
        link
        type="danger"
        :icon="Delete"
        @click="emit('deleteNode', props.node)"
      >
        删除
      </ElButton>
    </div>
  </ElCard>
</template>
