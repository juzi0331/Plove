<script setup lang="ts">
/**
 * 加载 / 出错 / 空 三态的统一呈现。
 *
 * 为什么要抽出来：源站随时可能坏，这三个状态在每个内容页面都会出现。
 * 如果每个页面各写一遍，就会出现"首页说源站超时、详情说网络错误"这种
 * 同一件事两种说法 —— 用户没法据此判断该重试还是该换源。
 *
 * 两个刻意的选择：
 *
 * 1. **加载态是骨架屏，不是转圈。** 转圈只说明"在忙"，骨架屏还能说明
 *    "会出来什么、长什么样"——页面结构提前就位，数据到了不会整页跳一下。
 *    影院风尤其需要这个：海报一块一块亮起来，比一个孤零零的圈好看得多。
 * 2. **出错时永远同时给「重试」和「换一个源」。** 源站坏了时重试往往没用，
 *    而"换源"是用户唯一能自救的手段（这也解释了首页那个换源入口为什么存在）。
 */

withDefaults(
  defineProps<{
    loading?: boolean
    /** 已经翻译成人话的错误（用 describeError 得到）。null = 没出错 */
    error?: string | null
    /** 加载完了但是空的 */
    empty?: boolean
    emptyText?: string
    /** 出错时除了"重试"，还给一个"换源" */
    canSwitchSite?: boolean
    /**
     * 加载态长什么样：
     * - `grid` 分类页那种三列网格
     * - `rows` 首页那种横向行
     * - `none` 播放页之类，骨架屏反而碍事
     */
    skeleton?: 'grid' | 'rows' | 'none'
  }>(),
  {
    loading: false,
    error: null,
    empty: false,
    emptyText: '这里什么都没有',
    canSwitchSite: false,
    skeleton: 'grid',
  },
)

const emit = defineEmits<{
  (event: 'retry'): void
  (event: 'switch-site'): void
}>()

//: 骨架屏铺几块。6 块正好填满一屏（2 行 3 列），多铺没有意义、还会拖慢首帧
const SKELETON_COUNT = 6
</script>

<template>
  <div v-if="loading" class="state-skeleton" :class="`state-skeleton--${skeleton}`">
    <div
      v-for="n in skeleton === 'none' ? 0 : SKELETON_COUNT"
      :key="n"
      class="state-skeleton__tile"
    />
  </div>

  <div v-else-if="error" class="state-block">
    <p class="state-block__text">{{ error }}</p>
    <div class="state-block__actions">
      <van-button type="primary" @click="emit('retry')">重试</van-button>
      <van-button v-if="canSwitchSite" plain @click="emit('switch-site')">换一个源</van-button>
    </div>
  </div>

  <div v-else-if="empty" class="state-block">
    <p class="state-block__text">{{ emptyText }}</p>
  </div>

  <slot v-else />
</template>

<style scoped>
/* ------------------------------------------------------------ 骨架屏 */

.state-skeleton--grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--plove-gap);
  padding: var(--plove-pad);
}

.state-skeleton--rows {
  display: flex;
  gap: var(--plove-gap);
  padding: 0 var(--plove-pad);
  margin-top: var(--plove-row-gap);
  overflow: hidden;
}

.state-skeleton--rows .state-skeleton__tile {
  flex: 0 0 31vw;
  max-width: 130px;
}

.state-skeleton--none {
  padding: 0;
}

.state-skeleton__tile {
  aspect-ratio: 2 / 3;
  border-radius: var(--plove-radius);
  background: linear-gradient(100deg, #161616 30%, #242424 50%, #161616 70%);
  background-size: 220% 100%;
  animation: plove-shimmer 1.3s linear infinite;
}

@keyframes plove-shimmer {
  from {
    background-position: 220% 0;
  }
  to {
    background-position: -220% 0;
  }
}

/* 系统里关了动效就别晃（iOS 的"减弱动态效果"、安卓的"移除动画"都会命中） */
@media (prefers-reduced-motion: reduce) {
  .state-skeleton__tile {
    animation: none;
  }
}

/* ------------------------------------------------------------ 出错 / 空 */

.state-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 18px;
  padding: 56px 32px;
}

.state-block__text {
  margin: 0;
  max-width: 22em;
  color: var(--plove-text-dim);
  font-size: 14px;
  line-height: 1.7;
  text-align: center;
}

.state-block__actions {
  display: flex;
  gap: 12px;
}
</style>
