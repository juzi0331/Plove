<script setup lang="ts">
/**
 * 图片防盗链代理与持久化缓存总控：
 * 1. 全局海报防盗链中继开关（开启后前台所有海报自动经由本站代理中继，无需逐张配置）；
 * 2. 服务端磁盘持久化缓存统计与一键清空；
 * 3. 真实影视海报样本提取与【原图直连 vs 防盗链中继】双轨对比沙盒。
 */
import {
  ElAlert,
  ElButton,
  ElCard,
  ElCol,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElMessageBox,
  ElRow,
  ElSwitch,
  ElTag,
} from 'element-plus'
import {
  Check,
  Delete,
  Refresh,
} from '@element-plus/icons-vue'
import { onMounted, ref } from 'vue'

import {
  clearImageProxy,
  getImageProxyConfig,
  getImageProxyStats,
  getSamplePosters,
  updateImageProxyConfig,
} from '@/admin/api'
import { ui } from '@/admin/ui'
import type { ImageProxyConfig, ImageProxyStats, SamplePosterItem } from '@/api/types'

const loading = ref(false)
const savingConfig = ref(false)
const clearing = ref(false)
const loadingSamples = ref(false)

const stats = ref<ImageProxyStats | null>(null)
const config = ref<ImageProxyConfig>({
  global_proxy_enabled: false,
  disk_cache_enabled: false,
  auto_strip_referer: true,
  custom_referer: '',
  cache_max_mb: 1024,
})

const samplePosters = ref<SamplePosterItem[]>([])
const testUrl = ref('')
const testReferer = ref('')
const testedImg = ref<{
  rawUrl: string
  proxyUrl: string
  timestamp: number
} | null>(null)

async function loadData(): Promise<void> {
  loading.value = true
  try {
    const [st, cfg] = await Promise.all([
      getImageProxyStats(),
      getImageProxyConfig(),
    ])
    stats.value = st
    config.value = cfg
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '加载图片代理配置失败')
  } finally {
    loading.value = false
  }
}

async function handleSaveConfig(): Promise<void> {
  savingConfig.value = true
  try {
    const res = await updateImageProxyConfig(config.value)
    config.value = res
    ElMessage.success(
      res.global_proxy_enabled
        ? '已开启【全局海报防盗链中继】：前台所有海报自动经由服务端代理，无需单独配置！'
        : '已保存防盗链设置（当前处于原图直连模式）'
    )
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '保存配置失败')
  } finally {
    savingConfig.value = false
  }
}

async function loadSamplePosters(): Promise<void> {
  loadingSamples.value = true
  try {
    const res = await getSamplePosters()
    samplePosters.value = res.items ?? []
    if (!testUrl.value && samplePosters.value.length > 0) {
      testUrl.value = samplePosters.value[0].url
      runSandboxTest()
    }
  } catch {
    // 静默降级
  } finally {
    loadingSamples.value = false
  }
}

function selectSample(poster: SamplePosterItem): void {
  testUrl.value = poster.url
  runSandboxTest()
  ElMessage.success(`已选入《${poster.title}》真实源站海报并开始对比！`)
}

import { getAdminToken } from '@/admin/token'

function runSandboxTest(): void {
  const url = testUrl.value.trim()
  if (!url) {
    ElMessage.warning('请输入待测试的图片链接')
    return
  }
  const adminToken = getAdminToken()
  const tokenParam = adminToken ? `&token=${encodeURIComponent(adminToken)}` : ''
  let proxySrc = `/api/v1/proxy/image?url=${encodeURIComponent(url)}${tokenParam}`
  if (testReferer.value.trim()) {
    proxySrc += `&referer=${encodeURIComponent(testReferer.value.trim())}`
  }
  testedImg.value = {
    rawUrl: url,
    proxyUrl: proxySrc,
    timestamp: Date.now(),
  }
}

