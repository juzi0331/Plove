<script setup lang="ts">
/**
 * SiteDetailPolicy - 详情页展示策略（广告过滤、线路映射、集数命名、兜底海报）对话框
 */
import {
  ElButton,
  ElDialog,
  ElDivider,
  ElForm,
  ElFormItem,
  ElInput,
  ElRadio,
  ElRadioGroup,
  ElTag,
} from 'element-plus'

import type { SiteDetailPolicyPayload } from '@/api/types'

defineProps<{
  modelValue: boolean
  detailPolicy: SiteDetailPolicyPayload
  detailPolicyLoading: boolean
  detailPolicySaving: boolean
  adPatternInput: string
  newLineOrig: string
  newLineAlias: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'update:adPatternInput', value: string): void
  (e: 'update:newLineOrig', value: string): void
  (e: 'update:newLineAlias', value: string): void
  (e: 'addAdPattern'): void
  (e: 'removeAdPattern', idx: number): void
  (e: 'addLineOverride'): void
  (e: 'removeLineOverride', orig: string): void
  (e: 'save'): void
}>()
</script>

<template>
  <ElDialog
    :model-value="modelValue"
    :title="`详情页展示与清洗策略 · ${detailPolicy.site_key}`"
    width="680px"
    destroy-on-close
    @update:model-value="(val) => emit('update:modelValue', val)"
  >
    <div v-loading="detailPolicyLoading">
      <ElForm label-position="top">
        <!-- 广告清洗黑名单 -->
        <ElFormItem label="牛皮癣广告过滤（命中关键词或正则将自动从剧名、备注与简介中剔除）">
          <div class="tags-editor">
            <ElTag
              v-for="(pat, pIdx) in (detailPolicy.ad_patterns || [])"
              :key="pIdx"
              closable
              type="danger"
              effect="plain"
              class="pat-tag"
              @close="emit('removeAdPattern', pIdx)"
            >
              {{ pat }}
            </ElTag>
          </div>
          <div class="add-pat-row">
            <ElInput
              :model-value="adPatternInput"
              placeholder="输入广告词或正则，如：关注公众号|最新无删减"
              size="small"
              @update:model-value="(val) => emit('update:adPatternInput', String(val))"
              @keyup.enter="emit('addAdPattern')"
            />
            <ElButton size="small" type="primary" @click="emit('addAdPattern')">添加过滤词</ElButton>
          </div>
        </ElFormItem>

        <ElDivider />

        <!-- 线路别名映射 -->
        <ElFormItem label="线路名称别名映射（将难看源站线路重命名为高大上专线）">
          <div class="overrides-table">
            <div
              v-for="(alias, orig) in (detailPolicy.line_name_overrides || {})"
              :key="orig"
              class="override-row"
            >
              <span class="a-mono orig-name">{{ orig }}</span>
              <span class="arrow">&rarr;</span>
              <span class="alias-name">{{ alias }}</span>
              <ElButton link type="danger" size="small" @click="emit('removeLineOverride', String(orig))">删除</ElButton>
            </div>
            <div v-if="!Object.keys(detailPolicy.line_name_overrides || {}).length" class="a-muted no-sub">
              未配置映射（保持源站原样）
            </div>
          </div>
          <div class="add-line-row">
            <ElInput
              :model-value="newLineOrig"
              placeholder="源站线路名（如 lzm3u8）"
              size="small"
              style="width: 200px;"
              @update:model-value="(val) => emit('update:newLineOrig', String(val))"
            />
            <ElInput
              :model-value="newLineAlias"
              placeholder="映射别名（如 超清极速专线）"
              size="small"
              style="width: 220px;"
              @update:model-value="(val) => emit('update:newLineAlias', String(val))"
            />
            <ElButton size="small" type="primary" @click="emit('addLineOverride')">添加映射</ElButton>
          </div>
        </ElFormItem>

        <ElDivider />

        <!-- 集数命名 -->
        <ElFormItem label="剧集名称格式化规则">
          <ElRadioGroup v-model="detailPolicy.ep_naming_rule">
            <ElRadio value="auto">智能清洗（剔除重复剧名与长前缀，推荐）</ElRadio>
            <ElRadio value="standard">强制统一（统一格式化为「第 N 集」）</ElRadio>
            <ElRadio value="raw">原始名称（完全保留源站输出）</ElRadio>
          </ElRadioGroup>
        </ElFormItem>

        <!-- 兜底海报 -->
        <ElFormItem label="兜底海报 URL（海报为空或源站防盗链失效时兜底展示）">
          <ElInput v-model="detailPolicy.default_poster" placeholder="https://.../fallback_poster.jpg" />
        </ElFormItem>
      </ElForm>
    </div>

    <template #footer>
      <ElButton @click="emit('update:modelValue', false)">取消</ElButton>
      <ElButton type="primary" :loading="detailPolicySaving" @click="emit('save')">
        保存策略
      </ElButton>
    </template>
  </ElDialog>
</template>
