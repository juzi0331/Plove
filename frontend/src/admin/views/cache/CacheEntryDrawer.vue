<script setup lang="ts">
import { DocumentCopy, Film } from '@element-plus/icons-vue'
import {
  ElButton,
  ElCard,
  ElDescriptions,
  ElDescriptionsItem,
  ElDrawer,
  ElIcon,
  ElMessage,
  ElTabPane,
  ElTabs,
  ElTag,
  ElTooltip,
} from 'element-plus'
import { computed, ref, watch } from 'vue'

import { getCacheEntry } from '@/admin/api'
import type { CacheEntryDetail } from '@/api/types'
import { nsFriendlyName, nsTagType } from './useCacheCenter'

const props = defineProps<{
  modelValue: boolean
  entryKey: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
}>()

const loadingDetail = ref(false)
const currentEntryDetail = ref<CacheEntryDetail | null>(null)
const activeDetailTab = ref<'visual' | 'json'>('visual')

interface ParsedDrama {
  id?: string | number
  name: string
  pic?: string
  remarks?: string
  typeName?: string
  year?: string
  area?: string
  actor?: string
  director?: string
  desc?: string
}

interface ParsedEpisode {
  name: string
  url?: string
}

interface ParsedSection {
  title: string
  items: ParsedDrama[]
}

interface ParsedCacheResult {
  type: 'detail' | 'category' | 'home' | 'list' | 'object'
  video?: ParsedDrama
  episodes?: ParsedEpisode[]
  lines?: any[]
  total?: number
  page?: number
  pagecount?: number
  limit?: number
  items?: ParsedDrama[]
  banners?: ParsedDrama[]
  sections?: ParsedSection[]
  categories?: any[]
  raw?: any
}

function parseDramaItem(item: any): ParsedDrama {
  if (!item || typeof item !== 'object') return { name: String(item || '') }
  return {
    id: item.vod_id || item.id,
    name: item.vod_name || item.name || item.title || '未知剧名',
    pic: item.vod_pic || item.pic || item.cover || '',
    remarks: item.vod_remarks || item.remarks || item.note || '',
    typeName: item.type_name || item.category || '',
    year: item.vod_year || item.year || '',
    area: item.vod_area || item.area || '',
    actor: item.vod_actor || item.actor || '',
    director: item.vod_director || item.director || '',
    desc: item.vod_content || item.desc || item.description || '',
  }
}

const parsedCacheView = computed<ParsedCacheResult | null>(() => {
  if (!currentEntryDetail.value || !currentEntryDetail.value.data) {
    return null
  }
  const raw: any = currentEntryDetail.value.data
  const ns = currentEntryDetail.value.namespace

  // 1. DETAIL 详情页与选集
  if (ns === 'detail' || raw.video || raw.episodes) {
    const videoRaw = raw.video || raw
    const video = parseDramaItem(videoRaw)
    const rawEpisodes = raw.episodes || videoRaw.episodes || []
    let episodes: ParsedEpisode[] = []

    if (Array.isArray(rawEpisodes)) {
      episodes = rawEpisodes.map((ep, i) => {
        if (typeof ep === 'string') return { name: ep }
        return {
          name: ep.name || ep.title || `第 ${i + 1} 集`,
          url: ep.url || ep.link || '',
        }
      })
    } else if (typeof rawEpisodes === 'string') {
      episodes = rawEpisodes.split('#').filter(Boolean).map((part, i) => {
        const segs = part.split('$')
        return {
          name: segs[0] || `第 ${i + 1} 集`,
          url: segs[1] || '',
        }
      })
    }

    const lines = Array.isArray(raw.lines) ? raw.lines : []
    return {
      type: 'detail',
      video,
      episodes,
      lines,
    }
  }

  // 2. CATEGORY 分类筛选页
  if (ns === 'category' || Array.isArray(raw.items) || Array.isArray(raw.videos) || Array.isArray(raw.list)) {
    const listRaw = raw.items || raw.videos || raw.list || []
    const items = listRaw.map(parseDramaItem)
    return {
      type: 'category',
      total: raw.total ?? items.length,
      page: raw.page ?? 1,
      pagecount: raw.pagecount ?? 1,
      limit: raw.limit ?? items.length,
      items,
    }
  }

  // 3. HOME 首页大盘
  if (ns === 'home' || raw.banners || raw.sections) {
    const banners = (raw.banners || []).map(parseDramaItem)
    const sections: ParsedSection[] = []
    if (Array.isArray(raw.sections)) {
      for (const sec of raw.sections) {
        sections.push({
          title: sec.title || sec.name || '热门推荐',
          items: (sec.items || sec.videos || []).map(parseDramaItem),
        })
      }
    }
    const categories = Array.isArray(raw.categories) ? raw.categories : []
    return {
      type: 'home',
      banners,
      sections,
      categories,
    }
  }

  // 4. 纯数组列表
  if (Array.isArray(raw)) {
    return {
      type: 'list',
      items: raw.map(parseDramaItem),
    }
  }

  // 5. 其他复合对象
  return {
    type: 'object',
    raw,
  }
})

