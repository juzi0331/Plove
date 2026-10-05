<script setup lang="ts">
import {
  ElAlert,
  ElButton,
  ElDialog,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus'
import {
  Delete,
  Edit,
  MagicStick,
  Plus,
  VideoPlay,
} from '@element-plus/icons-vue'
import { ui } from '@/admin/ui'
import type { ImageDecryptionRule, TestDecryptResult } from '@/api/types'
import RuleEditModal from './RuleEditModal.vue'
import AiImportModal from './AiImportModal.vue'
import TestDecryptModal from './TestDecryptModal.vue'

const props = defineProps<{
  modelValue: boolean
  rulesList: ImageDecryptionRule[]
  showSecret: Record<string, boolean>
  // Edit modal props
  showRuleDialog: boolean
  isEditing: boolean
  ruleForm: ImageDecryptionRule
  domainsInput: string
  inlineTestUrl: string
  inlineTesting: boolean
  inlineTestResult: TestDecryptResult | null
  // AI import props
  showAiImportDialog: boolean
  aiImportText: string
  // Test modal props
  showTestModal: boolean
  testModalRule: ImageDecryptionRule | null
  testModalUrl: string
  testModalLoading: boolean
  testModalResult: TestDecryptResult | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'update:showRuleDialog', val: boolean): void
  (e: 'update:domainsInput', val: string): void
  (e: 'update:inlineTestUrl', val: string): void
  (e: 'update:showAiImportDialog', val: boolean): void
  (e: 'update:aiImportText', val: string): void
  (e: 'update:showTestModal', val: boolean): void
  (e: 'update:testModalUrl', val: string): void
  (e: 'openAddRule'): void
  (e: 'openEditRule', row: ImageDecryptionRule): void
  (e: 'deleteRule', row: ImageDecryptionRule): void
  (e: 'toggleRule'): void
  (e: 'toggleSecret', id?: string): void
  (e: 'copyRuleKey', row: ImageDecryptionRule): void
  (e: 'fillHuangguoaiSample'): void
  (e: 'saveRule'): void
  (e: 'runInlineTest'): void
  (e: 'openAiImport'): void
  (e: 'parseAiJson'): void
  (e: 'openTestRuleModal', row: ImageDecryptionRule): void
  (e: 'runModalTest'): void
}>()

function maskSecret(val?: string): string {
  if (!val) return ''
  if (val.length <= 8) return '******'
  return val.slice(0, 3) + '****' + val.slice(-3)
}
</script>

