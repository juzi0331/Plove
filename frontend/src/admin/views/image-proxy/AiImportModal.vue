<script setup lang="ts">
import {
  ElAlert,
  ElButton,
  ElDialog,
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
    title="粘贴导入 AI 逆向输出的解密配置"
    width="600px"
    @update:model-value="emit('update:modelValue', $event)"
  >
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
