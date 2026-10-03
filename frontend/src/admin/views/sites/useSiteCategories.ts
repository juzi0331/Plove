/**
 * useSiteCategories - 站点分类与子分类/标签规则控制
 */

import { ElMessage } from 'element-plus'
import { ref } from 'vue'

import { describeError } from '@/api/http'
import type {
  AdminSiteItem,
  CategoryRuleItem,
  SiteCategoryRulePayload,
  SubCategoryItem,
} from '@/api/types'

import * as api from '../../api'

export function useSiteCategories() {
  const isCategoryDrawerVisible = ref(false)
  const categoryLoading = ref(false)
  const categorySaving = ref(false)
  const categoryPayload = ref<SiteCategoryRulePayload>({
    site_key: '',
    rules: [],
    default_tid: null,
  })

  // 为每个分类维护新增子分类的临时输入
  const subCatInputs = ref<Record<string, { tid: string; name: string; custom_name?: string }>>({})

  function getSubInput(tid: string): { tid: string; name: string; custom_name?: string } {
    if (!subCatInputs.value[tid]) {
      subCatInputs.value[tid] = { tid: '', name: '', custom_name: '' }
    }
    return subCatInputs.value[tid]!
  }

  function formatCategoryPreview(rawName: string, customName?: string): string {
    if (!customName || !customName.trim()) {
      return rawName
    }
    let c = customName.trim()
    if ((c.startsWith('(') && c.endsWith(')')) || (c.startsWith('（') && c.endsWith('）'))) {
      c = c.slice(1, -1).trim()
    }
    if (!c) return rawName
    return `${rawName}（${c}）`
  }

  function toggleSubCategoryHidden(sub: SubCategoryItem): void {
    sub.hidden = !sub.hidden
  }

  async function openCategoryDrawer(site: AdminSiteItem): Promise<void> {
    categoryPayload.value = {
      site_key: site.key,
      rules: [],
      default_tid: null,
    }
    subCatInputs.value = {}
    isCategoryDrawerVisible.value = true
    categoryLoading.value = true
    try {
      const res = await api.getSiteCategories(site.key)
      categoryPayload.value = {
        site_key: res.site_key,
        rules: (res.rules ?? []).map((r) => ({
          ...r,
          subcategories: (r.subcategories ?? []).map((s) => ({
            ...s,
            custom_name: s.custom_name ?? '',
            hidden: !!s.hidden,
          })),
        })),
        default_tid: res.default_tid ?? null,
      }
    } catch (err) {
      ElMessage.error(describeError(err))
    } finally {
      categoryLoading.value = false
    }
  }

  function addSubCategory(rule: CategoryRuleItem): void {
    const input = getSubInput(rule.tid)
    if (!input.tid.trim() || !input.name.trim()) {
      ElMessage.warning('请输入子分类 ID 与名称')
      return
    }
    rule.subcategories ??= []
    if (rule.subcategories.some((s) => s.tid === input.tid.trim())) {
      ElMessage.warning('子分类 ID 已存在')
      return
    }
    rule.subcategories.push({
      tid: input.tid.trim(),
      name: input.name.trim(),
      custom_name: input.custom_name?.trim() || '',
      hidden: false,
    })
    input.tid = ''
    input.name = ''
    input.custom_name = ''
  }

  function removeSubCategory(rule: CategoryRuleItem, sub: SubCategoryItem): void {
    if (!rule.subcategories) return
    rule.subcategories = rule.subcategories.filter((s) => s.tid !== sub.tid)
  }

  async function saveCategoryRules(): Promise<void> {
    categorySaving.value = true
    try {
      await api.updateSiteCategories(categoryPayload.value.site_key, {
        rules: categoryPayload.value.rules,
        default_tid: categoryPayload.value.default_tid,
      })
      ElMessage.success('分类与子分类规则已保存')
      isCategoryDrawerVisible.value = false
    } catch (err) {
      ElMessage.error(describeError(err))
    } finally {
      categorySaving.value = false
    }
  }

  return {
    isCategoryDrawerVisible,
    categoryLoading,
    categorySaving,
    categoryPayload,
    getSubInput,
    formatCategoryPreview,
    toggleSubCategoryHidden,
    openCategoryDrawer,
    addSubCategory,
    removeSubCategory,
    saveCategoryRules,
  }
}
