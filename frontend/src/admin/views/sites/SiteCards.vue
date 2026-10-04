<script setup lang="ts">
/**
 * SiteCards - 站点管理卡片流与网格列表
 */
import { Right, Setting } from '@element-plus/icons-vue'
import {
  ElButton,
  ElCard,
  ElDivider,
  ElIcon,
  ElSwitch,
  ElTag,
  ElTooltip,
} from 'element-plus'

import { ref } from 'vue'
import type { AdminSiteItem } from '@/api/types'

import { probePlayground } from '../../api'
import { type TagType } from '../../format'
import { ui } from '../../ui'

defineProps<{
  sites: AdminSiteItem[]
  busyKey: string | null
  firstKey?: string
  lastKey?: string
  getProxyTooltip: (site: AdminSiteItem) => string
  getBoundNodeBadgeText: (site: AdminSiteItem) => string
  healthState: (site: AdminSiteItem) => { label: string; tag: TagType }
}>()

const emit = defineEmits<{
  (e: 'toggleProxy', site: AdminSiteItem): void
  (e: 'toggleEnabled', site: AdminSiteItem, next: boolean): void
  (e: 'move', index: number, delta: number): void
  (e: 'openDetail', site: AdminSiteItem): void
  (e: 'openAdvanced', site: AdminSiteItem): void
  (e: 'openCategory', site: AdminSiteItem): void
  (e: 'openDetailPolicy', site: AdminSiteItem): void
  (e: 'viewCode', site: AdminSiteItem): void
  (e: 'deleteSite', site: AdminSiteItem): void
}>()

const pingStates = ref<Record<string, { testing: boolean; latencyMs?: number; ok?: boolean }>>({})

async function pingSite(siteKey: string): Promise<void> {
  pingStates.value[siteKey] = { testing: true }
  const start = performance.now()
  try {
    const res = await probePlayground({
      site: siteKey,
      command: 'home',
      bypass_cache: true,
    })
    const elapsed = Math.round(performance.now() - start)
    pingStates.value[siteKey] = {
      testing: false,
      latencyMs: res.elapsed_ms || elapsed,
      ok: res.status === 'OK',
    }
  } catch {
    pingStates.value[siteKey] = {
      testing: false,
      latencyMs: 9999,
      ok: false,
    }
  }
}
</script>

<template>
  <div class="sites-container">
    <div class="site-cards-grid">
      <ElCard
        v-for="(site, index) in sites"
        :key="site.key"
        shadow="hover"
        class="site-card site-card--clickable"
        :class="{ 'site-card--disabled': !site.enabled, 'site-card--open': site.health.state === 'open' }"
        @click="emit('openDetail', site)"
      >
        <!-- 卡片顶栏 -->
        <div class="site-card-header">
          <div class="site-title-box">
            <span class="site-name" :title="site.name">{{ site.name }}</span>
            <code class="site-key-badge">{{ site.key }}</code>
            <ElTag v-if="site.mode === 'proxy'" size="small" type="warning" effect="plain" class="mini-tag">
              反代
            </ElTag>
            <ElTag v-if="site.version" size="small" type="info" effect="plain" class="mini-badge">
              v{{ site.version }}
            </ElTag>
            <!-- 独立代理状态徽章 -->
            <ElTooltip
              :content="getProxyTooltip(site)"
              placement="top"
            >
              <ElTag
                size="small"
                :type="site.proxy_enabled ? 'success' : 'info'"
                :effect="site.proxy_enabled ? 'dark' : 'plain'"
                class="mini-tag proxy-status-tag"
                style="cursor: pointer"
                @click.stop="emit('toggleProxy', site)"
              >
                <template v-if="site.proxy_enabled">
                  代理: {{ getBoundNodeBadgeText(site) }}
                </template>
                <template v-else>
                  直连
                </template>
              </ElTag>
            </ElTooltip>
          </div>
          <div class="site-switch-box">
            <ElTooltip :content="site.enabled ? '已启用（用户端可见）' : '已停用（用户端不可见）'" placement="top">
              <ElSwitch
                :model-value="site.enabled"
                size="small"
                :loading="busyKey === site.key"
                :disabled="ui.readOnly"
                @click.stop
                @update:model-value="(val) => emit('toggleEnabled', site, Boolean(val))"
              />
            </ElTooltip>
          </div>
        </div>

        <!-- 卡片状态与排序 -->
        <div class="site-meta-bar">
          <div class="status-indicator">
            <ElTag :type="healthState(site).tag" size="small" effect="light">
              {{ healthState(site).label }}
            </ElTag>
            <!-- 实时延迟徽章与点击测速 -->
            <ElTag
              size="small"
              :type="pingStates[site.key]?.latencyMs ? (pingStates[site.key]!.latencyMs! < 300 ? 'success' : pingStates[site.key]!.latencyMs! < 1000 ? 'warning' : 'danger') : 'info'"
              effect="plain"
              style="cursor: pointer"
              title="点击单站即时测速"
              @click.stop="pingSite(site.key)"
            >
              {{ pingStates[site.key]?.testing ? '测速中...' : (pingStates[site.key]?.latencyMs ? `${pingStates[site.key]!.latencyMs}ms` : '测速') }}
            </ElTag>
            <span v-if="site.health.failures" class="fail-text">
              失败 {{ site.health.failures }}/{{ site.health.fail_threshold }}
            </span>
            <span v-if="site.health.retry_after" class="retry-text">
              熔断中，约 {{ Math.ceil(site.health.retry_after) }}s 后试探
            </span>
          </div>

          <!-- 排序控制 -->
          <div class="order-control">
            <span class="a-muted order-label">位次 {{ site.sort_order }}</span>
            <ElButton
              link
              size="small"
              :disabled="ui.readOnly || site.key === firstKey"
              title="上移"
              @click.stop="emit('move', index, -1)"
            >
              ↑
            </ElButton>
            <ElButton
              link
              size="small"
              :disabled="ui.readOnly || site.key === lastKey"
              title="下移"
              @click.stop="emit('move', index, 1)"
            >
              ↓
            </ElButton>
          </div>
        </div>

        <!-- 能力清单 -->
        <div class="capabilities-box">
          <div class="cap-title a-muted">支持能力：</div>
          <div class="cap-tags">
            <ElTag
              v-for="cap in site.capabilities"
              :key="cap"
              size="small"
              class="cap-tag"
              effect="plain"
            >
              {{ cap }}
            </ElTag>
          </div>
        </div>

        <!-- 运维备忘 -->
        <div v-if="site.note" class="site-note-text" :title="site.note">
          {{ site.note }}
        </div>

        <ElDivider style="margin: 12px 0 10px 0" />

        <!-- 底部轻量卡片弹出指引栏（彻底告别臃肿的按钮堆叠！） -->
        <div class="site-card-footer">
          <div class="site-card-tip">
            <ElIcon :size="13"><Setting /></ElIcon>
            <span>点击卡片弹出详细配置 (基础/分类/清洗/源码)</span>
          </div>
          <div class="site-card-arrow">
            <ElIcon :size="13"><Right /></ElIcon>
          </div>
        </div>
      </ElCard>
    </div>
  </div>
</template>
