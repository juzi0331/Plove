<script setup lang="ts">
/**
 * 全站公告与维护广播中心（全卡片式模块架构）：
 * 1. 停机维护闸门控制卡片（前台全屏拦截阻断，后台白名单放行，1:1 锁屏预览）；
 * 2. 全站公告广播中心卡片（多渠道消息发布与总控）；
 * 3. 广播发布方式矩阵（支持 6 大公告场景：顶部常驻横幅、顶部滚动跑马灯、大厅居中强弹窗、右下角悬浮通知、弹窗+跑马灯、全渠道强力广播）；
 * 4. 前台视觉所见即所得实时模拟沙盒（多渠道 1:1 动态实时预览）；
 * 5. 模块化独立配置弹窗（维护文案配置、公告广播详细配置）。
 */
import {
  ElButton,
  ElCard,
  ElCol,
  ElDialog,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElRadio,
  ElRadioButton,
  ElRadioGroup,
  ElRow,
  ElSelect,
  ElSwitch,
  ElTag,
} from 'element-plus'
import {
  Bell,
  Check,
  Edit,
  Monitor,
  Promotion,
  Refresh,
  Tools,
} from '@element-plus/icons-vue'
import { computed, onMounted, ref } from 'vue'

import {
  getSystemMaintenance,
  getSystemNotice,
  updateSystemMaintenance,
  updateSystemNotice,
} from '@/admin/api'
import { ui } from '@/admin/ui'
import type { SystemMaintenancePayload, SystemNoticePayload } from '@/api/types'

const loading = ref(false)
const savingNotice = ref(false)
const savingMaint = ref(false)

// 弹窗控制
const showMaintDialog = ref(false)
const showNoticeDialog = ref(false)

// 当前沙盒激活 Tab
const activePreviewTab = ref<'header_bar' | 'banner' | 'modal' | 'float' | 'maintenance'>('header_bar')

const noticeForm = ref<SystemNoticePayload>({
  enabled: false,
  title: 'Plove 影视全新升级公告',
  content: '尊敬的用户，我们已全面优化了蓝光秒播解析核心与全站海报防盗链加速通道。享受极致视听盛宴！',
  level: 'info',
  display_type: 'header_bar',
  action_text: '查看详情',
  action_url: '',
  dismissible: true,
  updated_at: '',
})

const maintForm = ref<SystemMaintenancePayload>({
  enabled: false,
  message: '尊敬的用户：为了提供更优质的超清流媒体服务，系统正在进行机房网络升级，预计 30 分钟内完成，感谢您的理解与支持！',
  allow_admin: true,
  updated_at: '',
})

// 公告发布方式定义列表
const displayTypeOptions = [
  {
    type: 'header_bar',
    name: '顶部常驻横幅',
    tag: '置顶静态栏',
    desc: '固定置顶通告条，文字清晰不闪烁眩晕，支持行动按钮与关闭，适合重大通知与活动导流',
    features: ['醒目常驻', '支持外链', '优雅不遮挡'],
  },
  {
    type: 'banner',
    name: '顶部滚动跑马灯',
    tag: '动态跑马灯',
    desc: '经典流媒体走字条幅，水平平滑滚动长文本，适合持续滚动展示最新动态或提示',
    features: ['长文本滚动', '流媒体质感', '轻量提示'],
  },
  {
    type: 'modal',
    name: '大厅居中强弹窗',
    tag: '强力交互弹窗',
    desc: '用户进站时首次居中弹出半透明磨砂卡片对话框，必须手动确认，适合核心政策与重磅更新',
    features: ['强制关注', '高视觉权重', '会话记忆'],
  },
  {
    type: 'float',
    name: '右下角悬浮卡片',
    tag: '轻量气泡卡片',
    desc: '悬浮于右下角（移动端底部安全区上方），不遮挡主体内容，现代化轻量消息提示',
    features: ['微交互设计', '不扰用户', '快捷跳转'],
  },
  {
    type: 'both',
    name: '弹窗 + 跑马灯组合',
    tag: '双重组合通知',
    desc: '进站弹窗强提醒 + 顶部走字跑马灯双轨并行，兼具瞬时冲击力与长效提示',
    features: ['双重触达', '渐进引导', '双重提示'],
  },
  {
    type: 'all',
    name: '全渠道强力广播',
    tag: '全矩阵覆盖',
    desc: '顶部横幅 + 居中弹窗 + 右下角悬浮卡片全方位同步推送，最高级别广播通知',
    features: ['全场景覆盖', '最高响应级', '全方位触达'],
  },
] as const

const currentDisplayOption = computed(() => {
  return displayTypeOptions.find(o => o.type === noticeForm.value.display_type) || displayTypeOptions[0]
})

async function loadData(): Promise<void> {
  loading.value = true
  try {
    const [n, m] = await Promise.all([getSystemNotice(), getSystemMaintenance()])
    if (n.title || n.content) {
      noticeForm.value = { ...noticeForm.value, ...n }
    }
    if (m.message) {
      maintForm.value = { ...maintForm.value, ...m }
    }
    // 同步沙盒默认预览视图
    if (maintForm.value.enabled) {
      activePreviewTab.value = 'maintenance'
    } else if (noticeForm.value.display_type === 'modal') {
      activePreviewTab.value = 'modal'
    } else if (noticeForm.value.display_type === 'banner') {
      activePreviewTab.value = 'banner'
    } else if (noticeForm.value.display_type === 'float') {
      activePreviewTab.value = 'float'
    } else {
      activePreviewTab.value = 'header_bar'
    }
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '加载系统配置失败')
  } finally {
    loading.value = false
  }
}

