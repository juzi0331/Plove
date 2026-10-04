<script setup lang="ts">
/**
 * 受控页面组件渲染器 (DynamicSectionRenderer.vue)。
 *
 * 遵循后端蓝图：
 * 1. 仅渲染服务端允许的白名单安全组件 (hero, video_rail, video_grid, notice, empty_state)
 * 2. 严格按后端给出的 sections[] 顺序呈现，不再在前端自行拆分或二次合成推荐
 * 3. 动作仅限于受控命名意图 (open_detail, open_home 等)，禁止执行任意远程脚本
 */

import { useRouter } from 'vue-router'
import type { ActionPayload, SectionDefinition } from '@/api/types'

export interface DynamicItem {
  content_id?: string
  title: string
  subtitle?: string
  poster_url?: string
  badge?: { text?: string }
  action?: ActionPayload
}

defineProps<{
  sections: SectionDefinition[]
}>()

const router = useRouter()

function handleAction(action?: ActionPayload | null) {
  if (!action || !action.type) return

  switch (action.type) {
    case 'open_detail':
      if (action.content_id) {
        router.push({ name: 'detail', params: { id: action.content_id } })
      }
      break
    case 'open_home':
      router.push({ name: 'home' })
      break
    case 'open_category':
      if (action.category_id) {
        router.push({ name: 'category', params: { id: action.category_id } })
      }
      break
    case 'start_playback':
      if (action.content_id) {
        router.push({
          name: 'player',
          params: { id: action.content_id },
          query: { ep: action.episode_id || '1' },
        })
      }
      break
    default:
      console.warn('忽略未支持的命名意图动作:', action.type)
  }
}
</script>

<template>
  <div class="dynamic-sections-container">
    <template v-for="sec in sections" :key="sec.id">
      <!-- 1. Hero 巨幕横幅 -->
      <section v-if="sec.component === 'hero'" class="section-hero">
        <div class="hero-backdrop" :style="sec.props?.poster_url ? { backgroundImage: `url(${sec.props.poster_url})` } : {}">
          <div class="hero-overlay"></div>
        </div>
        <div class="hero-content">
          <h1 class="hero-title">{{ sec.props?.title || '精彩热播' }}</h1>
          <p v-if="sec.props?.subtitle" class="hero-subtitle">{{ sec.props.subtitle }}</p>
          <div class="hero-actions">
            <button
              class="btn-primary hero-play-btn"
              type="button"
              @click="handleAction((sec.props?.action as ActionPayload | undefined))"
            >
              <span class="play-icon">▶</span> 立即播放
            </button>
          </div>
        </div>
      </section>

      <!-- 2. Video Rail 横向滚动栏目 -->
      <section v-else-if="sec.component === 'video_rail'" class="section-rail">
        <div class="section-header">
          <h2 class="section-title">{{ sec.props?.title || '推荐精选' }}</h2>
        </div>
        <div class="rail-scroll-track">
          <div
            v-for="(item, idx) in ((sec.props?.items as DynamicItem[] | undefined) || [])"
            :key="item.content_id || idx"
            class="rail-card"
            @click="handleAction(item.action || (item.content_id ? { type: 'open_detail', content_id: item.content_id } : undefined))"
          >
            <div class="card-poster-wrap">
              <img
                v-if="item.poster_url"
                :src="item.poster_url"
                :alt="item.title"
                class="card-img"
                loading="lazy"
              />
              <div v-else class="card-placeholder">
                <span>{{ item.title }}</span>
              </div>
              <span v-if="item.badge?.text" class="card-badge">{{ item.badge.text }}</span>
            </div>
            <div class="card-meta">
              <div class="card-title">{{ item.title }}</div>
              <div v-if="item.subtitle" class="card-subtitle">{{ item.subtitle }}</div>
            </div>
          </div>
        </div>
      </section>

      <!-- 3. Video Grid 响应式栅格 -->
      <section v-else-if="sec.component === 'video_grid'" class="section-grid-wrap">
        <div class="section-header">
          <h2 class="section-title">{{ sec.props?.title || '全部片库' }}</h2>
        </div>
        <div class="section-grid">
          <div
            v-for="(item, idx) in ((sec.props?.items as DynamicItem[] | undefined) || [])"
            :key="item.content_id || idx"
            class="grid-card"
            @click="handleAction(item.action || (item.content_id ? { type: 'open_detail', content_id: item.content_id } : undefined))"
          >
            <div class="card-poster-wrap">
              <img
                v-if="item.poster_url"
                :src="item.poster_url"
                :alt="item.title"
                class="card-img"
                loading="lazy"
              />
              <div v-else class="card-placeholder">
                <span>{{ item.title }}</span>
              </div>
              <span v-if="item.badge?.text" class="card-badge">{{ item.badge.text }}</span>
            </div>
            <div class="card-meta">
              <div class="card-title">{{ item.title }}</div>
              <div v-if="item.subtitle" class="card-subtitle">{{ item.subtitle }}</div>
            </div>
          </div>
        </div>
      </section>

      <!-- 4. 公告横幅 (Notice) -->
      <section v-else-if="sec.component === 'notice'" class="section-notice">
        <div class="notice-box">
          <span class="notice-icon">📢</span>
          <span class="notice-text">{{ sec.props?.message || sec.props?.title }}</span>
        </div>
      </section>

      <!-- 5. 空状态 (Empty State) -->
      <section v-else-if="sec.component === 'empty_state'" class="section-empty">
        <div class="empty-box">
          <p>{{ sec.props?.message || '暂无内容' }}</p>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.dynamic-sections-container {
  display: flex;
  flex-direction: column;
  gap: var(--plove-gap, 16px);
  width: 100%;
}

