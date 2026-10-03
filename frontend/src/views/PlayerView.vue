<script setup lang="ts">
import PlayerView from './player/PlayerView.vue'

defineProps<{ vodId: string; ep: string }>()
</script>

<template>
  <PlayerView :vod-id="vodId" :ep="ep" />
</template>
