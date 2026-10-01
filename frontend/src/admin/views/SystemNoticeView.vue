<script setup lang="ts">
/**
 * 全站公告发布与维护广播总控中心：
 * 1. 停机维护闸门控制（带 1:1 前台锁屏预览）；
 * 2. 大厅重要通知强弹窗 Modal（带 1:1 Netflix 风格半透明磨砂弹窗预览）；
 * 3. 顶部滚动跑马灯 Ticker（带 1:1 动态走字跑马灯预览）。
 */
import {
  ElButton,
  ElCard,
  ElCol,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElRadio,
  ElRadioGroup,
  ElRow,
  ElSelect,
  ElSwitch,
  ElTag,
} from 'element-plus'
import {
  Bell,
  Check,
  Refresh,
  Tools,
  View,
} from '@element-plus/icons-vue'
import { onMounted, ref } from 'vue'

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

const noticeForm = ref<SystemNoticePayload>({
  enabled: false,
  title: '🎉 Plove 影视全新升级公告',
  content: '尊敬的用户，我们已全面优化了蓝光秒播解析核心与全站海报防盗链加速通道。享受极致视听盛宴！',
  level: 'info',
  display_type: 'both',
  dismissible: true,
  updated_at: '',
})

const maintForm = ref<SystemMaintenancePayload>({
  enabled: false,
  message: '尊敬的用户：为了提供更优质的超清流媒体服务，系统正在进行机房网络升级，预计 30 分钟内完成，感谢您的理解与支持！',
  allow_admin: true,
  updated_at: '',
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
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '保存公告配置失败')
  } finally {
    savingNotice.value = false
  }
}

