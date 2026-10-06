<script setup lang="ts">
/**
 * 品牌与体验编排中心 (Experience Center)：
 * 1. 顶部现代化状态大屏 (Dash Hero) 与运行指针状态；
 * 2. 5大核心指标透明透视卡片矩阵 (Brand, Tokens, Sections, Player, Releases)；
 * 3. 品牌标识与未激活落地页引导文案卡片；
 * 4. 主题设计与色彩视觉 Token 卡片（含海报比例、圆角、调色板预设）；
 * 5. 播放器偏好与交互控制卡片；
 * 6. 首页动态区块编排卡片（支持 Hero、Video Rail、Notice 等拖拽式排序与参数配置）；
 * 7. 版本快照历史与单向单调递增一键回滚表格；
 * 8. 所见即所得实时模拟沙盒弹窗（Live Visual Sandbox）。
 */

import {
  ElButton,
  ElCard,
  ElColorPicker,
  ElDialog,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElRadioButton,
  ElRadioGroup,
  ElSelect,
  ElSlider,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus'
import {
  Brush,
  Clock,
  Document,
  FolderAdd,
  Grid,
  MagicStick,
  Monitor,
  Picture,
  Refresh,
  Switch,
  Top,
  VideoPlay,
  View,
} from '@element-plus/icons-vue'
import { computed, onMounted, ref } from 'vue'

import {
  getExperienceDraft,
  getExperienceReleases,
  getPreviewBootstrap,
  getPreviewPage,
  publishExperienceRelease,
  rollbackExperienceRelease,
  updateExperienceDraft,
} from '@/admin/api'
import { ui } from '@/admin/ui'
import type {
  ClientBootstrapPayload,
  ExperienceDraftPayload,
  ExperienceReleaseItem,
  PageViewModel,
  SectionDefinition,
} from '@/api/types'

const loading = ref(false)
const saving = ref(false)
const publishing = ref(false)
const rollingBack = ref(false)

const DEFAULT_LANDING_TEXT: Record<string, string> = {
  landing_title: '大家都在聊的人氣作品',
  landing_subtitle: '隨時隨地，隨心暢看海量超清影視。',
  landing_lead: '準備開始觀賞了嗎？請輸入您的激活碼，開啟專屬私人影院。',
  landing_input_placeholder: '激活碼地址 (例如: PLV-XXXX-XXXX)',
  landing_button_text: '開始使用',
}

// 当前编辑的草稿数据
const draft = ref<ExperienceDraftPayload>({
  draft_id: 'default',
  revision: 1,
  updated_at: '',
  updated_by: 'admin',
  brand: {
    name: 'Plove',
    logo_url: '',
  },
  text: { ...DEFAULT_LANDING_TEXT },
  theme: {
    color: {
      background: '#141414',
      surface: '#202020',
      primary: '#E50914',
      text: '#FFFFFF',
      muted: '#B8B8B8',
      border: '#2A2A2A',
      danger: '#E50914',
    },
    typography: {
      family: 'system',
      body_px: 15,
      title_px: 26,
    },
    layout: {
      max_width_px: 1440,
      page_padding_px: 16,
      gap_px: 14,
    },
    card: {
      aspect_ratio: '16:9',
      radius_px: 6,
      image_fit: 'cover',
    },
    motion: {
      preset: 'subtle',
      duration_ms: 200,
    },
  },
  player_defaults: {
    auto_next: true,
    auto_next_delay_seconds: 5,
    default_rate: 1.0,
    allowed_rates: [0.75, 1.0, 1.25, 1.5, 2.0],
    hud_hide_after_ms: 3500,
  },
  pages: {
    home: {
      id: 'home',
      title: '首页',
      sections: [],
    },
  },
})

// 发布历史
const releases = ref<ExperienceReleaseItem[]>([])

// 活跃快照指针
const activeRelease = computed<ExperienceReleaseItem | undefined>(() => {
  return releases.value.find((r) => r.is_active)
})

// 首页区块快捷计算与同步
const homeSections = computed<SectionDefinition[]>({
  get: () => {
    if (!draft.value.pages) draft.value.pages = {}
    if (!draft.value.pages.home) {
      draft.value.pages.home = { id: 'home', title: '首页', sections: [] }
    }
    if (!draft.value.pages.home.sections) {
      draft.value.pages.home.sections = []
    }
    return draft.value.pages.home.sections
  },
  set: (val: SectionDefinition[]) => {
    if (!draft.value.pages) draft.value.pages = {}
    if (!draft.value.pages.home) {
      draft.value.pages.home = { id: 'home', title: '首页', sections: [] }
    }
    draft.value.pages.home.sections = val
  },
})

// 统计各类型区块数量
const heroCount = computed(() => homeSections.value.filter((s) => s.component === 'hero').length)
const railCount = computed(() => homeSections.value.filter((s) => s.component === 'video_rail').length)
const noticeCount = computed(() => homeSections.value.filter((s) => s.component === 'notice').length)

// 实时预览抽屉/弹窗状态
const previewVisible = ref(false)
const previewLoading = ref(false)
const previewMode = ref<'home' | 'landing'>('home')
const previewBootstrapData = ref<ClientBootstrapPayload | null>(null)
const previewPageData = ref<PageViewModel | null>(null)

async function fetchDraft(): Promise<void> {
  loading.value = true
  try {
    const res = await getExperienceDraft('default')
    draft.value = {
      ...res,
      brand: {
        name: 'Plove',
        logo_url: '',
        ...(res.brand || {}),
      },
      text: {
        ...DEFAULT_LANDING_TEXT,
        ...(res.text || {}),
      },
      theme: {
        color: {
          background: '#141414',
          surface: '#202020',
          primary: '#E50914',
          text: '#FFFFFF',
          muted: '#B8B8B8',
          border: '#2A2A2A',
          danger: '#E50914',
          ...(res.theme?.color || {}),
        },
        typography: {
          family: 'system',
          body_px: 15,
          title_px: 26,
          ...(res.theme?.typography || {}),
        },
        layout: {
          max_width_px: 1440,
          page_padding_px: 16,
          gap_px: 14,
          ...(res.theme?.layout || {}),
        },
        card: {
          aspect_ratio: '16:9',
          radius_px: 6,
          image_fit: 'cover',
          ...(res.theme?.card || {}),
        },
        motion: {
          preset: 'subtle',
          duration_ms: 200,
          ...(res.theme?.motion || {}),
        },
      },
      player_defaults: {
        auto_next: true,
        auto_next_delay_seconds: 5,
        default_rate: 1.0,
        allowed_rates: [0.75, 1.0, 1.25, 1.5, 2.0],
        hud_hide_after_ms: 3500,
        ...(res.player_defaults || {}),
      },
    }
  } catch (err: unknown) {
    ElMessage.error(err instanceof Error ? err.message : '获取草稿失败')
  } finally {
    loading.value = false
  }
}

async function fetchReleases(): Promise<void> {
  try {
    releases.value = await getExperienceReleases(50)
  } catch (err: unknown) {
    ElMessage.error(err instanceof Error ? err.message : '获取发布历史失败')
  }
}

async function handleSaveDraft(): Promise<void> {
  if (ui.readOnly) {
    ElMessage.warning('只读保护模式已开启，禁止修改草稿')
    return
  }
  saving.value = true
  try {
    const res = await updateExperienceDraft('default', {
      revision: draft.value.revision,
      brand: draft.value.brand,
      theme: draft.value.theme,
      text: draft.value.text,
      navigation: draft.value.navigation,
      pages: draft.value.pages,
      player_defaults: draft.value.player_defaults,
    })
    draft.value.revision = res.revision
    ElMessage.success(`草稿保存成功（修订版本号：r${res.revision}）`)
  } catch (err: unknown) {
    ElMessage.error(err instanceof Error ? err.message : '保存草稿失败，可能已被其他管理员修改')
    void fetchDraft()
  } finally {
    saving.value = false
  }
}

async function handleOpenPreview(mode: 'home' | 'landing' = 'home'): Promise<void> {
  previewMode.value = mode
  previewLoading.value = true
  previewVisible.value = true
  try {
    const [b, p] = await Promise.all([
      getPreviewBootstrap('default'),
      getPreviewPage('home', 'default'),
    ])
    previewBootstrapData.value = b
    previewPageData.value = p
  } catch (err: unknown) {
    ElMessage.error(err instanceof Error ? err.message : '加载沙盒预览失败')
  } finally {
    previewLoading.value = false
  }
}

async function handlePublish(): Promise<void> {
  if (ui.readOnly) {
    ElMessage.warning('只读保护模式已开启，禁止发布版本')
    return
  }
  try {
    const { value: note } = await ElMessageBox.prompt('请输入本次发布的变更日志 / 说明：', '正式发布上线', {
      confirmButtonText: '立即发布',
      cancelButtonText: '取消',
      inputPlaceholder: '例如：升级新春红色主题并更新首页推荐楼层',
      inputValue: `版本更新 (r${draft.value.revision})`,
    })

    publishing.value = true
    const res = await publishExperienceRelease({
      draft_id: 'default',
      note: note || undefined,
    })
    ElMessage.success(`🎉 成功发布版本 ${res.release_id} (修订号 r${res.revision})！已连线用户将在 30 秒内自动更新。`)
    await fetchDraft()
    await fetchReleases()
  } catch (err: unknown) {
    if (err !== 'cancel') {
      ElMessage.error(err instanceof Error ? err.message : '发布失败')
    }
  } finally {
    publishing.value = false
  }
}

async function handleRollback(rel: ExperienceReleaseItem): Promise<void> {
  if (ui.readOnly) {
    ElMessage.warning('只读保护模式已开启，禁止回滚版本')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定要将前台体验即刻回滚至历史版本 ${rel.release_id} (r${rel.revision}) 吗？\n回滚将单调生成新修订号并立即推送全端生效。`,
      '版本回滚确认',
      {
        confirmButtonText: '确认回滚',
        cancelButtonText: '放弃',
        type: 'warning',
      },
    )

    rollingBack.value = true
    const res = await rollbackExperienceRelease(rel.release_id, {
      note: `回滚至历史版本 ${rel.release_id} (原 r${rel.revision})`,
    })
    ElMessage.success(`已成功回滚至目标快照！新生效版本 ${res.release_id} (新修订号 r${res.revision})`)
    await fetchDraft()
    await fetchReleases()
  } catch (err: unknown) {
    if (err !== 'cancel') {
      ElMessage.error(err instanceof Error ? err.message : '回滚失败')
    }
  } finally {
    rollingBack.value = false
  }
}

// 区块操作
function addSection(type: string): void {
  const count = homeSections.value.length + 1
  if (type === 'hero') {
    homeSections.value.push({
      id: `hero_${Date.now().toString(36)}`,
      component: 'hero',
      component_version: 1,
      style: { density: 'normal' },
      props: {
        title: '全新大片火热开播',
        subtitle: '全网超清多线路零缓冲极速体验',
        backdrop_url: '',
        cta_text: '立即播放',
      },
    })
  } else if (type === 'video_rail') {
    homeSections.value.push({
      id: `rail_${Date.now().toString(36)}`,
      component: 'video_rail',
      component_version: 1,
      style: { card_variant: 'standard' },
      props: {
        title: `热门推荐分类 ${count}`,
        category_id: '',
        limit: 10,
      },
    })
  } else if (type === 'notice') {
    homeSections.value.push({
      id: `notice_${Date.now().toString(36)}`,
      component: 'notice',
      component_version: 1,
      style: { level: 'info' },
      props: {
        text: '欢迎来到全新体验版 Plove 流媒体大厅！',
      },
    })
  }
}

function moveSection(index: number, direction: 'up' | 'down'): void {
  const target = direction === 'up' ? index - 1 : index + 1
  if (target < 0 || target >= homeSections.value.length) return
  const item = homeSections.value.splice(index, 1)[0]
  homeSections.value.splice(target, 0, item)
}

function removeSection(index: number): void {
  homeSections.value.splice(index, 1)
}

function applyDefaultSections(): void {
  homeSections.value = [
    {
      id: 'hero_featured',
      component: 'hero',
      component_version: 1,
      style: { density: 'normal' },
      props: {
        title: '院线重磅巨献',
        subtitle: '全站免翻直连，4K HDR 臻彩杜比环绕音效',
        backdrop_url: '',
        cta_text: '立即开播',
      },
    },
    {
      id: 'rail_hot',
      component: 'video_rail',
      component_version: 1,
      style: { card_variant: 'standard' },
      props: {
        title: '热播电视剧榜单',
        category_id: '1',
        limit: 10,
      },
    },
    {
      id: 'rail_movies',
      component: 'video_rail',
      component_version: 1,
      style: { card_variant: 'standard' },
      props: {
        title: '高分院线大片',
        category_id: '2',
        limit: 10,
      },
    },
  ]
  ElMessage.success('已载入经典热门推荐楼层编排模板！')
}

// 调色板预设
const themePresets = [
  {
    name: '经典暗黑 (Netflix)',
    bg: '#141414',
    surface: '#202020',
    primary: '#E50914',
    text: '#FFFFFF',
    muted: '#B8B8B8',
    border: '#2A2A2A',
  },
  {
    name: '午夜深蓝 (Midnight)',
    bg: '#0B0F19',
    surface: '#111827',
    primary: '#3B82F6',
    text: '#F9FAFB',
    muted: '#9CA3AF',
    border: '#1F2937',
  },
  {
    name: '翡翠绿野 (Emerald)',
    bg: '#061E14',
    surface: '#0B2E21',
    primary: '#10B981',
    text: '#F0FDF4',
    muted: '#6EE7B7',
    border: '#14532D',
  },
  {
    name: '赛博霓虹 (Cyber)',
    bg: '#120E1F',
    surface: '#1A142C',
    primary: '#A855F7',
    text: '#FAF5FF',
    muted: '#C084FC',
    border: '#2E1065',
  },
]

function applyThemePreset(p: typeof themePresets[0]): void {
  if (!draft.value.theme) return
  draft.value.theme.color = {
    ...draft.value.theme.color,
    background: p.bg,
    surface: p.surface,
    primary: p.primary,
    text: p.text,
    muted: p.muted,
    border: p.border,
  }
  ElMessage.success(`已应用「${p.name}」色彩主题`)
}

function asProps(sec: SectionDefinition | { props?: Record<string, unknown> } | null | undefined): Record<string, any> {
  if (!sec) return {}
  if (!sec.props) {
    sec.props = {}
  }
  return sec.props as Record<string, any>
}

onMounted(() => {
  void fetchDraft()
  void fetchReleases()
})
</script>

<template>
  <div class="experience-page">
    <!-- 1. 顶部状态大屏 (统一样式标准) -->
    <div class="dash-hero">
      <div class="dash-hero-info">
        <div class="hero-badge">
          <span class="hero-pulse" :class="{ 'is-busy': saving || publishing }" />
          <span>{{ activeRelease ? `生产指针活跃 (r${activeRelease.revision})` : '体验中枢运行就绪' }}</span>
        </div>
        <h1 class="hero-title">品牌与体验中心</h1>
        <p class="hero-desc">
          统筹管理前台全站品牌标识、未激活落地页引导文案、主题与色彩视觉 Token、首页瀑布流动态区块编排及播放器偏好。配置采用乐观并发，支持所见即所得沙盒预览，发布后全网客户端 30 秒无感热更新生效。
        </p>
      </div>

      <div class="dash-hero-actions">
        <ElTag
          :type="activeRelease ? 'success' : 'info'"
          effect="light"
          size="default"
          style="font-weight: 600;"
        >
          ● 当前草稿版本: r{{ draft.revision }}
        </ElTag>

        <ElButton
          size="default"
          :icon="Refresh"
          :loading="loading"
          @click="() => { fetchDraft(); fetchReleases(); }"
        >
          刷新状态
        </ElButton>

        <ElButton
          size="default"
          :icon="View"
          @click="handleOpenPreview('home')"
        >
          沙盒实时预览
        </ElButton>

        <ElButton
          type="primary"
          size="default"
          :icon="Document"
          :loading="saving"
          :disabled="ui.readOnly"
          @click="handleSaveDraft"
        >
          保存草稿
        </ElButton>

        <ElButton
          type="danger"
          size="default"
          :icon="Top"
          :loading="publishing"
          :disabled="ui.readOnly"
          @click="handlePublish"
        >
          发布上线
        </ElButton>
      </div>
    </div>

    <!-- 2. KPI 核心指标透视矩阵微卡 -->
    <div class="exp-kpi-grid">
      <div class="exp-kpi-card">
        <span class="exp-kpi-label">站点品牌标识</span>
        <div class="exp-kpi-val">
          <span>{{ draft.brand?.name || 'Plove' }}</span>
          <ElTag size="small" :type="draft.brand?.logo_url ? 'primary' : 'info'">
            {{ draft.brand?.logo_url ? '图片 Logo' : '文字 Logo' }}
          </ElTag>
        </div>
        <span class="exp-kpi-desc">全站标题与前台导航品牌</span>
      </div>

      <div class="exp-kpi-card">
        <span class="exp-kpi-label">卡片与排版</span>
        <div class="exp-kpi-val mono">
          <span>{{ draft.theme?.card?.aspect_ratio || '16:9' }}</span>
          <span style="font-size: 13px; color: #64748b;">{{ draft.theme?.card?.radius_px ?? 6 }}px</span>
        </div>
        <span class="exp-kpi-desc">字体族: {{ draft.theme?.typography?.family || 'system' }}</span>
      </div>

      <div class="exp-kpi-card">
        <span class="exp-kpi-label">首页受控楼层</span>
        <div class="exp-kpi-val mono">
          <span>{{ homeSections.length }} <small style="font-size: 12px; font-weight: normal;">个楼层</small></span>
        </div>
        <span class="exp-kpi-desc">横幅 {{ heroCount }} · 滑轨 {{ railCount }} · 公告 {{ noticeCount }}</span>
      </div>

      <div class="exp-kpi-card">
        <span class="exp-kpi-label">播放器偏好</span>
        <div class="exp-kpi-val">
          <ElTag size="small" :type="draft.player_defaults?.auto_next ? 'success' : 'info'">
            {{ draft.player_defaults?.auto_next ? '自动连播' : '手动播下集' }}
          </ElTag>
          <span style="font-size: 13px;">{{ draft.player_defaults?.default_rate }}x</span>
        </div>
        <span class="exp-kpi-desc">切集倒计时 {{ draft.player_defaults?.auto_next_delay_seconds }} 秒</span>
      </div>

      <div class="exp-kpi-card">
        <span class="exp-kpi-label">版本快照指针</span>
        <div class="exp-kpi-val mono">
          <span style="color: #10b981;">r{{ activeRelease?.revision ?? draft.revision }}</span>
          <ElTag size="small" type="success" effect="plain">{{ releases.length }} 个快照</ElTag>
        </div>
        <span class="exp-kpi-desc">
          {{ draft.updated_at ? `上次保存: ${draft.updated_at.slice(0, 16)}` : '配置即时热更新' }}
        </span>
      </div>
    </div>

    <!-- 3. 核心板块卡片矩阵 (全卡片化设计) -->
    <div class="cards-grid">
      <!-- 卡片 1: 品牌与落地页文案 -->
      <ElCard shadow="hover" class="module-card">
        <div class="card-top-bar">
          <div class="card-title-group">
            <div class="card-icon-box icon-box--primary">
              <ElIcon :size="20"><Monitor /></ElIcon>
            </div>
            <div>
              <div class="card-title">品牌标识与落地页引导文案</div>
              <div class="card-subtitle">控制全站网页标题 (document.title)、Logo 及未激活落地页文案</div>
            </div>
          </div>
          <ElTag type="primary" effect="dark" class="status-tag">
            {{ draft.brand?.name || 'Plove' }} 品牌
          </ElTag>
        </div>

        <div class="card-body-section">
          <ElForm label-width="110px" label-position="left">
            <ElFormItem label="站点名称">
              <ElInput v-model="draft.brand!.name" placeholder="Plove" />
              <div class="pill-hint">
                控制全站网页标题、浏览器标签页及手机任务栏显示名称
              </div>
            </ElFormItem>
            <ElFormItem label="品牌 Logo URL">
              <ElInput v-model="draft.brand!.logo_url" placeholder="留空则显示优雅纯文本 Logo" clearable>
                <template #prefix>
                  <ElIcon><Picture /></ElIcon>
                </template>
              </ElInput>
              <div class="pill-hint">
                支持直接填写网络图片地址或图床地址，留空将自动渲染文字版徽章
              </div>
            </ElFormItem>
          </ElForm>

          <!-- 落地页引导文案组 -->
          <div class="info-pill-grid">
            <div class="info-pill-item pill-full">
              <span class="pill-label">未激活落地页 (Landing Page) 引导文案设置</span>
            </div>

            <div class="info-pill-item pill-full">
              <span class="pill-label">首屏大标题</span>
              <ElInput
                v-model="draft.text!['landing_title']"
                placeholder="大家都在聊的人氣作品"
              />
            </div>

            <div class="info-pill-item pill-full">
              <span class="pill-label">首屏副标题</span>
              <ElInput
                v-model="draft.text!['landing_subtitle']"
                placeholder="隨時隨地，隨心暢看海量超清影視。"
              />
            </div>

            <div class="info-pill-item pill-full">
              <span class="pill-label">引导提示语 (Lead)</span>
              <ElInput
                v-model="draft.text!['landing_lead']"
                type="textarea"
                :rows="2"
                placeholder="準備開始觀賞了嗎？請輸入您的激活碼，開啟專屬私人影院。"
              />
            </div>

            <div class="info-pill-item">
              <span class="pill-label">输入框提示文字</span>
              <ElInput
                v-model="draft.text!['landing_input_placeholder']"
                placeholder="激活碼地址 (例如: PLV-XXXX-XXXX)"
              />
            </div>

            <div class="info-pill-item">
              <span class="pill-label">激活按钮文字</span>
              <ElInput
                v-model="draft.text!['landing_button_text']"
                placeholder="開始使用"
              />
            </div>
          </div>
        </div>

        <div class="card-footer-bar">
          <div class="footer-hint">
            <span>✨ 客户端切回前台或每 30 秒轮询无感拉取最新文案</span>
          </div>
          <div style="display: flex; gap: 8px;">
            <ElButton size="small" :icon="View" @click="handleOpenPreview('landing')">
              预览落地页
            </ElButton>
            <ElButton
              type="primary"
              size="small"
              :loading="saving"
              :disabled="ui.readOnly"
              @click="handleSaveDraft"
            >
              保存草稿
            </ElButton>
          </div>
        </div>
      </ElCard>

      <!-- 卡片 2: 主题设计与色彩视觉 Token -->
      <ElCard shadow="hover" class="module-card">
        <div class="card-top-bar">
          <div class="card-title-group">
            <div class="card-icon-box icon-box--purple">
              <ElIcon :size="20"><Brush /></ElIcon>
            </div>
            <div>
              <div class="card-title">主题设计与色彩视觉 Token</div>
              <div class="card-subtitle">海报卡片比例、圆角、字体预设与全局调色板</div>
            </div>
          </div>
          <ElTag type="warning" effect="dark" class="status-tag">
            {{ draft.theme?.card?.aspect_ratio }} · {{ draft.theme?.card?.radius_px }}px
          </ElTag>
        </div>

        <div class="card-body-section">
          <!-- 卡片比例与圆角 -->
          <ElForm label-width="110px" label-position="left">
            <ElFormItem label="卡片海报比例">
              <ElRadioGroup v-model="draft.theme!.card!.aspect_ratio" size="default">
                <ElRadioButton value="16:9">16:9 奈飞宽屏</ElRadioButton>
                <ElRadioButton value="2:3">2:3 纵向海报</ElRadioButton>
                <ElRadioButton value="3:4">3:4 标准海报</ElRadioButton>
                <ElRadioButton value="1:1">1:1 方形卡</ElRadioButton>
              </ElRadioGroup>
            </ElFormItem>

            <ElFormItem label="卡片圆角半径">
              <div style="display: flex; align-items: center; gap: 16px; width: 100%;">
                <ElSlider
                  v-model="draft.theme!.card!.radius_px"
                  :min="0"
                  :max="24"
                  :step="1"
                  style="flex: 1;"
                />
                <ElTag size="small" type="info">{{ draft.theme!.card!.radius_px }}px</ElTag>
              </div>
            </ElFormItem>

            <ElFormItem label="字体族预设">
              <ElSelect v-model="draft.theme!.typography!.family" style="width: 220px;">
                <ElOption label="系统原生 (System Default)" value="system" />
                <ElOption label="Inter 现代极简" value="inter" />
                <ElOption label="Roboto 经典" value="roboto" />
              </ElSelect>
            </ElFormItem>
          </ElForm>

          <!-- 预设调色板快速栏 -->
          <div class="theme-presets-bar">
            <span class="presets-label">快速套用主题调色板：</span>
            <ElButton
              v-for="p in themePresets"
              :key="p.name"
              size="small"
              round
              @click="applyThemePreset(p)"
            >
              {{ p.name }}
            </ElButton>
          </div>

          <!-- 色彩 Token 调色板栅格 -->
          <div class="palette-grid">
            <div class="palette-item">
              <div class="palette-header">
                <span class="palette-label">页面主背景</span>
                <div class="color-dot-preview" :style="{ backgroundColor: draft.theme!.color!.background }" />
              </div>
              <div class="palette-input-row">
                <ElColorPicker v-model="draft.theme!.color!.background" />
                <ElInput v-model="draft.theme!.color!.background" size="small" />
              </div>
            </div>

            <div class="palette-item">
              <div class="palette-header">
                <span class="palette-label">卡片表面色</span>
                <div class="color-dot-preview" :style="{ backgroundColor: draft.theme!.color!.surface }" />
              </div>
              <div class="palette-input-row">
                <ElColorPicker v-model="draft.theme!.color!.surface" />
                <ElInput v-model="draft.theme!.color!.surface" size="small" />
              </div>
            </div>

            <div class="palette-item">
              <div class="palette-header">
                <span class="palette-label">品牌强调色</span>
                <div class="color-dot-preview" :style="{ backgroundColor: draft.theme!.color!.primary }" />
              </div>
              <div class="palette-input-row">
                <ElColorPicker v-model="draft.theme!.color!.primary" />
                <ElInput v-model="draft.theme!.color!.primary" size="small" />
              </div>
            </div>

            <div class="palette-item">
              <div class="palette-header">
                <span class="palette-label">主要文字色</span>
                <div class="color-dot-preview" :style="{ backgroundColor: draft.theme!.color!.text }" />
              </div>
              <div class="palette-input-row">
                <ElColorPicker v-model="draft.theme!.color!.text" />
                <ElInput v-model="draft.theme!.color!.text" size="small" />
              </div>
            </div>

            <div class="palette-item">
              <div class="palette-header">
                <span class="palette-label">次要弱化色</span>
                <div class="color-dot-preview" :style="{ backgroundColor: draft.theme!.color!.muted }" />
              </div>
              <div class="palette-input-row">
                <ElColorPicker v-model="draft.theme!.color!.muted" />
                <ElInput v-model="draft.theme!.color!.muted" size="small" />
              </div>
            </div>

            <div class="palette-item">
              <div class="palette-header">
                <span class="palette-label">边框分割线</span>
                <div class="color-dot-preview" :style="{ backgroundColor: draft.theme!.color!.border }" />
              </div>
              <div class="palette-input-row">
                <ElColorPicker v-model="draft.theme!.color!.border" />
                <ElInput v-model="draft.theme!.color!.border" size="small" />
              </div>
            </div>
          </div>
        </div>

        <div class="card-footer-bar">
          <div class="footer-hint">
            <span>🎨 调色板将注入前端 CSS Custom Properties 变量系统</span>
          </div>
          <ElButton
            type="primary"
            size="small"
            :loading="saving"
            :disabled="ui.readOnly"
            @click="handleSaveDraft"
          >
            保存主题
          </ElButton>
        </div>
      </ElCard>

      <!-- 卡片 3: 播放器偏好与交互控制 -->
      <ElCard shadow="hover" class="module-card">
        <div class="card-top-bar">
          <div class="card-title-group">
            <div class="card-icon-box icon-box--cyan">
              <ElIcon :size="20"><VideoPlay /></ElIcon>
            </div>
            <div>
              <div class="card-title">播放器偏好与交互控制 (Player Defaults)</div>
              <div class="card-subtitle">客户端连播逻辑、自动切集倒计时与默认起播倍速</div>
            </div>
          </div>
          <ElTag :type="draft.player_defaults?.auto_next ? 'success' : 'info'" effect="dark" class="status-tag">
            {{ draft.player_defaults?.auto_next ? '自动连播开启' : '连播关闭' }}
          </ElTag>
        </div>

        <div class="card-body-section">
          <div class="info-pill-grid">
            <div class="info-pill-item">
              <span class="pill-label">自动播放下一集</span>
              <div style="display: flex; align-items: center; justify-content: space-between;">
                <span class="pill-value-text">{{ draft.player_defaults?.auto_next ? '开启自动切集' : '关闭' }}</span>
                <ElSwitch v-model="draft.player_defaults!.auto_next" :disabled="ui.readOnly" />
              </div>
              <span class="pill-hint">正片结束时自动进入下一集倒计时</span>
            </div>

            <div class="info-pill-item">
              <span class="pill-label">连播倒计时 (秒)</span>
              <ElInputNumber
                v-model="draft.player_defaults!.auto_next_delay_seconds"
                :min="1"
                :max="30"
                :disabled="ui.readOnly"
                style="width: 100%;"
              />
              <span class="pill-hint">留给用户取消连播或选集的缓冲时间</span>
            </div>

            <div class="info-pill-item">
              <span class="pill-label">默认起播倍速</span>
              <ElSelect
                v-model="draft.player_defaults!.default_rate"
                :disabled="ui.readOnly"
                style="width: 100%;"
              >
                <ElOption :value="0.75" label="0.75x 慢速" />
                <ElOption :value="1.0" label="1.0x (原速推荐)" />
                <ElOption :value="1.25" label="1.25x 极速" />
                <ElOption :value="1.5" label="1.5x 倍速" />
                <ElOption :value="2.0" label="2.0x 双倍速" />
              </ElSelect>
              <span class="pill-hint">新视频首次载入时的默认播放速率</span>
            </div>

            <div class="info-pill-item">
              <span class="pill-label">HUD 控制台隐匿延时</span>
              <span class="pill-value-text">{{ (draft.player_defaults?.hud_hide_after_ms ?? 3500) / 1000 }} 秒</span>
              <span class="pill-hint">鼠标或触控停止后自动隐去播放条</span>
            </div>
          </div>
        </div>

        <div class="card-footer-bar">
          <span class="footer-hint">所有新接入设备与离线APP都将默认遵循此策略</span>
          <ElButton
            type="primary"
            size="small"
            :loading="saving"
            :disabled="ui.readOnly"
            @click="handleSaveDraft"
          >
            保存偏好
          </ElButton>
        </div>
      </ElCard>

      <!-- 卡片 4: 快速操作提示微卡 -->
      <ElCard shadow="hover" class="module-card">
        <div class="card-top-bar">
          <div class="card-title-group">
            <div class="card-icon-box icon-box--warning">
              <ElIcon :size="20"><MagicStick /></ElIcon>
            </div>
            <div>
              <div class="card-title">原子热发布与离线安全兜底机制</div>
              <div class="card-subtitle">无需重新构建镜像或让用户重新安装客户端</div>
            </div>
          </div>
          <ElTag type="success" effect="plain" class="status-tag">安全保障</ElTag>
        </div>

        <div class="card-body-section">
          <div class="info-pill-grid">
            <div class="info-pill-item pill-full">
              <span class="pill-label">1. 草稿乐观并发保护 (Optimistic Lock)</span>
              <span class="pill-hint" style="color: #475569; font-size: 12px; line-height: 1.6;">
                后台每次提交保存都会检验 Revision 版本号，多管理员同时操作时绝不出现后者静默覆盖前者配置的安全事故。
              </span>
            </div>
            <div class="info-pill-item pill-full">
              <span class="pill-label">2. 全网 30 秒无感生效</span>
              <span class="pill-hint" style="color: #475569; font-size: 12px; line-height: 1.6;">
                前台浏览器与移动端会自动比对当前版本指针，并在后台拉取最新生效快照无缝热更新，用户观影不受任何中断干扰。
              </span>
            </div>
            <div class="info-pill-item pill-full">
              <span class="pill-label">3. 离线硬编码兜底 (Zero-Downtime Guarantee)</span>
              <span class="pill-hint" style="color: #475569; font-size: 12px; line-height: 1.6;">
                若遇到网络波动或极端弱网环境，客户端将自动启用经典默认文案与排版样式兜底，确保永远不发生白屏。
              </span>
            </div>
          </div>
        </div>

        <div class="card-footer-bar">
          <span class="footer-hint">支持一键进入沙盒进行真实 1:1 动态渲染</span>
          <ElButton size="small" type="success" :icon="View" @click="handleOpenPreview('home')">
            打开沙盒预览
          </ElButton>
        </div>
      </ElCard>

      <!-- 卡片 5: 首页动态区块编排 (全宽卡片) -->
      <ElCard shadow="hover" class="module-card card-full">
        <div class="card-top-bar">
          <div class="card-title-group">
            <div class="card-icon-box icon-box--success">
              <ElIcon :size="20"><Grid /></ElIcon>
            </div>
            <div>
              <div class="card-title">首页动态区块编排 (Sections Orchestration)</div>
              <div class="card-subtitle">无代码灵活组装首页瀑布流楼层：首屏巨幅横幅、横向分类滑轨与提醒公告</div>
            </div>
          </div>
          <ElTag type="success" effect="dark" class="status-tag">
            {{ homeSections.length }} 个受控楼层
          </ElTag>
        </div>

        <div class="card-body-section">
          <!-- 工具条 -->
          <div class="section-toolbar">
            <span class="footer-hint">受控区块列表 (从上至下依次排列)</span>
            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
              <ElButton size="small" type="primary" :icon="FolderAdd" @click="addSection('hero')">
                + 巨幅横幅 (Hero)
              </ElButton>
              <ElButton size="small" type="success" :icon="FolderAdd" @click="addSection('video_rail')">
                + 视频分类横向滑轨 (Rail)
              </ElButton>
              <ElButton size="small" type="warning" :icon="FolderAdd" @click="addSection('notice')">
                + 提醒通知 (Notice)
              </ElButton>
              <ElButton size="small" plain @click="applyDefaultSections">
                载入标准影视布局模板
              </ElButton>
            </div>
          </div>

          <!-- 空状态 -->
          <div v-if="homeSections.length === 0" class="empty-sections-tip">
            <ElEmpty description="暂无自定义编排楼层，前台将自动回退渲染全部片源分类">
              <template #image>
                <ElIcon :size="48" style="color: #94a3b8;"><Grid /></ElIcon>
              </template>
              <ElButton type="primary" size="small" @click="applyDefaultSections">
                一键载入标准影视推荐布局
              </ElButton>
            </ElEmpty>
          </div>

          <!-- 楼层卡片列表 -->
          <div v-else class="section-card-list">
            <div v-for="(sec, idx) in homeSections" :key="sec.id" class="sec-item-box">
              <div class="sec-item-header">
                <div class="sec-title-tag">
                  <ElTag
                    size="small"
                    :type="sec.component === 'hero' ? 'primary' : sec.component === 'video_rail' ? 'success' : 'warning'"
                    effect="dark"
                  >
                    {{ sec.component.toUpperCase() }}
                  </ElTag>
                  <span class="sec-id-text">ID: {{ sec.id }}</span>
                </div>
                <div class="sec-order-btns">
                  <ElButton size="small" text :disabled="idx === 0" @click="moveSection(idx, 'up')">
                    ↑ 上移
                  </ElButton>
                  <ElButton size="small" text :disabled="idx === homeSections.length - 1" @click="moveSection(idx, 'down')">
                    ↓ 下移
                  </ElButton>
                  <ElButton size="small" text type="danger" @click="removeSection(idx)">
                    删除
                  </ElButton>
                </div>
              </div>

              <!-- 参数表单 -->
              <div class="sec-item-body">
                <!-- Hero 组件 -->
                <template v-if="sec.component === 'hero'">
                  <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px;">
                    <ElInput v-model="asProps(sec).title" placeholder="横幅主标题 (如: 院线大片抢先看)" size="default" />
                    <ElInput v-model="asProps(sec).subtitle" placeholder="横幅副标题" size="default" />
                    <ElInput v-model="asProps(sec).backdrop_url" placeholder="海报背景图片 URL (留空显示渐变色块)" size="default" />
                    <ElInput v-model="asProps(sec).cta_text" placeholder="主按钮文字 (默认: 立即播放)" size="default" />
                  </div>
                </template>

                <!-- Video Rail 组件 -->
                <template v-else-if="sec.component === 'video_rail'">
                  <div style="display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 10px;">
                    <ElInput v-model="asProps(sec).title" placeholder="楼层标题 (如: 热门影视精选)" size="default" />
                    <ElInput v-model="asProps(sec).category_id" placeholder="关联分类 TID (留空按热门)" size="default" />
                    <ElInputNumber
                      v-model="asProps(sec).limit"
                      :min="1"
                      :max="30"
                      placeholder="条数"
                      size="default"
                      style="width: 100%;"
                    />
                  </div>
                </template>

                <!-- Notice 组件 -->
                <template v-else-if="sec.component === 'notice'">
                  <ElInput v-model="asProps(sec).text" placeholder="提醒公告文本内容" size="default" />
                </template>
              </div>
            </div>
          </div>
        </div>

        <div class="card-footer-bar">
          <span class="footer-hint">支持自由增删与上下排序，保存草稿后点击发布即刻推送到前台首页</span>
          <div style="display: flex; gap: 8px;">
            <ElButton size="small" :icon="View" @click="handleOpenPreview('home')">
              预览首页布局
            </ElButton>
            <ElButton
              type="primary"
              size="small"
              :loading="saving"
              :disabled="ui.readOnly"
              @click="handleSaveDraft"
            >
              保存区块编排
            </ElButton>
          </div>
        </div>
      </ElCard>

      <!-- 卡片 6: 版本历史与一键回滚 (全宽卡片) -->
      <ElCard shadow="hover" class="module-card card-full">
        <div class="card-top-bar">
          <div class="card-title-group">
            <div class="card-icon-box icon-box--danger">
              <ElIcon :size="20"><Clock /></ElIcon>
            </div>
            <div>
              <div class="card-title">版本快照历史与安全原子回滚 (Release History & Rollback)</div>
              <div class="card-subtitle">不可变快照记录，支持一键单调递增安全回滚，防止配置覆盖与误操作</div>
            </div>
          </div>
          <ElTag type="info" effect="dark" class="status-tag">
            共 {{ releases.length }} 个历史版本
          </ElTag>
        </div>

        <div class="card-body-section" style="padding: 0;">
          <ElTable :data="releases" style="width: 100%;" stripe>
            <ElTableColumn prop="release_id" label="快照 ID" min-width="170">
              <template #default="{ row }">
                <span style="font-family: monospace; font-weight: 600;">{{ row.release_id }}</span>
              </template>
            </ElTableColumn>

            <ElTableColumn label="修订号" width="100">
              <template #default="{ row }">
                <ElTag type="info" effect="plain" style="font-weight: 700;">r{{ row.revision }}</ElTag>
              </template>
            </ElTableColumn>

            <ElTableColumn label="指针状态" width="140">
              <template #default="{ row }">
                <ElTag v-if="row.is_active" type="success" effect="dark">
                  ● 生产生效中
                </ElTag>
                <span v-else style="color: #94a3b8; font-size: 12px;">历史存档</span>
              </template>
            </ElTableColumn>

            <ElTableColumn prop="published_by" label="发布人" width="110" />

            <ElTableColumn prop="published_at" label="发布时间" width="180">
              <template #default="{ row }">
                <span style="font-size: 12px; color: #64748b;">
                  {{ row.published_at ? row.published_at.replace('T', ' ').slice(0, 19) : '-' }}
                </span>
              </template>
            </ElTableColumn>

            <ElTableColumn prop="note" label="变更日志 / 说明" min-width="220">
              <template #default="{ row }">
                <span>{{ row.note || '常规版本发布' }}</span>
              </template>
            </ElTableColumn>

            <ElTableColumn label="操作" width="140" fixed="right">
              <template #default="{ row }">
                <ElButton
                  v-if="!row.is_active"
                  size="small"
                  type="danger"
                  text
                  :icon="Switch"
                  :loading="rollingBack"
                  :disabled="ui.readOnly"
                  @click="handleRollback(row as ExperienceReleaseItem)"
                >
                  回滚至此版本
                </ElButton>
                <span v-else style="font-size: 12px; color: #10b981; font-weight: 600;">当前活跃</span>
              </template>
            </ElTableColumn>
          </ElTable>
        </div>

        <div class="card-footer-bar">
          <span class="footer-hint">每次回滚都会生成单调递增的新修订号（如 r3 回滚生成 r4），确保全网版本号不回退</span>
          <ElButton size="small" :icon="Refresh" @click="fetchReleases">刷新发布列表</ElButton>
        </div>
      </ElCard>
    </div>

    <!-- 4. 所见即所得沙盒预览弹窗 (Submodal Styling) -->
    <ElDialog
      v-model="previewVisible"
      width="860px"
      align-center
      append-to-body
      destroy-on-close
      class="submodal-dialog"
    >
      <template #header>
        <div class="submodal-header">
          <div class="submodal-icon-badge">
            <ElIcon :size="20"><View /></ElIcon>
          </div>
          <div>
            <div class="submodal-title">前台视觉所见即所得沙盒实时渲染预览</div>
            <div class="submodal-subtitle">1:1 动态还原前台实际呈现效果与设计 Token 视觉映射</div>
          </div>
        </div>
      </template>

      <div v-loading="previewLoading" class="preview-dialog-inner">
        <!-- 预览模式切换栏 -->
        <div class="sandbox-toolbar">
          <ElRadioGroup v-model="previewMode" size="small">
            <ElRadioButton value="home">首页影视大厅 (Home)</ElRadioButton>
            <ElRadioButton value="landing">未激活落地页 (Landing Page)</ElRadioButton>
          </ElRadioGroup>

          <span class="footer-hint">
            实际卡片圆角: {{ previewBootstrapData?.theme?.card?.radius_px ?? draft.theme?.card?.radius_px }}px ·
            海报比例: {{ previewBootstrapData?.theme?.card?.aspect_ratio ?? draft.theme?.card?.aspect_ratio }}
          </span>
        </div>

        <!-- 首页模拟视口 -->
        <div
          v-if="previewMode === 'home'"
          class="mock-preview-viewport"
          :style="{
            '--mock-bg': previewBootstrapData?.theme?.color?.background || draft.theme?.color?.background || '#141414',
            '--mock-surface': previewBootstrapData?.theme?.color?.surface || draft.theme?.color?.surface || '#202020',
            '--mock-primary': previewBootstrapData?.theme?.color?.primary || draft.theme?.color?.primary || '#E50914',
            '--mock-text': previewBootstrapData?.theme?.color?.text || draft.theme?.color?.text || '#ffffff',
            '--mock-radius': `${previewBootstrapData?.theme?.card?.radius_px ?? draft.theme?.card?.radius_px ?? 6}px`,
          }"
        >
          <!-- 模拟导航条 -->
          <div class="mock-nav">
            <div class="mock-logo">
              <img
                v-if="previewBootstrapData?.brand?.logo_url || draft.brand?.logo_url"
                :src="previewBootstrapData?.brand?.logo_url || draft.brand?.logo_url"
                alt="logo"
                style="height: 22px; max-width: 120px; object-fit: contain;"
              />
              <span v-else>{{ previewBootstrapData?.brand?.name || draft.brand?.name || 'Plove' }}</span>
            </div>
            <div class="mock-nav-items">
              <span class="mock-active">首页</span>
              <span>电视剧</span>
              <span>电影</span>
              <span>综艺</span>
              <span>动漫</span>
            </div>
            <div class="mock-user-badge">VIP 活跃</div>
          </div>

          <!-- 模拟受控区块 -->
          <div class="mock-sections">
            <div
              v-for="s in (previewPageData?.sections?.length ? previewPageData.sections : homeSections)"
              :key="s.id"
            >
              <!-- Hero 横幅 -->
              <div v-if="s.component === 'hero'" class="mock-hero">
                <div class="mock-hero-title">{{ asProps(s).title || '巨幅大片重磅上线' }}</div>
                <div class="mock-hero-sub">{{ asProps(s).subtitle || '全网超清极速播放' }}</div>
                <button class="mock-hero-btn">{{ asProps(s).cta_text || '立即开播' }}</button>
              </div>

              <!-- Video Rail 滑轨 -->
              <div v-else-if="s.component === 'video_rail'" class="mock-rail">
                <div class="mock-rail-title">{{ asProps(s).title || '热门推荐楼层' }}</div>
                <div class="mock-rail-cards">
                  <div
                    v-for="i in Math.min(Number(asProps(s).limit || 5), 6)"
                    :key="i"
                    class="mock-card"
                  >
                    <div
                      class="mock-card-img"
                      :style="{
                        aspectRatio: (draft.theme?.card?.aspect_ratio || '16:9').replace(':', '/'),
                      }"
                    />
                    <div class="mock-card-text">影片条目 {{ i }}</div>
                  </div>
                </div>
              </div>

              <!-- Notice 通知条 -->
              <div v-else-if="s.component === 'notice'" class="mock-notice">
                📢 {{ asProps(s).text }}
              </div>
            </div>
          </div>
        </div>

        <!-- 落地页模拟视口 -->
        <div
          v-else
          class="mock-landing-viewport"
          :style="{
            '--mock-primary': previewBootstrapData?.theme?.color?.primary || draft.theme?.color?.primary || '#E50914',
            '--mock-radius': `${previewBootstrapData?.theme?.card?.radius_px ?? draft.theme?.card?.radius_px ?? 6}px`,
          }"
        >
          <div class="mock-logo" style="margin-bottom: 12px; font-size: 26px;">
            {{ previewBootstrapData?.brand?.name || draft.brand?.name || 'Plove' }}
          </div>
          <h2 class="mock-landing-title">
            {{ draft.text!['landing_title'] || '大家都在聊的人氣作品' }}
          </h2>
          <p class="mock-landing-sub">
            {{ draft.text!['landing_subtitle'] || '隨時隨地，隨心暢看海量超清影視。' }}
          </p>
          <p class="mock-landing-lead">
            {{ draft.text!['landing_lead'] || '準備開始觀賞了嗎？請輸入您的激活碼，開啟專屬私人影院。' }}
          </p>

          <div class="mock-landing-form">
            <input
              class="mock-landing-input"
              type="text"
              :placeholder="draft.text!['landing_input_placeholder'] || '激活碼地址 (例如: PLV-XXXX-XXXX)'"
              readonly
            />
            <button class="mock-landing-btn">
              {{ draft.text!['landing_button_text'] || '開始使用' }}
            </button>
          </div>
        </div>
      </div>

      <template #footer>
        <ElButton @click="previewVisible = false">关闭预览</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style>
@import './experience/experience.css';
</style>
