<script setup lang="ts">
import {
  ElButton,
  ElIcon,
  ElInput,
  ElInputNumber,
  ElOption,
  ElSelect,
  ElSwitch,
} from 'element-plus'
import {
  Aim,
  DataAnalysis,
  Film,
  FolderOpened,
  VideoPlay,
} from '@element-plus/icons-vue'
import type { AdminSiteItem } from '@/api/types'

const props = defineProps<{
  sites: AdminSiteItem[]
  form: {
    site: string
    command: 'home' | 'category' | 'detail' | 'play'
    tid: string
    page: number
    vod_id: string
    ep: number
    bypass_cache: boolean
  }
  probing: boolean
}>()

const emit = defineEmits<{
  runProbe: []
  quickPreset: [type: 'home' | 'category' | 'detail_auto' | 'play_auto']
}>()
</script>

<template>
  <div>
    <!-- 顶部控制与源站切换卡片 -->
    <div class="probe-toolbar-card">
      <div class="toolbar-left">
        <span class="toolbar-label">调试目标源：</span>
        <ElSelect v-model="props.form.site" style="width: 240px">
          <ElOption
            v-for="s in props.sites"
            :key="s.key"
            :label="`${s.name} (${s.key})`"
            :value="s.key"
          />
        </ElSelect>
      </div>
      <div class="toolbar-right">
        <ElSwitch v-model="props.form.bypass_cache" active-text="强制穿透源站 (跳过缓存)" />
      </div>
    </div>

    <!-- 「4步全链路体检工作流」卡片矩阵 -->
    <div class="workflow-cards-grid">
      <!-- 步骤 1: 首页推荐 -->
      <div
        class="workflow-card"
        :class="{ 'is-active': props.form.command === 'home' }"
        @click="props.form.command = 'home'"
      >
        <div class="wf-header">
          <span class="wf-badge">步骤 1</span>
          <ElIcon :size="20"><Film /></ElIcon>
        </div>
        <div class="wf-title">首页推荐嗅探</div>
        <div class="wf-desc">提取源站首页骨架与推荐片单</div>
        <div class="wf-btn-box">
          <ElButton
            size="small"
            type="primary"
            :loading="props.probing && props.form.command === 'home'"
            @click.stop="emit('quickPreset', 'home')"
          >
            一键探测首页
          </ElButton>
        </div>
      </div>

      <!-- 步骤 2: 分类提取 -->
      <div
        class="workflow-card"
        :class="{ 'is-active': props.form.command === 'category' }"
        @click="props.form.command = 'category'"
      >
        <div class="wf-header">
          <span class="wf-badge">步骤 2</span>
          <ElIcon :size="20"><FolderOpened /></ElIcon>
        </div>
        <div class="wf-title">分类标签抽样</div>
        <div class="wf-desc">提取所有主分类与二级标签树</div>
        <div class="wf-btn-box">
          <ElButton
            size="small"
            type="primary"
            :loading="props.probing && props.form.command === 'category'"
            @click.stop="emit('quickPreset', 'category')"
          >
            一键提取分类
          </ElButton>
        </div>
      </div>

      <!-- 步骤 3: 详情穿透 -->
      <div
        class="workflow-card"
        :class="{ 'is-active': props.form.command === 'detail' }"
        @click="props.form.command = 'detail'"
      >
        <div class="wf-header">
          <span class="wf-badge">步骤 3</span>
          <ElIcon :size="20"><DataAnalysis /></ElIcon>
        </div>
        <div class="wf-title">详情全量穿透</div>
        <div class="wf-desc">自动抽片提取剧集、线路与简介</div>
        <div class="wf-btn-box">
          <ElButton
            size="small"
            type="primary"
            plain
            :loading="props.probing && props.form.command === 'detail'"
            @click.stop="emit('quickPreset', 'detail_auto')"
          >
            自动抽片测详情
          </ElButton>
        </div>
      </div>

      <!-- 步骤 4: 播放嗅探 -->
      <div
        class="workflow-card"
        :class="{ 'is-active': props.form.command === 'play' }"
        @click="props.form.command = 'play'"
      >
        <div class="wf-header">
          <span class="wf-badge">步骤 4</span>
          <ElIcon :size="20"><VideoPlay /></ElIcon>
        </div>
        <div class="wf-title">视频播放流嗅探</div>
        <div class="wf-desc">解析真实 m3u8 并直接在播放器试播</div>
        <div class="wf-btn-box">
          <ElButton
            size="small"
            type="success"
            :loading="props.probing && props.form.command === 'play'"
            @click.stop="emit('quickPreset', 'play_auto')"
          >
            自动抽片试播
          </ElButton>
        </div>
      </div>
    </div>

    <!-- 可选手填自定义参数栏 -->
    <div
      v-if="props.form.command === 'category' || props.form.command === 'detail' || props.form.command === 'play'"
      class="custom-param-bar"
    >
      <span class="param-tip">自定义参数调试：</span>
      <template v-if="props.form.command === 'category'">
        <span class="param-label">分类 ID (tid):</span>
        <ElInput v-model="props.form.tid" placeholder="留空为全部" size="small" style="width: 140px" />
        <span class="param-label">页码:</span>
        <ElInputNumber v-model="props.form.page" :min="1" :max="999" size="small" style="width: 100px" />
      </template>
      <template v-if="props.form.command === 'detail' || props.form.command === 'play'">
        <span class="param-label">影片 ID (vod_id):</span>
        <ElInput
          v-model="props.form.vod_id"
          placeholder="输入 ID 或点击上方卡片自动抽片"
          size="small"
          style="width: 220px"
        />
      </template>
      <template v-if="props.form.command === 'play'">
        <span class="param-label">集数 (ep):</span>
        <ElInputNumber v-model="props.form.ep" :min="1" :max="9999" size="small" style="width: 90px" />
      </template>
      <ElButton
        type="primary"
        size="small"
        :icon="Aim"
        :loading="props.probing"
        style="margin-left: 12px"
        @click="emit('runProbe')"
      >
        以自定义参数执行
      </ElButton>
    </div>
  </div>
</template>