async function handleClear(): Promise<void> {
  try {
    await ElMessageBox.confirm('确定清空所有已持久化的图片代理缓存文件吗？', '提示', {
      confirmButtonText: '确定清空',
      cancelButtonText: '取消',
      type: 'warning',
    })
    clearing.value = true
    const res = await clearImageProxy()
    ElMessage.success(`清理完成：清除了 ${res.cleared_files} 个文件，释放了 ${res.freed_mb} MB 磁盘空间`)
    await loadData()
  } catch {
    /* 取消 */
  } finally {
    clearing.value = false
  }
}

onMounted(() => {
  void loadData()
  void loadSamplePosters()
})
</script>

<template>
  <div class="proxy-page">
    <!-- 顶栏标题 -->
    <div class="header-section">
      <div>
        <h2 class="title">图片防盗链代理与持久化加速</h2>
        <p class="subtitle">
          解决第三方影视站/图床开启防盗链导致前台海报 403 破图问题。服务端自动伪造 Referer 与 User-Agent，结合本地磁盘缓存极大提升加载速度。
        </p>
      </div>
      <div class="header-actions">
        <ElButton :icon="Refresh" :loading="loading" @click="loadData">刷新状态</ElButton>
      </div>
    </div>

    <!-- 卡片 1: 全局防盗链总控中心 -->
    <ElCard shadow="hover" class="card-glow control-card">
      <template #header>
        <div class="card-header-flex">
          <div class="flex-align">
            <span class="header-badge" :class="config.global_proxy_enabled ? 'badge-active' : 'badge-idle'">
              {{ config.global_proxy_enabled ? '⚡ 全局防盗链中继已生效' : '⚪ 原图直连模式（未开启中继）' }}
            </span>
            <span class="header-title">全局海报防盗链中继总控</span>
          </div>
          <ElTag v-if="config.global_proxy_enabled" type="success" effect="dark">
            全站影视海报自动代理
          </ElTag>
          <ElTag v-else type="info" effect="plain">
            仅沙盒测试生效
          </ElTag>
        </div>
      </template>

      <div class="control-content">
        <ElAlert
          type="info"
          show-icon
          :closable="false"
          class="notice-alert"
        >
          <template #title>
            <span style="font-weight: 600;">关于图片防盗链机制说明：</span>
          </template>
          开启「全局海报防盗链中继」后，<strong>前台全站（首页、分类大厅、详情页）的所有影视海报将自动通过本站代理中继</strong>，
          服务端会自动剥离敏感请求头、去 Referer 并本地哈希持久化。<strong>无需为任何单部影片单独设置代理！</strong>
        </ElAlert>

        <ElForm :model="config" label-position="top" class="config-form">
          <ElRow :gutter="24">
            <ElCol :xs="24" :md="12">
              <div class="switch-box">
                <div class="switch-info">
                  <div class="switch-title">全局开启海报防盗链中继</div>
                  <div class="switch-desc">
                    开启后，前台影视海报均通过 <code>/api/v1/proxy/image</code> 中继加速，彻底杜绝 403 破图
                  </div>
                </div>
                <ElSwitch
                  v-model="config.global_proxy_enabled"
                  :disabled="ui.readOnly"
                  active-text="全局启用"
                  inactive-text="关闭"
                />
              </div>
            </ElCol>

            <ElCol :xs="24" :md="12">
              <div class="switch-box">
                <div class="switch-info">
                  <div class="switch-title">图片本地持久化磁盘缓存</div>
                  <div class="switch-desc">
                    默认关闭。开启后海报图片将持久化缓存到服务端磁盘，避免频繁向源站重抓；关闭时图片通过内存流式中继，不占用任何本地磁盘。
                  </div>
                </div>
                <ElSwitch
                  v-model="config.disk_cache_enabled"
                  :disabled="ui.readOnly"
                  active-text="开启缓存"
                  inactive-text="关闭（纯透传）"
                />
              </div>
            </ElCol>

            <ElCol :xs="24" :md="12">
              <div class="switch-box">
                <div class="switch-info">
                  <div class="switch-title">自动剥离 / 同源伪装 Referer</div>
                  <div class="switch-desc">
                    向源站发起代理请求时自动伪装为源站本站 Referer，完美绕过绝大多数防盗链白名单机制
                  </div>
                </div>
                <ElSwitch
                  v-model="config.auto_strip_referer"
                  :disabled="ui.readOnly"
                  active-text="自动伪装"
                  inactive-text="直接透传"
                />
              </div>
            </ElCol>

            <ElCol :xs="24" :md="12">
              <ElFormItem label="自定义全局伪装 Referer（选填）">
                <ElInput
                  v-model="config.custom_referer"
                  placeholder="留空时自动提取图片 URL 的 host 域名作为同源 Referer"
                  :disabled="ui.readOnly"
                />
              </ElFormItem>
            </ElCol>

            <ElCol :xs="24" :md="12">
              <ElFormItem label="磁盘缓存保护上限 (MB)">
                <ElInputNumber
                  v-model="config.cache_max_mb"
                  :min="128"
                  :max="51200"
                  :step="256"
                  :disabled="ui.readOnly"
                  style="width: 100%;"
                />
              </ElFormItem>
            </ElCol>
          </ElRow>

          <div class="form-bottom-actions">
            <ElButton
              type="primary"
              :icon="Check"
              :loading="savingConfig"
              :disabled="ui.readOnly"
              @click="handleSaveConfig"
            >
              保存并应用全局配置
            </ElButton>
            <span v-if="config.updated_at" class="update-hint">
              最后更新时间：{{ config.updated_at }}
            </span>
          </div>
        </ElForm>
      </div>
    </ElCard>

    <!-- 卡片 2: 缓存看板指标 -->
    <div class="metrics-grid">
      <div class="metric-card">
        <div class="metric-label">已持久化海报数量</div>
        <div class="metric-value">
          {{ stats?.cached_files ?? 0 }}
          <span class="metric-unit">张</span>
        </div>
        <div class="metric-sub">本地磁盘 SHA256 去重存储</div>
      </div>

      <div class="metric-card">
        <div class="metric-label">磁盘空间占用</div>
        <div class="metric-value">
          {{ stats?.total_size_mb ?? 0 }}
          <span class="metric-unit">MB</span>
        </div>
        <div class="metric-sub">支持 HTTP 304 ETag 毫秒级协商</div>
      </div>

      <div class="metric-card metric-card--action">
        <div class="metric-label">缓存目录与操作</div>
        <div class="dir-text" :title="stats?.cache_dir">
          {{ stats?.cache_dir || 'data/img_cache' }}
        </div>
        <div class="dir-actions">
          <ElButton
            type="danger"
            size="small"
            plain
            :icon="Delete"
            :loading="clearing"
            :disabled="ui.readOnly"
            @click="handleClear"
          >
            清空所有海报缓存
          </ElButton>
        </div>
      </div>
    </div>

    <!-- 卡片 3: 真实海报提取样本库 -->
    <ElCard shadow="never" class="samples-card">
      <template #header>
        <div class="card-header-flex">
          <div>
            <span class="header-title">真实影视封面提取库（免手动找图）</span>
            <span class="header-desc">系统已自动从内容源与内置库提取真实影视海报，点击即可载入下方沙盒进行直连与代理对比</span>
          </div>
          <ElButton
            size="small"
            :icon="Refresh"
            :loading="loadingSamples"
            @click="loadSamplePosters"
          >
            重新提取海报
          </ElButton>
        </div>
      </template>

      <div v-loading="loadingSamples" class="samples-stream">
        <div
          v-for="item in samplePosters"
          :key="item.url"
          class="sample-pill"
          :class="{ 'sample-pill--selected': testUrl === item.url }"
          @click="selectSample(item)"
        >
          <img :src="item.url" alt="海报" class="sample-pill-thumb" loading="lazy" />
          <div class="sample-pill-meta">
            <div class="sample-pill-title" :title="item.title">{{ item.title }}</div>
            <ElTag size="small" effect="plain">{{ item.site }}</ElTag>
          </div>
          <div class="sample-pill-hover">点击测试</div>
        </div>
      </div>
    </ElCard>

    <!-- 卡片 4: 双轨真机对比测试沙盒 -->
    <ElCard shadow="never" class="sandbox-card">
      <template #header>
        <div class="card-header-flex">
          <div>
            <span class="header-title">防盗链双轨对比测试沙盒</span>
            <span class="header-desc">可自定义输入任意图片地址，直观对比【原图直连】与【防盗链中继】加载表现</span>
          </div>
          <ElButton type="primary" size="small" @click="runSandboxTest">
            运行对比测试
          </ElButton>
        </div>
      </template>

      <div class="sandbox-form">
        <ElRow :gutter="16">
          <ElCol :xs="24" :md="16">
            <ElInput
              v-model="testUrl"
              placeholder="输入待测试的第三方图片 URL，如 https://.../poster.jpg"
              clearable
              @keyup.enter="runSandboxTest"
            >
              <template #prepend>图片 URL</template>
            </ElInput>
          </ElCol>
          <ElCol :xs="24" :md="8">
            <ElInput
              v-model="testReferer"
              placeholder="可选自定义 Referer（默认自动同源）"
              clearable
              @keyup.enter="runSandboxTest"
            >
              <template #prepend>伪装 Referer</template>
            </ElInput>
          </ElCol>
        </ElRow>
      </div>

      <!-- 双轨对比舞台 -->
      <div v-if="testedImg" class="dual-stage">
        <!-- 左侧：原图直连 -->
        <div class="stage-track track-direct">
          <div class="track-header">
            <div class="track-tag tag-direct">模式 1：原图直接加载 (Direct)</div>
            <div class="track-sub">浏览器直接向第三方源站请求，若对方设置防盗链白名单将报 403 碎图</div>
          </div>
          <div class="track-preview">
            <img
              :src="testedImg.rawUrl"
              alt="原图直连"
              class="preview-img"
              loading="eager"
            />
          </div>
          <div class="track-footer">
            <div class="track-url-box">
              <code>{{ testedImg.rawUrl }}</code>
            </div>
          </div>
        </div>

        <!-- 右侧：防盗链代理中继 -->
        <div class="stage-track track-proxy">
          <div class="track-header">
            <div class="track-tag tag-proxy">模式 2：防盗链代理中继 (Proxy & Cache)</div>
            <div class="track-sub">服务端伪装 Referer 绕过防盗链限制，本地磁盘持久化缓存，支持秒开</div>
          </div>
          <div class="track-preview">
            <img
              :src="testedImg.proxyUrl"
              alt="代理中继"
              class="preview-img"
              loading="eager"
            />
          </div>
          <div class="track-footer">
            <div class="track-url-box">
              <code>{{ testedImg.proxyUrl }}</code>
            </div>
            <div class="track-badge-ok">
              ✔ 自动防盗链欺骗 + 本地持久化缓存
            </div>
          </div>
        </div>
      </div>
    </ElCard>
  </div>
