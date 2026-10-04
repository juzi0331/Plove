<script setup lang="ts">
/**
 * CacheCenterView - 全局缓存控制中心与命中率透视（组件化架构）
 * 1. 全局内容缓存与主动预热总控卡片
 * 2. 5大核心指标透明透视卡片
 * 3. 分站点缓存矩阵卡片
 * 4. 内存缓存条目检索与管理
 * 5. 缓存数据深度可视化透视抽屉（CacheEntryDrawer 子组件）
 */
import {
  Delete,
  Lightning,
  List,
  Platform,
  Refresh,
  Timer,
  VideoPlay,
  View,
} from '@element-plus/icons-vue'
import {
  ElButton,
  ElCard,
  ElEmpty,
  ElIcon,
  ElProgress,
  ElSkeleton,
  ElSwitch,
  ElTag,
} from 'element-plus'

import PageHeader from '../components/PageHeader.vue'
import { ui } from '@/admin/ui'
import { useCacheCenter } from './cache/useCacheCenter'
import CacheEntryDrawer from './cache/CacheEntryDrawer.vue'

const {
  loading,
  preheating,
  updatingGlobal,
  stats,
  globalConfig,
  isEntryDrawerVisible,
  selectedEntryKey,
  loadData,
  handleSaveGlobalConfig,
  handleViewEntry,
  handlePreheat,
  handleClearAll,
  handleClearKey,
  handleClearSite,
  handlePreheatSite,
  filteredEntries,
  capacityPercent,
  hitRatio,
  savedBandwidthMb,
  siteSummaries,
  nsTagType,
  nsFriendlyName,
} = useCacheCenter()
</script>

