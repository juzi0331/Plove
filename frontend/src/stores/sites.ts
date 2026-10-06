/**
 * 站点（源）状态：有哪些源、当前在用哪个。
 *
 * 为什么要让用户能换源：两个源都是抓来的第三方站，**任何一个随时可能坏**
 * （被反爬、改版、变慢）。出现这种情况时用户唯一的自救手段就是换一个源，
 * 所以\"选源\"必须是一等公民，而不是藏在设置里。
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import * as api from '@/api/client'
import { describeError } from '@/api/http'
import type { SiteMeta, VodCategory } from '@/api/types'

const KEY = 'plove.site_key'

export const useSitesStore = defineStore('sites', () => {
  const sites = ref<SiteMeta[]>([])
  const currentKey = ref<string | null>(readSavedKey())
  const loading = ref(false)
  const lastError = ref<string | null>(null)

  // 站点与分类共享响应式缓存：siteKey -> VodCategory[]
  const categoriesMap = ref<Record<string, VodCategory[]>>({})
  const categoriesLoading = ref(false)

  const current = computed(() => sites.value.find((s) => s.key === currentKey.value) ?? null)
  const isEmpty = computed(() => !loading.value && sites.value.length === 0)

  // 当前选中站点的分类列表（自动过滤隐藏分类）
  const currentCategories = computed<VodCategory[]>(() => {
    if (!currentKey.value) return []
    return (categoriesMap.value[currentKey.value] ?? []).filter((c) => !c.hidden)
  })

  function getCategories(key: string): VodCategory[] | undefined {
    return categoriesMap.value[key]
  }

  function setCategories(key: string, cats: VodCategory[]): void {
    categoriesMap.value = {
      ...categoriesMap.value,
      [key]: cats,
    }
  }

  async function loadCategoriesForSite(key: string, force = false): Promise<VodCategory[]> {
    if (!force && categoriesMap.value[key] && categoriesMap.value[key].length > 0) {
      return categoriesMap.value[key]
    }
    try {
      categoriesLoading.value = true
      const homeData = await api.getHome(key)
      const cats = homeData.categories ?? []
      setCategories(key, cats)
      return cats
    } catch (err) {
      throw err
    } finally {
      categoriesLoading.value = false
    }
  }

  function readSavedKey(): string | null {
    try {
      return localStorage.getItem(KEY)
    } catch {
      return null
    }
  }

  function select(key: string): void {
    currentKey.value = key
    try {
      localStorage.setItem(KEY, key)
    } catch {
      /* 存不进就算了 */
    }
  }

  let inFlightPromise: Promise<void> | null = null

  /**
   * 拉取站点列表。
   *
   * `force` 为 false 时如果已经加载过就直接返回 —— 站点列表在一次会话里
   * 基本不会变，没必要每次进首页都去问一遍。
   */
  async function load(force = false): Promise<void> {
    if (inFlightPromise) return inFlightPromise
    if (!force && sites.value.length > 0) return

    loading.value = true
    lastError.value = null
    inFlightPromise = (async () => {
      try {
        const result = await api.listSites()
        sites.value = result.sites ?? []
        // 当前选的源可能已经没了（被下架 / 跑不起来）—— 这时自动切到第一个，
        // 否则用户会停在一个永远转圈的首页上。
        if (sites.value.length > 0 && !sites.value.some((s) => s.key === currentKey.value)) {
          select(sites.value[0]!.key)
        }
        if (sites.value.length === 0) currentKey.value = null
      } catch (error) {
        lastError.value = describeError(error)
      } finally {
        loading.value = false
        inFlightPromise = null
      }
    })()

    return inFlightPromise
  }

  /** 在当前源出问题时用：切到列表里的下一个源 */
  function nextSite(): string | null {
    if (sites.value.length < 2) return null
    const index = sites.value.findIndex((s) => s.key === currentKey.value)
    const next = sites.value[(index + 1) % sites.value.length]!
    select(next.key)
    return next.key
  }

  return {
    sites,
    currentKey,
    current,
    loading,
    lastError,
    isEmpty,
    categoriesMap,
    categoriesLoading,
    currentCategories,
    getCategories,
    setCategories,
    loadCategoriesForSite,
    load,
    select,
    nextSite,
  }
})
