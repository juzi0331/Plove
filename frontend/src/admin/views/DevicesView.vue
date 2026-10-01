<script setup lang="ts">
/**
 * 某个激活码用过的设备。
 *
 * ### 这里为什么没有"查看令牌"按钮
 *
 * 设备令牌是客户端凭证（等于密码）。后台只需要能区分"是哪一台"，
 * 所以只显示前 6 位 —— 后端契约里也**根本没有这个字段**。
 *
 * ### 「在线」有两种口径（重设计加的）
 *
 * * **活跃位**（`is_active`）：此刻唯一能看内容的那台 —— 服务端语义；
 * * **最近出现**（`last_seen_at` 在 5 分钟内）：弱在线判定 —— 服务端**不做**离线
 *   超时释放（锁屏/切后台不会改变活跃位），所以光看活跃位会把"锁屏的人"当离线。
 *
 * ### 踢下线和封码的区别（界面上必须让人看见）
 *
 * 踢 = 请它下线，**它还能自己再登回来**；想彻底用不了，要去停用整个码。
 */
import { ElButton, ElLoading, ElMessage, ElMessageBox, ElSkeleton, ElTable, ElTableColumn, ElTag } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const vLoading = ElLoading.directive

import { describeError } from '@/api/http'
import type { DeviceItem, DeviceListPayload } from '@/api/types'

import * as api from '../api'
import EmptyState from '../components/EmptyState.vue'
import ErrorState from '../components/ErrorState.vue'
import PageHeader from '../components/PageHeader.vue'
import TimeAgo from '../components/TimeAgo.vue'
import { type TagType } from '../format'
import { ui } from '../ui'

const props = defineProps<{ codeId: string }>()

const router = useRouter()
const codeId = Number(props.codeId)

const data = ref<DeviceListPayload | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

async function load(): Promise<void> {
  loading.value = true
  try {
    data.value = await api.listDevices(codeId)
    error.value = null
  } catch (err) {
    error.value = describeError(err)
  } finally {
    loading.value = false
  }
}

onMounted(load)

const isEmpty = computed(() => !loading.value && !error.value && (data.value?.devices?.length ?? 0) === 0)

/** 最近 5 分钟内出现过 → 算"最近活跃"（弱在线，不依赖活跃位） */
const RECENT_MS = 5 * 60 * 1000

function onlineState(device: DeviceItem): { label: string; tag: TagType } {
  if (device.is_active) return { label: '活跃位', tag: 'success' }
  const seen = new Date(device.last_seen_at).getTime()
  if (!Number.isNaN(seen) && Date.now() - seen < RECENT_MS) return { label: '最近活跃', tag: 'info' }
  return { label: '离线', tag: 'info' }
}

async function kick(device: DeviceItem): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `把「${device.name || '未命名设备'}」踢下线？它正在播的话会立刻停，并显示"已在别的设备上使用"。` +
        '注意：它还能用同一个码自己登回来 —— 想彻底禁掉要停用整个激活码。',
      '踢下线',
      { type: 'warning', confirmButtonText: '踢下线', cancelButtonText: '取消' },
    )
  } catch {
    return
  }

  try {
    const result = await api.kickDevice(device.id)
    ElMessage.success(result.message)
    await load()
  } catch (err) {
    ElMessage.error(describeError(err))
  }
}

function back(): void {
  void router.push({ name: 'admin-codes' })
}
</script>

<template>
  <div class="a-page">
    <PageHeader title="设备" :desc="`激活码 #${codeId} 用过的设备 · 令牌永远只显示前 6 位`">
      <template #actions>
        <ElButton size="small" @click="back">← 返回激活码</ElButton>
        <ElButton size="small" :loading="loading" @click="load">刷新</ElButton>
      </template>
    </PageHeader>

    <ErrorState v-if="error" :message="error" @retry="load" />

    <div v-if="loading && !data" class="a-card skeleton">
      <ElSkeleton :rows="4" animated />
    </div>

    <EmptyState
      v-else-if="isEmpty"
      title="这个码还没有任何设备"
      hint="用户激活成功之后，这里会出现它的设备记录（令牌只给前 6 位）"
    />

    <ElTable v-else v-loading="loading" :data="data?.devices ?? []" size="small" max-height="calc(100vh - 280px)">
      <ElTableColumn prop="name" label="设备名" min-width="150" show-overflow-tooltip>
        <template #default="{ row }">{{ row.name || '未命名设备' }}</template>
      </ElTableColumn>
      <ElTableColumn label="令牌" width="130">
        <!-- 只有掩码。**契约里根本没有明文令牌这个字段**，见本文件顶部说明。 -->
        <template #default="{ row }">
          <span class="a-mono">{{ row.token_prefix }}…</span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="状态" width="120">
        <template #default="{ row }">
          <ElTag :type="onlineState(row as DeviceItem).tag" size="small" effect="light">
            {{ onlineState(row as DeviceItem).label }}
          </ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn label="首次激活" width="140">
        <template #default="{ row }"><TimeAgo :value="row.created_at" /></template>
      </ElTableColumn>
      <ElTableColumn label="最后出现" width="140">
        <template #default="{ row }"><TimeAgo :value="row.last_seen_at" /></template>
      </ElTableColumn>
      <ElTableColumn label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <ElButton
            v-if="row.is_active"
            link
            type="danger"
            size="small"
            :disabled="ui.readOnly"
            @click="kick(row as DeviceItem)"
          >
            踢下线
          </ElButton>
          <span v-else class="a-muted">—</span>
        </template>
      </ElTableColumn>
    </ElTable>

    <p class="a-note">
      「活跃位」= 此刻唯一能看内容的那台。服务端<strong>不做离线超时释放</strong> ——
      锁屏、切后台都不会改变它，只有人主动抢或你在这里踢。
      <br />
      被踢的设备<strong>还能自己抢回来</strong>（用户端会提示）；想彻底禁掉，要停用整个激活码。
    </p>
  </div>
</template>

<style scoped>
.skeleton {
  padding: 18px;
}
</style>
