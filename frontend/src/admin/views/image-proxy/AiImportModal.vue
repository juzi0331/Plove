<script setup lang="ts">
import {
  ElAlert,
  ElButton,
  ElDialog,
  ElIcon,
  ElInput,
} from 'element-plus'
import { MagicStick } from '@element-plus/icons-vue'

const props = defineProps<{
  modelValue: boolean
  aiImportText: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'update:aiImportText', val: string): void
  (e: 'parse'): void
}>()
</script>

<template>
  <ElDialog
    :model-value="props.modelValue"
    width="620px"
    align-center
    append-to-body
    destroy-on-close
    class="submodal-dialog"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #header>
      <div class="submodal-header">
        <div class="submodal-icon-badge" style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);">
          <ElIcon :size="18"><MagicStick /></ElIcon>
        </div>
        <div>
          <div class="submodal-title">导入 AI 逆向输出的解密配置</div>
          <div class="submodal-subtitle">智能提取 JSON 块或自然语言中的 Key、IV 与算法</div>
        </div>
      </div>
    </template>
    <ElAlert
      type="info"
      :closable="false"
      show-icon
      style="margin-bottom: 12px;"
    >
      将 ChatGPT / DeepSeek / Claude 回复给您的 JSON 配置块或包含 key/iv 的文本直接粘贴在下方，系统会自动识别提取并为您填好表单！
    </ElAlert>
    <ElInput
      :model-value="props.aiImportText"
      type="textarea"
      :rows="8"
      placeholder='示例直接粘贴：
{
  "site_key": "my_new_site",
  "match_domains": ["pic.example.com"],
  "algorithm": "AES-128-CBC",
  "key": "f5d965df75336270",
  "iv": "97b60394abc2fbe1"
}'
      @update:model-value="emit('update:aiImportText', $event)"
    />
    <template #footer>
      <ElButton @click="emit('update:modelValue', false)">取消</ElButton>
      <ElButton type="primary" :icon="MagicStick" @click="emit('parse')">
        智能解析并填入规则
      </ElButton>
    </template>
  </ElDialog>
</template>