</template>

<style scoped>
.proxy-page {
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

.header-desc {
  display: block;
  font-size: 12px;
  color: var(--a-text-2, #64748b);
  margin-top: 2px;
}

.header-badge {
  font-size: 12px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 6px;
}

.badge-active {
  background: rgba(16, 185, 129, 0.12);
  color: #059669;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.badge-idle {
  background: rgba(148, 163, 184, 0.12);
  color: #64748b;
  border: 1px solid rgba(148, 163, 184, 0.25);
}

.notice-alert {
  margin-bottom: 16px;
  border-radius: 6px;
}

.switch-box {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--el-fill-color-light, #f8fafc);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 16px;
  min-height: 72px;
}

.switch-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--a-text, #1e293b);
  margin-bottom: 4px;
}

.switch-desc {
  font-size: 12px;
  color: var(--a-text-2, #64748b);
  line-height: 1.4;
}

.switch-desc code {
  color: var(--el-color-primary, #4f46e5);
  background: rgba(79, 70, 229, 0.08);
  padding: 1px 4px;
  border-radius: 4px;
}

.form-bottom-actions {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 8px;
}

.update-hint {
  font-size: 12px;
  color: var(--a-text-2, #64748b);
}

/* 统计卡片网格 */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.metric-card {
  background: var(--a-card, #ffffff);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: var(--a-radius, 8px);
  box-shadow: var(--a-shadow, 0 1px 3px rgba(0, 0, 0, 0.05));
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.metric-label {
  font-size: 13px;
  color: var(--a-text-2, #64748b);
  margin-bottom: 6px;
}

.metric-value {
  font-size: 28px;
  font-weight: 800;
  color: var(--el-color-primary, #4f46e5);
  line-height: 1.1;
  margin-bottom: 6px;
}

.metric-unit {
  font-size: 14px;
  font-weight: 500;
  color: var(--a-text-2, #64748b);
  margin-left: 4px;
}

.metric-sub {
  font-size: 12px;
  color: var(--a-text-2, #64748b);
}

.dir-text {
  font-family: monospace;
  font-size: 12px;
  color: var(--a-text, #1e293b);
  background: var(--el-fill-color-light, #f1f5f9);
  border: 1px solid var(--a-border, #e2e8f0);
  padding: 6px 10px;
  border-radius: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 10px;
}

.dir-actions {
  display: flex;
  justify-content: flex-end;
}

/* 抽样库 */
.samples-card {
  background: var(--a-card, #ffffff);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: var(--a-radius, 8px);
  box-shadow: var(--a-shadow, 0 1px 3px rgba(0, 0, 0, 0.05));
}

.samples-stream {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
  max-height: 280px;
  overflow-y: auto;
  padding-right: 6px;
}

.sample-pill {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--el-fill-color-light, #f8fafc);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: 8px;
  padding: 8px 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  overflow: hidden;
}

.sample-pill:hover {
  background: rgba(79, 70, 229, 0.05);
  border-color: var(--el-color-primary, #4f46e5);
  transform: translateY(-2px);
}

.sample-pill--selected {
  background: rgba(79, 70, 229, 0.1) !important;
  border-color: var(--el-color-primary, #4f46e5) !important;
}

.sample-pill-thumb {
  width: 44px;
  height: 60px;
  object-fit: cover;
  border-radius: 4px;
  background: #e2e8f0;
  flex-shrink: 0;
}

.sample-pill-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow: hidden;
}

.sample-pill-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--a-text, #1e293b);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sample-pill-hover {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  background: var(--el-color-primary, #4f46e5);
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  padding: 0 10px;
  opacity: 0;
  transform: translateX(100%);
  transition: all 0.2s ease;
}

.sample-pill:hover .sample-pill-hover {
  opacity: 1;
  transform: translateX(0);
}

/* 沙盒与双轨对比 */
.sandbox-card {
  background: var(--a-card, #ffffff);
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: var(--a-radius, 8px);
  box-shadow: var(--a-shadow, 0 1px 3px rgba(0, 0, 0, 0.05));
}

.sandbox-form {
  margin-bottom: 18px;
}

.dual-stage {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}

@media (max-width: 768px) {
  .dual-stage {
    grid-template-columns: 1fr;
  }
}

.stage-track {
  background: var(--el-fill-color-light, #f8fafc);
  border-radius: 10px;
  border: 1px solid var(--a-border, #e2e8f0);
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.track-direct {
  border-left: 4px solid #f59e0b;
}

.track-proxy {
  border-left: 4px solid #10b981;
}

.track-header {
  margin-bottom: 12px;
}

.track-tag {
  font-size: 13.5px;
  font-weight: 700;
  margin-bottom: 4px;
}

.tag-direct {
  color: #d97706;
}

.tag-proxy {
  color: #059669;
}

.track-sub {
  font-size: 12px;
  color: var(--a-text-2, #64748b);
  line-height: 1.4;
}

.track-preview {
  min-height: 240px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ffffff;
  border: 1px solid var(--a-border, #e2e8f0);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
}

.preview-img {
  max-width: 100%;
  max-height: 220px;
  object-fit: contain;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.track-footer {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.track-url-box {
  background: var(--el-fill-color-blank, #ffffff);
  border: 1px solid var(--a-border, #e2e8f0);
  padding: 8px 10px;
  border-radius: 6px;
  font-size: 11px;
  word-break: break-all;
  color: var(--a-text-2, #64748b);
}

.track-badge-ok {
  font-size: 12px;
  color: #059669;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>
