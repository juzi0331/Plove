<script setup lang="ts">
/**
 * SiteCategoryRules - 站点分类与子分类控制抽屉
 */
import {
  ElButton,
  ElDivider,
  ElDrawer,
  ElInput,
  ElInputNumber,
  ElOption,
  ElPopover,
  ElSelect,
  ElSwitch,
  ElTag,
} from 'element-plus'

import type {
  CategoryRuleItem,
  SiteCategoryRulePayload,
  SubCategoryItem,
} from '@/api/types'

defineProps<{
  modelValue: boolean
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
  (e: 'update:modelValue', value: boolean): void
  (e: 'save'): void
}>()
</script>

<template>
  <ElDrawer
    :model-value="modelValue"
    :title="`分类与子分类控制 · ${categoryPayload.site_key}`"
    size="720px"
    destroy-on-close
    @update:model-value="(val) => emit('update:modelValue', val)"
  >
    <div v-loading="categoryLoading" class="category-drawer-content">
      <div class="drawer-tip">
        源站分类由爬虫返回。您可以在此<strong>决定哪些分类在首页以横幅展示（每分类横向展示10部）</strong>、<strong>屏蔽不需要的分类</strong>、<strong>重命名分类名称</strong>，或<strong>挂载二级子分类与筛选标签</strong>。
      </div>

      <div class="default-tid-bar">
        <span class="bar-label">默认推荐分类 TID：</span>
        <ElSelect v-model="categoryPayload.default_tid" placeholder="默认全部" clearable style="width: 220px;">
          <ElOption
            v-for="r in categoryPayload.rules"
            :key="r.tid"
            :label="`${r.custom_name || r.name} (${r.tid})`"
            :value="r.tid"
          />
        </ElSelect>
      </div>

      <ElDivider />

      <div class="rules-list">
        <div
          v-for="rule in categoryPayload.rules"
          :key="rule.tid"
          class="rule-card"
          :class="{ 'is-hidden': rule.hidden }"
        >
          <div class="rule-header">
            <div class="rule-title-area">
              <span class="cat-tid a-mono">#{{ rule.tid }}</span>
              <span class="cat-raw-name">{{ rule.name }}</span>
              <ElTag v-if="rule.hidden" type="danger" size="small">已隐藏</ElTag>
              <ElTag v-else-if="rule.show_on_home" type="success" size="small">首页横幅 (10部)</ElTag>
            </div>

            <div class="rule-actions">
              <ElSwitch
                v-model="rule.hidden"
                active-text="屏蔽"
                inactive-text="展示"
                :active-value="true"
                :inactive-value="false"
                size="small"
              />
            </div>
          </div>

          <div v-if="!rule.hidden" class="rule-body">
            <div class="rule-row">
              <span class="label">前台别名：</span>
              <ElInput v-model="rule.custom_name" placeholder="留空保持原名" size="small" style="width: 150px;" clearable />
              <span class="cat-preview-text">
                前台显示：<strong :class="{ 'has-custom': !!rule.custom_name?.trim() }">{{ formatCategoryPreview(rule.name, rule.custom_name) }}</strong>
              </span>

              <span class="label ml">排序：</span>
              <ElInputNumber v-model="rule.sort_order" size="small" :step="1" style="width: 90px;" />

              <span class="label ml">首页横幅：</span>
              <ElSwitch
                v-model="rule.show_on_home"
                active-text="上首页"
                inactive-text="不展示"
                size="small"
              />
            </div>

            <!-- 二级子分类标签 -->
            <div class="subcategories-wrap">
              <div class="sub-label-row">
                <span class="sub-label">二级子分类/筛选标签：</span>
                <span class="sub-tip-desc">（点击胶囊切换显隐：变红即隐藏；点击 ✏️ 可重命名）</span>
              </div>
              <div class="sub-tags">
                <div
                  v-for="sub in (rule.subcategories || [])"
                  :key="sub.tid"
                  class="sub-item-pill"
                  :class="{ 'is-hidden': sub.hidden }"
                >
                  <div
                    class="sub-tag-body"
                    :title="sub.hidden ? '当前已隐藏（前台不展示），点击恢复展示' : '当前正常展示，点击切换为隐藏（变红）'"
                    @click="toggleSubCategoryHidden(sub)"
                  >
                    <span class="sub-status-dot" :class="sub.hidden ? 'dot-danger' : 'dot-success'" />
                    <span class="sub-title" :style="{ textDecoration: sub.hidden ? 'line-through' : 'none' }">
                      {{ formatCategoryPreview(sub.name, sub.custom_name) }}
                    </span>
                    <span class="sub-tid">#{{ sub.tid }}</span>
                    <span v-if="sub.hidden" class="sub-hidden-label">已隐藏</span>
                  </div>

                  <!-- 重命名二级分类 popover -->
                  <ElPopover trigger="click" :width="280" placement="top">
                    <template #reference>
                      <button class="sub-icon-btn edit-btn" type="button" title="重命名二级分类" @click.stop>
                        ✏️
                      </button>
                    </template>
                    <div class="sub-popover-content">
                      <div class="popover-title">重命名二级分类</div>
                      <div class="popover-orig">原名：{{ sub.name }} (#{{ sub.tid }})</div>
                      <ElInput
                        v-model="sub.custom_name"
                        placeholder="前台别名（留空保持原名）"
                        size="small"
                        clearable
                      />
                      <div class="popover-preview">
                        前台显示：<strong>{{ formatCategoryPreview(sub.name, sub.custom_name) }}</strong>
                      </div>
                    </div>
                  </ElPopover>

                  <!-- 彻底删除按钮 -->
                  <button
                    class="sub-icon-btn remove-btn"
                    type="button"
                    title="从列表中彻底移除该子分类"
                    @click.stop="removeSubCategory(rule, sub)"
                  >
                    ×
                  </button>
                </div>
                <span v-if="!(rule.subcategories && rule.subcategories.length)" class="a-muted no-sub">无子分类</span>
              </div>

              <!-- 添加子分类 -->
              <div class="add-sub-box">
                <ElInput
                  v-model="getSubInput(rule.tid).tid"
                  placeholder="子分类 TID"
                  size="small"
                  style="width: 100px;"
                />
                <ElInput
                  v-model="getSubInput(rule.tid).name"
                  placeholder="分类原名"
                  size="small"
                  style="width: 120px;"
                />
                <ElInput
                  v-model="getSubInput(rule.tid).custom_name"
                  placeholder="别名（选填）"
                  size="small"
                  style="width: 110px;"
                />
                <ElButton
                  size="small"
                  type="primary"
                  plain
                  @click="addSubCategory(rule)"
                >
                  添加子分类
                </ElButton>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="drawer-footer">
        <ElButton @click="emit('update:modelValue', false)">取消</ElButton>
        <ElButton type="primary" :loading="categorySaving" @click="emit('save')">
          保存分类配置
        </ElButton>
      </div>
    </template>
  </ElDrawer>
</template>
