<script setup lang="ts">
/**
 * Plove Cloud Console - 总览看板 (Dashboard)
 *
 * 全新设计语言：
 * 1. 现代化顶部 Hero 状态大屏：环境状态、运行节点信息、快速运维操作；
 * 2. 核心 KPI 矩阵卡片：秒开缓存条目水位、实时命中率、SingleFlight 护盾、预热巡检状态；
 * 3. 源健康状态网格：带心跳状态指示灯、熔断保护倒计时、失败计数；
 * 4. 预热战报审查表格；
 * 5. 右下角悬浮智能运维指南 (FAB)，弹出结构化深度解析对话框。
 *
 * 绝对不含任何 emoji。
 */
import {
  ElButton,
  ElDialog,
  ElIcon,
  ElMessage,
  ElProgress,
  ElSkeleton,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus'
import {
  CircleCheck,
  Document,
  Lightning,
  Refresh,
  Warning,
} from '@element-plus/icons-vue'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { describeError } from '@/api/http'
import type { AdminStatusPayload } from '@/api/types'

import * as api from '../api'
import EmptyState from '../components/EmptyState.vue'
import ErrorState from '../components/ErrorState.vue'
import SourceHealthCard from '../components/SourceHealthCard.vue'
import TimeAgo from '../components/TimeAgo.vue'
import { hitRate } from '../format'
import { ui } from '../ui'

const data = ref<AdminStatusPayload | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const refreshing = ref(false)
const waitForWarmup = ref(false)
const isHelpDocVisible = ref(false)

let timer: number | null = null

async function load(silent = false): Promise<void> {
  if (!silent) loading.value = true
  try {
    data.value = await api.status()
    error.value = null
  } catch (err) {
    error.value = describeError(err)
  } finally {
    loading.value = false
  }
}

async function refreshCache(): Promise<void> {
  refreshing.value = true
  try {
    const result = await api.refreshCache(waitForWarmup.value)
    ElMessage.success(result.message)
    await load(true)
  } catch (err) {
    ElMessage.error(describeError(err))
  } finally {
    refreshing.value = false
  }
}

function startTimer(): void {
  stopTimer()
  if (!ui.autoRefreshEnabled) return
  timer = window.setInterval(() => void load(true), ui.autoRefreshSeconds * 1000)
}

function stopTimer(): void {
  if (timer !== null) {
    window.clearInterval(timer)
    timer = null
  }
}

watch(() => [ui.autoRefreshEnabled, ui.autoRefreshSeconds], startTimer)

onMounted(async () => {
  await load()
  startTimer()
})
onUnmounted(stopTimer)

// ------------------------------------------------------------------ 异常与告警

interface Notice {
  level: 'danger' | 'warn' | 'info'
  text: string
}

const notices = computed<Notice[]>(() => {
  const payload = data.value
  if (!payload) return []
  const list: Notice[] = []

  for (const site of payload.sites ?? []) {
    if (site.probed && site.state === 'open') {
      const remain = site.retry_after ? `，约 ${Math.ceil(site.retry_after)} 秒后放探针` : ''
      list.push({ level: 'danger', text: `${site.site} 已熔断（连续失败 ${site.failures} 次）${remain}` })
    }
  }

  const failed = (payload.warmup.sites ?? []).filter((site) => !site.ok)
  if (failed.length) {
    list.push({
      level: 'warn',
      text: `上次预热有 ${failed.length} 个源失败：${failed.map((s) => `${s.site}（${s.error ?? '未知错误'}）`).join('；')}`,
    })
  }

  const zeroTtl = Object.entries(payload.cache.ttl)
    .filter(([, seconds]) => seconds <= 0)
    .map(([key]) => key)
  if (zeroTtl.length) {
    list.push({ level: 'warn', text: `缓存已关闭：${zeroTtl.join(' / ')}（TTL 配成了 0）` })
  }

  if (!payload.warmup.enabled) {
    list.push({ level: 'info', text: '主动预热未开启：内容在用户首次访问时抓取，首位来访者承担抓取耗时' })
  }

  return list
})

const cachePercent = computed(() => {
  if (!data.value || !data.value.cache.maxsize) return 0
  return Math.min(100, Math.round((data.value.cache.size / data.value.cache.maxsize) * 100))
})
</script>

<template>
  <div class="a-page dashboard-page">
    <!-- 顶部状态大屏 -->
    <div class="dash-hero">
      <div class="dash-hero-info">
        <div class="hero-badge">
          <span class="hero-pulse" />
          <span>系统实时运维看板</span>
        </div>
        <h1 class="hero-title">全局监控与运维中心</h1>
        <p class="hero-desc">
          多源采集、动态缓存防击穿、源站熔断健康度与数据预热全景透视。
        </p>
      </div>

      <div class="dash-hero-actions">
        <label class="wait-label">
          <span>等待预热完成</span>
          <ElSwitch v-model="waitForWarmup" size="small" />
        </label>
        <ElButton size="default" :icon="Refresh" @click="load()">
          立即刷新
        </ElButton>
        <ElButton
          type="primary"
          size="default"
          :icon="Lightning"
          :loading="refreshing"
          @click="refreshCache"
        >
          全站缓存刷新
        </ElButton>
      </div>
    </div>

    <!-- 告警横幅 -->
    <div v-if="notices.length" class="notices-grid">
      <div v-for="(notice, index) in notices" :key="index" class="notice-card" :class="`notice--${notice.level}`">
        <ElIcon :size="16" class="notice-icon">
          <Warning v-if="notice.level !== 'info'" />
          <CircleCheck v-else />
        </ElIcon>
        <span class="notice-text">{{ notice.text }}</span>
      </div>
    </div>

    <ErrorState v-if="error" :message="error" hint="如果一直失败，检查后端进程与令牌是否还有效" @retry="load()" />

    <!-- 骨架屏 -->
    <div v-if="!data && loading" class="kpi-grid">
      <div v-for="i in 4" :key="i" class="kpi-card skeleton">
        <ElSkeleton :rows="3" animated />
      </div>
    </div>

    <!-- KPI 核心指标卡片矩阵 -->
    <template v-else-if="data">
      <div class="kpi-grid">
        <!-- 卡片 1: 秒开缓存条目 -->
        <div class="kpi-card">
          <div class="kpi-head">
            <span class="kpi-label">高速秒开缓存</span>
            <ElTag size="small" type="success" effect="light">LRU 内存保鲜</ElTag>
          </div>
          <div class="kpi-main">
            <div class="kpi-val">{{ data.cache.size }}</div>
            <div class="kpi-unit">/ {{ data.cache.maxsize }} 条</div>
          </div>
          <div class="kpi-progress">
            <ElProgress :percentage="cachePercent" :stroke-width="6" :show-text="false" color="#4f46e5" />
          </div>
          <div class="kpi-footer">
            <span>命中秒开 {{ data.cache.hits }} 次</span>
            <span class="footer-divider">·</span>
            <span>查源 {{ data.cache.misses }} 次</span>
          </div>
        </div>

        <!-- 卡片 2: 缓存命中率 -->
        <div class="kpi-card">
          <div class="kpi-head">
            <span class="kpi-label">全站缓存命中率</span>
            <ElTag size="small" :type="hitRate(data.cache.hits, data.cache.misses) >= 80 ? 'success' : 'warning'" effect="light">
              {{ hitRate(data.cache.hits, data.cache.misses) >= 80 ? '极佳' : '正常' }}
            </ElTag>
          </div>
          <div class="kpi-main">
            <div class="kpi-val text-indigo">{{ hitRate(data.cache.hits, data.cache.misses) }}</div>
            <div class="kpi-unit">%</div>
          </div>
          <div class="kpi-footer highlight-footer">
            累计节省用户等待约 <strong>{{ (data.cache.hits * 0.8).toFixed(1) }}</strong> 秒
          </div>
        </div>

        <!-- 卡片 3: 并发防击穿保护 -->
        <div class="kpi-card">
          <div class="kpi-head">
            <span class="kpi-label">并发防击穿保护</span>
            <ElTag size="small" type="info" effect="light">SingleFlight</ElTag>
          </div>
          <div class="kpi-main">
            <div class="kpi-val">{{ data.cache.inflight }}</div>
            <div class="kpi-unit">个排队抓取</div>
          </div>
          <div class="kpi-footer">
            多并发相同 Key 自动合并为单次查源
          </div>
        </div>

        <!-- 卡片 4: 主动预热巡检守护 -->
        <div class="kpi-card">
          <div class="kpi-head">
            <span class="kpi-label">主动预热巡检</span>
            <ElTag size="small" :type="data.warmup.enabled ? 'success' : 'info'" effect="light">
              {{ data.warmup.enabled ? (data.warmup.running ? '巡检中' : '守护中') : '未开启' }}
            </ElTag>
          </div>
          <div class="kpi-main">
            <div class="kpi-val" style="font-size: 20px">
              {{ data.warmup.enabled ? (data.warmup.running ? '正在抓取' : '定时保鲜中') : '按需懒加载' }}
            </div>
          </div>
          <div class="kpi-footer">
            <template v-if="data.warmup.last_finished_at">
              {{ data.warmup.last_reason ?? '自动巡检' }} · <TimeAgo :value="data.warmup.last_finished_at" />
              <template v-if="data.warmup.last_seconds">（耗时 {{ data.warmup.last_seconds.toFixed(1) }}s）</template>
            </template>
            <template v-else>当前进程尚未触发定时预热</template>
          </div>
        </div>
      </div>

      <!-- 源健康监控大屏 -->
      <div class="section-header">
        <div>
          <h2 class="section-title">内容源健康与熔断状态</h2>
          <p class="section-desc">实时监控各个采集站点的连通性、错误率及自动熔断保护机制。</p>
        </div>
      </div>

      <div v-if="data.sites?.length" class="sites-health-grid">
        <SourceHealthCard v-for="site in data.sites" :key="site.site" :health="site" />
      </div>
      <EmptyState v-else title="未发现任何内容源" hint="检查 crawler/sites/ 目录下是否存在可用的源驱动脚本" />

      <!-- 上次预热战报表格 -->
      <div class="section-header" style="margin-top: 36px">
        <div>
          <h2 class="section-title">全站预热与保鲜战报</h2>
          <p class="section-desc">记录上次后台预热对各个源站首页与分类的抓取执行成果。</p>
        </div>
      </div>

      <div class="warmup-table-box">
        <ElTable v-if="data.warmup.sites?.length" :data="data.warmup.sites" size="default" max-height="360">
          <ElTableColumn prop="site" label="内容源标识" width="160">
            <template #default="{ row }">
              <span class="site-tag">{{ row.site }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="执行状态" width="120">
            <template #default="{ row }">
              <ElTag :type="row.ok ? 'success' : 'danger'" size="small" effect="light">
                {{ row.ok ? '抓取成功' : '抓取异常' }}
              </ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="home_items" label="首页影视数" width="140" align="center" />
          <ElTableColumn prop="categories" label="分类标签数" width="130" align="center" />
          <ElTableColumn label="抓取耗时" width="120">
            <template #default="{ row }">{{ (row.seconds ?? 0).toFixed(1) }} 秒</template>
          </ElTableColumn>
          <ElTableColumn prop="error" label="异常诊断" min-width="240">
            <template #default="{ row }">
              <span v-if="row.error" class="text-danger">{{ row.error }}</span>
              <span v-else class="text-muted">无异常</span>
            </template>
          </ElTableColumn>
        </ElTable>
        <EmptyState v-else title="尚未执行全站预热" hint="可以在右上角点击「全站缓存刷新」手动发起一轮预热" />
      </div>
    </template>

    <!-- 右下角悬浮智能运维手册按钮 (FAB) -->
    <div class="help-fab-btn" title="查看系统关键指标与架构解析指南" @click="isHelpDocVisible = true">
      <ElIcon :size="16"><Document /></ElIcon>
      <span class="fab-text">指标指南</span>
    </div>

    <!-- 弹出的指标说明与运维指南对话框 -->
    <ElDialog
      v-model="isHelpDocVisible"
      title="系统关键指标说明与运维指南"
      width="680px"
      destroy-on-close
    >
      <div class="help-doc-modal">
        <div class="doc-card">
          <div class="doc-title">高速秒开缓存（条目容量与水位）</div>
          <div class="doc-desc">
            <strong>业务说明</strong>：系统将已抓取的影视首页、分类数据与详情元数据暂存在高速内存中。<br />
            <strong>实际价值</strong>：客户端用户浏览时直接 <strong>0 秒极速出图响应</strong>，彻底摆脱源站网络爬虫的慢速等待。<br />
            <strong>淘汰算法</strong>：达到最大容量配置后，系统依据 LRU（最近最久未使用）算法自动淘汰旧条目，确保内存恒定受控。
          </div>
        </div>

        <div class="doc-card">
          <div class="doc-title">防击穿并发合并保护 (SingleFlight)</div>
          <div class="doc-desc">
            <strong>业务说明</strong>：高并发请求的防击穿保护隔离层。<br />
            <strong>场景案例</strong>：当某热门影视缓存失效或初次上线时，若有 100 位用户同时点开，普通系统会发起 100 次爬虫撞击源站，造成源站封禁或超时；<br />
            <strong>保护原理</strong>：系统自动合并为 <strong>1 次真实源站请求</strong>，其余 99 位请求在内存排队共享这一份结果，保护系统与源站网络。
          </div>
        </div>

        <div class="doc-card">
          <div class="doc-title">主动预热巡检 vs 按需懒加载</div>
          <div class="doc-desc">
            <strong>按需懒加载</strong>：仅当用户打开时现抓，首位访问者需要承担几秒的抓取耗时；<br />
            <strong>主动预热巡检</strong>：后台自动化定时静默全量抓取所有站点的首页推荐片单，保证任何时刻所有用户点开都是秒开体验。
          </div>
        </div>

        <div class="doc-card">
          <div class="doc-title">内容源管理与全局缓存中心的分工界限</div>
          <div class="doc-desc">
            • <strong>「内容源管理」</strong>：卡片化一站式操作，可直接针对单个站点执行“预热首页”并查看该站的精美分类与片单战报，或单独清空该站缓存；<br />
            • <strong>「全局缓存中心」</strong>：专职于全局宏观容量透视、存活 Key 审查、TTL 倒计时与底层反序列化 JSON 结构检视，两者分工清晰，绝无重复操作。
          </div>
        </div>
      </div>

      <template #footer>
        <ElButton type="primary" @click="isHelpDocVisible = false">已了解，关闭指南</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 顶部状态大屏 */
.dash-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 20px;
  padding: 28px 32px;
  background: linear-gradient(135deg, rgba(79, 70, 229, 0.08) 0%, rgba(6, 182, 212, 0.04) 100%);
  border: 1px solid var(--a-border);
  border-radius: var(--a-radius-lg);
  box-shadow: var(--a-shadow-xs);
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px;
  border-radius: 20px;
  background: rgba(79, 70, 229, 0.1);
  border: 1px solid rgba(79, 70, 229, 0.2);
  color: var(--a-brand);
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 8px;
}

.hero-pulse {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--a-brand);
}

