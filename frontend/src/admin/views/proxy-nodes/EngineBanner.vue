<script setup lang="ts">
import {
  Cpu,
  Download,
  RefreshRight,
  VideoPause,
  VideoPlay,
} from '@element-plus/icons-vue'
import {
  ElButton,
  ElIcon,
  ElTag,
} from 'element-plus'
import type { ProxyEngineStatusPayload } from '@/api/types'

const props = defineProps<{
  engineStatus: ProxyEngineStatusPayload | null
  engineActionLoading: boolean
}>()

const emit = defineEmits<{
  (e: 'install'): void
  (e: 'start'): void
  (e: 'stop'): void
  (e: 'restart'): void
}>()
</script>

<template>
  <div
    class="engine-banner"
    :class="{
      'engine-banner--running': props.engineStatus?.running,
      'engine-banner--stopped': props.engineStatus && !props.engineStatus.running && props.engineStatus.installed,
      'engine-banner--uninstalled': props.engineStatus && !props.engineStatus.installed,
    }"
  >
    <div class="engine-banner-left">
      <div class="engine-icon-box">
        <ElIcon :size="24"><Cpu /></ElIcon>
      </div>
      <div class="engine-meta">
        <div class="engine-title-row">
          <span class="engine-title">内置 Xray-core 转发守护引擎</span>
          <ElTag
            v-if="props.engineStatus?.running"
            size="small"
            type="success"
            effect="dark"
            class="engine-badge"
          >
            🟢 运行中 (PID {{ props.engineStatus.pid }})
          </ElTag>
          <ElTag
            v-else-if="props.engineStatus?.installed"
            size="small"
            type="info"
            class="engine-badge"
          >
            ⚪ 已停止
          </ElTag>
          <ElTag
            v-else
            size="small"
            type="warning"
            class="engine-badge"
          >
            🟡 未安装内核
          </ElTag>

          <span v-if="props.engineStatus?.version" class="engine-version">
            Xray {{ props.engineStatus.version }}
          </span>
        </div>

        <div class="engine-desc">
          <template v-if="props.engineStatus?.running">
            已成功接管 <b>{{ props.engineStatus.managed_nodes }}</b> 个 VLESS 节点。系统会在本地动态监听独立端口为爬虫采集器提供高速透明中转。
          </template>
          <template v-else-if="props.engineStatus?.installed">
            Xray 内核已就绪，当前处于离线状态。请点击右侧「启动引擎」按钮拉起中转进程。
          </template>
          <template v-else>
            检测到当前服务器尚未安装 Xray-core 独立内核。点击右侧「一键安装」即可自动部署适配您系统的官方二进制文件。
          </template>
        </div>
      </div>
    </div>

    <div class="engine-banner-right">
      <template v-if="!props.engineStatus?.installed">
        <ElButton
          type="primary"
          :icon="Download"
          :loading="props.engineActionLoading"
          @click="emit('install')"
        >
          一键安装 Xray-core
        </ElButton>
      </template>
      <template v-else>
        <ElButton
          v-if="!props.engineStatus.running"
          type="success"
          :icon="VideoPlay"
          :loading="props.engineActionLoading"
          @click="emit('start')"
        >
          启动引擎
        </ElButton>
        <ElButton
          v-else
          type="danger"
          plain
          :icon="VideoPause"
          :loading="props.engineActionLoading"
          @click="emit('stop')"
        >
          停止引擎
        </ElButton>

        <ElButton
          :icon="RefreshRight"
          :loading="props.engineActionLoading"
          @click="emit('restart')"
        >
          重新加载 / 重启
        </ElButton>
      </template>
    </div>
  </div>
</template>