<template>
  <div class="a-page cache-page">
    <PageHeader
      title="全局缓存控制中心与命中率透视"
      desc="全面透视内存与磁盘缓存容量、防击穿 SingleFlight 队列及命中状态（HIT / MISS），支持全站一键预热与深层数据解析。"
    >
      <template #actions>
        <ElButton :icon="Refresh" :loading="loading" @click="loadData">刷新状态</ElButton>
        <ElButton
          type="primary"
          :icon="VideoPlay"
          :loading="preheating"
          :disabled="ui.readOnly"
          @click="() => handlePreheat()"
        >
          一键全站预热
        </ElButton>
        <ElButton
          type="danger"
          plain
          :icon="Delete"
          :disabled="ui.readOnly"
          @click="handleClearAll"
        >
          全量清空缓存
        </ElButton>
      </template>
    </PageHeader>

    <!-- 骨架屏加载状态 -->
    <div v-if="loading && !stats" class="a-card skeleton">
      <ElSkeleton :rows="6" animated />
    </div>

    <template v-else>
      <!-- 1. 全局缓存与主动预热总控卡片 (开关标明「开启」「关闭」) -->
      <div class="control-cards-grid">
        <!-- 缓存总开关卡片 -->
        <ElCard shadow="hover" class="switch-box-card">
          <div class="switch-box-content">
            <div class="switch-icon-col icon-primary">
              <ElIcon :size="24"><Lightning /></ElIcon>
            </div>
            <div class="switch-info-col">
              <div class="switch-title-row">
                <span class="switch-main-name">全局内容缓存总开关</span>
                <ElTag size="small" :type="globalConfig.cache_enabled ? 'success' : 'info'" effect="dark">
                  {{ globalConfig.cache_enabled ? '已开启' : '已关闭' }}
                </ElTag>
              </div>
              <p class="switch-sub-desc">
                开启后，首页、分类大厅和详情页将自动享受 0ms 内存与磁盘极速响应，大幅降低源站压力；关闭后所有请求穿透直达源站。
              </p>
            </div>
            <div class="switch-toggle-col">
              <ElSwitch
                v-model="globalConfig.cache_enabled"
                :disabled="ui.readOnly || updatingGlobal"
                inline-prompt
                active-text="开启"
                inactive-text="关闭"
                @change="handleSaveGlobalConfig"
              />
            </div>
          </div>
        </ElCard>

        <!-- 预热总开关卡片 -->
        <ElCard shadow="hover" class="switch-box-card">
          <div class="switch-box-content">
            <div class="switch-icon-col icon-success">
              <ElIcon :size="24"><Timer /></ElIcon>
            </div>
            <div class="switch-info-col">
              <div class="switch-title-row">
                <span class="switch-main-name">自动定时预热总开关</span>
                <ElTag size="small" :type="globalConfig.warmup_enabled ? 'success' : 'info'" effect="dark">
                  {{ globalConfig.warmup_enabled ? '已开启' : '已关闭' }}
                </ElTag>
              </div>
              <p class="switch-sub-desc">
                开启后，后台每隔 24 小时主动模拟访问各源站热门页面注入缓存，杜绝冷启动首访等待；关闭后服务不在后台自主请求。
              </p>
            </div>
            <div class="switch-toggle-col">
              <ElSwitch
                v-model="globalConfig.warmup_enabled"
                :disabled="ui.readOnly || updatingGlobal"
                inline-prompt
                active-text="开启"
                inactive-text="关闭"
                @change="handleSaveGlobalConfig"
              />
            </div>
          </div>
        </ElCard>
      </div>

      <!-- 2. KPI 统计卡片（纯 Grid 等宽响应式排布） -->
      <div class="metric-row">
        <ElCard shadow="hover" class="metric-card metric-card--primary">
          <div class="metric-head">
            <span>实时缓存命中率</span>
            <ElTag size="small" type="success" effect="plain">透明可感知</ElTag>
          </div>
          <div class="metric-val highlight">
            {{ hitRatio }}<span class="metric-unit">%</span>
          </div>
          <div class="metric-foot">
            <span>节约流量: ~{{ savedBandwidthMb }} MB</span>
            <span class="foot-sep">·</span>
            <span>命中: {{ stats?.hits ?? 0 }} / 穿透: {{ stats?.misses ?? 0 }}</span>
          </div>
        </ElCard>

        <ElCard shadow="hover" class="metric-card">
          <div class="metric-head">
            <span>L1 内存缓存容量</span>
            <span class="a-muted">{{ capacityPercent }}%</span>
          </div>
          <div class="metric-val">
            {{ stats?.size ?? 0 }}
            <span class="metric-sub">/ {{ stats?.maxsize ?? 512 }}</span>
          </div>
          <ElProgress
            :percentage="capacityPercent"
            :show-text="false"
            :stroke-width="6"
            color="var(--el-color-primary)"
          />
        </ElCard>

        <ElCard shadow="hover" class="metric-card">
          <div class="metric-head">
            <span>L2 磁盘持久化镜像</span>
            <ElTag size="small" type="success" effect="plain">SQLite WAL</ElTag>
          </div>
          <div class="metric-val">
            {{ stats?.disk?.count ?? 0 }}
            <span class="metric-unit">条目</span>
          </div>
          <div class="metric-foot">
            <span>磁盘: {{ stats?.disk?.size_mb ?? 0 }} MB</span>
            <span class="foot-sep">·</span>
            <span class="a-muted">重启零丢失</span>
          </div>
        </ElCard>

        <ElCard shadow="hover" class="metric-card">
          <div class="metric-head">
            <span>防击穿并发队列</span>
            <ElTag size="small" :type="stats?.inflight ? 'warning' : 'info'">SingleFlight</ElTag>
          </div>
          <div class="metric-val">
            {{ stats?.inflight ?? 0 }}
            <span class="metric-unit">tasks</span>
          </div>
          <div class="metric-foot a-muted">并发请求瞬间合并为 1 次请求</div>
        </ElCard>

        <ElCard shadow="hover" class="metric-card">
          <div class="metric-head">
            <span>默认存活时间</span>
            <span class="a-muted">TTL 策略</span>
          </div>
          <div class="metric-kv">
            <span>首页: {{ stats?.ttl?.home ?? 600 }}s</span>
            <span>列表: {{ stats?.ttl?.category ?? 300 }}s</span>
            <span>详情: {{ stats?.ttl?.detail ?? 300 }}s</span>
          </div>
          <div class="metric-foot a-muted">播放地址不缓存</div>
        </ElCard>
      </div>

      <!-- 3. 分站点缓存矩阵卡片（展示全量接入源站状态） -->
      <div v-if="siteSummaries.length > 0" class="section-container">
        <div class="section-title-bar">
          <div class="title-with-icon">
            <ElIcon :size="16"><Platform /></ElIcon>
            <span>分源站缓存矩阵 ({{ siteSummaries.length }} 个源站)</span>
          </div>
        </div>

        <div class="site-cache-grid">
          <ElCard
            v-for="s in siteSummaries"
            :key="s.site"
            shadow="hover"
            class="site-item-card"
          >
            <div class="s-card-top">
              <div class="s-card-title-box">
                <span class="s-card-name" :title="s.site">{{ s.name }}</span>
                <code class="s-card-key">{{ s.site }}</code>
              </div>
              <ElTag size="small" :type="s.total > 0 ? 'success' : 'info'" effect="plain">
                {{ s.total > 0 ? `${s.total} 条缓存` : '暂无缓存' }}
              </ElTag>
            </div>

            <div class="s-card-counts">
              <div class="count-pill">
                <span class="c-label">首页:</span>
                <span class="c-num">{{ s.homeCount }}</span>
              </div>
              <div class="count-pill">
                <span class="c-label">分类:</span>
                <span class="c-num">{{ s.categoryCount }}</span>
              </div>
              <div class="count-pill">
                <span class="c-label">详情:</span>
                <span class="c-num">{{ s.detailCount }}</span>
              </div>
            </div>

            <div class="s-card-actions">
              <ElButton
                size="small"
                type="primary"
                plain
                :icon="VideoPlay"
                :loading="preheating"
                :disabled="ui.readOnly"
                @click="handlePreheatSite(s.site)"
              >
                预热该站
              </ElButton>
              <ElButton
                size="small"
                type="danger"
                plain
                :icon="Delete"
                :disabled="s.total === 0 || ui.readOnly"
                @click="handleClearSite(s.site)"
              >
                清空该站
              </ElButton>
            </div>
          </ElCard>
        </div>
      </div>

      <!-- 4. 内存缓存条目卡片管理 -->
      <div class="section-container">
        <div class="section-title-bar">
          <div class="title-with-icon">
            <ElIcon :size="16"><List /></ElIcon>
            <span>当前内存缓存条目 (共 {{ filteredEntries.length }} 项)</span>
          </div>
        </div>

        <!-- 条目卡片网格 -->
        <div v-if="filteredEntries.length > 0" class="entry-cards-grid">
          <ElCard
            v-for="row in filteredEntries"
            :key="row.key"
            shadow="hover"
            class="entry-item-card"
          >
            <div class="entry-card-header">
              <div class="entry-tags">
                <ElTag size="small" effect="plain">{{ row.site }}</ElTag>
                <ElTag size="small" :type="nsTagType(row.namespace)" effect="dark">
                  {{ nsFriendlyName(row.namespace) }}
                </ElTag>
                <ElTag v-if="row.is_disk" size="small" type="success" effect="plain">L2磁盘</ElTag>
              </div>
              <span class="entry-ttl-pill">
                剩余 {{ row.remaining_seconds }}s
              </span>
            </div>

            <div class="entry-card-body">
              <div class="entry-ident" :title="row.ident || '首页推荐排盘'">
                {{ row.ident ? `标识: ${row.ident}` : '全站首页推荐排盘' }}
              </div>
              <code class="entry-full-key" :title="row.key">{{ row.key }}</code>
            </div>

            <div class="entry-card-footer">
              <ElButton
                type="primary"
                size="small"
                plain
                :icon="View"
                @click="handleViewEntry(row.key)"
              >
                查看数据
              </ElButton>
              <ElButton
                type="danger"
                size="small"
                plain
                :icon="Delete"
                :disabled="ui.readOnly"
                @click="handleClearKey(row.key)"
              >
                删除键
              </ElButton>
            </div>
          </ElCard>
        </div>

        <ElCard v-else shadow="hover" class="empty-entries-card">
          <ElEmpty description="当前未发现匹配的缓存条目，可点击上方「一键全站预热」或通过前台访问自动生成" />
        </ElCard>
      </div>
    </template>

    <!-- 5. 缓存数据可视化透视抽屉 (子组件) -->
    <CacheEntryDrawer
      v-model="isEntryDrawerVisible"
      :entry-key="selectedEntryKey"
    />
  </div>
</template>

<style>
@import './cache/cache-center.css';
</style>