async function handleSaveNotice(): Promise<void> {
  savingNotice.value = true
  try {
    const res = await updateSystemNotice(noticeForm.value)
    noticeForm.value = res
    ElMessage.success('全站广播公告已更新并立即在前台生效！')
    showNoticeDialog.value = false
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '保存公告配置失败')
  } finally {
    savingNotice.value = false
  }
}

async function handleQuickToggleNotice(): Promise<void> {
  await handleSaveNotice()
}

async function handleSaveMaintenance(): Promise<void> {
  const willEnable = maintForm.value.enabled
  if (willEnable) {
    try {
      await ElMessageBox.confirm(
        '开启维护模式后，除后台管理端（/admin）受到白名单保护持续放行外，所有前台用户访问均将被即刻拦截并展示维护锁屏。确定开启吗？',
        '开启全站停机维护警告',
        {
          confirmButtonText: '确定开启维护',
          cancelButtonText: '取消',
          type: 'warning',
        },
      )
    } catch {
      maintForm.value.enabled = false
      return
    }
  }

  savingMaint.value = true
  try {
    const res = await updateSystemMaintenance(maintForm.value)
    maintForm.value = res
    ElMessage.success(
      res.enabled
        ? '已开启全站停机维护：前台已全面阻断并展示锁屏'
        : '已关闭维护模式，前台服务恢复正常对外开放',
    )
    showMaintDialog.value = false
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '保存维护设置失败')
  } finally {
    savingMaint.value = false
  }
}

async function handleQuickToggleMaintenance(): Promise<void> {
  await handleSaveMaintenance()
}

function selectDisplayType(type: typeof displayTypeOptions[number]['type']): void {
  noticeForm.value.display_type = type
  if (type === 'modal') {
    activePreviewTab.value = 'modal'
  } else if (type === 'banner') {
    activePreviewTab.value = 'banner'
  } else if (type === 'float') {
    activePreviewTab.value = 'float'
  } else if (type === 'header_bar') {
    activePreviewTab.value = 'header_bar'
  }
}

// 维护模板快速填充
function applyMaintTemplate(type: 'network' | 'db' | 'cdn'): void {
  if (type === 'network') {
    maintForm.value.message =
      '尊敬的用户：为了提供更优质的超清流媒体服务，系统正在进行机房网络升级，预计 30 分钟内完成，感谢您的理解与支持！'
  } else if (type === 'db') {
    maintForm.value.message =
      '系统正在进行核心数据库例行容灾割接与冷备份作业，期间前台服务暂不可用，预计在 1 小时内恢复访问。'
  } else if (type === 'cdn') {
    maintForm.value.message =
      '为了防范网络拥塞并提升海报与流媒体加速质量，系统正在切换高防 CDN 线路节点，请稍候刷新访问。'
  }
  ElMessage.info('已载入常用维护模板')
}

// 公告模板快速填充
function applyNoticeTemplate(type: 'upgrade' | 'mirror' | 'speed'): void {
  if (type === 'upgrade') {
    noticeForm.value.title = 'Plove 影视全新版本升级'
    noticeForm.value.content =
      '尊敬的用户，我们已全面优化蓝光秒播解析核心与全站海报防盗链加速通道。享受极致视听盛宴！'
    noticeForm.value.level = 'info'
    noticeForm.value.action_text = '查看新版特性'
    noticeForm.value.action_url = ''
  } else if (type === 'mirror') {
    noticeForm.value.title = '官方备用域名与防失联通知'
    noticeForm.value.content =
      '为防止个别地区网络解析波动导致访问受阻，请各位用户及时保存我们的备用官方发布入口与交流平台。'
    noticeForm.value.level = 'warning'
    noticeForm.value.action_text = '收藏发布页'
    noticeForm.value.action_url = 'https://github.com'
  } else if (type === 'speed') {
    noticeForm.value.title = '多线蓝光解析专线已部署'
    noticeForm.value.content =
      '系统现已支持超清源站自动动态穿透解密，若在观看过程中遇到个别源卡顿，可在播放界面自由切换解析路线。'
    noticeForm.value.level = 'info'
    noticeForm.value.action_text = '立即体验'
    noticeForm.value.action_url = ''
  }
  ElMessage.info('已载入常用公告模板')
}

onMounted(() => {
  void loadData()
})
</script>

