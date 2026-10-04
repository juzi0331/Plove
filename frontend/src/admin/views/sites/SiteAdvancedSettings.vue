<script setup lang="ts">
/**
 * SiteAdvancedSettings - 单站高级配置、代理节点绑定与缓存 TTL 对话框
 */
import { Lightning, TopRight } from '@element-plus/icons-vue'
import {
  ElButton,
  ElDialog,
  ElDivider,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElOption,
  ElOptionGroup,
  ElSelect,
  ElTag,
} from 'element-plus'
import { useRouter } from 'vue-router'

import type {
  ProxyNodeItem,
  SiteAdvancedSettingPayload,
  SiteCachePolicy,
} from '@/api/types'

import { adminPath } from '../../config'

defineProps<{
  modelValue: boolean
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
  (e: 'update:modelValue', value: boolean): void
  (e: 'proxyChoiceChange', choice: string): void
  (e: 'testNode'): void
  (e: 'save'): void
}>()

const router = useRouter()
</script>

<template>
  <ElDialog
    :model-value="modelValue"
    :title="`单站高级控制 · ${currentAdvanced.key}`"
    width="560px"
    align-center
    destroy-on-close
    @update:model-value="(val) => emit('update:modelValue', val)"
  >
    <div v-loading="advancedLoading">
      <ElForm label-position="top">
        <ElFormItem label="客户端显示别名（自定义对外站名，留空则使用源站原名）">
          <ElInput v-model="currentAdvanced.custom_name" placeholder="如：VIP蓝光秒播站" />
        </ElFormItem>

        <ElFormItem label="站点角标 / 徽章（如：4K, 极速, 推荐, 备用）">
          <ElInput v-model="currentAdvanced.badge" placeholder="如：4K极速" />
        </ElFormItem>

        <ElFormItem label="单站独立超时秒数（0 表示使用系统全局默认 20s/25s）">
          <ElInputNumber v-model="currentAdvanced.timeout_seconds" :min="0" :max="120" :step="1" />
          <span class="a-muted desc-hint">秒（慢速站可适当放宽，极速站可配置短超时以快速熔断）</span>
        </ElFormItem>

        <ElFormItem label="运维备注说明">
          <ElInput v-model="currentAdvanced.note" type="textarea" :rows="2" placeholder="填写备忘信息" />
        </ElFormItem>

        <ElDivider content-position="left">🌐 采集代理节点配置 (Proxy Routing)</ElDivider>

        <ElFormItem label="网络请求通道">
          <div class="proxy-select-wrap">
            <ElSelect
              :model-value="selectedProxyChoice"
              placeholder="请选择网络通道或代理节点"
              style="width: 100%"
              @change="(val) => emit('proxyChoiceChange', String(val))"
            >
              <ElOption label="直连源站（不走代理，各源站互不干扰）" value="direct" />
              <ElOptionGroup v-if="proxyNodes.length > 0" label="已添加的代理节点池">
                <ElOption
                  v-for="node in proxyNodes"
                  :key="node.id"
                  :label="formatNodeLabel(node)"
                  :value="node.id"
                >
                  <div class="node-option-row">
                    <ElTag size="small" :type="node.protocol === 'vless' ? 'warning' : 'primary'" effect="plain">
                      {{ node.protocol.toUpperCase() }}
                    </ElTag>
                    <span class="node-name-text">{{ node.name }}</span>
                    <span class="node-meta-text">{{ node.server }}:{{ node.port }}</span>
                    <ElTag v-if="node.ping_ms" size="small" type="success" effect="light">
                      {{ node.ping_ms }}ms
                    </ElTag>
                  </div>
                </ElOption>
              </ElOptionGroup>
              <ElOption label="自定义本地中转端口 / 地址（手动输入）" value="custom" />
            </ElSelect>

            <div class="proxy-nodes-pool-link">
              <ElButton
                type="primary"
                link
                size="small"
                :icon="TopRight"
                @click="router.push(adminPath('/proxy-nodes'))"
              >
                前往代理节点池 (添加多个 VLESS 节点 / 管理 / 测速)
              </ElButton>
            </div>
          </div>
        </ElFormItem>

        <!-- 选择了节点池中的具体节点时展示卡片 -->
        <transition name="el-fade-in-linear">
          <div v-if="selectedNode" class="node-detail-card">
            <div class="node-card-head">
              <div class="node-card-title">
                <ElTag size="small" :type="selectedNode.protocol === 'vless' ? 'warning' : 'primary'" effect="dark">
                  {{ selectedNode.protocol.toUpperCase() }}
                </ElTag>
                <strong>{{ selectedNode.name }}</strong>
                <span class="a-muted">({{ selectedNode.server }}:{{ selectedNode.port }})</span>
              </div>
              <div class="node-card-actions">
                <ElButton
                  size="small"
                  type="success"
                  plain
                  :loading="testingNode"
                  :icon="Lightning"
                  @click="emit('testNode')"
                >
                  测试延迟 {{ selectedNode.ping_ms ? `(${selectedNode.ping_ms}ms)` : '' }}
                </ElButton>
              </div>
            </div>

            <div class="node-card-grid">
              <div class="node-grid-item">
                <span class="grid-label">传输 / 安全：</span>
                <span>{{ selectedNode.network_type || 'tcp' }} / {{ selectedNode.security || 'none' }}</span>
              </div>
              <div v-if="selectedNode.sni" class="node-grid-item">
                <span class="grid-label">SNI 伪装：</span>
                <span>{{ selectedNode.sni }}</span>
              </div>
              <div class="node-grid-item">
                <span class="grid-label">本地中转地址：</span>
                <code>{{ selectedNode.proxy_url || 'http://127.0.0.1:10809' }}</code>
              </div>
            </div>

            <div class="node-card-tip">
              💡 <strong>隔离生效</strong>：该采集器适配器所有网络请求（分类/搜索/详情/播放流探测）将全自动通过此节点中转。
            </div>
          </div>
        </transition>

        <!-- 自定义代理地址输入框 -->
        <transition name="el-fade-in-linear">
          <div v-if="selectedProxyChoice === 'custom'" class="proxy-setting-box">
            <ElFormItem label="自定义代理地址 (Proxy URL)">
              <ElInput
                v-model="currentAdvanced.proxy_url"
                placeholder="如 http://192.168.31.5:10809 或 http://127.0.0.1:10809 (支持 http / socks5)"
                clearable
              />
            </ElFormItem>

            <div class="proxy-quick-actions">
              <span class="quick-title a-muted">常用预设快捷填入：</span>
              <ElButton size="small" link type="primary" @click="currentAdvanced.proxy_url = 'http://127.0.0.1:10809'">
                本地 10809
              </ElButton>
              <ElButton size="small" link type="primary" @click="currentAdvanced.proxy_url = 'http://192.168.31.5:10809'">
                NAS 局域网 192.168.31.5:10809
              </ElButton>
              <ElButton size="small" link type="primary" @click="currentAdvanced.proxy_url = 'http://127.0.0.1:7890'">
                Clash 7890
              </ElButton>
              <ElButton size="small" link type="primary" @click="currentAdvanced.proxy_url = 'socks5://127.0.0.1:10808'">
                SOCKS5 10808
              </ElButton>
            </div>

            <div class="proxy-notice-tip">
              <strong>💡 隔离说明</strong>：此配置仅对当前适配器生效。部署在宝塔/Docker 时若代理运行在宿主机，请填宿主机局域网 IP（如 <code>http://192.168.31.5:10809</code>）。
            </div>
          </div>
        </transition>

        <ElDivider content-position="left">该站点独立缓存存活时间 (TTL)</ElDivider>

        <div class="cache-policy-grid">
          <ElFormItem label="首页缓存秒数">
            <ElInputNumber
              v-model="currentCachePolicy.home_ttl"
              :min="0"
              :max="86400"
              placeholder="默认 600s (0不缓存)"
              style="width: 100%"
            />
          </ElFormItem>

          <ElFormItem label="分类列表秒数">
            <ElInputNumber
              v-model="currentCachePolicy.category_ttl"
              :min="0"
              :max="86400"
              placeholder="默认 300s (0不缓存)"
              style="width: 100%"
            />
          </ElFormItem>

          <ElFormItem label="影视详情秒数">
            <ElInputNumber
              v-model="currentCachePolicy.detail_ttl"
              :min="0"
              :max="86400"
              placeholder="默认 300s (0不缓存)"
              style="width: 100%"
            />
          </ElFormItem>

          <ElFormItem label="封面/简介长效静态缓存">
            <ElInputNumber
              v-model="currentCachePolicy.long_term_static_ttl"
              :min="0"
              :max="2592000"
              :step="3600"
              placeholder="默认 86400s (24小时)"
              style="width: 100%"
            />
          </ElFormItem>
        </div>

        <div class="cache-policy-tip">
          <strong>静态元数据长效化建议</strong>：海报封面图片 URL、剧情简介、演职员等信息极少失效，推荐保持 86400 秒（24小时）乃至更高，可大幅降低源站爬虫频次并显著提升前台秒开速度。
        </div>
      </ElForm>
    </div>

    <template #footer>
      <ElButton @click="emit('update:modelValue', false)">取消</ElButton>
      <ElButton type="primary" :loading="advancedSaving" @click="emit('save')">
        保存配置
      </ElButton>
    </template>
  </ElDialog>
</template>