async function handleToggleMaintenance(): Promise<void> {
  const willEnable = maintForm.value.enabled
  if (willEnable) {
    try {
      await ElMessageBox.confirm(
        '开启维护模式后，除后台管理端外，所有普通前台用户均将被即刻拦截并展示维护锁屏。确定开启吗？',
        '开启紧急维护警告',
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
        ? '已开启【全站紧急维护】：前台已全部拦截并进入维护状态！'
        : '已解除维护模式，前台服务恢复正常对外开放！'
    )
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '保存维护设置失败')
  } finally {
    savingMaint.value = false
  }
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
          统筹管理前台全站运行闸门。可一键开启全站停机维护，或发布前台大厅弹窗、顶部滚动跑马灯通知，所有配置即时同步。
        </p>
      </div>
      <div class="header-actions">
        <ElButton :icon="Refresh" :loading="loading" @click="loadData">刷新状态</ElButton>
      </div>
    </div>

    <!-- 场景 1: 停机维护闸门控制卡片 -->
    <ElCard
      shadow="hover"
      class="card-glow maint-card"
      :class="{ 'maint-card--danger': maintForm.enabled }"
    >
      <template #header>
        <div class="card-header-flex">
          <div class="flex-align">
            <span class="status-indicator" :class="maintForm.enabled ? 'indicator-red' : 'indicator-green'" />
            <span class="header-title">场景 1：全站停服维护闸门 (Maintenance Gateway)</span>
          </div>
          <div class="flex-align">
            <ElTag :type="maintForm.enabled ? 'danger' : 'success'" effect="dark">
              {{ maintForm.enabled ? '⚠️ 全站维护模式生效中（前台已阻断）' : '✅ 正常对外服务运营中' }}
            </ElTag>
            <ElSwitch
              v-model="maintForm.enabled"
              :disabled="ui.readOnly || savingMaint"
              active-text="开启维护"
              inactive-text="关闭"
              @change="handleToggleMaintenance"
            />
          </div>
        </div>
      </template>

      <div class="maint-body-grid">
        <div class="maint-form-col">
          <p class="desc-text">
            开启维护后，前台用户访问任何站点/首页/列表/播放均会展示沉浸式维护页面；
            <strong>当前管理后台（/admin）受到白名单保护，持续放行</strong>。
          </p>

          <ElForm :model="maintForm" label-position="top">
            <ElFormItem label="展示给用户的维护原因与预计恢复时间">
              <ElInput
                v-model="maintForm.message"
                type="textarea"
                :rows="3"
                placeholder="请输入维护告示文案..."
                :disabled="ui.readOnly"
              />
            </ElFormItem>

            <div class="form-action-row">
              <ElButton
                type="danger"
                :loading="savingMaint"
                :disabled="ui.readOnly"
                @click="handleToggleMaintenance"
              >
                保存维护文案并应用
              </ElButton>
              <span v-if="maintForm.updated_at" class="timestamp-hint">
                更新时间：{{ maintForm.updated_at }}
              </span>
            </div>
          </ElForm>
        </div>

        <!-- 1:1 前台维护锁屏预览 -->
        <div class="maint-preview-col">
          <div class="preview-label">
            <el-icon><View /></el-icon> 前台锁屏 1:1 视觉预览
          </div>
          <div class="lock-preview-stage">
            <div class="lock-icon-halo">
              <el-icon :size="32" class="lock-spin-icon"><Tools /></el-icon>
            </div>
            <div class="lock-title">SYSTEM MAINTENANCE</div>
            <div class="lock-badge">系统升级维护中</div>
            <div class="lock-message">
              {{ maintForm.message || '系统维护中，请稍后访问...' }}
            </div>
            <div class="lock-btn-fake">刷新页面尝试</div>
          </div>
        </div>
      </div>
    </ElCard>

    <!-- 场景 2 & 场景 3: 广播公告发布与实时预览 -->
    <div class="notice-workspace-grid">
      <!-- 左列：配置表单卡片 -->
      <ElCard shadow="never" class="card-glow config-card">
        <template #header>
          <div class="card-header-flex">
            <div class="flex-align">
              <el-icon><Bell /></el-icon>
              <span class="header-title">前台全站广播发布配置</span>
            </div>
            <ElSwitch
              v-model="noticeForm.enabled"
              :disabled="ui.readOnly"
              active-text="广播生效中"
              inactive-text="关闭广播"
            />
          </div>
        </template>

        <ElForm :model="noticeForm" label-position="top" class="notice-form">
          <ElRow :gutter="16">
            <ElCol :xs="24" :sm="14">
              <ElFormItem label="公告主标题">
                <ElInput
                  v-model="noticeForm.title"
                  placeholder="如：🎉 影视库全新升级通知"
                  :disabled="ui.readOnly"
                />
              </ElFormItem>
            </ElCol>
            <ElCol :xs="24" :sm="10">
              <ElFormItem label="广播紧急级别">
                <ElSelect v-model="noticeForm.level" style="width: 100%" :disabled="ui.readOnly">
                  <ElOption label="💡 提示（默认蓝色/绿色）" value="info" />
                  <ElOption label="⚠️ 警告（琥珀色注意）" value="warning" />
                  <ElOption label="🚨 紧急（红色重点通知）" value="danger" />
                </ElSelect>
              </ElFormItem>
            </ElCol>
          </ElRow>

          <ElFormItem label="前台展示场景与形式">
            <ElRadioGroup v-model="noticeForm.display_type" :disabled="ui.readOnly">
              <ElRadio value="both" border>两者兼具（弹窗 + 跑马灯）</ElRadio>
              <ElRadio value="modal" border>大厅首次重要弹窗 Modal</ElRadio>
              <ElRadio value="banner" border>顶部滚动走字跑马灯</ElRadio>
            </ElRadioGroup>
          </ElFormItem>

          <ElFormItem label="公告详细正文内容">
            <ElInput
              v-model="noticeForm.content"
              type="textarea"
              :rows="4"
              placeholder="请输入公告详细内容..."
              :disabled="ui.readOnly"
            />
          </ElFormItem>

          <ElRow :gutter="16">
            <ElCol :xs="24" :sm="12">
              <div class="switch-box-mini">
                <div class="switch-info-mini">
                  <div class="switch-title-mini">允许用户点击关闭</div>
                  <div class="switch-desc-mini">关闭后不再遮挡前台界面</div>
                </div>
                <ElSwitch v-model="noticeForm.dismissible" :disabled="ui.readOnly" />
              </div>
            </ElCol>
          </ElRow>

          <div class="form-action-row" style="margin-top: 16px;">
            <ElButton
              type="primary"
              :icon="Check"
              :loading="savingNotice"
              :disabled="ui.readOnly"
              @click="handleSaveNotice"
            >
              保存并立即向前台广播
            </ElButton>
            <span v-if="noticeForm.updated_at" class="timestamp-hint">
              最后发布：{{ noticeForm.updated_at }}
            </span>
          </div>
        </ElForm>
      </ElCard>

      <!-- 右列：1:1 所见即所得视觉预览卡片 -->
      <ElCard shadow="never" class="card-glow preview-card">
        <template #header>
          <div class="card-header-flex">
            <div class="flex-align">
              <el-icon><View /></el-icon>
              <span class="header-title">前台视觉所见即所得实时预览</span>
            </div>
            <ElTag size="small" effect="plain" type="info">实时响应</ElTag>
          </div>
        </template>

        <div class="preview-container">
          <!-- 跑马灯预览 -->
          <div class="preview-block">
            <div class="preview-block-title">
              1. 顶部跑马灯条幅预览
              <span v-if="noticeForm.display_type === 'modal'" class="off-tag">(当前配置未开启)</span>
            </div>
            <div
              class="marquee-preview-bar"
              :class="`marquee--${noticeForm.level}`"
              :style="{ opacity: noticeForm.display_type === 'modal' ? 0.3 : 1 }"
            >
              <div class="marquee-icon">📢</div>
              <div class="marquee-content-scroller">
                <span class="marquee-text">
                  <strong>【{{ noticeForm.title || '系统广播' }}】</strong>
                  {{ noticeForm.content || '暂无广播内容' }}
                </span>
              </div>
              <div v-if="noticeForm.dismissible" class="marquee-close">✕</div>
            </div>
          </div>

          <!-- 弹窗预览 -->
          <div class="preview-block">
            <div class="preview-block-title">
              2. 大厅首次重要弹窗 Modal 预览
              <span v-if="noticeForm.display_type === 'banner'" class="off-tag">(当前配置未开启)</span>
            </div>
            <div
              class="modal-preview-stage"
              :style="{ opacity: noticeForm.display_type === 'banner' ? 0.3 : 1 }"
            >
              <div class="modal-box" :class="`modal--${noticeForm.level}`">
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
                  <div class="modal-btn">我知道了</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </ElCard>
    </div>
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
  gap: 16px;
  width: 100%;
}