.hero-title {
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin: 0 0 6px 0;
  color: var(--a-text);
}

.hero-desc {
  font-size: 13px;
  color: var(--a-text-2);
  margin: 0;
}

.dash-hero-actions {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.wait-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--a-text-2);
  cursor: pointer;
}

/* 告警列表 */
.notices-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.notice-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: var(--a-radius);
  border: 1px solid transparent;
  font-size: 13px;
}

.notice--danger {
  background: var(--a-danger-bg);
  border-color: var(--a-danger-border);
  color: var(--a-danger-text);
}

.notice--warn {
  background: var(--a-warn-bg);
  border-color: var(--a-warn-border);
  color: var(--a-warn-text);
}

.notice--info {
  background: var(--a-bg-subtle);
  border-color: var(--a-border);
  color: var(--a-text-2);
}

/* KPI 核心指标卡片矩阵 */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
}

.kpi-card {
  background: var(--a-card);
  border: 1px solid var(--a-border);
  border-radius: var(--a-radius);
  padding: 20px 22px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  box-shadow: var(--a-shadow-xs);
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--a-shadow-1);
}

.kpi-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.kpi-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--a-text-2);
}

.kpi-main {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.kpi-val {
  font-size: 28px;
  font-weight: 800;
  color: var(--a-text);
  line-height: 1.1;
  font-family: 'JetBrains Mono', monospace;
}

.kpi-val.text-indigo {
  color: var(--a-brand);
}

.kpi-unit {
  font-size: 13px;
  color: var(--a-text-3);
  font-weight: 500;
}

.kpi-progress {
  margin-top: -4px;
}

.kpi-footer {
  font-size: 12px;
  color: var(--a-text-3);
  line-height: 1.5;
  margin-top: auto;
}

.highlight-footer {
  color: var(--a-text-2);
}

.highlight-footer strong {
  color: var(--el-color-success);
}

.footer-divider {
  margin: 0 4px;
}

/* 区域标题 */
.section-header {
  margin-top: 16px;
  margin-bottom: 4px;
}

.section-title {
  font-size: 16px;
  font-weight: 750;
  margin: 0 0 4px 0;
  color: var(--a-text);
}

.section-desc {
  font-size: 12.5px;
  color: var(--a-text-3);
  margin: 0;
}

/* 源健康网格 */
.sites-health-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

/* 预热表格容器 */
.warmup-table-box {
  background: var(--a-card);
  border: 1px solid var(--a-border);
  border-radius: var(--a-radius);
  overflow: hidden;
}

.site-tag {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 600;
  font-size: 13px;
}

.text-danger {
  color: var(--el-color-danger);
  font-size: 12px;
}

.text-muted {
  color: var(--a-text-3);
  font-size: 12px;
}

/* 悬浮指南按钮 (FAB) */
.help-fab-btn {
  position: fixed;
  right: 32px;
  bottom: 32px;
  z-index: 99;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  background: linear-gradient(135deg, var(--a-brand) 0%, #06b6d4 100%);
  color: #ffffff;
  border-radius: 30px;
  box-shadow: 0 6px 20px rgba(79, 70, 229, 0.4);
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  transition: all 0.25s ease;
  user-select: none;
}

.help-fab-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 26px rgba(79, 70, 229, 0.55);
}

.help-doc-modal {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.doc-card {
  background: var(--a-bg-subtle);
  border: 1px solid var(--a-border);
  border-radius: 10px;
  padding: 14px 18px;
}

.doc-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--a-brand);
  margin-bottom: 6px;
}

.doc-desc {
  font-size: 12.5px;
  color: var(--a-text-2);
  line-height: 1.6;
}

.doc-desc strong {
  color: var(--a-text);
}
</style>