<template>
  <div class="system-notice-page">
    <!-- 顶栏标题 -->
    <div class="header-section">
      <div>
        <h2 class="title">全站公告与维护广播中心</h2>
        <p class="subtitle">
          统筹管理前台全站运行闸门。可一键开启全站停机维护，或发布前台大厅弹窗、顶部滚动跑马灯、静态通告横幅、右下角悬浮通知等多渠道广播。
        </p>
      </div>
      <div class="header-actions">
        <ElButton :icon="Refresh" :loading="loading" @click="loadData">刷新状态</ElButton>
      </div>
    </div>

    <!-- 核心板块卡片矩阵 (全卡片化设计) -->
    <div class="cards-grid">
      <!-- 卡片 1: 停机维护闸门控制卡片 -->
      <ElCard
        shadow="hover"
        class="module-card maint-card"
        :class="{ 'card--danger': maintForm.enabled }"
        @click="showMaintDialog = true"
      >
        <div class="card-top-bar">
          <div class="card-title-group">
            <div class="card-icon-box" :class="maintForm.enabled ? 'icon-box--danger' : 'icon-box--primary'">
              <ElIcon :size="20"><Tools /></ElIcon>
            </div>
            <div>
              <div class="card-title">全站停服维护闸门 (Maintenance Gateway)</div>
              <div class="card-subtitle">前台全屏拦截阻断，管理后台持续放行</div>
            </div>
          </div>
          <ElTag :type="maintForm.enabled ? 'danger' : 'success'" effect="dark" class="status-tag">
            {{ maintForm.enabled ? '全站维护中（前台已阻断）' : '正常对外运营中' }}
          </ElTag>
        </div>

        <div class="card-body-section">
          <div class="info-pill-grid">
            <div class="info-pill-item">
              <span class="pill-label">维护状态</span>
              <div class="pill-value-switch" @click.stop>
                <ElSwitch
                  v-model="maintForm.enabled"
                  :disabled="ui.readOnly || savingMaint"
                  active-text="开启维护"
                  inactive-text="正常运营"
                  @change="handleQuickToggleMaintenance"
                />
              </div>
            </div>

            <div class="info-pill-item">
              <span class="pill-label">后台放行</span>
              <ElTag size="small" type="success" effect="plain">白名单持续通行</ElTag>
            </div>

            <div class="info-pill-item pill-full">
              <span class="pill-label">展示文案摘要</span>
              <span class="pill-text-truncate" :title="maintForm.message">
                {{ maintForm.message || '未设置维护告示文案' }}
              </span>
            </div>
          </div>
        </div>

        <div class="card-footer-bar" @click.stop>
          <div class="footer-hint">
            <span v-if="maintForm.updated_at">更新于 {{ maintForm.updated_at }}</span>
            <span v-else>配置即时在前台生效</span>
          </div>
          <ElButton
            :type="maintForm.enabled ? 'danger' : 'default'"
            size="small"
            :icon="Edit"
            @click="showMaintDialog = true"
          >
            配置文案与锁屏预览
          </ElButton>
        </div>
      </ElCard>

      <!-- 卡片 2: 全站广播发布总控卡片 -->
      <ElCard
        shadow="hover"
        class="module-card broadcast-card"
        :class="{ 'card--active': noticeForm.enabled }"
        @click="showNoticeDialog = true"
      >
        <div class="card-top-bar">
          <div class="card-title-group">
            <div class="card-icon-box" :class="noticeForm.enabled ? 'icon-box--success' : 'icon-box--info'">
              <ElIcon :size="20"><Bell /></ElIcon>
            </div>
            <div>
              <div class="card-title">全站公告广播中心 (Broadcast Notice)</div>
              <div class="card-subtitle">向全站用户推送多渠道消息通告，支持即时生效</div>
            </div>
          </div>
          <ElTag :type="noticeForm.enabled ? 'success' : 'info'" effect="dark" class="status-tag">
            {{ noticeForm.enabled ? '广播生效中' : '广播已关闭' }}
          </ElTag>
        </div>

        <div class="card-body-section">
          <div class="info-pill-grid">
            <div class="info-pill-item">
              <span class="pill-label">广播状态</span>
              <div class="pill-value-switch" @click.stop>
                <ElSwitch
                  v-model="noticeForm.enabled"
                  :disabled="ui.readOnly || savingNotice"
                  active-text="开启"
                  inactive-text="关闭"
                  @change="handleQuickToggleNotice"
                />
              </div>
            </div>

            <div class="info-pill-item">
              <span class="pill-label">紧急级别</span>
              <ElTag
                size="small"
                :type="noticeForm.level === 'danger' ? 'danger' : noticeForm.level === 'warning' ? 'warning' : 'info'"
                effect="plain"
              >
                {{ noticeForm.level === 'danger' ? '紧急通告' : noticeForm.level === 'warning' ? '重要提醒' : '常规提示' }}
              </ElTag>
            </div>

            <div class="info-pill-item">
              <span class="pill-label">发布方式</span>
              <ElTag size="small" type="primary" effect="light">
                {{ currentDisplayOption.name }}
              </ElTag>
            </div>

            <div class="info-pill-item">
              <span class="pill-label">关闭权限</span>
              <ElTag size="small" :type="noticeForm.dismissible ? 'info' : 'warning'" effect="plain">
                {{ noticeForm.dismissible ? '允许手动关闭' : '强制驻留' }}
              </ElTag>
            </div>

            <div class="info-pill-item pill-full">
              <span class="pill-label">公告主标题</span>
              <span class="pill-text-truncate" :title="noticeForm.title">
                {{ noticeForm.title || '未配置标题' }}
              </span>
            </div>
          </div>
        </div>

        <div class="card-footer-bar" @click.stop>
          <div class="footer-hint">
            <span v-if="noticeForm.updated_at">最后发布：{{ noticeForm.updated_at }}</span>
            <span v-else>点击卡片修改内容</span>
          </div>
          <div class="card-footer-actions">
            <ElButton size="small" :icon="Edit" @click="showNoticeDialog = true">
              编辑内容与渠道
            </ElButton>
            <ElButton
              size="small"
              type="primary"
              :icon="Check"
              :loading="savingNotice"
              :disabled="ui.readOnly"
              @click="handleSaveNotice"
            >
              即刻发布广播
            </ElButton>
          </div>
        </div>
      </ElCard>
    </div>

    <!-- 卡片 3: 广播发布方式矩阵卡片 -->
    <ElCard shadow="hover" class="module-card channel-matrix-card">
      <div class="card-top-bar">
        <div class="card-title-group">
          <div class="card-icon-box icon-box--primary">
            <ElIcon :size="20"><Promotion /></ElIcon>
          </div>
          <div>
            <div class="card-title">广播发布方式矩阵 (Channels Matrix)</div>
            <div class="card-subtitle">
              支持 6 种丰富通知形式，点击可快速切换生效方式，并在下方沙盒中实时预览
            </div>
          </div>
        </div>
        <div class="flex-align">
          <span class="current-label">当前选定方式：</span>
          <ElTag type="success" effect="dark">{{ currentDisplayOption.name }}</ElTag>
        </div>
      </div>

      <div class="channel-grid">
        <div
          v-for="opt in displayTypeOptions"
          :key="opt.type"
          class="channel-box"
          :class="{ 'channel-box--active': noticeForm.display_type === opt.type }"
          @click="selectDisplayType(opt.type)"
        >
          <div class="channel-box-header">
            <div class="channel-name-row">
              <span class="channel-name">{{ opt.name }}</span>
              <span class="channel-tag">{{ opt.tag }}</span>
            </div>
            <span v-if="noticeForm.display_type === opt.type" class="channel-active-indicator">
              生效中
            </span>
          </div>

          <p class="channel-desc">{{ opt.desc }}</p>

          <div class="channel-features">
            <span v-for="f in opt.features" :key="f" class="feature-chip">{{ f }}</span>
          </div>
        </div>
      </div>

      <div class="card-footer-bar">
        <span class="footer-hint">切换发布方式后，点击下方「即刻发布广播」或弹窗内保存即可向前台全网推送</span>
        <ElButton
          type="primary"
          size="small"
          :loading="savingNotice"
          :disabled="ui.readOnly"
          @click="handleSaveNotice"
        >
          保存并应用当前方式
        </ElButton>
      </div>
    </ElCard>

    <!-- 卡片 4: 前台视觉所见即所得沙盒卡片 -->
    <ElCard shadow="hover" class="module-card sandbox-card">
      <div class="card-top-bar">
        <div class="card-title-group">
          <div class="card-icon-box icon-box--primary">
            <ElIcon :size="20"><Monitor /></ElIcon>
          </div>
          <div>
            <div class="card-title">前台视觉所见即所得实时模拟沙盒 (Live Visual Sandbox)</div>
            <div class="card-subtitle">
              1:1 动态展示各场景在前台用户界面的呈现效果，所见即所得
            </div>
          </div>
        </div>

        <div class="sandbox-tabs">
          <ElRadioGroup v-model="activePreviewTab" size="small">
            <ElRadioButton value="header_bar">顶部常驻横幅</ElRadioButton>
            <ElRadioButton value="banner">顶部跑马灯</ElRadioButton>
            <ElRadioButton value="modal">大厅居中强弹窗</ElRadioButton>
            <ElRadioButton value="float">右下角悬浮卡片</ElRadioButton>
            <ElRadioButton value="maintenance">全站维护锁屏</ElRadioButton>
          </ElRadioGroup>
        </div>
      </div>

      <!-- 实时沙盒渲染舞台 -->
      <div class="sandbox-stage">
        <!-- 1. 顶部常驻横幅预览 -->
        <div v-if="activePreviewTab === 'header_bar'" class="stage-view">
          <div class="view-intro">
            <span class="view-tag">顶部常驻横幅效果</span>
            <span class="view-desc">
              置顶于网站导航栏，文字清晰平稳，适合通知或指引用户点击跳转
            </span>
          </div>

          <div class="preview-header-bar" :class="`preview-bar--${noticeForm.level || 'info'}`">
            <div class="preview-bar-inner">
              <span class="preview-bar-tag">公告</span>
              <span class="preview-bar-title">{{ noticeForm.title || '公告标题' }}</span>
              <span class="preview-bar-sep">—</span>
              <span class="preview-bar-content">{{ noticeForm.content || '请输入公告详细内容...' }}</span>
              <span v-if="noticeForm.action_text" class="preview-bar-action">
                {{ noticeForm.action_text }} &rarr;
              </span>
            </div>
            <span v-if="noticeForm.dismissible" class="preview-bar-close">✕</span>
          </div>

          <div class="fake-page-content">
            <div class="fake-nav-line" />
            <div class="fake-banner-card" />
            <div class="fake-grid-row">
              <div class="fake-card" />
              <div class="fake-card" />
              <div class="fake-card" />
              <div class="fake-card" />
            </div>
          </div>
        </div>

        <!-- 2. 顶部滚动跑马灯预览 -->
        <div v-if="activePreviewTab === 'banner'" class="stage-view">
          <div class="view-intro">
            <span class="view-tag">顶部滚动走字跑马灯效果</span>
            <span class="view-desc">长文本平滑横向滚动走字，流媒体风格沉浸提示</span>
          </div>

          <div class="marquee-preview-bar" :class="`marquee--${noticeForm.level || 'info'}`">
            <div class="marquee-badge">系统广播</div>
            <div class="marquee-viewport">
              <div class="marquee-track">
                <span class="marquee-text">
                  <strong>【{{ noticeForm.title || '系统广播' }}】</strong>
                  {{ noticeForm.content || '暂无广播内容' }}
                </span>
              </div>
            </div>
            <span v-if="noticeForm.action_text" class="marquee-action-fake">
              {{ noticeForm.action_text }}
            </span>
            <span v-if="noticeForm.dismissible" class="marquee-close-fake">✕</span>
          </div>

          <div class="fake-page-content">
            <div class="fake-nav-line" />
            <div class="fake-banner-card" />
            <div class="fake-grid-row">
              <div class="fake-card" />
              <div class="fake-card" />
              <div class="fake-card" />
              <div class="fake-card" />
            </div>
          </div>
        </div>

        <!-- 3. 大厅居中强弹窗预览 -->
        <div v-if="activePreviewTab === 'modal'" class="stage-view">
          <div class="view-intro">
            <span class="view-tag">大厅居中强弹窗 Modal 效果</span>
            <span class="view-desc">进站强提醒，半透明磨砂遮罩与高质感对话框</span>
          </div>

          <div class="modal-preview-stage">
            <div class="modal-box" :class="`modal--${noticeForm.level || 'info'}`">
              <div class="modal-header">
                <div class="modal-title-row">
                  <span class="modal-level-badge">{{ (noticeForm.level || 'info').toUpperCase() }}</span>
                  <span class="modal-title">{{ noticeForm.title || '公告标题' }}</span>
                </div>
                <span v-if="noticeForm.dismissible" class="modal-x">✕</span>
              </div>
              <div class="modal-content">
                {{ noticeForm.content || '请输入公告详细正文内容...' }}
              </div>
              <div class="modal-footer">
                <span v-if="noticeForm.action_text" class="modal-action-fake">
                  {{ noticeForm.action_text }}
                </span>
                <span class="modal-btn-fake">我知道了</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 4. 右下角悬浮卡片预览 -->
        <div v-if="activePreviewTab === 'float'" class="stage-view">
          <div class="view-intro">
            <span class="view-tag">右下角悬浮卡片效果</span>
            <span class="view-desc">常驻轻量气泡卡片，不遮挡主内容，优雅微交互</span>
          </div>

          <div class="float-preview-container">
            <div class="fake-page-content" style="opacity: 0.5;">
              <div class="fake-nav-line" />
              <div class="fake-banner-card" />
              <div class="fake-grid-row">
                <div class="fake-card" />
                <div class="fake-card" />
                <div class="fake-card" />
                <div class="fake-card" />
              </div>
            </div>

            <div class="float-preview-capsule" :class="`float--${noticeForm.level || 'info'}`">
              <div class="float-header">
                <div class="float-title-row">
                  <span class="float-badge">站内通报</span>
                  <span class="float-title">{{ noticeForm.title || '公告标题' }}</span>
                </div>
                <span v-if="noticeForm.dismissible" class="float-close">✕</span>
              </div>
              <div class="float-body">
                {{ noticeForm.content || '请输入公告详细内容...' }}
              </div>
              <div v-if="noticeForm.action_text" class="float-footer">
                <span class="float-btn-fake">{{ noticeForm.action_text }} &rarr;</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 5. 全站维护锁屏预览 -->
        <div v-if="activePreviewTab === 'maintenance'" class="stage-view">
          <div class="view-intro">
            <span class="view-tag">全站停机维护全屏锁屏效果</span>
            <span class="view-desc">普通前台用户将被全面拦截并显示维护屏，管理后台持续放行</span>
          </div>

          <div class="lock-preview-stage">
            <div class="lock-icon-halo">
              <ElIcon :size="32" class="lock-spin-icon"><Tools /></ElIcon>
            </div>
            <div class="lock-title">SYSTEM MAINTENANCE</div>
            <div class="lock-badge">系统升级维护中</div>
            <div class="lock-message">
              {{ maintForm.message || '系统维护中，请稍后访问...' }}
            </div>
            <div class="lock-actions">
              <div class="lock-btn-fake">刷新页面重试</div>
              <div class="lock-btn-fake lock-btn-sub">管理后台通道</div>
            </div>
          </div>
        </div>
      </div>
    </ElCard>

    <!-- 弹窗 1: 停机维护闸门详细配置弹窗 -->
    <ElDialog
      v-model="showMaintDialog"
      title="配置全站停服维护闸门"
      width="640px"
      append-to-body
      destroy-on-close
    >
      <ElForm :model="maintForm" label-position="top">
        <ElFormItem label="全站停服维护总闸门">
          <div class="dialog-switch-row">
            <div>
              <div class="switch-row-title">紧急停机维护开关</div>
              <div class="switch-row-desc">
                开启后，所有普通前台路由（除 /admin 管理后台）一律展示维护锁屏
              </div>
            </div>
            <ElSwitch
              v-model="maintForm.enabled"
              :disabled="ui.readOnly"
              active-text="开启维护"
              inactive-text="关闭"
            />
          </div>
        </ElFormItem>

        <ElFormItem label="常用维护模板快捷填充">
          <div class="template-btns-row">
            <ElButton size="small" @click="applyMaintTemplate('network')">机房网络升级</ElButton>
            <ElButton size="small" @click="applyMaintTemplate('db')">数据库容灾割接</ElButton>
            <ElButton size="small" @click="applyMaintTemplate('cdn')">高防 CDN 切换</ElButton>
          </div>
        </ElFormItem>

        <ElFormItem label="展示给前台用户的维护告示文案">
          <ElInput
            v-model="maintForm.message"
            type="textarea"
            :rows="4"
            placeholder="请输入维护原因与预计恢复时间文案..."
            :disabled="ui.readOnly"
          />
        </ElFormItem>
      </ElForm>

      <template #footer>
        <div class="dialog-footer">
          <ElButton @click="showMaintDialog = false">取消</ElButton>
          <ElButton
            :type="maintForm.enabled ? 'danger' : 'primary'"
            :loading="savingMaint"
            :disabled="ui.readOnly"
            @click="handleSaveMaintenance"
          >
            保存并应用维护设置
          </ElButton>
        </div>
      </template>
    </ElDialog>

    <!-- 弹窗 2: 全站广播公告详细配置弹窗 -->
    <ElDialog
      v-model="showNoticeDialog"
      title="配置全站广播公告"
      width="680px"
      append-to-body
      destroy-on-close
    >
      <ElForm :model="noticeForm" label-position="top">
        <ElFormItem label="全站广播总开关">
          <div class="dialog-switch-row">
            <div>
              <div class="switch-row-title">广播发布状态</div>
              <div class="switch-row-desc">开启后立即在前台按照指定渠道进行展示</div>
            </div>
            <ElSwitch
              v-model="noticeForm.enabled"
              :disabled="ui.readOnly"
              active-text="广播生效"
              inactive-text="关闭"
            />
          </div>
        </ElFormItem>

        <ElRow :gutter="16">
          <ElCol :xs="24" :sm="15">
            <ElFormItem label="公告主标题">
              <ElInput
                v-model="noticeForm.title"
                placeholder="如：全站蓝光超清解析核心升级公告"
                :disabled="ui.readOnly"
              />
            </ElFormItem>
          </ElCol>

          <ElCol :xs="24" :sm="9">
            <ElFormItem label="紧急级别">
              <ElSelect v-model="noticeForm.level" style="width: 100%" :disabled="ui.readOnly">
                <ElOption label="常规提示 (Info 蓝/绿)" value="info" />
                <ElOption label="重要提醒 (Warning 琥珀橙)" value="warning" />
                <ElOption label="紧急通告 (Danger 警示红)" value="danger" />
              </ElSelect>
            </ElFormItem>
          </ElCol>
        </ElRow>

        <ElFormItem label="发布渠道与展示形式">
          <ElRadioGroup v-model="noticeForm.display_type" :disabled="ui.readOnly" class="dialog-radio-grid">
            <ElRadio
              v-for="opt in displayTypeOptions"
              :key="opt.type"
              :value="opt.type"
              border
              class="dialog-radio-item"
            >
              {{ opt.name }}
            </ElRadio>
          </ElRadioGroup>
        </ElFormItem>

        <ElFormItem label="常用公告模板快捷填充">
          <div class="template-btns-row">
            <ElButton size="small" @click="applyNoticeTemplate('upgrade')">影视全新升级</ElButton>
            <ElButton size="small" @click="applyNoticeTemplate('mirror')">备用发布页通知</ElButton>
            <ElButton size="small" @click="applyNoticeTemplate('speed')">线路优化提示</ElButton>
          </div>
        </ElFormItem>

        <ElFormItem label="公告详细正文内容">
          <ElInput
            v-model="noticeForm.content"
            type="textarea"
            :rows="4"
            placeholder="请输入公告正文详细内容..."
            :disabled="ui.readOnly"
          />
        </ElFormItem>

        <ElRow :gutter="16">
          <ElCol :xs="24" :sm="10">
            <ElFormItem label="行动引导按钮文案（选填）">
              <ElInput
                v-model="noticeForm.action_text"
                placeholder="如：查看详情 / 立即加群"
                :disabled="ui.readOnly"
              />
            </ElFormItem>
          </ElCol>

          <ElCol :xs="24" :sm="14">
            <ElFormItem label="引导跳转链接 URL（选填）">
              <ElInput
                v-model="noticeForm.action_url"
                placeholder="如：https://...（用户点击按钮跳转）"
                :disabled="ui.readOnly"
              />
            </ElFormItem>
          </ElCol>
        </ElRow>

        <ElFormItem label="交互权限控制">
          <div class="dialog-switch-row">
            <div>
              <div class="switch-row-title">允许用户手动点击关闭</div>
              <div class="switch-row-desc">关闭后不再遮挡用户视线，保持前台清爽</div>
            </div>
            <ElSwitch v-model="noticeForm.dismissible" :disabled="ui.readOnly" />
          </div>
        </ElFormItem>
      </ElForm>

      <template #footer>
        <div class="dialog-footer">
          <ElButton @click="showNoticeDialog = false">取消</ElButton>
          <ElButton
            type="primary"
            :loading="savingNotice"
            :disabled="ui.readOnly"
            @click="handleSaveNotice"
          >
            保存并立即向前台广播
          </ElButton>
        </div>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.system-notice-page {
  padding: 24px 32px;
  max-width: 1440px;
  margin: 0 auto;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
}