function copyJson(data: any): void {
  try {
    navigator.clipboard.writeText(JSON.stringify(data, null, 2))
    ElMessage.success('已复制缓存数据到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动选取复制')
  }
}

async function fetchEntry(key: string): Promise<void> {
  if (!key) return
  loadingDetail.value = true
  activeDetailTab.value = 'visual'
  try {
    currentEntryDetail.value = await getCacheEntry(key)
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '获取缓存数据详情失败')
  } finally {
    loadingDetail.value = false
  }
}

watch(
  () => [props.modelValue, props.entryKey] as const,
  ([visible, key]) => {
    if (visible && key) {
      void fetchEntry(key)
    }
  },
  { immediate: true },
)
</script>

<template>
  <ElDrawer
    :model-value="modelValue"
    title="缓存内容数据透视"
    size="680px"
    destroy-on-close
    class="cache-detail-drawer"
    @update:model-value="(val) => emit('update:modelValue', val)"
  >
    <div v-loading="loadingDetail" class="drawer-inner-box">
      <template v-if="currentEntryDetail">
        <!-- 顶部元信息卡片 -->
        <ElCard shadow="never" class="entry-meta-card">
          <div class="meta-row">
            <span class="meta-label">完整缓存 Key:</span>
            <code class="meta-key">{{ currentEntryDetail.key }}</code>
            <ElButton
              size="small"
              text
              :icon="DocumentCopy"
              @click="copyJson(currentEntryDetail.key)"
            >
              复制
            </ElButton>
          </div>
          <div class="meta-badges-row">
            <ElTag size="small" effect="plain">{{ currentEntryDetail.site }}</ElTag>
            <ElTag size="small" :type="nsTagType(currentEntryDetail.namespace)" effect="dark">
              {{ nsFriendlyName(currentEntryDetail.namespace) }}
            </ElTag>
            <span class="meta-ttl">TTL 剩余存活: <strong>{{ currentEntryDetail.remaining_seconds }} 秒</strong></span>
          </div>
        </ElCard>

        <!-- 模式切换：默认可视化预览，技术人员可切换查看 JSON -->
        <div class="tab-switcher-row">
          <ElTabs v-model="activeDetailTab" class="detail-tabs">
            <ElTabPane label="结构化可视化预览" name="visual" />
            <ElTabPane label="原始技术报文 (JSON)" name="json" />
          </ElTabs>

          <ElButton
            size="small"
            type="primary"
            plain
            :icon="DocumentCopy"
            @click="copyJson(currentEntryDetail.data)"
          >
            复制完整数据
          </ElButton>
        </div>

        <!-- TAB 1: 可视化结构预览 (告别生涩 JSON，一目了然看懂电影/剧集) -->
        <div v-if="activeDetailTab === 'visual'" class="visual-container">
          <!-- 1.1 详情页展示 -->
          <div v-if="parsedCacheView?.type === 'detail' && parsedCacheView.video" class="detail-visual-box">
            <ElCard shadow="hover" class="drama-hero-card">
              <div class="drama-hero-inner">
                <div class="drama-poster-box">
                  <img
                    v-if="parsedCacheView.video?.pic"
                    :src="parsedCacheView.video.pic"
                    :alt="parsedCacheView.video.name"
                    class="drama-poster-img"
                    loading="lazy"
                  />
                  <div v-else class="drama-poster-fallback">
                    <ElIcon :size="32"><Film /></ElIcon>
                  </div>
                </div>
                <div class="drama-info-box">
                  <h2 class="drama-title">{{ parsedCacheView.video?.name }}</h2>
                  <div class="drama-tags-row">
                    <ElTag v-if="parsedCacheView.video?.typeName" size="small" type="primary" effect="plain">
                      {{ parsedCacheView.video.typeName }}
                    </ElTag>
                    <ElTag v-if="parsedCacheView.video?.remarks" size="small" type="success" effect="plain">
                      {{ parsedCacheView.video.remarks }}
                    </ElTag>
                    <ElTag v-if="parsedCacheView.video?.year" size="small" type="info" effect="plain">
                      {{ parsedCacheView.video.year }}
                    </ElTag>
                    <ElTag v-if="parsedCacheView.video?.area" size="small" type="info" effect="plain">
                      {{ parsedCacheView.video.area }}
                    </ElTag>
                  </div>

                  <div v-if="parsedCacheView.video?.actor" class="drama-actor-row">
                    <span class="actor-label">主演:</span>
                    <span class="actor-text">{{ parsedCacheView.video.actor }}</span>
                  </div>

                  <div v-if="parsedCacheView.video?.director" class="drama-actor-row">
                    <span class="actor-label">导演:</span>
                    <span class="actor-text">{{ parsedCacheView.video.director }}</span>
                  </div>
                </div>
              </div>

              <div v-if="parsedCacheView.video?.desc" class="drama-desc-box">
                <div class="desc-title">剧情简介</div>
                <p class="desc-text">{{ parsedCacheView.video.desc }}</p>
              </div>
            </ElCard>

            <!-- 选集列表预览 -->
            <ElCard shadow="hover" class="episodes-card">
              <div class="episodes-card-header">
                <span class="episodes-card-title">选集列表 (共 {{ parsedCacheView.episodes?.length || 0 }} 集)</span>
                <span class="episodes-card-tip">点击集数可查看对应切片流地址</span>
              </div>

              <div v-if="(parsedCacheView.episodes?.length || 0) > 0" class="episodes-grid">
                <ElTooltip
                  v-for="(ep, i) in (parsedCacheView.episodes || [])"
                  :key="i"
                  :content="ep.url || '暂无直链'"
                  placement="top"
                >
                  <div class="episode-chip">
                    {{ ep.name }}
                  </div>
                </ElTooltip>
              </div>
              <div v-else class="no-episodes">暂未解析到分集列表</div>
            </ElCard>
          </div>

          <!-- 1.2 分类列表页展示 -->
          <div v-else-if="parsedCacheView?.type === 'category'" class="category-visual-box">
            <ElCard shadow="hover" class="category-summary-card">
              <div class="cat-summary-text">
                当前分类大厅已缓存 <strong>{{ parsedCacheView.items?.length || 0 }}</strong> 部剧目
                <span class="cat-pager-meta">（第 {{ parsedCacheView.page || 1 }} 页 / 共 {{ parsedCacheView.total || 0 }} 部）</span>
              </div>
            </ElCard>

            <div class="drama-grid-box">
              <div
                v-for="(item, idx) in (parsedCacheView.items || [])"
                :key="idx"
                class="drama-mini-card"
              >
                <div class="mini-poster-box">
                  <img
                    v-if="item.pic"
                    :src="item.pic"
                    :alt="item.name"
                    class="mini-poster-img"
                    loading="lazy"
                  />
                  <div v-else class="mini-poster-fallback">
                    <ElIcon :size="20"><Film /></ElIcon>
                  </div>
                  <span v-if="item.remarks" class="mini-remarks">{{ item.remarks }}</span>
                </div>
                <div class="mini-name" :title="item.name">{{ item.name }}</div>
                <div class="mini-type">{{ item.typeName || '短剧' }}</div>
              </div>
            </div>
          </div>

          <!-- 1.3 首页大盘展示 -->
          <div v-else-if="parsedCacheView?.type === 'home'" class="home-visual-box">
            <!-- 轮播焦点 -->
            <div v-if="(parsedCacheView.banners?.length || 0) > 0" class="home-section-block">
              <div class="home-section-title">首页轮播焦点 ({{ parsedCacheView.banners?.length || 0 }} 部)</div>
              <div class="drama-grid-box">
                <div
                  v-for="(item, idx) in (parsedCacheView.banners || [])"
                  :key="idx"
                  class="drama-mini-card"
                >
                  <div class="mini-poster-box">
                    <img v-if="item.pic" :src="item.pic" class="mini-poster-img" loading="lazy" />
                    <div v-else class="mini-poster-fallback"><ElIcon><Film /></ElIcon></div>
                    <span v-if="item.remarks" class="mini-remarks">{{ item.remarks }}</span>
                  </div>
                  <div class="mini-name">{{ item.name }}</div>
                </div>
              </div>
            </div>

            <!-- 分区板块 -->
            <div
              v-for="(sec, sIdx) in (parsedCacheView.sections || [])"
              :key="sIdx"
              class="home-section-block"
            >
              <div class="home-section-title">{{ sec.title }} ({{ sec.items?.length || 0 }} 部)</div>
              <div class="drama-grid-box">
                <div
                  v-for="(item, idx) in (sec.items || [])"
                  :key="idx"
                  class="drama-mini-card"
                >
                  <div class="mini-poster-box">
                    <img v-if="item.pic" :src="item.pic" class="mini-poster-img" loading="lazy" />
                    <div v-else class="mini-poster-fallback"><ElIcon><Film /></ElIcon></div>
                    <span v-if="item.remarks" class="mini-remarks">{{ item.remarks }}</span>
                  </div>
                  <div class="mini-name">{{ item.name }}</div>
                </div>
              </div>
            </div>
          </div>

          <!-- 1.4 通用数组 -->
          <div v-else-if="parsedCacheView?.type === 'list'" class="generic-list-box">
            <div class="drama-grid-box">
              <div
                v-for="(item, idx) in (parsedCacheView.items || [])"
                :key="idx"
                class="drama-mini-card"
              >
                <div class="mini-name">{{ item.name }}</div>
              </div>
            </div>
          </div>

          <!-- 1.5 通用对象 -->
          <div v-else class="generic-obj-box">
            <ElDescriptions :column="1" border size="small">
              <ElDescriptionsItem
                v-for="(val, key) in parsedCacheView?.raw"
                :key="key"
                :label="String(key)"
              >
                <span class="a-mono" style="font-size: 12.5px;">{{ typeof val === 'object' ? JSON.stringify(val) : String(val) }}</span>
              </ElDescriptionsItem>
            </ElDescriptions>
          </div>
        </div>

        <!-- TAB 2: 原始 JSON 报文 -->
        <div v-else class="json-container">
          <pre class="json-code-box">{{ JSON.stringify(currentEntryDetail.data, null, 2) }}</pre>
        </div>
      </template>
    </div>
  </ElDrawer>
</template>

<style scoped src="./cache-center.css"></style>
