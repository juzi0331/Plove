<script setup lang="ts">
/**
 * 图片防盗链代理与持久化缓存管理：
 * 监控图片缓存数量与磁盘大小、一键清理缓存、
 * 提供在线图片防盗链与跨域加载实时测试工具。
 */
import {
  ElButton,
  ElCard,
  ElCol,
  ElForm,
  ElFormItem,
  ElImage,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElRow,
  ElTag,
} from 'element-plus'
import {
  Delete,
  Picture,
  Refresh,
} from '@element-plus/icons-vue'
import { onMounted, ref } from 'vue'

import { clearImageProxy, getImageProxyStats, getSamplePosters } from '@/admin/api'
import { ui } from '@/admin/ui'
import type { ImageProxyStats, SamplePosterItem } from '@/api/types'

const loading = ref(false)
const clearing = ref(false)
const stats = ref<ImageProxyStats | null>(null)

const testUrl = ref('')
const testReferer = ref('')
const testedImg = ref<{ url: string; rawUrl: string; time: number } | null>(null)

const samplePosters = ref<SamplePosterItem[]>([])
const loadingSamples = ref(false)

async function loadSamplePosters(): Promise<void> {
  loadingSamples.value = true
  try {
    const res = await getSamplePosters()
    samplePosters.value = res.items ?? []
  } catch {
    // 静默忽略
  } finally {
    loadingSamples.value = false
  }
}

function selectSample(poster: SamplePosterItem): void {
  testUrl.value = poster.url
  handleTestProxy()
  ElMessage.success(`已选入《${poster.title}》真实源站海报并开始代理对比！`)
}

async function loadStats(): Promise<void> {
  loading.value = true
  try {
    stats.value = await getImageProxyStats()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '加载图片缓存统计失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadStats()
  void loadSamplePosters()
})

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
    await loadStats()
  } catch {
    /* 取消 */
  } finally {
    clearing.value = false
  }
}

function handleTestProxy(): void {
  if (!testUrl.value.trim()) {
    ElMessage.warning('请输入图片链接')
    return
  }
  const cleanUrl = testUrl.value.trim()
  let proxySrc = `/api/v1/proxy/image?url=${encodeURIComponent(cleanUrl)}`
  if (testReferer.value.trim()) {
    proxySrc += `&referer=${encodeURIComponent(testReferer.value.trim())}`
  }
  testedImg.value = {
    url: proxySrc,
    rawUrl: cleanUrl,
    time: Date.now(),
  }
}
</script>