.header-section {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 2px;
}

.title {
  margin: 0 0 4px;
  font-size: 20px;
  font-weight: 700;
  color: var(--a-text, #1e293b);
}

.subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--a-text-2, #64748b);
  line-height: 1.5;
}

.flex-align {
  display: flex;
  align-items: center;
  gap: 8px;
}

.current-label {
  font-size: 12px;
  color: var(--a-text-2, #64748b);
}

/* 卡片通用架构 */
.cards-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

@media (max-width: 960px) {
  .cards-grid {
    grid-template-columns: 1fr;
  }
}

.module-card {
  background: var(--a-card, #ffffff);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: var(--a-radius, 12px);
  box-shadow: var(--a-shadow, 0 1px 3px rgba(0, 0, 0, 0.05));
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
  overflow: hidden;
}

.module-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
}

.card--danger {
  border-color: rgba(239, 68, 68, 0.4);
  background: linear-gradient(180deg, rgba(254, 242, 242, 0.5) 0%, var(--a-card, #ffffff) 100%);
}

.card--active {
  border-color: rgba(14, 165, 233, 0.4);
}

.card-top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--a-border, #e2e8f0);
}

.card-title-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.card-icon-box {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.icon-box--primary {
  background: rgba(14, 165, 233, 0.12);
  color: #0284c7;
}

.icon-box--danger {
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
}

.icon-box--success {
  background: rgba(16, 185, 129, 0.12);
  color: #10b981;
}

.icon-box--info {
  background: rgba(100, 116, 139, 0.12);
  color: #64748b;
}

.card-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--a-text, #1e293b);
  line-height: 1.3;
}

.card-subtitle {
  font-size: 12px;
  color: var(--a-text-2, #64748b);
  margin-top: 2px;
}

.status-tag {
  font-weight: 600;
}

/* 卡片内容信息网格 */
.card-body-section {
  padding: 18px 20px;
}

.info-pill-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.info-pill-item {
  background: var(--el-fill-color-light, #f8fafc);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: 8px;
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.pill-full {
  grid-column: span 2;
}

.pill-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--a-text-2, #64748b);
}

.pill-value-switch {
  display: flex;
  align-items: center;
}

.pill-text-truncate {
  font-size: 12px;
  color: var(--a-text, #1e293b);
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-footer-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: var(--el-fill-color-extra-light, #fafafa);
  border-top: 1px solid var(--a-border, #e2e8f0);
}

.footer-hint {
  font-size: 12px;
  color: var(--a-text-2, #64748b);
}

.card-footer-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* 广播发布方式矩阵 */
.channel-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  padding: 20px;
}

@media (max-width: 1024px) {
  .channel-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 640px) {
  .channel-grid {
    grid-template-columns: 1fr;
  }
}

.channel-box {
  background: var(--el-fill-color-light, #f8fafc);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: 10px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 12px;
}

.channel-box:hover {
  border-color: #0284c7;
  background: #f0f9ff;
  transform: translateY(-2px);
}

.channel-box--active {
  border-color: #0284c7;
  background: #f0f9ff;
  box-shadow: 0 0 0 1px #0284c7;
}

.channel-box-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.channel-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.channel-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--a-text, #1e293b);
}

.channel-tag {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(2, 132, 199, 0.1);
  color: #0284c7;
}

.channel-active-indicator {
  font-size: 11px;
  font-weight: 700;
  color: #10b981;
  background: rgba(16, 185, 129, 0.12);
  padding: 2px 8px;
  border-radius: 12px;
}

.channel-desc {
  font-size: 12px;
  line-height: 1.5;
  color: var(--a-text-2, #64748b);
  margin: 0;
}

.channel-features {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.feature-chip {
  font-size: 10px;
  color: var(--a-text-2, #64748b);
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid var(--a-border, #e2e8f0);
  padding: 2px 6px;
  border-radius: 4px;
}

/* 实时模拟沙盒 */
.sandbox-card {
  margin-top: 4px;
}

.sandbox-tabs {
  display: flex;
  align-items: center;
}

.sandbox-stage {
  padding: 20px;
  background: #0f172a;
  border-radius: 0 0 var(--a-radius, 12px) var(--a-radius, 12px);
  min-height: 320px;
  display: flex;
  flex-direction: column;
}

.stage-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
}

.view-intro {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.view-tag {
  font-size: 11px;
  font-weight: 700;
  color: #38bdf8;
  background: rgba(56, 189, 248, 0.15);
  padding: 2px 8px;
  border-radius: 4px;
}

.view-desc {
  font-size: 12px;
  color: #94a3b8;
}

/* 模拟页面的背景线框 */
.fake-page-content {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 10px;
}

.fake-nav-line {
  height: 24px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
  width: 100%;
}

.fake-banner-card {
  height: 90px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.02) 100%);
  border-radius: 8px;
}

.fake-grid-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.fake-card {
  height: 80px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 6px;
}

/* 顶部常驻横幅模拟 */
.preview-header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 18px;
  border-radius: 8px;
  font-size: 13px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.preview-bar--info {
  background: #075985;
  color: #f0f9ff;
}

.preview-bar--warning {
  background: #854d0e;
  color: #fefce8;
}

.preview-bar--danger {
  background: #991b1b;
  color: #fef2f2;
}

.preview-bar-inner {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.preview-bar-tag {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.2);
}

.preview-bar-title {
  font-weight: 700;
}

.preview-bar-sep {
  opacity: 0.5;
}

.preview-bar-content {
  opacity: 0.95;
}

.preview-bar-action {
  font-size: 12px;
  font-weight: 600;
  text-decoration: underline;
  cursor: pointer;
  margin-left: 8px;
}

.preview-bar-close {
  cursor: pointer;
  opacity: 0.7;
}

/* 跑马灯模拟 */
.marquee-preview-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 13px;
  overflow: hidden;
}

.marquee--info {
  background: linear-gradient(90deg, #0369a1 0%, #0284c7 100%);
  color: #ffffff;
}

.marquee--warning {
  background: linear-gradient(90deg, #b45309 0%, #d97706 100%);
  color: #ffffff;
}

.marquee--danger {
  background: linear-gradient(90deg, #b91c1c 0%, #dc2626 100%);
  color: #ffffff;
}

.marquee-badge {
  font-size: 11px;
  font-weight: 700;
  background: rgba(0, 0, 0, 0.25);
  padding: 2px 8px;
  border-radius: 4px;
  white-space: nowrap;
}

.marquee-viewport {
  flex: 1;
  overflow: hidden;
  white-space: nowrap;
}

.marquee-track {
  display: inline-block;
  animation: roll 16s linear infinite;
}

@keyframes roll {
  0% { transform: translateX(100%); }
  100% { transform: translateX(-100%); }
}

.marquee-action-fake {
  font-size: 11px;
  font-weight: 600;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.3);
  padding: 2px 8px;
  border-radius: 4px;
  cursor: pointer;
}

.marquee-close-fake {
  cursor: pointer;
  opacity: 0.8;
}

/* 弹窗模拟 */
.modal-preview-stage {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 30px 16px;
  background: rgba(0, 0, 0, 0.4);
  border-radius: 10px;
}

.modal-box {
  width: 100%;
  max-width: 380px;
  background: #14171f;
  backdrop-filter: blur(16px);
  border-radius: 14px;
  padding: 20px;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.7);
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.modal--info {
  border: 1px solid rgba(56, 189, 248, 0.35);
}

.modal--warning {
  border: 1px solid rgba(245, 158, 11, 0.35);
}

.modal--danger {
  border: 1px solid rgba(239, 68, 68, 0.45);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.modal-level-badge {
  font-size: 10px;
  font-weight: 800;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.12);
  color: #ffffff;
}

.modal-title {
  font-size: 15px;
  font-weight: 700;
  color: #ffffff;
}

.modal-x {
  font-size: 13px;
  color: #94a3b8;
  cursor: pointer;
}

.modal-content {
  font-size: 13px;
  color: #cbd5e1;
  line-height: 1.5;
  background: rgba(255, 255, 255, 0.04);
  padding: 14px;
  border-radius: 8px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
}

.modal-action-fake {
  font-size: 12px;
  font-weight: 600;
  color: #ffffff;
  background: rgba(255, 255, 255, 0.1);
  padding: 6px 14px;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  cursor: pointer;
}

.modal-btn-fake {
  background: #e50914;
  color: #ffffff;
  font-size: 12px;
  font-weight: 600;
  padding: 6px 16px;
  border-radius: 4px;
  cursor: pointer;
}

/* 悬浮气泡卡片模拟 */
.float-preview-container {
  position: relative;
  min-height: 240px;
}

.float-preview-capsule {
  position: absolute;
  right: 16px;
  bottom: 16px;
  width: 320px;
  background: #14171f;
  border-radius: 12px;
  padding: 14px 16px;
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.6);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.float--info {
  border: 1px solid rgba(56, 189, 248, 0.35);
}

.float--warning {
  border: 1px solid rgba(245, 158, 11, 0.35);
}

.float--danger {
  border: 1px solid rgba(239, 68, 68, 0.45);
}

.float-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.float-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.float-badge {
  font-size: 9px;
  font-weight: 700;
  background: rgba(255, 255, 255, 0.1);
  color: #94a3b8;
  padding: 2px 6px;
  border-radius: 4px;
}

.float-title {
  font-size: 13px;
  font-weight: 700;
  color: #f8fafc;
}

.float-close {
  color: #64748b;
  font-size: 12px;
  cursor: pointer;
}

.float-body {
  font-size: 12px;
  line-height: 1.4;
  color: #cbd5e1;
}

.float-footer {
  display: flex;
  justify-content: flex-end;
}

.float-btn-fake {
  font-size: 11px;
  font-weight: 600;
  color: #38bdf8;
  background: rgba(56, 189, 248, 0.1);
  padding: 3px 10px;
  border-radius: 4px;
  border: 1px solid rgba(56, 189, 248, 0.2);
  cursor: pointer;
}

/* 锁屏模拟 */
.lock-preview-stage {
  background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  padding: 32px 20px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 240px;
}

.lock-icon-halo {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #f87171;
  margin-bottom: 12px;
}

.lock-spin-icon {
  animation: spin-slow 8s linear infinite;
}

@keyframes spin-slow {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.lock-title {
  font-family: monospace;
  font-size: 12px;
  letter-spacing: 2px;
  color: #94a3b8;
  margin-bottom: 4px;
}

.lock-badge {
  font-size: 17px;
  font-weight: 700;
  color: #f8fafc;
  margin-bottom: 8px;
}

.lock-message {
  font-size: 13px;
  color: #cbd5e1;
  line-height: 1.5;
  margin-bottom: 18px;
  max-width: 380px;
}

.lock-actions {
  display: flex;
  gap: 10px;
}

.lock-btn-fake {
  font-size: 12px;
  font-weight: 600;
  color: #ffffff;
  background: #e50914;
  padding: 6px 18px;
  border-radius: 6px;
}

.lock-btn-sub {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: #cbd5e1;
}

/* 弹窗表单样式 */
.dialog-switch-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--el-fill-color-light, #f8fafc);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: 8px;
  padding: 12px 16px;
  width: 100%;
  box-sizing: border-box;
}

.switch-row-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--a-text, #1e293b);
}

.switch-row-desc {
  font-size: 11px;
  color: var(--a-text-2, #64748b);
  margin-top: 2px;
}

.template-btns-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.dialog-radio-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  width: 100%;
}

.dialog-radio-item {
  margin-right: 0 !important;
  width: 100%;
  box-sizing: border-box;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
