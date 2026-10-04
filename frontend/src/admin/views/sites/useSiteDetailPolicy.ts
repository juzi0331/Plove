/**
 * useSiteDetailPolicy - 详情页展示策略（广告清洗、线路别名映射、集数规则、兜底海报）
 */

import { ElMessage } from 'element-plus'
import { ref } from 'vue'

import { describeError } from '@/api/http'
import type { AdminSiteItem, SiteDetailPolicyPayload } from '@/api/types'

import * as api from '../../api'

export function useSiteDetailPolicy() {
  const isDetailPolicyVisible = ref(false)
  const detailPolicyLoading = ref(false)
  const detailPolicySaving = ref(false)
  const detailPolicy = ref<SiteDetailPolicyPayload>({
    site_key: '',
    ad_patterns: [],
    line_name_overrides: {},
    ep_naming_rule: 'auto',
    default_poster: '',
    hide_fields: [],
  })

  const adPatternInput = ref('')
  const newLineOrig = ref('')
  const newLineAlias = ref('')

  async function openDetailPolicy(site: AdminSiteItem): Promise<void> {
    detailPolicy.value = {
      site_key: site.key,
      ad_patterns: [],
      line_name_overrides: {},
      ep_naming_rule: 'auto',
      default_poster: '',
      hide_fields: [],
    }
    adPatternInput.value = ''
    newLineOrig.value = ''
    newLineAlias.value = ''
    isDetailPolicyVisible.value = true
    detailPolicyLoading.value = true
    try {
      const res = await api.getSiteDetailPolicy(site.key)
      detailPolicy.value = {
        site_key: res.site_key,
        ad_patterns: res.ad_patterns ?? [],
        line_name_overrides: res.line_name_overrides ?? {},
        ep_naming_rule: res.ep_naming_rule ?? 'auto',
        default_poster: res.default_poster ?? '',
        hide_fields: res.hide_fields ?? [],
      }
    } catch (err) {
      ElMessage.error(describeError(err))
    } finally {
      detailPolicyLoading.value = false
    }
  }

  function addAdPattern(): void {
    const val = adPatternInput.value.trim()
    if (!val) return
    detailPolicy.value.ad_patterns ??= []
    if (!detailPolicy.value.ad_patterns.includes(val)) {
      detailPolicy.value.ad_patterns.push(val)
    }
    adPatternInput.value = ''
  }

  function removeAdPattern(idx: number): void {
    detailPolicy.value.ad_patterns?.splice(idx, 1)
  }

  function addLineOverride(): void {
    const orig = newLineOrig.value.trim()
    const alias = newLineAlias.value.trim()
    if (!orig || !alias) {
      ElMessage.warning('请输入原始线路名与映射别名')
      return
    }
    detailPolicy.value.line_name_overrides ??= {}
    detailPolicy.value.line_name_overrides[orig] = alias
    newLineOrig.value = ''
    newLineAlias.value = ''
  }

  function removeLineOverride(orig: string): void {
    if (!detailPolicy.value.line_name_overrides) return
    delete detailPolicy.value.line_name_overrides[orig]
  }

  async function saveDetailPolicy(): Promise<void> {
    detailPolicySaving.value = true
    try {
      await api.updateSiteDetailPolicy(detailPolicy.value.site_key, {
        ad_patterns: detailPolicy.value.ad_patterns,
        line_name_overrides: detailPolicy.value.line_name_overrides,
        ep_naming_rule: detailPolicy.value.ep_naming_rule,
        default_poster: detailPolicy.value.default_poster,
        hide_fields: detailPolicy.value.hide_fields,
      })
      ElMessage.success('详情页显示策略已保存')
      isDetailPolicyVisible.value = false
    } catch (err) {
      ElMessage.error(describeError(err))
    } finally {
      detailPolicySaving.value = false
    }
  }

  return {
    isDetailPolicyVisible,
    detailPolicyLoading,
    detailPolicySaving,
    detailPolicy,
    adPatternInput,
    newLineOrig,
    newLineAlias,
    openDetailPolicy,
    addAdPattern,
    removeAdPattern,
    addLineOverride,
    removeLineOverride,
    saveDetailPolicy,
  }
}