/* 巨幕横幅样式 */
.section-hero {
  position: relative;
  width: 100%;
  height: clamp(260px, 45vw, 480px);
  overflow: hidden;
  border-radius: var(--plove-radius, 6px);
  display: flex;
  align-items: flex-end;
  padding: clamp(16px, 4vw, 36px);
  box-sizing: border-box;
}

.hero-backdrop {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center top;
  background-repeat: no-repeat;
  filter: brightness(0.85);
  transition: transform 0.5s ease;
}

.hero-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    to bottom,
    rgba(20, 20, 20, 0.2) 0%,
    rgba(20, 20, 20, 0.6) 60%,
    rgba(20, 20, 20, 0.95) 100%
  );
}

.hero-content {
  position: relative;
  z-index: 2;
  max-width: 600px;
}

.hero-title {
  font-size: clamp(22px, 3.8vw, 36px);
  font-weight: 800;
  color: var(--plove-text, #ffffff);
  margin: 0 0 8px 0;
  line-height: 1.2;
}

.hero-subtitle {
  font-size: clamp(13px, 1.8vw, 16px);
  color: var(--plove-muted, #b8b8b8);
  margin: 0 0 16px 0;
  line-height: 1.4;
}

.hero-actions {
  display: flex;
  gap: 12px;
}

.hero-play-btn {
  background: var(--plove-accent, #e50914);
  color: #ffffff;
  border: none;
  border-radius: var(--plove-radius, 4px);
  padding: 10px 24px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: opacity 0.2s, transform 0.1s;
}

.hero-play-btn:hover {
  opacity: 0.9;
  transform: scale(1.02);
}

/* 栏目头部 */
.section-header {
  padding: 4px 0 8px 0;
}

.section-title {
  font-size: clamp(16px, 2.2vw, 20px);
  font-weight: 700;
  color: var(--plove-text, #ffffff);
  margin: 0;
}

/* 横向滚动栏目 */
.rail-scroll-track {
  display: flex;
  gap: var(--plove-gap, 12px);
  overflow-x: auto;
  scroll-behavior: smooth;
  padding-bottom: 8px;
  -webkit-overflow-scrolling: touch;
}

.rail-scroll-track::-webkit-scrollbar {
  height: 4px;
}

.rail-scroll-track::-webkit-scrollbar-thumb {
  background: var(--plove-line, #333333);
  border-radius: 4px;
}

.rail-card {
  flex: 0 0 clamp(130px, 18vw, 190px);
  cursor: pointer;
  transition: transform 0.2s ease;
}

.rail-card:hover {
  transform: translateY(-4px);
}

/* 响应式网格 */
.section-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(clamp(130px, 16vw, 180px), 1fr));
  gap: var(--plove-gap, 14px);
}

.grid-card {
  cursor: pointer;
  transition: transform 0.2s ease;
}

.grid-card:hover {
  transform: translateY(-4px);
}

/* 卡片海报与信息 */
.card-poster-wrap {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: var(--plove-radius, 6px);
  overflow: hidden;
  background: var(--plove-surface, #202020);
}

.card-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.card-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
  color: var(--plove-muted, #8c8c8c);
  font-size: 12px;
  text-align: center;
  box-sizing: border-box;
}

.card-badge {
  position: absolute;
  top: 6px;
  right: 6px;
  background: var(--plove-accent, #e50914);
  color: #ffffff;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 3px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.4);
}

.card-meta {
  padding-top: 6px;
}

.card-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--plove-text, #ffffff);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-subtitle {
  font-size: 11px;
  color: var(--plove-muted, #8c8c8c);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 2px;
}

/* 公告区块 */
.section-notice {
  padding: 4px 0;
}

.notice-box {
  background: var(--plove-surface, #202020);
  border: 1px solid var(--plove-line, #2a2a2a);
  border-radius: var(--plove-radius, 6px);
  padding: 10px 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--plove-text, #ffffff);
  font-size: 13px;
}

/* 空状态 */
.section-empty {
  padding: 30px 0;
  text-align: center;
  color: var(--plove-muted, #8c8c8c);
}
</style>
