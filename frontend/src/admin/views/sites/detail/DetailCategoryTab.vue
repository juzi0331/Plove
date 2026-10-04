<script setup lang="ts">
import { Plus, Right } from '@element-plus/icons-vue'
import {
  ElAlert,
  ElButton,
  ElEmpty,
  ElIcon,
  ElInput,
  ElOption,
  ElPopover,
  ElSelect,
  ElSwitch,
} from 'element-plus'

import type {
  CategoryRuleItem,
  SiteCategoryRulePayload,
  SubCategoryItem,
} from '@/api/types'
import { ui } from '@/admin/ui'

defineProps<{
  categoryPayload: SiteCategoryRulePayload
  categoryLoading: boolean
  categorySaving: boolean
  getSubInput: (tid: string) => { tid: string; name: string; custom_name?: string }
  formatCategoryPreview: (rawName: string, customName?: string) => string
  toggleSubCategoryHidden: (sub: SubCategoryItem) => void
  addSubCategory: (rule: CategoryRuleItem) => void
  removeSubCategory: (rule: CategoryRuleItem, sub: SubCategoryItem) => void
}>()

const emit = defineEmits<{
  (e: 'saveCategory'): void
}>()
</script>

<template>
  <div v-loading="categoryLoading" class="tab-pane-content">
    <ElAlert
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 16px;"
    >
      您可以在此决定哪些分类在首页横向展示、屏蔽不需要的垃圾分类、重命名分类显示名称，或挂载二级子分类与筛选标签。
    </ElAlert>

    <div class="default-tid-bar">
      <span class="bar-label">用户端默认推荐主分类 TID：</span>
      <ElSelect
        v-model="categoryPayload.default_tid"
        placeholder="系统默认第一项"
        clearable
        style="width: 240px;"
      >
        <ElOption
          v-for="r in (categoryPayload.rules || [])"
          :key="r.tid"
          :label="`${r.name} (TID: ${r.tid})`"
          :value="r.tid"
        />
      </ElSelect>
    </div>

    <div v-if="!categoryPayload.rules || categoryPayload.rules.length === 0" class="empty-rules">
      <ElEmpty description="该采集器尚未返回任何分类数据，请先在探针中测试分类接口" />
    </div>

    <div v-else class="rules-list">
      <div
        v-for="rule in (categoryPayload.rules || [])"
        :key="rule.tid"
        class="category-rule-card"
        :class="{ 'is-hidden': rule.hidden }"
      >
        <div class="rule-card-header">
          <div class="rule-title-group">
            <span class="rule-tid-badge">TID: {{ rule.tid }}</span>
            <span class="rule-orig-name">{{ rule.name }}</span>
            <ElIcon v-if="rule.custom_name" :size="12"><Right /></ElIcon>
            <span v-if="rule.custom_name" class="rule-preview-name">
              {{ formatCategoryPreview(rule.name, rule.custom_name) }}
            </span>
          </div>

          <div class="rule-switches">
            <ElSwitch
              v-model="rule.show_on_home"
              active-text="首页横向展示"
              size="small"
              :disabled="rule.hidden || ui.readOnly"
            />
            <ElSwitch
              v-model="rule.hidden"
              active-text="屏蔽此分类"
              size="small"
              active-color="var(--el-color-danger)"
              :disabled="ui.readOnly"
            />
          </div>
        </div>

        <div v-if="!rule.hidden" class="rule-body">
          <div class="rule-inputs-row">
            <ElInput
              v-model="rule.custom_name"
              placeholder="自定义别名（如：热播国产剧）"
              size="small"
              style="flex: 1;"
              :disabled="ui.readOnly"
            />
            <span class="sub-count-tag">
              子分类 ({{ rule.subcategories?.length || 0 }})
            </span>
          </div>

          <!-- 二级子分类标签 -->
          <div class="sub-categories-wrap">
            <div
              v-for="sub in (rule.subcategories || [])"
              :key="sub.tid"
              class="sub-pill"
              :class="{ 'sub-pill--hidden': sub.hidden }"
              :title="sub.hidden ? '点击解除屏蔽' : '点击屏蔽此子标签'"
              @click="toggleSubCategoryHidden(sub)"
            >
              <span class="sub-pill-name">{{ sub.name }}</span>
              <span
                class="sub-pill-del"
                title="删除子分类"
                @click.stop="removeSubCategory(rule, sub)"
              >
                ×
              </span>
            </div>

            <ElPopover placement="bottom-start" :width="280" trigger="click">
              <template #reference>
                <ElButton size="small" :icon="Plus" plain class="add-sub-btn">
                  添加子标签
                </ElButton>
              </template>
              <div class="add-sub-popover">
                <div class="popover-title">挂载子分类 / 过滤标签</div>
                <ElInput
                  v-model="getSubInput(rule.tid).tid"
                  placeholder="子分类 TID（如 13）"
                  size="small"
                  style="margin-bottom: 8px;"
                />
                <ElInput
                  v-model="getSubInput(rule.tid).name"
                  placeholder="子分类名称（如 动作片）"
                  size="small"
                  style="margin-bottom: 8px;"
                />
                <ElButton
                  size="small"
                  type="primary"
                  style="width: 100%;"
                  @click="addSubCategory(rule)"
                >
                  确认添加
                </ElButton>
              </div>
            </ElPopover>
          </div>
        </div>
      </div>
    </div>

    <div class="pane-footer-actions">
      <ElButton
        type="primary"
        :loading="categorySaving"
        :disabled="ui.readOnly"
        @click="emit('saveCategory')"
      >
        保存分类规则
      </ElButton>
    </div>
  </div>
</template>

<style scoped src="./site-detail-modal.css"></style>
