<script setup lang="ts">
import {
  ElButton,
  ElCol,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElRow,
  ElTabPane,
  ElTabs,
} from 'element-plus'

const props = defineProps<{
  modelValue: boolean
  addMode: 'vless' | 'http'
  addForm: {
    raw_url: string
    name: string
    local_port: number
  }
  adding: boolean
  parsedPreview: {
    protocol: string
    name?: string
    uuid?: string
    server?: string
    port?: string | number
  } | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'update:addMode', val: 'vless' | 'http'): void
  (e: 'save'): void
}>()
</script>

<template>
  <ElDialog
    :model-value="props.modelValue"
    title="添加代理节点"
    width="640px"
    align-center
    append-to-body
    destroy-on-close
    class="submodal-dialog"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <ElTabs
      :model-value="props.addMode"
      @update:model-value="emit('update:addMode', $event as 'vless' | 'http')"
    >
      <ElTabPane label="VLESS 链接导入 (内置 Xray 直接驱动)" name="vless">
        <div style="background: var(--el-fill-color-light); border-radius: 8px; padding: 10px 14px; margin-bottom: 14px; font-size: 12.5px; color: var(--el-text-color-regular);">
          🚀 <strong>开箱即用说明</strong>：系统内置 Xray 核心引擎。添加后，系统将自动在本地开放独立 HTTP 端口为您托管中转，无需再手动导出配置！
        </div>

        <ElForm label-position="top">
          <ElFormItem label="VLESS 节点连接串 (以 vless:// 开头)" required>
            <ElInput
              v-model="props.addForm.raw_url"
              type="textarea"
              :rows="4"
              placeholder="vless://uuid@server:port?type=tcp&security=reality&pbk=...#香港高速节点"
            />
          </ElFormItem>

          <!-- 动态解析预览 -->
          <div v-if="props.parsedPreview" class="preview-box">
            <div class="preview-title">✨ 已识别节点参数：</div>
            <div class="preview-items">
              <div><strong>备注：</strong>{{ props.parsedPreview.name || '默认' }}</div>
              <div><strong>服务器：</strong>{{ props.parsedPreview.server }}:{{ props.parsedPreview.port }}</div>
              <div><strong>UUID：</strong>{{ props.parsedPreview.uuid }}</div>
            </div>
          </div>

          <ElRow :gutter="16">
            <ElCol :span="14">
              <ElFormItem label="自定义节点备注名称（选填，留空自动提取 # 备注）">
                <ElInput v-model="props.addForm.name" placeholder="如：自建香港高速专线" />
              </ElFormItem>
            </ElCol>
            <ElCol :span="10">
              <ElFormItem label="内置 Xray 托管端口">
                <ElInputNumber v-model="props.addForm.local_port" :min="1024" :max="65535" style="width: 100%" />
              </ElFormItem>
            </ElCol>
          </ElRow>
        </ElForm>
      </ElTabPane>

      <ElTabPane label="常规 HTTP / SOCKS5 代理" name="http">
        <ElForm label-position="top">
          <ElFormItem label="代理服务器完整 URL" required>
            <ElInput
              v-model="props.addForm.raw_url"
              placeholder="如 http://192.168.31.5:10809 或 http://127.0.0.1:7890"
            />
          </ElFormItem>

          <ElFormItem label="节点备注名称">
            <ElInput v-model="props.addForm.name" placeholder="如：本地 Clash 代理" />
          </ElFormItem>
        </ElForm>
      </ElTabPane>
    </ElTabs>

    <template #footer>
      <ElButton @click="emit('update:modelValue', false)">取消</ElButton>
      <ElButton type="primary" :loading="props.adding" @click="emit('save')">
        确认添加并启动
      </ElButton>
    </template>
  </ElDialog>
</template>