<template>
  <div class="proxy-view">
    <div class="header-section">
      <div>
        <h2 class="title">图片防盗链代理与持久化缓存</h2>
        <p class="subtitle">
          自动欺骗 Referer 与 User-Agent 抓取防盗链海报，本地磁盘哈希持久化存储并支持 HTTP 304 快速协商。
        </p>
      </div>
      <ElButton :icon="Refresh" :loading="loading" @click="loadStats">刷新状态</ElButton>
    </div>

    <!-- 统计指标 -->
    <ElRow :gutter="16">
      <ElCol :xs="24" :sm="8">
        <ElCard shadow="hover" class="stat-card">
          <div class="stat-title">已缓存图片文件数</div>
          <div class="stat-num">{{ stats?.cached_files ?? 0 }} <span class="unit">张</span></div>
          <div class="stat-sub">服务端磁盘持久化存储</div>
        </ElCard>
      </ElCol>

      <ElCol :xs="24" :sm="8">
        <ElCard shadow="hover" class="stat-card">
          <div class="stat-title">磁盘空间占用</div>
          <div class="stat-num">{{ stats?.total_size_mb ?? 0 }} <span class="unit">MB</span></div>
          <div class="stat-sub">基于 SHA256 自动去重</div>
        </ElCard>
      </ElCol>

      <ElCol :xs="24" :sm="8">
        <ElCard shadow="hover" class="stat-card">
          <div class="stat-title">缓存存储目录</div>
          <div class="dir-code" :title="stats?.cache_dir">{{ stats?.cache_dir || 'data/img_cache' }}</div>
          <div class="stat-action">
            <ElButton
              type="danger"
              size="small"
              plain
              :icon="Delete"
              :loading="clearing"
              :disabled="ui.readOnly"
              @click="handleClear"
            >
              清空图片缓存
            </ElButton>
          </div>
        </ElCard>
      </ElCol>
    </ElRow>

    <!-- 真实源站海报提取库（免手动输入，点击即测） -->
    <ElCard shadow="never" class="samples-card">
      <template #header>
        <div class="card-header">
          <div>
            <span class="header-title">源站真实封面提取器（免手动找图）</span>
            <span class="a-muted" style="margin-left: 8px; font-size: 12px">
              无需繁琐寻找或复制图片链接，系统已自动从内容源提取真实海报。点击任意卡片立即自动填入并对比代理效果！
            </span>
          </div>
          <ElButton size="small" :icon="Refresh" :loading="loadingSamples" @click="loadSamplePosters">
            重新提取海报
          </ElButton>
        </div>
      </template>

      <div v-loading="loadingSamples" class="samples-grid">
        <div
          v-for="item in samplePosters"
          :key="item.url"
          class="sample-item-card"
          @click="selectSample(item)"
        >
          <div class="sample-img-box">
            <img :src="item.url" alt="海报" loading="lazy" />
            <div class="sample-hover-badge">点击测试</div>
          </div>
          <div class="sample-info">
            <div class="sample-title" :title="item.title">{{ item.title }}</div>
            <ElTag size="small" effect="light">{{ item.site }}</ElTag>
          </div>
        </div>
        <div v-if="!samplePosters.length && !loadingSamples" class="a-muted empty-samples">
          暂未提取到启用站点的封面海报（可先在内容源管理中点击“预热该源首页”）
        </div>
      </div>
    </ElCard>

    <!-- 在线图片防盗链代理测试台与分屏对比 -->
    <ElCard shadow="never" class="test-card">
      <template #header>
        <div class="card-header">
          <span class="header-title">图片代理加载实时测试</span>
          <span class="a-muted" style="font-size: 12px">测试任意源站防盗链（403）海报能否通过服务端代理正常出图</span>
        </div>
      </template>

      <ElForm label-position="top">
        <ElRow :gutter="16">
          <ElCol :xs="24" :md="14">
            <ElFormItem label="原始图片链接 (URL)" required>
              <ElInput
                v-model="testUrl"
                placeholder="从上方海报库点击自动选入，或手动粘贴图片地址"
                clearable
              />
            </ElFormItem>
          </ElCol>

          <ElCol :xs="24" :md="7">
            <ElFormItem label="可选伪造 Referer">
              <ElInput
                v-model="testReferer"
                placeholder="留空则自动提取图片所在域名"
                clearable
              />
            </ElFormItem>
          </ElCol>

          <ElCol :xs="24" :md="3" class="btn-col">
            <ElButton
              type="primary"
              :icon="Picture"
              @click="handleTestProxy"
            >
              代理加载
            </ElButton>
          </ElCol>
        </ElRow>
      </ElForm>

      <!-- 效果对比区：直连 vs 代理 -->
      <div v-if="testedImg" class="preview-box">
        <div class="preview-head">
          <span>代理接口路径: <code>{{ testedImg.url }}</code></span>
        </div>

        <div class="comparison-grid">
          <!-- 效果 1: 浏览器原图直连（通常因防盗链而裂图/403） -->
          <div class="comparison-column">
            <div class="col-title text-orange">浏览器原图直连（未伪造防盗链，易报 403 拦截）</div>
            <div class="preview-img-wrapper">
              <ElImage
                :src="testedImg.rawUrl"
                fit="contain"
                class="tested-image"
              >
                <template #placeholder>
                  <div class="img-slot">原图直连尝试中...</div>
                </template>
                <template #error>
                  <div class="img-slot error">原图直连被源站防盗链阻断 (403 Forbidden / 裂图)</div>
                </template>
              </ElImage>
            </div>
          </div>

          <!-- 效果 2: 服务端防盗链代理（秒级出图并落盘缓存） -->
          <div class="comparison-column">
            <div class="col-title text-green">服务端防盗链代理（已伪造 Referer 并持久化缓存）</div>
            <div class="preview-img-wrapper">
              <ElImage
                :src="testedImg.url"
                fit="contain"
                class="tested-image"
              >
                <template #placeholder>
                  <div class="img-slot">代理抓取中...</div>
                </template>
                <template #error>
                  <div class="img-slot error">图片加载失败（请检查目标链接或服务端日志）</div>
                </template>
              </ElImage>
            </div>
          </div>
        </div>
      </div>
    </ElCard>
  </div>
</template>

<style scoped>
.proxy-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
}

.subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.stat-card {
  border-radius: 8px;
}

.stat-title {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.stat-num {
  font-size: 26px;
  font-weight: 800;
  margin: 6px 0;
}

.unit {
  font-size: 14px;
  font-weight: normal;
}

.stat-sub {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

.dir-code {
  font-family: monospace;
  font-size: 12px;
  color: var(--el-text-color-regular);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin: 8px 0;
}

.stat-action {
  margin-top: 8px;
}

.test-card {
  border-radius: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-title {
  font-weight: 600;
}

.btn-col {
  display: flex;
  align-items: flex-end;
  margin-bottom: 18px;
}

.preview-box {
  margin-top: 16px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  overflow: hidden;
  background: var(--el-fill-color-light);
}

.preview-head {
  padding: 8px 12px;
  font-size: 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color);
}

.preview-head code {
  font-family: monospace;
  color: var(--el-color-primary);
}

.preview-img-wrapper {
  padding: 24px;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 240px;
}

.tested-image {
  max-width: 320px;
  max-height: 400px;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.img-slot {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 240px;
  height: 180px;
  background: var(--el-fill-color);
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.img-slot.error {
  color: var(--el-color-danger);
  padding: 12px;
  text-align: center;
}

/* 样片提取库 */
.samples-card {
  border-radius: 8px;
}

.samples-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 12px;
  max-height: 260px;
  overflow-y: auto;
  padding: 4px;
}

.sample-item-card {
  cursor: pointer;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-blank);
  transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
}

.sample-item-card:hover {
  transform: translateY(-2px);
  border-color: var(--el-color-primary);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
}

.sample-img-box {
  position: relative;
  width: 100%;
  aspect-ratio: 2/3;
  background: #000;
  overflow: hidden;
}

.sample-img-box img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.sample-hover-badge {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  opacity: 0;
  transition: opacity 0.2s;
}

.sample-item-card:hover .sample-hover-badge {
  opacity: 1;
}

.sample-info {
  padding: 6px 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sample-title {
  font-size: 11.5px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.empty-samples {
  grid-column: 1 / -1;
  text-align: center;
  padding: 30px;
}

/* 分屏对比 */
.comparison-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
  padding: 16px;
}

.comparison-column {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.col-title {
  font-size: 13px;
  font-weight: 600;
  padding: 6px 10px;
  border-radius: 4px;
  background: var(--el-fill-color);
}
</style>
