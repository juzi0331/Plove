<script setup lang="ts">
import { Lightning, TopRight } from '@element-plus/icons-vue'
import {
  ElButton,
  ElDivider,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElOption,
  ElOptionGroup,
  ElSelect,
} from 'element-plus'
import { useRouter } from 'vue-router'

import type {
  ProxyNodeItem,
  SiteAdvancedSettingPayload,
  SiteCachePolicy,
} from '@/api/types'
import { adminPath } from '@/admin/config'
import { ui } from '@/admin/ui'

defineProps<{
  currentAdvanced: SiteAdvancedSettingPayload
  currentCachePolicy: SiteCachePolicy
  proxyNodes: ProxyNodeItem[]
  selectedProxyChoice: string
  selectedNode?: ProxyNodeItem
  advancedLoading: boolean
  advancedSaving: boolean
  testingNode: boolean
  formatNodeLabel: (node: ProxyNodeItem) => string
}>()

const emit = defineEmits<{
  (e: 'proxyChoiceChange', choice: string): void
  (e: 'testNode'): void
  (e: 'saveAdvanced'): void
  (e: 'closeModal'): void
}>()

const router = useRouter()

function goToProxyNodes(): void {
  emit('closeModal')
  void router.push(adminPath('/proxy-nodes'))
}
</script>

<template>
  <div v-loading="advancedLoading" class="tab-pane-content">
    <ElForm label-position="top">
      <div class="form-row-2">
        <ElFormItem label="用户端显示别名" style="flex: 1;">
          <ElInput
            v-model="currentAdvanced.custom_name"
            placeholder="留空则显示脚本默认名称"
            :disabled="ui.readOnly"
          />
        </ElFormItem>

        <ElFormItem label="自定义线路标识 / 角标" style="width: 260px;">
          <ElInput
            v-model="currentAdvanced.badge"
            :placeholder="currentAdvanced.key ? `留空显示 (${currentAdvanced.key})` : '留空显示原始Key'"
            maxlength="20"
            show-word-limit
            :disabled="ui.readOnly"
          />
        </ElFormItem>
      </div>
      <div class="form-item-tip" style="margin-top: -10px; margin-bottom: 14px;">
        💡 线路标识将直接展示在前台切源下拉列表中（「线路标识: 自定义值」），如：蓝光专线、极速4K；留空则显示原始爬虫 Key
      </div>

      <div class="form-row-2">
        <ElFormItem label="抓取请求超时 (秒)" style="flex: 1;">
          <ElInputNumber
            v-model="currentAdvanced.timeout_seconds"
            :min="0"
            :max="120"
            :step="1"
            :disabled="ui.readOnly"
            style="width: 100%;"
          />
          <div class="form-item-tip">0 为使用系统默认超时（15 秒）</div>
        </ElFormItem>

        <ElFormItem label="运维备忘 / 站点特征说明" style="flex: 1;">
          <ElInput
            v-model="currentAdvanced.note"
            placeholder="填写站长联系方式、接口特性等备忘"
            :disabled="ui.readOnly"
          />
        </ElFormItem>
      </div>

      <ElDivider content-position="left">爬虫网络代理与节点池指派</ElDivider>

      <ElFormItem label="网络请求通道指派">
        <div class="proxy-select-row">
          <ElSelect
            :model-value="selectedProxyChoice"
            style="flex: 1;"
            :disabled="ui.readOnly"
            @update:model-value="(val) => emit('proxyChoiceChange', val as string)"
          >
            <ElOption label="直连源站（不使用代理中转，最快）" value="direct" />
            <ElOptionGroup v-if="proxyNodes.length > 0" label="已配置代理节点池">
              <ElOption
                v-for="node in proxyNodes"
                :key="node.id"
                :label="formatNodeLabel(node)"
                :value="node.id"
              />
            </ElOptionGroup>
            <ElOption label="自定义本地 HTTP / SOCKS5 代理地址" value="custom" />
          </ElSelect>

          <ElButton
            v-if="selectedNode"
            :loading="testingNode"
            :icon="Lightning"
            @click="emit('testNode')"
          >
            节点测速
          </ElButton>

          <ElButton
            link
            type="primary"
            :icon="TopRight"
            @click="goToProxyNodes"
          >
            管理代理节点池 ({{ proxyNodes.length }})
          </ElButton>
        </div>

        <div v-if="selectedNode" class="node-meta-banner">
          <div><strong>服务器：</strong>{{ selectedNode.server }}:{{ selectedNode.port }}</div>
          <div><strong>本地中转：</strong><code>{{ selectedNode.proxy_url }}</code></div>
          <div v-if="selectedNode.protocol === 'vless'" class="xray-badge-text">
            内置 Xray 核心引擎自动接管本地监听，免手动配置
          </div>
        </div>

        <div v-if="selectedProxyChoice === 'custom'" style="margin-top: 10px;">
          <ElInput
            v-model="currentAdvanced.proxy_url"
            placeholder="http://127.0.0.1:10809 或 socks5://127.0.0.1:10808"
            :disabled="ui.readOnly"
          />
        </div>
      </ElFormItem>

      <ElDivider content-position="left">单站独立内容缓存与 TTL (秒)</ElDivider>

      <div class="ttl-row">
        <ElFormItem label="首页 TTL">
          <ElInputNumber
            v-model="currentCachePolicy.home_ttl"
            :min="0"
            :max="86400"
            :step="60"
            placeholder="留空继承"
            :disabled="ui.readOnly"
            style="width: 100%;"
          />
        </ElFormItem>
        <ElFormItem label="分类大厅 TTL">
          <ElInputNumber
            v-model="currentCachePolicy.category_ttl"
            :min="0"
            :max="86400"
            :step="60"
            placeholder="留空继承"
            :disabled="ui.readOnly"
          />
        </ElFormItem>
        <ElFormItem label="详情页 TTL">
          <ElInputNumber
            v-model="currentCachePolicy.detail_ttl"
            :min="0"
            :max="86400"
            :step="60"
            placeholder="留空继承"
            :disabled="ui.readOnly"
          />
        </ElFormItem>
      </div>
      <div class="form-item-tip">
        留空时自动继承系统全局默认缓存策略（首页 600s、分类 300s、详情 300s），输入 0 则单站禁用缓存。
      </div>

      <div class="pane-footer-actions">
        <ElButton
          type="primary"
          :loading="advancedSaving"
          :disabled="ui.readOnly"
          @click="emit('saveAdvanced')"
        >
          保存基础与网络设置
        </ElButton>
      </div>
    </ElForm>
  </div>
</template>

<style scoped src="./site-detail-modal.css"></style>
