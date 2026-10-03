<script setup lang="ts">
/**
 * 总览。**这个页面的存在理由只有一个：解释"为什么这个源没内容了"。**
 *
 * 重设计（第一批）做了四件事：
 * 1. **告警横幅**（A1）—— 熔断 / 预热失败 / TTL 配成 0 / 预热没开，打开就能看见；
 * 2. **统计卡**（原来的四个小卡片）—— 数字变大、层级拉开；
 * 3. **源健康卡片**（A2）—— 原来是表格，现在一眼扫过，冷却倒计时自己跳；
 * 4. **骨架屏 / 空状态 / 错误态** —— "在加载"和"坏了"不再长得一样。
 *
 * 自动刷新的开关与间隔在顶栏（`ui.ts` 里），本页只是执行者。
 */
import { ElButton, ElMessage, ElSkeleton, ElSwitch, ElTable, ElTableColumn, ElTag } from 'element-plus'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { describeError } from '@/api/http'
import type { AdminStatusPayload } from '@/api/types'

import * as api from '../api'
import EmptyState from '../components/EmptyState.vue'
import ErrorState from '../components/ErrorState.vue'
import PageHeader from '../components/PageHeader.vue'
import SourceHealthCard from '../components/SourceHealthCard.vue'
import StatCard from '../components/StatCard.vue'
import TimeAgo from '../components/TimeAgo.vue'
import { hitRate } from '../format'
import { ui } from '../ui'

const data = ref<AdminStatusPayload | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const refreshing = ref(false)
const waitForWarmup = ref(false)

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

/** 自动刷新跟着顶栏的设置走：间隔改了要重建定时器 */
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

// ------------------------------------------------------------------ 告警

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
    list.push({ level: 'info', text: '主动预热未开启：内容只在有人访问时抓取，缓存过期由下一个来访者承担' })
  }

  return list
})
</script>

<template>
  <div class="a-page">
      <PageHeader title="总览" desc="缓存、预热、每个源的健康 —— 排查「这个源为什么没内容」时缺一不可。">
        <template #actions>
          <label class="wait">
            等待完成
            <ElSwitch v-model="waitForWarmup" size="small" />
          </label>
          <ElButton size="small" @click="load()">立即刷新</ElButton>
          <ElButton type="primary" size="small" :loading="refreshing" @click="refreshCache">
            刷新缓存
          </ElButton>
        </template>
      </PageHeader>

      <!-- 告警横幅（A1）：打开页面就能看见，不用自己去表里找 -->
      <div v-if="notices.length" class="notices">
        <div v-for="(notice, index) in notices" :key="index" class="notice" :class="`notice--${notice.level}`">
          <span class="notice__dot" />
          {{ notice.text }}
        </div>
      </div>

      <ErrorState v-if="error" :message="error" hint="如果一直失败，检查后端进程与令牌是否还有效" @retry="load()" />

      <!-- 首屏加载：骨架屏，而不是白屏一闪 -->
      <div v-if="!data && loading" class="a-grid">
        <div v-for="i in 4" :key="i" class="a-card skeleton-card">
          <ElSkeleton :rows="2" animated />
        </div>
      </div>

      <template v-else-if="data">
        <div class="a-grid">
          <StatCard label="环境" :value="data.env" foot="来自后端 PLOVE_ENV" />
          <StatCard
            label="缓存条目"
            :value="data.cache.size"
            :unit="`/ ${data.cache.maxsize}`"
            :foot="`命中 ${data.cache.hits} · 未命中 ${data.cache.misses}`"
          />
          <StatCard
            label="缓存命中率"
            :value="hitRate(data.cache.hits, data.cache.misses)"
            unit="%"
            :tone="hitRate(data.cache.hits, data.cache.misses) >= 80 ? 'good' : 'default'"
            foot="进程启动以来的累计值"
          />
          <StatCard
            label="合并中的请求"
            :value="data.cache.inflight"
            foot="同一 key 的并发请求被合成一次抓取"
          />
          <StatCard
            label="主动预热"
            :value="data.warmup.enabled ? (data.warmup.running ? '正在跑' : '已开启') : '未开启'"
            :tone="data.warmup.enabled ? 'good' : 'warn'"
          >
            <template #foot>
              <template v-if="data.warmup.last_finished_at">
                {{ data.warmup.last_reason ?? '—' }} · <TimeAgo :value="data.warmup.last_finished_at" />
                <template v-if="data.warmup.last_seconds">（{{ data.warmup.last_seconds.toFixed(1) }}s）</template>
              </template>
              <template v-else>这个进程还没跑过预热</template>
            </template>
          </StatCard>
        </div>

        <h2 class="a-section">源的健康</h2>
        <div v-if="data.sites?.length" class="a-grid">
          <SourceHealthCard v-for="site in data.sites" :key="site.site" :health="site" />
        </div>
        <EmptyState v-else title="没有发现任何源" hint="检查 crawler/sites/ 目录下有没有可用的源脚本" />

      <h2 class="a-section">上次预热的结果</h2>
        <ElTable v-if="data.warmup.sites?.length" :data="data.warmup.sites" size="small" max-height="360">
          <ElTableColumn prop="site" label="源" width="120" />
          <ElTableColumn label="结果" width="100">
            <template #default="{ row }">
              <ElTag :type="row.ok ? 'success' : 'danger'" size="small" effect="light">
                {{ row.ok ? '成功' : '失败' }}
              </ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="home_items" label="首页条数" width="110" />
          <ElTableColumn prop="categories" label="分类数" width="100" />
          <ElTableColumn label="耗时" width="100">
            <template #default="{ row }">{{ (row.seconds ?? 0).toFixed(1) }}s</template>
          </ElTableColumn>
          <ElTableColumn prop="error" label="错误" min-width="220" />
        </ElTable>
        <EmptyState v-else title="这个进程还没跑过预热" hint="可以在右上角点「刷新缓存」手动跑一轮" />
      </template>
    </div>
  </template>

<style scoped>
.notices {
  display: grid;
  gap: 8px;
  margin-bottom: 16px;
}

.notice {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border: 1px solid var(--a-border);
  border-radius: var(--a-radius-sm);
  background: var(--a-card);
  font-size: 12.5px;
}

.notice__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--a-text-3);
  flex: 0 0 auto;
}

.notice--danger {
  border-color: var(--a-danger-border);
  background: var(--a-danger-bg);
}

.notice--danger .notice__dot {
  background: var(--el-color-danger);
}

.notice--warn {
  border-color: var(--a-warn-border);
  background: var(--a-warn-bg);
}

.notice--warn .notice__dot {
  background: var(--el-color-warning);
}

.skeleton-card {
  padding: 16px;
}

.wait {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--a-text-2);
  font-size: 12.5px;
}
</style>
