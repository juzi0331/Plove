<script setup lang="ts">
import { Plus } from '@element-plus/icons-vue'
import {
  ElButton,
  ElForm,
  ElInput,
  ElRadio,
  ElRadioGroup,
  ElTag,
} from 'element-plus'

import type { SiteDetailPolicyPayload } from '@/api/types'
import { ui } from '@/admin/ui'

defineProps<{
  detailPolicy: SiteDetailPolicyPayload
  detailPolicyLoading: boolean
  detailPolicySaving: boolean
  adPatternInput: string
  newLineOrig: string
  newLineAlias: string
}>()

const emit = defineEmits<{
  (e: 'removeAdPattern', idx: number): void
  (e: 'update:adPatternInput', val: string): void
  (e: 'addAdPattern'): void
  (e: 'removeLineOverride', orig: string): void
  (e: 'update:newLineOrig', val: string): void
  (e: 'update:newLineAlias', val: string): void
  (e: 'addLineOverride'): void
  (e: 'saveDetailPolicy'): void
}>()
</script>

<template>
  <div v-loading="detailPolicyLoading" class="tab-pane-content">
    <ElForm label-position="top" class="policy-clean-form">
      <!-- 板块 1: 牛皮癣广告过滤 -->
      <div class="policy-card-section">
        <div class="policy-card-header">
          <div class="policy-card-title">牛皮癣广告清洗过滤</div>
          <div class="policy-card-desc">
            命中关键词或正则表达式将自动从剧名、备注与简介中剔除，保护播放端纯净体验
          </div>
        </div>

        <div class="policy-card-body">
          <div class="tags-editor-box">
            <template v-if="(detailPolicy.ad_patterns || []).length > 0">
              <ElTag
                v-for="(pat, pIdx) in detailPolicy.ad_patterns"
                :key="pIdx"
                closable
                type="danger"
                effect="plain"
                class="ad-tag"
                @close="emit('removeAdPattern', pIdx)"
              >
                {{ pat }}
              </ElTag>
            </template>
            <div v-else class="empty-policy-hint">
              暂无过滤规则。在下方输入广告关键词或正则表达式添加规则
            </div>
          </div>

          <div class="add-pattern-row">
            <ElInput
              :model-value="adPatternInput"
              placeholder="输入广告关键词或正则（如：菠菜、TG频道、http://...）"
              size="small"
              style="flex: 1;"
              :disabled="ui.readOnly"
              @update:model-value="(val) => emit('update:adPatternInput', val as string)"
              @keyup.enter="emit('addAdPattern')"
            />
            <ElButton
              size="small"
              type="primary"
              plain
              :icon="Plus"
              :disabled="ui.readOnly"
              @click="emit('addAdPattern')"
            >
              添加规则
            </ElButton>
          </div>
        </div>
      </div>

      <!-- 板块 2: 线路别名映射 -->
      <div class="policy-card-section">
        <div class="policy-card-header">
          <div class="policy-card-title">线路名称友好别名映射</div>
          <div class="policy-card-desc">
            将源站原始线路名映射为直观别名（如：ffm3u8 ➔ 极速蓝光专线，kkm3u8 ➔ 4K超清专线）
          </div>
        </div>

        <div class="policy-card-body">
          <div class="line-overrides-box">
            <template v-if="detailPolicy.line_name_overrides && Object.keys(detailPolicy.line_name_overrides).length > 0">
              <div
                v-for="(alias, orig) in detailPolicy.line_name_overrides"
                :key="orig"
                class="line-override-pill"
              >
                <code class="orig-code">{{ orig }}</code>
                <span class="arrow">&rarr;</span>
                <span class="alias-text">{{ alias }}</span>
                <span
                  class="del-btn"
                  title="删除此映射"
                  @click="emit('removeLineOverride', String(orig))"
                >
                  ✕
                </span>
              </div>
            </template>
            <div v-else class="empty-policy-hint">
              暂无别名映射，线路将显示采集器原始名称
            </div>
          </div>

          <div class="add-override-row">
            <ElInput
              :model-value="newLineOrig"
              placeholder="原始线路名 (如 ffm3u8)"
              size="small"
              style="flex: 1;"
              :disabled="ui.readOnly"
              @update:model-value="(val) => emit('update:newLineOrig', val as string)"
            />
            <ElInput
              :model-value="newLineAlias"
              placeholder="前台显示别名 (如 极速蓝光专线)"
              size="small"
              style="flex: 1;"
              :disabled="ui.readOnly"
              @update:model-value="(val) => emit('update:newLineAlias', val as string)"
            />
            <ElButton
              size="small"
              type="primary"
              plain
              :icon="Plus"
              :disabled="ui.readOnly"
              @click="emit('addLineOverride')"
            >
              添加映射
            </ElButton>
          </div>
        </div>
      </div>

      <!-- 板块 3: 剧集标题规范化 -->
      <div class="policy-card-section">
        <div class="policy-card-header">
          <div class="policy-card-title">集数标题自动规范化策略</div>
          <div class="policy-card-desc">自动解析并格式化源站剧集标题序号</div>
        </div>
        <div class="policy-card-body">
          <ElRadioGroup v-model="detailPolicy.ep_naming_rule" :disabled="ui.readOnly">
            <ElRadio value="auto">智能提取（第01集、全集等）</ElRadio>
            <ElRadio value="keep_raw">保持源站原始剧集文本</ElRadio>
            <ElRadio value="numeric_only">纯序号提取（1, 2, 3...）</ElRadio>
          </ElRadioGroup>
        </div>
      </div>

      <div class="pane-footer-actions">
        <ElButton
          type="primary"
          :loading="detailPolicySaving"
          :disabled="ui.readOnly"
          @click="emit('saveDetailPolicy')"
        >
          保存广告清洗与线路策略
        </ElButton>
      </div>
    </ElForm>
  </div>
</template>

<style scoped src="./site-detail-modal.css"></style>