.header-section {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 4px;
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

.card-glow {
  background: var(--a-card, #ffffff);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: var(--a-radius, 8px);
  box-shadow: var(--a-shadow, 0 1px 3px rgba(0, 0, 0, 0.05));
}

.card-header-flex {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.flex-align {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--a-text, #1e293b);
}

.status-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.indicator-green {
  background: #10b981;
  box-shadow: 0 0 6px #10b981;
}

.indicator-red {
  background: #ef4444;
  box-shadow: 0 0 8px #ef4444;
  animation: pulse-red 1.5s infinite;
}

@keyframes pulse-red {
  0% { transform: scale(0.95); opacity: 0.8; }
  50% { transform: scale(1.2); opacity: 1; }
  100% { transform: scale(0.95); opacity: 0.8; }
}

/* 维护闸门网格 */
.maint-card--danger {
  border-color: rgba(239, 68, 68, 0.4);
  background: #fff5f5;
}

.maint-body-grid {
  display: grid;
  grid-template-columns: 1fr 340px;
  gap: 24px;
}

@media (max-width: 900px) {
  .maint-body-grid {
    grid-template-columns: 1fr;
  }
}

.desc-text {
  font-size: 13px;
  color: var(--a-text-2, #64748b);
  line-height: 1.5;
  margin-top: 0;
  margin-bottom: 14px;
}

.form-action-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.timestamp-hint {
  font-size: 12px;
  color: var(--a-text-2, #64748b);
}

/* 锁屏预览 stage */
.maint-preview-col {
  display: flex;
  flex-direction: column;
}

.preview-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--a-text-2, #64748b);
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.lock-preview-stage {
  background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: 10px;
  padding: 24px 20px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 220px;
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
  font-size: 16px;
  font-weight: 700;
  color: #f8fafc;
  margin-bottom: 8px;
}

.lock-message {
  font-size: 12px;
  color: #cbd5e1;
  line-height: 1.4;
  margin-bottom: 16px;
  max-width: 280px;
}

.lock-btn-fake {
  font-size: 11px;
  font-weight: 600;
  color: #e2e8f0;
  background: rgba(255, 255, 255, 0.1);
  padding: 5px 14px;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

/* 广播工作区网格 */
.notice-workspace-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

@media (max-width: 1024px) {
  .notice-workspace-grid {
    grid-template-columns: 1fr;
  }
}

.switch-box-mini {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--el-fill-color-light, #f8fafc);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: 8px;
  padding: 12px 16px;
}

.switch-title-mini {
  font-size: 13px;
  font-weight: 600;
  color: var(--a-text, #1e293b);
}

.switch-desc-mini {
  font-size: 11px;
  color: var(--a-text-2, #64748b);
}

/* 实时预览容器 */
.preview-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.preview-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.preview-block-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--a-text, #1e293b);
}

.off-tag {
  color: #64748b;
  font-size: 11px;
  font-weight: normal;
  margin-left: 6px;
}

/* 跑马灯条幅预览 */
.marquee-preview-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 13px;
  overflow: hidden;
  transition: opacity 0.3s ease;
}

.marquee--info {
  background: rgba(14, 165, 233, 0.15);
  border: 1px solid rgba(14, 165, 233, 0.3);
  color: #38bdf8;
}

.marquee--warning {
  background: rgba(245, 158, 11, 0.15);
  border: 1px solid rgba(245, 158, 11, 0.3);
  color: #fbbf24;
}

.marquee--danger {
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #f87171;
}

.marquee-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.marquee-content-scroller {
  flex: 1;
  overflow: hidden;
  white-space: nowrap;
}

.marquee-text {
  display: inline-block;
  animation: marquee-roll 15s linear infinite;
}

@keyframes marquee-roll {
  0% { transform: translateX(100%); }
  100% { transform: translateX(-100%); }
}

.marquee-close {
  cursor: pointer;
  opacity: 0.7;
}

/* 弹窗预览 */
.modal-preview-stage {
  background: rgba(0, 0, 0, 0.5);
  border-radius: 10px;
  padding: 30px 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 240px;
  transition: opacity 0.3s ease;
}

.modal-box {
  width: 100%;
  max-width: 360px;
  background: #14171f;
  backdrop-filter: blur(16px);
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 16px 36px rgba(0, 0, 0, 0.7);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.modal--info {
  border: 1px solid rgba(56, 189, 248, 0.4);
}

.modal--warning {
  border: 1px solid rgba(245, 158, 11, 0.4);
}

.modal--danger {
  border: 1px solid rgba(239, 68, 68, 0.4);
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
  background: rgba(255, 255, 255, 0.1);
  color: #ffffff;
}

.modal-title {
  font-size: 15px;
  font-weight: 700;
  color: #ffffff;
}

.modal-x {
  font-size: 12px;
  color: #64748b;
  cursor: pointer;
}

.modal-content {
  font-size: 13px;
  color: #cbd5e1;
  line-height: 1.5;
  background: rgba(255, 255, 255, 0.03);
  padding: 12px;
  border-radius: 8px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
}

.modal-btn {
  background: #e50914;
  color: #ffffff;
  font-size: 12px;
  font-weight: 600;
  padding: 6px 16px;
  border-radius: 4px;
  cursor: pointer;
}
</style>
