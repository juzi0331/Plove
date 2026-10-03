<script setup lang="ts">
/**
 * 选源页。它存在的理由只有一条：**源随时会坏，用户得有个地方换。**
 * 所以这里的重点不是好看，而是"哪个源能用"要一眼看得出来。
 */
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

import StateBlock from '@/components/StateBlock.vue'
import { useSitesStore } from '@/stores/sites'

const sites = useSitesStore()
const router = useRouter()

onMounted(() => void sites.load(true))

async function choose(key: string): Promise<void> {
  sites.select(key)
  await router.push({ name: 'home' })
}
</script>

<template>
  <div class="page sites">
    <van-nav-bar title="选择片源" left-arrow @click-left="router.back()" />

    <StateBlock
      :loading="sites.loading"
      :error="sites.lastError"
      :empty="sites.isEmpty"
      empty-text="后端还没有可用的源"
      skeleton="none"
      @retry="sites.load(true)"
    >
      <ul class="sites__list">
        <li v-for="site in sites.sites" :key="site.key">
          <button
            class="site"
            :class="{ 'is-active': site.key === sites.currentKey }"
            type="button"
            @click="choose(site.key)"
          >
            <span class="site__body">
              <span class="site__name">
                {{ site.name }}
                <span v-if="site.key === sites.currentKey" class="site__now">当前</span>
              </span>
              <span class="site__note">{{ site.note ?? site.base_url }}</span>
              <span class="site__key">{{ site.key }}</span>
            </span>
            <span class="site__chevron">›</span>
          </button>
        </li>
      </ul>

      <p class="sites__hint">
        这里只会列出真的能跑起来的源（后端逐个调过一次 meta）。<br />
        某个源坏掉时，换一个就行 —— 这也是这个页面存在的理由。
      </p>
    </StateBlock>
  </div>
</template>

<style scoped>
.sites__list {
  margin: 8px 0 0;
  padding: 0 var(--plove-pad);
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.site {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 14px var(--plove-pad-sm);
  border: 1px solid var(--plove-line);
  border-radius: var(--plove-radius);
  background: var(--plove-surface);
  color: var(--plove-text);
  text-align: left;
}

.site.is-active {
  border-color: var(--plove-accent);
}

.site:active {
  background: var(--plove-surface-2);
}

.site__body {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.site__name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 700;
}

.site__now {
  padding: 1px 6px;
  border-radius: var(--plove-radius-pill);
  background: var(--plove-accent);
  color: #fff;
  font-size: 10px;
  font-weight: 700;
}

.site__note {
  color: var(--plove-text-dim);
  font-size: 12px;
  line-height: 1.5;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.site__key {
  color: #5c5c5c;
  font-size: 11px;
}

.site__chevron {
  flex: 0 0 auto;
  color: var(--plove-muted);
  font-size: 20px;
}

.sites__hint {
  margin: 20px var(--plove-pad) 0;
  color: var(--plove-muted);
  font-size: 12px;
  line-height: 1.8;
}
</style>
