<script setup lang="ts">
/**
 * 站点管理（内容源）—— 后台真正"动得了源"的地方。
 *
 * 以前源只有真相、没有开关：``crawler/sites/<key>.py`` 存在即存在，
 * 想停掉一个源只能把文件挪走（没有记录、没有回滚、没人知道为什么）。
 * 这个页面把它变成两件可逆的事：**开关**与**顺序**。
 *
 * ### 三个刻意的界面决定
 *
 * 1. **停用要二次确认，启用不要。** 停用会让所有用户端少一个源（正在用它的客户端
 *    下一次请求就会拿到"该源已关闭"），误点代价高；启用只是恢复，没有代价。
 * 2. **顺序是上移/下移，不是拖拽。** 源只有 2~5 个，两个按钮比拖拽更少误解，
 *    而且手机上也能点。每次移动都提交**完整顺序**（后端一次落成一个最终状态）。
 * 3. **"取不到 meta"要显示出来，而不是安静地少一行。** 一个刚上传、还没跑通的源
 *    最需要在这里被看见。
 */
import { ElButton, ElMessage, ElMessageBox, ElSkeleton, ElSwitch, ElTable, ElTableColumn, ElTag, ElTooltip } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

import { describeError } from '@/api/http'
import type { AdminSiteItem, AdminSiteListPayload } from '@/api/types'

import * as api from '../api'
import EmptyState from '../components/EmptyState.vue'
import ErrorState from '../components/ErrorState.vue'
import PageHeader from '../components/PageHeader.vue'
import { type TagType } from '../format'
import { ui } from '../ui'

const data = ref<AdminSiteListPayload | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const busyKey = ref<string | null>(null)

async function load(): Promise<void> {
  loading.value = true
  try {
    data.value = await api.listSites()
    error.value = null
  } catch (err) {
    error.value = describeError(err)
  } finally {
    loading.value = false
  }
}

onMounted(load)

const sites = computed(() => data.value?.sites ?? [])
const isEmpty = computed(() => !loading.value && !error.value && sites.value.length === 0)

// ------------------------------------------------------------------ 健康

const STATE: Record<string, { label: string; tag: TagType }> = {
  closed: { label: '正常', tag: 'success' },
  half_open: { label: '探测中', tag: 'warning' },
  open: { label: '已熔断', tag: 'danger' },
}

function healthState(site: AdminSiteItem): { label: string; tag: TagType } {
  // 没取过 meta 的源 state 也是 closed、failures 也是 0，和"一直正常"长得一样
  if (!site.health.probed) return { label: '未探测', tag: 'info' }
  return STATE[site.health.state] ?? { label: site.health.state, tag: 'info' }
}

// ------------------------------------------------------------------ 开关

async function toggle(site: AdminSiteItem, next: boolean): Promise<void> {
  if (next === site.enabled) return

  if (!next) {
    try {
      await ElMessageBox.confirm(
        `停用 ${site.key}？用户端的站点列表里不再出现它，正在用它的人下一次请求会看到"该源已关闭"。` +
          '（缓存里已有的内容也不再发出，缓存本身不用清。）',
        '停用这个源',
        { type: 'warning', confirmButtonText: '停用', cancelButtonText: '取消' },
      )
    } catch {
      return // 用户取消
    }
  }

  busyKey.value = site.key
  try {
    const result = next ? await api.enableSite(site.key) : await api.disableSite(site.key)
    ElMessage.success(result.message)
    await load()
  } catch (err) {
    ElMessage.error(describeError(err))
  } finally {
    busyKey.value = null
  }
}

// ------------------------------------------------------------------ 顺序

const firstKey = computed(() => sites.value[0]?.key)
const lastKey = computed(() => sites.value[sites.value.length - 1]?.key)

async function move(index: number, delta: number): Promise<void> {
  const keys = sites.value.map((site) => site.key)
  const target = index + delta
  if (target < 0 || target >= keys.length) return

  const swapped = [...keys]
  ;[swapped[index], swapped[target]] = [swapped[target], swapped[index]]

  busyKey.value = keys[index]
  try {
    // 提交**完整顺序**：一次就是一个一致的最终状态
    data.value = await api.orderSites(swapped)
    ElMessage.success('顺序已更新（用户端下次刷新即生效）')
  } catch (err) {
    ElMessage.error(describeError(err))
    await load()
  } finally {
    busyKey.value = null
  }
}
</script>

