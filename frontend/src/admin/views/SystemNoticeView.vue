<script setup lang="ts">
/**
 * 全站公告发布与紧急停服维护模式控制：
 * 1. 紧急维护模式：一键开启全站维护、自定义维护理由文案、自动放行后台管理端；
 * 2. 全站公告：顶部横幅 / 首次弹窗 / 告警级别设置，附带右侧所见即所得前台实时预览。
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
  ElRow,
  ElSelect,
  ElSwitch,
  ElTag,
} from 'element-plus'
import {
  Promotion,
  Refresh,
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
  title: '',
  content: '',
  level: 'info',
  display_type: 'banner',
  dismissible: true,
  updated_at: '',
})

const maintForm = ref<SystemMaintenancePayload>({
  enabled: false,
  message: '系统正在进行维护升级，预计稍后恢复，请耐心等待。',
  allow_admin: true,
  updated_at: '',
})

async function loadData(): Promise<void> {
  loading.value = true
  try {
    const [n, m] = await Promise.all([getSystemNotice(), getSystemMaintenance()])
    noticeForm.value = n
    maintForm.value = m
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '加载系统配置失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadData()
})

async function handleSaveNotice(): Promise<void> {
  savingNotice.value = true
  try {
    const res = await updateSystemNotice(noticeForm.value)
    noticeForm.value = res
    ElMessage.success('全站公告配置已更新并生效')
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '保存公告失败')
  } finally {
    savingNotice.value = false
  }
}

async function handleToggleMaintenance(): Promise<void> {
  const willEnable = maintForm.value.enabled
  if (willEnable) {
    try {
      await ElMessageBox.confirm(
        '开启维护模式后，除后台管理端外，所有普通用户接口均将被拦截并提示维护文案。确定开启吗？',
        '开启维护模式警告',
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
    ElMessage.success(res.enabled ? '已开启全站紧急维护模式' : '已关闭维护模式，前台服务恢复正常')
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '修改维护模式失败')
  } finally {
    savingMaint.value = false
  }
}
</script>

<template>
  <div class="system-view">
    <div class="header-section">
      <div>
        <h2 class="title">系统公告与维护广播</h2>
        <p class="subtitle">
          配置全站通知横幅、首次强弹窗公告，或在服务器紧急割接/升级时一键开启停服维护模式。
        </p>
      </div>
      <ElButton :icon="Refresh" :loading="loading" @click="loadData">刷新状态</ElButton>
    </div>

    <!-- 紧急停服维护模式卡片 -->
    <ElCard
      shadow="hover"
      class="maint-card"
      :class="{ 'maint-card--active': maintForm.enabled }"
    >
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <ElTag :type="maintForm.enabled ? 'danger' : 'success'" effect="dark">
              {{ maintForm.enabled ? '维护模式生效中' : '正常对外服务' }}
            </ElTag>
            <span class="header-title">紧急停服维护模式</span>
          </div>
          <ElSwitch
            v-model="maintForm.enabled"
            :disabled="ui.readOnly || savingMaint"
            active-text="开启维护"
            inactive-text="正常运行"
            @change="handleToggleMaintenance"
          />
        </div>
      </template>

      <div class="maint-body">
        <p class="maint-desc">
          开启维护后，前台用户访问任何站点/首页/列表/播放均会友好展示维护页面；
          <strong>管理后台（当前页面）始终保持白名单放行</strong>，方便运维人员继续操作。
        </p>
        <ElForm :model="maintForm" label-position="top">
          <ElFormItem label="展示给用户的维护文案">
            <ElInput
              v-model="maintForm.message"
              type="textarea"
              :rows="2"
              placeholder="请输入维护提示文案..."
              :disabled="ui.readOnly"
            />
          </ElFormItem>
          <ElButton
            v-if="maintForm.enabled"
            type="primary"
            size="small"
            :loading="savingMaint"
            :disabled="ui.readOnly"
            @click="handleToggleMaintenance"
          >
            更新维护文案
          </ElButton>
        </ElForm>
      </div>
    </ElCard>

    <!-- 全站公告设置 -->
    <ElRow :gutter="16">
      <ElCol :xs="24" :md="13">
        <ElCard shadow="never" class="notice-card">
          <template #header>
            <div class="card-header">
              <span class="header-title">全站公告发布配置</span>
              <ElSwitch
                v-model="noticeForm.enabled"
                :disabled="ui.readOnly"
                active-text="启用公告"
                inactive-text="关闭"
              />
            </div>
          </template>

          <ElForm :model="noticeForm" label-position="top">
            <ElFormItem label="公告标题" required>
              <ElInput
                v-model="noticeForm.title"
                placeholder="如：国庆假期影视更新通知"
                :disabled="ui.readOnly"
              />
            </ElFormItem>

            <ElFormItem label="公告正文内容" required>
              <ElInput
                v-model="noticeForm.content"
                type="textarea"
                :rows="4"
                placeholder="详细通知正文..."
                :disabled="ui.readOnly"
              />
            </ElFormItem>

            <ElRow :gutter="12">
              <ElCol :span="12">
                <ElFormItem label="通知级别">
                  <ElSelect v-model="noticeForm.level" :disabled="ui.readOnly" style="width: 100%">
                    <ElOption label="一般提示 (info)" value="info" />
                    <ElOption label="注意警告 (warning)" value="warning" />
                    <ElOption label="紧急通告 (danger)" value="danger" />
                  </ElSelect>
                </ElFormItem>
              </ElCol>

              <ElCol :span="12">
                <ElFormItem label="展示形式">
                  <ElSelect v-model="noticeForm.display_type" :disabled="ui.readOnly" style="width: 100%">
                    <ElOption label="顶部横幅条 (banner)" value="banner" />
                    <ElOption label="居中强弹窗 (modal)" value="modal" />
                    <ElOption label="两者兼具 (both)" value="both" />
                  </ElSelect>
                </ElFormItem>
              </ElCol>
            </ElRow>

            <ElFormItem label="允许用户手动关闭">
              <ElSwitch v-model="noticeForm.dismissible" :disabled="ui.readOnly" />
            </ElFormItem>

            <ElFormItem>
              <ElButton
                type="primary"
                :icon="Promotion"
                :loading="savingNotice"
                :disabled="ui.readOnly"
                @click="handleSaveNotice"
              >
                保存并发布全站
              </ElButton>
            </ElFormItem>
          </ElForm>
        </ElCard>
      </ElCol>

      <!-- 右侧：前台实时预览模拟器 -->
      <ElCol :xs="24" :md="11">
        <ElCard shadow="never" class="preview-card">
          <template #header>
            <div class="card-header">
              <span class="header-title">前台用户端展示模拟</span>
              <ElTag size="small" type="info">实时渲染</ElTag>
            </div>
          </template>

          <div class="mock-device">
            <div class="mock-bar">
              <span class="mock-dot" />
              <span class="mock-dot" />
              <span class="mock-dot" />
              <span class="mock-url">https://plove.tv/home</span>
            </div>

            <div class="mock-content">
              <div v-if="noticeForm.enabled">
                <!-- Banner 模式模拟 -->
                <div
                  v-if="noticeForm.display_type === 'banner' || noticeForm.display_type === 'both'"
                  class="mock-banner"
                  :class="`mock-banner--${noticeForm.level}`"
                >
                  <div class="banner-body">
                    <strong>{{ noticeForm.title || '（标题）' }}</strong>
                    <span>: {{ noticeForm.content || '（内容文案）' }}</span>
                  </div>
                  <span v-if="noticeForm.dismissible" class="banner-close">&times;</span>
                </div>

                <!-- 弹窗模式模拟 -->
                <div
                  v-if="noticeForm.display_type === 'modal' || noticeForm.display_type === 'both'"
                  class="mock-modal-overlay"
                >
                  <div class="mock-modal">
                    <div class="modal-head" :class="`modal-head--${noticeForm.level}`">
                      <span>{{ noticeForm.title || '系统公告' }}</span>
                    </div>
                    <div class="modal-body">
                      {{ noticeForm.content || '这里将显示公告具体正文内容。' }}
                    </div>
                    <div class="modal-foot">
                      <button class="mock-btn">我知道了</button>
                    </div>
                  </div>
                </div>

                <div class="mock-page-stub">
                  <div class="stub-line stub-line--title" />
                  <div class="stub-grid">
                    <div class="stub-card" />
                    <div class="stub-card" />
                    <div class="stub-card" />
                  </div>
                </div>
              </div>

              <div v-else class="mock-disabled">
                <p>当前未开启全站公告</p>
                <span class="a-muted">开启并在左侧编辑后，此处将实时展示用户端视觉效果</span>
              </div>
            </div>
          </div>
        </ElCard>
      </ElCol>
    </ElRow>
  </div>
</template>

<style scoped>
.system-view {
  max-width: 1440px;
  margin: 0 auto;
  padding: 24px 32px 64px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.header-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  padding: 20px 24px;
  background: var(--a-card, #ffffff);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: var(--a-radius, 8px);
  box-shadow: var(--a-shadow-xs, 0 1px 3px rgba(0, 0, 0, 0.05));
}

.title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--a-text, #1e293b);
  letter-spacing: -0.01em;
}

.subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--a-text-2, #64748b);
}

.maint-card {
  border-radius: 8px;
  border-left: 4px solid var(--el-color-success);
}

.maint-card--active {
  border-left-color: var(--el-color-danger);
  background: var(--el-color-danger-light-9);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-title {
  font-weight: 600;
  font-size: 15px;
}

.maint-desc {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-top: 0;
}

.notice-card,
.preview-card {
  border-radius: 8px;
}

.mock-device {
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.mock-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: var(--el-fill-color-light);
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.mock-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--el-text-color-placeholder);
}

.mock-url {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-left: 6px;
}

.mock-content {
  padding: 16px;
  min-height: 320px;
  position: relative;
}

.mock-banner {
  padding: 8px 12px;
  border-radius: 4px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  margin-bottom: 16px;
}

.mock-banner--info {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}

.mock-banner--warning {
  background: var(--el-color-warning-light-9);
  color: var(--el-color-warning-dark-2);
}

.mock-banner--danger {
  background: var(--el-color-danger-light-9);
  color: var(--el-color-danger);
}

.banner-close {
  cursor: pointer;
  opacity: 0.6;
}

.mock-modal-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
  backdrop-filter: blur(2px);
}

.mock-modal {
  background: var(--el-bg-color);
  border-radius: 8px;
  width: 80%;
  max-width: 280px;
  overflow: hidden;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
}

.modal-head {
  padding: 10px 14px;
  font-weight: 700;
  font-size: 13px;
}

.modal-head--info {
  background: var(--el-color-primary);
  color: #fff;
}

.modal-head--warning {
  background: var(--el-color-warning);
  color: #fff;
}

.modal-head--danger {
  background: var(--el-color-danger);
  color: #fff;
}

.modal-body {
  padding: 14px;
  font-size: 12px;
  color: var(--el-text-color-regular);
  line-height: 1.5;
}

.modal-foot {
  padding: 8px 14px;
  text-align: right;
  border-top: 1px solid var(--el-border-color-lighter);
}

.mock-btn {
  background: var(--el-color-primary);
  color: #fff;
  border: none;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 11px;
}

.mock-page-stub {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stub-line--title {
  width: 40%;
  height: 16px;
  background: var(--el-fill-color);
  border-radius: 4px;
}

.stub-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.stub-card {
  height: 80px;
  background: var(--el-fill-color);
  border-radius: 6px;
}

.mock-disabled {
  text-align: center;
  padding: 60px 0;
  color: var(--el-text-color-placeholder);
  font-size: 13px;
}
</style>
