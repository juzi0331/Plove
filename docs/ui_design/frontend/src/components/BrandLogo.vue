<script setup lang="ts">
/**
 * BrandLogo - 奈飞官方 1:1 标准规格 PLOVE 标识
 *
 * 严格遵照官方参数：
 * - 渲染大小：148 x 40 px
 * - 渲染宽高比：37:10
 * - 固有尺寸：370 x 100 px
 * - 固有宽高比：37:10
 */

withDefaults(
  defineProps<{
    width?: number | string
    height?: number | string
  }>(),
  {
    width: 148,
    height: 40,
  },
)
</script>

<template>
  <div class="nf-brand-logo">
    <img
      src="/logo.png"
      alt="PLOVE"
      class="nf-brand-logo__img"
      width="148"
      height="40"
      :style="{
        width: typeof width === 'number' ? `${width}px` : width,
        height: typeof height === 'number' ? `${height}px` : height,
      }"
    />
  </div>
</template>

<style scoped>
.nf-brand-logo {
  display: inline-flex;
  align-items: center;
  user-select: none;
  cursor: pointer;
  line-height: 1;
}

.nf-brand-logo__img {
  display: block;
  width: 148px;
  height: 40px;
  aspect-ratio: 37 / 10;
  object-fit: contain;
  transition: transform 0.22s cubic-bezier(0.2, 0, 0.1, 1);
}

.nf-brand-logo:hover .nf-brand-logo__img {
  transform: scale(1.04);
}
</style>