<template>
  <div class="a-page">
    <PageHeader
      title="站点管理"
      desc="内容源（爬虫）的开关与顺序。停用的源：用户端不显示、内容接口回「已关闭」，且不会再被调用。"
    >
      <template #actions>
        <ElButton size="small" :loading="loading" @click="load">刷新</ElButton>
      </template>
    </PageHeader>

    <ErrorState v-if="error" :message="error" @retry="load" />

    <div v-if="loading && !data" class="a-card skeleton">
      <ElSkeleton :rows="4" animated />
    </div>

    <EmptyState
      v-else-if="isEmpty"
      title="这台机器上还没有任何源"
      hint="源就是 crawler/sites/ 目录下的 .py 文件（文件名即 key）。上传爬虫是下一批要做的功能。"
    />

    <ElTable v-else v-loading="loading" :data="sites" size="small" max-height="calc(100vh - 280px)">
      <ElTableColumn label="顺序" width="104">
        <template #default="{ row, $index }">
          <ElButton
            link
            size="small"
            :disabled="ui.readOnly || row.key === firstKey"
            title="上移"
            @click="move($index, -1)"
          >
            ↑
          </ElButton>
          <ElButton
            link
            size="small"
            :disabled="ui.readOnly || row.key === lastKey"
            title="下移"
            @click="move($index, 1)"
          >
            ↓
          </ElButton>
          <span class="a-muted order">{{ row.sort_order }}</span>
        </template>
      </ElTableColumn>

      <ElTableColumn label="源" min-width="150">
        <template #default="{ row }">
          <span class="a-mono">{{ row.key }}</span>
          <div class="a-muted sub">{{ row.name }}</div>
        </template>
      </ElTableColumn>

      <ElTableColumn label="用户可见" width="110">
        <template #default="{ row }">
          <ElTooltip :content="row.enabled ? '点一下停用（用户端不再显示）' : '点一下恢复'" placement="top">
            <ElSwitch
              :model-value="row.enabled"
              size="small"
              :loading="busyKey === row.key"
              :disabled="ui.readOnly"
              @update:model-value="(value) => toggle(row as AdminSiteItem, Boolean(value))"
            />
          </ElTooltip>
        </template>
      </ElTableColumn>

      <ElTableColumn label="健康" width="130">
        <template #default="{ row }">
          <ElTag :type="healthState(row as AdminSiteItem).tag" size="small" effect="light">
            {{ healthState(row as AdminSiteItem).label }}
          </ElTag>
          <div v-if="row.health.failures" class="a-muted sub">
            连续失败 {{ row.health.failures }}/{{ row.health.fail_threshold }}
          </div>
        </template>
      </ElTableColumn>

      <ElTableColumn label="能力" min-width="220">
        <template #default="{ row }">
          <ElTag v-for="item in row.capabilities" :key="item" size="small" class="cap" effect="plain">
            {{ item }}
          </ElTag>
          <span v-if="!row.capabilities.length" class="a-muted">—</span>
        </template>
      </ElTableColumn>

      <ElTableColumn label="版本" width="150">
        <template #default="{ row }">
          <div>{{ row.version || '—' }}</div>
          <div class="a-muted sub">{{ row.mode }}</div>
        </template>
      </ElTableColumn>

      <ElTableColumn label="异常" min-width="200">
        <template #default="{ row }">
          <span v-if="row.meta_error" class="bad">{{ row.meta_error }}</span>
          <span v-else class="a-muted">—</span>
        </template>
      </ElTableColumn>
    </ElTable>

    <p class="a-note">
      「停用」与「源站坏了」是两件事，所以错误码也是两个：源站坏了是 <span class="a-mono">UPSTREAM_*</span>
      （用户看得到这个源，只是打不开），被停用是 <span class="a-mono">SITE_DISABLED</span>（它根本不该出现）。
      <br />
      停用<strong>不会清缓存</strong>：缓存里已有的内容也不再发出（缓存留着，恢复时立刻可用）。
      <br />
      顺序决定用户端列表的先后，也决定预热的先后 —— 把快的那台放前面。
    </p>
  </div>
</template>

<style scoped>
.skeleton {
  padding: 18px;
}

.sub {
  font-size: 12px;
  margin-top: 2px;
}

.order {
  margin-left: 4px;
  font-size: 11px;
}

.cap {
  margin-right: 4px;
}

.bad {
  color: var(--el-color-danger);
  font-size: 12px;
}
</style>
