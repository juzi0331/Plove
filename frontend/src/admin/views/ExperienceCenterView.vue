<script setup lang="ts">
/**
 * 体验发布中心 (Experience Center)：
 * 1. 品牌与设计 Token 在线编辑（主题主色、背景色、卡片圆角、海报比例等）；
 * 2. 首页动态组件区块（Hero、Video Rail、Notice 等）无代码可视化编排；
 * 3. 播放器客户端偏好控制（自动连播、倒计时）；
 * 4. 草稿保存（带乐观并发冲突检测）；
 * 5. 实时沙箱预览（独立预览 Draft 快照）；
 * 6. 一键发布上线与全量客户端 30s 自动无缝热更新；
 * 7. 历史版本管理与单向单调递增一键回滚。
 */

import {
  ElButton,
  ElCard,
  ElColorPicker,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElRadio,
  ElRadioGroup,
  ElSelect,
  ElSlider,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTabPane,
  ElTabs,
  ElTag,
} from 'element-plus'
import {
  Document,
  FolderAdd,
  Refresh,
  Switch,
  Top,
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

const activeTab = ref('theme')
const loading = ref(false)
const saving = ref(false)
const publishing = ref(false)
const rollingBack = ref(false)

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

// 实时预览抽屉/弹窗状态
const previewVisible = ref(false)
const previewLoading = ref(false)
const previewBootstrapData = ref<ClientBootstrapPayload | null>(null)
const previewPageData = ref<PageViewModel | null>(null)

// 首页区块快捷计算
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

async function fetchDraft(): Promise<void> {
  loading.value = true
  try {
    const res = await getExperienceDraft('default')
    draft.value = res
  } catch (err: unknown) {
    ElMessage.error(err instanceof Error ? err.message : '获取草稿失败')
  } finally {
    loading.value = false
  }
}

async function fetchReleases(): Promise<void> {
  try {
    releases.value = await getExperienceReleases(20)
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

async function handleOpenPreview(): Promise<void> {
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
    ElMessage.error(err instanceof Error ? err.message : '加载预览失败')
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
  <div class="experience-center">
    <!-- 顶部操作条 -->
    <div class="exp-header-bar">
      <div class="exp-header-info">
        <h2 class="exp-title">体验与前台编排中心</h2>
        <div class="exp-meta">
          <ElTag type="info" size="small">草稿 ID: {{ draft.draft_id }}</ElTag>
          <ElTag type="warning" size="small">修订版本: r{{ draft.revision }}</ElTag>
          <span class="exp-time" v-if="draft.updated_at">上次保存: {{ draft.updated_at }} ({{ draft.updated_by }})</span>
        </div>
      </div>
      <div class="exp-header-actions">
        <ElButton :icon="Refresh" @click="fetchDraft" :loading="loading">拉取最新</ElButton>
        <ElButton type="primary" :icon="Document" @click="handleSaveDraft" :loading="saving">保存草稿</ElButton>
        <ElButton type="success" :icon="View" @click="handleOpenPreview">实时预览</ElButton>
        <ElButton type="danger" :icon="Top" @click="handlePublish" :loading="publishing">发布上线</ElButton>
      </div>
    </div>

    <!-- 主体 Tabs -->
    <ElTabs v-model="activeTab" class="exp-tabs" type="border-card">
      <!-- 1. 主题与视觉 Token -->
      <ElTabPane label="主题与视觉 Token" name="theme">
        <div class="tab-pane-inner">
          <ElRow :gutter="24">
            <ElCol :xs="24" :md="12">
              <ElCard shadow="never" class="sub-card">
                <template #header><div class="card-head">品牌标识</div></template>
                <ElForm label-width="110px" label-position="left">
                  <ElFormItem label="品牌名称">
                    <ElInput v-model="draft.brand!.name" placeholder="Plove" />
                  </ElFormItem>
                  <ElFormItem label="品牌 Logo URL">
                    <ElInput v-model="draft.brand!.logo_url" placeholder="留空则显示文本 Logo" />
                  </ElFormItem>
                </ElForm>
              </ElCard>

              <ElCard shadow="never" class="sub-card" style="margin-top: 16px">
                <template #header><div class="card-head">卡片与排版</div></template>
                <ElForm label-width="110px" label-position="left">
                  <ElFormItem label="卡片海报比例">
                    <ElRadioGroup v-model="draft.theme!.card!.aspect_ratio">
                      <ElRadio value="16:9">16:9 宽屏 (奈飞风)</ElRadio>
                      <ElRadio value="2:3">2:3 纵向海报</ElRadio>
                      <ElRadio value="3:4">3:4 标准海报</ElRadio>
                      <ElRadio value="1:1">1:1 方形</ElRadio>
                    </ElRadioGroup>
                  </ElFormItem>
                  <ElFormItem label="卡片圆角半径">
                    <div class="slider-row">
                      <ElSlider v-model="draft.theme!.card!.radius_px" :min="0" :max="24" :step="1" style="flex: 1" />
                      <span class="slider-val">{{ draft.theme!.card!.radius_px }}px</span>
                    </div>
                  </ElFormItem>
                  <ElFormItem label="字体族预设">
                    <ElSelect v-model="draft.theme!.typography!.family">
                      <ElOption label="系统原生 (System)" value="system" />
                      <ElOption label="Inter 现代极简" value="inter" />
                      <ElOption label="Roboto 经典" value="roboto" />
                    </ElSelect>
                  </ElFormItem>
                </ElForm>
              </ElCard>
            </ElCol>

            <ElCol :xs="24" :md="12">
              <ElCard shadow="never" class="sub-card">
                <template #header><div class="card-head">色彩 Token 调色板</div></template>
                <ElForm label-width="120px" label-position="left">
                  <ElFormItem label="页面主背景">
                    <div class="color-picker-row">
                      <ElColorPicker v-model="draft.theme!.color!.background" />
                      <ElInput v-model="draft.theme!.color!.background" style="width: 140px" />
                    </div>
                  </ElFormItem>
                  <ElFormItem label="卡片表面色">
                    <div class="color-picker-row">
                      <ElColorPicker v-model="draft.theme!.color!.surface" />
                      <ElInput v-model="draft.theme!.color!.surface" style="width: 140px" />
                    </div>
                  </ElFormItem>
                  <ElFormItem label="品牌强调色">
                    <div class="color-picker-row">
                      <ElColorPicker v-model="draft.theme!.color!.primary" />
                      <ElInput v-model="draft.theme!.color!.primary" style="width: 140px" />
                    </div>
                  </ElFormItem>
                  <ElFormItem label="主要文字色">
                    <div class="color-picker-row">
                      <ElColorPicker v-model="draft.theme!.color!.text" />
                      <ElInput v-model="draft.theme!.color!.text" style="width: 140px" />
                    </div>
                  </ElFormItem>
                  <ElFormItem label="次要弱化色">
                    <div class="color-picker-row">
                      <ElColorPicker v-model="draft.theme!.color!.muted" />
                      <ElInput v-model="draft.theme!.color!.muted" style="width: 140px" />
                    </div>
                  </ElFormItem>
                  <ElFormItem label="边框与分割线">
                    <div class="color-picker-row">
                      <ElColorPicker v-model="draft.theme!.color!.border" />
                      <ElInput v-model="draft.theme!.color!.border" style="width: 140px" />
                    </div>
                  </ElFormItem>
                </ElForm>
              </ElCard>
            </ElCol>
          </ElRow>
        </div>
      </ElTabPane>

      <!-- 2. 首页区块编排 -->
      <ElTabPane label="首页动态区块编排" name="sections">
        <div class="tab-pane-inner">
          <div class="section-actions-bar">
            <span class="sub-title">当前受控区块清单 (按从上到下排列)</span>
            <div class="btn-group">
              <ElButton size="small" type="primary" :icon="FolderAdd" @click="addSection('hero')">添加巨幅横幅 (Hero)</ElButton>
              <ElButton size="small" type="success" :icon="FolderAdd" @click="addSection('video_rail')">添加视频分类横向滑轨 (Rail)</ElButton>
              <ElButton size="small" type="warning" :icon="FolderAdd" @click="addSection('notice')">添加通知提醒 (Notice)</ElButton>
            </div>
          </div>

          <div v-if="homeSections.length === 0" class="empty-sections-tip">
            暂无自定义编排区块，前台将自动回退渲染全部片源分类。点击上方按钮可添加首屏横幅或置顶滑轨！
          </div>

          <div v-else class="section-card-list">
            <div v-for="(sec, idx) in homeSections" :key="sec.id" class="sec-item-box">
              <div class="sec-item-header">
                <div class="sec-title-tag">
                  <ElTag size="small" :type="sec.component === 'hero' ? 'primary' : sec.component === 'video_rail' ? 'success' : 'warning'">
                    {{ sec.component.toUpperCase() }}
                  </ElTag>
                  <span class="sec-id-text">ID: {{ sec.id }}</span>
                </div>
                <div class="sec-order-btns">
                  <ElButton size="small" text :disabled="idx === 0" @click="moveSection(idx, 'up')">上移</ElButton>
                  <ElButton size="small" text :disabled="idx === homeSections.length - 1" @click="moveSection(idx, 'down')">下移</ElButton>
                  <ElButton size="small" text type="danger" @click="removeSection(idx)">删除</ElButton>
                </div>
              </div>

              <!-- 根据组件类型展示参数表单 -->
              <div class="sec-item-body">
                <!-- Hero 组件 -->
                <template v-if="sec.component === 'hero'">
                  <ElRow :gutter="16">
                    <ElCol :xs="24" :sm="12">
                      <ElInput v-model="asProps(sec).title" placeholder="横幅主标题" size="small" />
                    </ElCol>
                    <ElCol :xs="24" :sm="12">
                      <ElInput v-model="asProps(sec).subtitle" placeholder="横幅副标题" size="small" />
                    </ElCol>
                    <ElCol :xs="24" :sm="12" style="margin-top: 8px">
                      <ElInput v-model="asProps(sec).backdrop_url" placeholder="海报背景图片 URL" size="small" />
                    </ElCol>
                    <ElCol :xs="24" :sm="12" style="margin-top: 8px">
                      <ElInput v-model="asProps(sec).cta_text" placeholder="主按钮文字 (默认: 立即播放)" size="small" />
                    </ElCol>
                  </ElRow>
                </template>

                <!-- Video Rail 组件 -->
                <template v-else-if="sec.component === 'video_rail'">
                  <ElRow :gutter="16">
                    <ElCol :xs="24" :sm="10">
                      <ElInput v-model="asProps(sec).title" placeholder="楼层标题 (如: 院线重磅推荐)" size="small" />
                    </ElCol>
                    <ElCol :xs="24" :sm="8">
                      <ElInput v-model="asProps(sec).category_id" placeholder="关联分类 TID (如: 1, 2，留空按热门推荐)" size="small" />
                    </ElCol>
                    <ElCol :xs="24" :sm="6">
                      <ElInputNumber v-model="asProps(sec).limit" :min="1" :max="20" placeholder="部数" size="small" style="width: 100%" />
                    </ElCol>
                  </ElRow>
                </template>

                <!-- Notice 组件 -->
                <template v-else-if="sec.component === 'notice'">
                  <ElInput v-model="asProps(sec).text" placeholder="提醒公告文本内容" size="small" />
                </template>
              </div>
            </div>
          </div>
        </div>
      </ElTabPane>

      <!-- 3. 播放偏好设置 -->
      <ElTabPane label="播放器默认偏好" name="player">
        <div class="tab-pane-inner" style="max-width: 580px">
          <ElCard shadow="never" class="sub-card">
            <template #header><div class="card-head">连播与控件行为</div></template>
            <ElForm label-width="160px" label-position="left">
              <ElFormItem label="自动播放下一集">
                <ElSwitch v-model="draft.player_defaults!.auto_next" />
              </ElFormItem>
              <ElFormItem label="连播倒计时 (秒)">
                <ElInputNumber v-model="draft.player_defaults!.auto_next_delay_seconds" :min="1" :max="30" />
              </ElFormItem>
              <ElFormItem label="默认播放倍速">
                <ElSelect v-model="draft.player_defaults!.default_rate" style="width: 120px">
                  <ElOption :value="0.75" label="0.75x" />
                  <ElOption :value="1.0" label="1.0x (原速)" />
                  <ElOption :value="1.25" label="1.25x" />
                  <ElOption :value="1.5" label="1.5x" />
                  <ElOption :value="2.0" label="2.0x" />
                </ElSelect>
              </ElFormItem>
            </ElForm>
          </ElCard>
        </div>
      </ElTabPane>

      <!-- 4. 版本历史与回滚 -->
      <ElTabPane label="版本历史与一键回滚" name="releases">
        <div class="tab-pane-inner">
          <ElTable :data="releases" style="width: 100%" stripe border>
            <ElTableColumn prop="release_id" label="发布快照 ID" min-width="160" />
            <ElTableColumn label="修订号" width="100">
              <template #default="{ row }">
                <ElTag type="info">r{{ row.revision }}</ElTag>
              </template>
            </ElTableColumn>
            <ElTableColumn prop="published_by" label="发布人" width="120" />
            <ElTableColumn prop="published_at" label="发布时间" width="200" />
            <ElTableColumn prop="note" label="变更说明" min-width="200" />
            <ElTableColumn label="操作" width="140" fixed="right">
              <template #default="{ row }">
                <ElButton
                  size="small"
                  type="danger"
                  text
                  :icon="Switch"
                  :loading="rollingBack"
                  @click="handleRollback(row as ExperienceReleaseItem)"
                >
                  回滚至此版
                </ElButton>
              </template>
            </ElTableColumn>
          </ElTable>
        </div>
      </ElTabPane>
    </ElTabs>

    <!-- 实时沙箱预览弹窗 -->
    <ElDialog
      v-model="previewVisible"
      title="草稿沙箱实时渲染预览 (Preview Sandbox)"
      width="800px"
      align-center
      append-to-body
      destroy-on-close
      class="submodal-dialog"
    >
      <div v-loading="previewLoading" class="preview-dialog-content">
        <div
          class="mock-preview-viewport"
          :style="{
            '--mock-bg': previewBootstrapData?.theme?.color?.background || '#141414',
            '--mock-surface': previewBootstrapData?.theme?.color?.surface || '#202020',
            '--mock-primary': previewBootstrapData?.theme?.color?.primary || '#E50914',
            '--mock-text': previewBootstrapData?.theme?.color?.text || '#ffffff',
            '--mock-radius': `${previewBootstrapData?.theme?.card?.radius_px ?? 6}px`,
          }"
        >
          <!-- 模拟前台导航条 -->
          <div class="mock-nav">
            <div class="mock-logo">{{ previewBootstrapData?.brand?.name || 'Plove' }}</div>
            <div class="mock-nav-items">
              <span class="mock-active">首页</span>
              <span>电视剧</span>
              <span>电影</span>
            </div>
            <div class="mock-user-badge">VIP</div>
          </div>

          <!-- 模拟渲染的受控区块 -->
          <div class="mock-sections">
            <div v-if="!previewPageData?.sections?.length" class="mock-fallback-tip">
              首页当前采用动态片源分类保底，未配置首屏 Hero。
            </div>

            <div
              v-for="s in previewPageData?.sections ?? []"
              :key="s.id"
              class="mock-sec-card"
            >
              <div v-if="s.component === 'hero'" class="mock-hero">
                <div class="mock-hero-title">{{ asProps(s).title || '巨幅大片' }}</div>
                <div class="mock-hero-sub">{{ asProps(s).subtitle }}</div>
                <button class="mock-hero-btn">{{ asProps(s).cta_text || '立即播放' }}</button>
              </div>

              <div v-else-if="s.component === 'video_rail'" class="mock-rail">
                <div class="mock-rail-title">{{ asProps(s).title }}</div>
                <div class="mock-rail-cards">
                  <div v-for="i in 5" :key="i" class="mock-card">
                    <div class="mock-card-img" />
                    <div class="mock-card-text">影片条目 {{ i }}</div>
                  </div>
                </div>
              </div>

              <div v-else-if="s.component === 'notice'" class="mock-notice">
                📢 {{ asProps(s).text }}
              </div>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <ElButton @click="previewVisible = false">关闭预览</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.experience-center {
  padding: 20px;
}

.exp-header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  background: var(--el-bg-color-overlay, #1e1e24);
  padding: 16px 20px;
  border-radius: 8px;
  margin-bottom: 20px;
  border: 1px solid var(--el-border-color-light, #2e2e38);
}

.exp-title {
  margin: 0 0 6px;
  font-size: 18px;
  font-weight: 700;
  color: var(--el-text-color-primary, #ffffff);
}

.exp-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}

.exp-time {
  font-size: 12px;
  color: var(--el-text-color-secondary, #94a3b8);
}

.exp-header-actions {
  display: flex;
  gap: 10px;
}

.tab-pane-inner {
  padding: 16px 8px;
}

.card-head {
  font-weight: 600;
  font-size: 14px;
}

.color-picker-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
}

.slider-val {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  width: 40px;
}

.section-actions-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.sub-title {
  font-size: 14px;
  font-weight: 600;
}

.empty-sections-tip {
  padding: 32px;
  text-align: center;
  color: var(--el-text-color-secondary);
  background: rgba(255, 255, 255, 0.02);
  border: 1px dashed var(--el-border-color);
  border-radius: 8px;
}

.section-card-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sec-item-box {
  background: var(--el-bg-color-overlay, #1c1c24);
  border: 1px solid var(--el-border-color-light, #2c2c36);
  border-radius: 6px;
  padding: 14px 16px;
}

.sec-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.sec-title-tag {
  display: flex;
  align-items: center;
  gap: 10px;
}

.sec-id-text {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-family: monospace;
}

/* 模拟器样式 */
.mock-preview-viewport {
  background-color: var(--mock-bg);
  color: var(--mock-text);
  border-radius: 10px;
  padding: 16px;
  min-height: 400px;
  overflow: hidden;
}

.mock-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  margin-bottom: 16px;
}

.mock-logo {
  font-size: 18px;
  font-weight: 800;
  color: var(--mock-primary);
}

.mock-nav-items {
  display: flex;
  gap: 14px;
  font-size: 13px;
}

.mock-active {
  color: var(--mock-primary);
  font-weight: 700;
}

.mock-user-badge {
  font-size: 10px;
  font-weight: 700;
  background: var(--mock-primary);
  color: #ffffff;
  padding: 2px 6px;
  border-radius: 3px;
}

.mock-sections {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.mock-hero {
  background: var(--mock-surface);
  border-radius: var(--mock-radius);
  padding: 24px;
}

.mock-hero-title {
  font-size: 20px;
  font-weight: 800;
  margin-bottom: 6px;
}

.mock-hero-sub {
  font-size: 13px;
  opacity: 0.8;
  margin-bottom: 14px;
}

.mock-hero-btn {
  background: var(--mock-primary);
  color: #ffffff;
  border: none;
  padding: 6px 16px;
  border-radius: var(--mock-radius);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.mock-rail-title {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 8px;
}

.mock-rail-cards {
  display: flex;
  gap: 10px;
}

.mock-card {
  flex: 1;
  background: var(--mock-surface);
  border-radius: var(--mock-radius);
  overflow: hidden;
}

.mock-card-img {
  aspect-ratio: 16/9;
  background: rgba(255, 255, 255, 0.08);
}

.mock-card-text {
  padding: 6px;
  font-size: 11px;
}

.mock-notice {
  background: rgba(255, 255, 255, 0.08);
  padding: 8px 12px;
  border-radius: var(--mock-radius);
  font-size: 12px;
}

.mock-fallback-tip {
  padding: 20px;
  text-align: center;
  font-size: 13px;
  opacity: 0.6;
}
</style>
