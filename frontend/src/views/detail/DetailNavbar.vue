<script setup lang="ts">
import { useRouter } from 'vue-router'
import BrandLogo from '@/components/BrandLogo.vue'
import UserMenu from '@/components/UserMenu.vue'

const props = defineProps<{
  scrolled: boolean
  vodName?: string
}>()

const emit = defineEmits<{
  goBack: []
}>()

const router = useRouter()
</script>

<template>
  <header class="nf-navbar" :class="{ 'is-scrolled': props.scrolled }">
    <div class="nf-navbar__left">
      <!-- 品牌官方 Logo -->
      <BrandLogo :width="118" :height="32" @click="router.push({ name: 'home' })" />

      <!-- 返回主页按钮 -->
      <button class="nf-back-btn" type="button" @click="emit('goBack')">
        <span class="nf-back-arrow">‹</span>
        <span class="nf-back-text">返回</span>
      </button>

      <!-- 当前影片标题标签 -->
      <span v-if="props.vodName" class="nf-nav-vod-title">{{ props.vodName }}</span>
    </div>

    <div class="nf-navbar__right">
      <!-- 用户头像与 VIP 会员到期时间面板组件 -->
      <UserMenu />
    </div>
  </header>
</template>
