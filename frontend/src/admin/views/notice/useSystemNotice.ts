import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getSystemMaintenance,
  getSystemNotice,
  updateSystemMaintenance,
  updateSystemNotice,
} from '@/admin/api'
import type { SystemMaintenancePayload, SystemNoticePayload } from '@/api/types'

// 公告发布方式定义列表
export const displayTypeOptions = [
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

export type DisplayType = typeof displayTypeOptions[number]['type']
export type PreviewTab = 'header_bar' | 'banner' | 'modal' | 'float' | 'maintenance'

export function useSystemNotice() {
  const loading = ref(false)
  const savingNotice = ref(false)
  const savingMaint = ref(false)

  // 弹窗控制
  const showMaintDialog = ref(false)
  const showNoticeDialog = ref(false)

  // 当前沙盒激活 Tab
  const activePreviewTab = ref<PreviewTab>('header_bar')

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

  function selectDisplayType(type: DisplayType): void {
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

  return {
    loading,
    savingNotice,
    savingMaint,
    showMaintDialog,
    showNoticeDialog,
    activePreviewTab,
    noticeForm,
    maintForm,
    displayTypeOptions,
    currentDisplayOption,
    loadData,
    handleSaveNotice,
    handleQuickToggleNotice,
    handleSaveMaintenance,
    handleQuickToggleMaintenance,
    selectDisplayType,
    applyMaintTemplate,
    applyNoticeTemplate,
  }
}