<template>
  <ElDialog
    :model-value="props.modelValue"
    title="第三方源站加密海报动态解密配置"
    width="1180px"
    align-center
    append-to-body
    destroy-on-close
    @update:model-value="emit('update:modelValue', $event)"
  >
    <ElAlert
      type="info"
      :closable="false"
      show-icon
      style="margin-bottom: 16px;"
    >
      当源站（如黄果艾、新抓取站点）对海报进行了 AES-128 等前端加密时，在此配置对应密钥与图床域名，系统自动流式解密，无需修改任何 Python 源码。
    </ElAlert>

    <div class="decryption-toolbar">
      <div class="toolbar-left">
        <span class="toolbar-title">解密规则列表</span>
        <ElTag size="small" type="info" effect="plain">{{ props.rulesList.length }} 条规则</ElTag>
      </div>
      <div class="toolbar-actions">
        <ElButton
          type="warning"
          plain
          :icon="MagicStick"
          @click="emit('openAiImport')"
        >
          一键导入 AI 逆向结果
        </ElButton>
        <ElButton
          type="primary"
          :icon="Plus"
          :disabled="ui.readOnly"
          @click="emit('openAddRule')"
        >
          添加解密规则
        </ElButton>
      </div>
    </div>

    <div class="decryption-table-wrap">
      <ElTable :data="props.rulesList" stripe style="width: 100%" empty-text="暂无解密规则，点击上方按钮添加或一键导入">
        <ElTableColumn prop="name" label="规则名称" min-width="160">
          <template #default="{ row }">
            <span class="rule-name-text">{{ row.name || '未命名规则' }}</span>
            <div v-if="row.id" class="rule-id-text">ID: {{ row.id }}</div>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="site_key" label="适用站点" min-width="130" align="center">
          <template #default="{ row }">
            <ElTag v-if="row.site_key" type="success" size="small">{{ row.site_key }}</ElTag>
            <ElTag v-else type="info" size="small">全站匹配</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="match_domains" label="匹配图床域名" min-width="160">
          <template #default="{ row }">
            <div v-if="row.match_domains && row.match_domains.length > 0" class="tags-cluster">
              <ElTag v-for="d in row.match_domains" :key="d" size="small" effect="plain">{{ d }}</ElTag>
            </div>
            <span v-else style="color: var(--a-text-3, #94a3b8); font-size: 12px;">该站点全部图片</span>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="algorithm" label="解密算法" min-width="140" align="center">
          <template #default="{ row }">
            <ElTag size="small" effect="dark" type="warning" class="algo-tag">{{ row.algorithm || 'AES-128-CBC' }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="密钥 (Key / IV)" min-width="230">
          <template #default="{ row }">
            <div class="cipher-keys-display">
              <div class="cipher-row">
                <span class="cipher-label">Key:</span>
                <code class="cipher-val" :title="row.key">{{ props.showSecret[row.id] ? row.key : maskSecret(row.key) }}</code>
              </div>
              <div v-if="row.iv" class="cipher-row">
                <span class="cipher-label">IV:</span>
                <code class="cipher-val" :title="row.iv">{{ props.showSecret[row.id] ? row.iv : maskSecret(row.iv) }}</code>
              </div>
              <div class="cipher-actions">
                <ElButton
                  link
                  type="primary"
                  size="small"
                  @click="emit('toggleSecret', row.id)"
                >
                  {{ props.showSecret[row.id] ? '隐藏' : '显示' }}
                </ElButton>
                <ElButton
                  link
                  type="primary"
                  size="small"
                  @click="emit('copyRuleKey', row)"
                >
                  复制
                </ElButton>
              </div>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="enabled" label="状态" width="85" align="center">
          <template #default="{ row }">
            <ElSwitch
              v-model="row.enabled"
              :disabled="ui.readOnly"
              inline-prompt
              active-text="开"
              inactive-text="关"
              @change="emit('toggleRule')"
            />
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" min-width="195" width="195" align="center">
          <template #default="{ row }">
            <div class="table-ops-group">
              <ElButton
                size="small"
                type="primary"
                link
                :icon="VideoPlay"
                @click="emit('openTestRuleModal', row)"
              >
                验证
              </ElButton>
              <ElButton
                size="small"
                type="primary"
                link
                :icon="Edit"
                :disabled="ui.readOnly"
                @click="emit('openEditRule', row)"
              >
                编辑
              </ElButton>
              <ElButton
                size="small"
                type="danger"
                link
                :icon="Delete"
                :disabled="ui.readOnly"
                @click="emit('deleteRule', row)"
              >
                删除
              </ElButton>
            </div>
          </template>
        </ElTableColumn>
      </ElTable>
    </div>

    <template #footer>
      <ElButton @click="emit('update:modelValue', false)">关闭</ElButton>
    </template>
  </ElDialog>

  <!-- 子弹窗 1: 添加/编辑解密规则 -->
  <RuleEditModal
    :model-value="props.showRuleDialog"
    :is-editing="props.isEditing"
    :rule-form="props.ruleForm"
    :domains-input="props.domainsInput"
    :inline-test-url="props.inlineTestUrl"
    :inline-testing="props.inlineTesting"
    :inline-test-result="props.inlineTestResult"
    @update:model-value="emit('update:showRuleDialog', $event)"
    @update:domains-input="emit('update:domainsInput', $event)"
    @update:inline-test-url="emit('update:inlineTestUrl', $event)"
    @fill-huangguoai-sample="emit('fillHuangguoaiSample')"
    @run-inline-test="emit('runInlineTest')"
    @save="emit('saveRule')"
  />

  <!-- 子弹窗 2: AI 逆向结果一键智能导入 -->
  <AiImportModal
    :model-value="props.showAiImportDialog"
    :ai-import-text="props.aiImportText"
    @update:model-value="emit('update:showAiImportDialog', $event)"
    @update:ai-import-text="emit('update:aiImportText', $event)"
    @parse="emit('parseAiJson')"
  />

  <!-- 子弹窗 3: 独立解密在线测试 -->
  <TestDecryptModal
    :model-value="props.showTestModal"
    :rule="props.testModalRule"
    :test-url="props.testModalUrl"
    :loading="props.testModalLoading"
    :result="props.testModalResult"
    @update:model-value="emit('update:showTestModal', $event)"
    @update:test-url="emit('update:testModalUrl', $event)"
    @run="emit('runModalTest')"
  />
</template>
