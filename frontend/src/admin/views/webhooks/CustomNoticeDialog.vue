<script setup lang="ts">
import { computed, watch } from 'vue'
import {
  ElButton,
  ElDialog,
  ElInput,
  ElOption,
  ElSelect,
  ElSwitch,
  ElTag,
} from 'element-plus'
import { Promotion } from '@element-plus/icons-vue'

const props = defineProps<{
  modelValue: boolean
  draft: {
    title: string
    category: string
    content: string
    extraNote: string
    rawHtml?: boolean
  }
  sending: boolean
  readOnly: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  send: []
}>()

const QUICK_TEMPLATES = [
  {
    label: '💎 授权管理中心 (设计版)',
    category: '📢 系统公告',
    title: '授权管理中心 · 实时广播',
    isRawHtml: true,
    content: `⚙️ <b>【 授权管理中心 · 实时广播 】</b>

▶️ <b>事件：</b> <b>#首次激活成功</b>
🔹 <b>项目：</b> Plove Watchdog 守护进程

🗂️ <b>[ 核心元数据 ]</b>
 ├— 🏷️ <b>卡密标头：</b> <code>PLV-KHKP…AM7A</code>
 ├— 🖥️ <b>宿主名称：</b> <code>测试机</code>
 ├— ⏱️ <b>生命周期：</b> <code>1 Day (24H)</code>
 └— 📆 <b>过期释放：</b> <code>2026-10-05 10:10:45</code>

📢 <b>监控策略：</b> 默认阻断已开启
⏰ <b>触发时间：</b> <code>2026-10-04 18:10:45</code>`,
    note: '',
  },
  {
    label: '🛠️ 临时维护通知',
    category: '🚨 紧急维护',
    title: '系统临时维护与升级提醒',
    isRawHtml: false,
    content: '尊敬的管理员与用户：系统定于今日凌晨进行网络割接与维护，预计耗时约 10 分钟，期间部分请求可能短暂波动，请知悉。',
    note: '预计 00:00 - 00:15 期间操作',
  },
  {
    label: '🚀 节点线路优化',
    category: '⚙️ 运维通知',
    title: '核心网络代理节点切换通知',
    isRawHtml: false,
    content: '已完成香港与日本骨干节点线路升级与负载均衡切换，各内容源爬虫抓取与图片加速已恢复最佳吞吐率。',
    note: '如遇节点连接超时，请尝试刷新缓存',
  },
  {
    label: '🎉 运营数据喜报',
    category: '💡 业务更新',
    title: 'Plove 运营动态简报',
    isRawHtml: false,
    content: '今日全站活跃绑定设备数突破新高，聚合内容源健康度达 100%，系统整体负载平稳。',
    note: '数据实时同步自集群大盘',
  },
  {
    label: '⚠️ 异常排查通报',
    category: '🚨 紧急维护',
    title: '上游源站波动排查通告',
    isRawHtml: false,
    content: '监控发现部分第三方站点响应延迟升高，备用探针已介入探测，技术团队正在持续跟进处理中。',
    note: '有最新进展将即时在群内通报',
  },
]

function applyTemplate(tpl: (typeof QUICK_TEMPLATES)[0]): void {
  props.draft.category = tpl.category
  props.draft.title = tpl.title
  props.draft.content = tpl.content
  props.draft.extraNote = tpl.note
  if (tpl.isRawHtml !== undefined) {
    props.draft.rawHtml = tpl.isRawHtml
  }
}

// 快捷标签插入
function insertTag(openTag: string, closeTag: string): void {
  const current = props.draft.content || ''
  props.draft.content = `${current}${openTag}文本${closeTag}`
  props.draft.rawHtml = true
}

// 检测用户输入是否包含 HTML 标签，自动激活 HTML 模式
watch(
  () => props.draft.content,
  (val) => {
    if (val && /<[a-z][\s\S]*>/i.test(val) && props.draft.rawHtml === false) {
      props.draft.rawHtml = true
    }
  },
)

const hasHtmlTags = computed(() => {
  return /<[a-z][\s\S]*>/i.test(props.draft.content || '')
})
</script>

<template>
  <ElDialog
    :model-value="props.modelValue"
    title="自定义即时消息推送与全网广播"
    width="740px"
    class="custom-notice-modal"
    destroy-on-close
    append-to-body
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="custom-notice-form">
      <!-- 快速模板胶囊 -->
      <div class="quick-templates-bar">
        <span class="quick-label">⚡ 快速填充模板:</span>
        <div class="templates-list">
          <button
            v-for="tpl in QUICK_TEMPLATES"
            :key="tpl.label"
            type="button"
            class="tpl-chip-btn"
            :class="{ 'tpl-highlight': tpl.isRawHtml }"
            :disabled="props.readOnly"
            @click="applyTemplate(tpl)"
          >
            {{ tpl.label }}
          </button>
        </div>
      </div>

      <!-- HTML 模式切换提示条 -->
      <div class="html-mode-bar">
        <div class="html-mode-left">
          <span class="html-icon">🎨</span>
          <div class="html-mode-info">
            <span class="html-mode-title">Telegram 原生 HTML 渲染模式</span>
            <span class="html-mode-desc">
              支持原生 <code>&lt;b&gt;</code>、<code>&lt;code&gt;</code>、<code>&lt;i&gt;</code>、<code>&lt;blockquote&gt;</code> 等标签排版，不转义
            </span>
          </div>
        </div>
        <ElSwitch
          v-model="props.draft.rawHtml"
          :disabled="props.readOnly"
          inline-prompt
          active-text="HTML"
          inactive-text="纯文本"
        />
      </div>

      <div class="custom-inputs-row">
        <div class="category-col">
          <label class="input-label">通知类别</label>
          <ElSelect
            v-model="props.draft.category"
            style="width: 100%;"
            :disabled="props.readOnly"
          >
            <ElOption label="📢 系统公告" value="📢 系统公告" />
            <ElOption label="🚨 紧急维护" value="🚨 紧急维护" />
            <ElOption label="💡 业务更新" value="💡 业务更新" />
            <ElOption label="⚙️ 运维通知" value="⚙️ 运维通知" />
          </ElSelect>
        </div>

        <div class="title-col">
          <label class="input-label">消息标题</label>
          <ElInput
            v-model="props.draft.title"
            placeholder="例如：系统临时维护与升级提醒"
            :disabled="props.readOnly"
          />
        </div>
      </div>

      <!-- 正文输入区与 HTML 辅助插入按钮 -->
      <div class="custom-content-row">
        <div class="content-header-row">
          <label class="input-label">
            通知正文内容
            <ElTag v-if="props.draft.rawHtml" size="small" type="success" effect="dark">
              HTML 解析已开启
            </ElTag>
          </label>

          <!-- 快捷 HTML 辅助标签 -->
          <div v-if="props.draft.rawHtml" class="tag-helpers">
            <span class="helper-hint">快捷插入:</span>
            <button
              type="button"
              class="tag-pill"
              @click="insertTag('<b>', '</b>')"
            >
              &lt;b&gt;加粗&lt;/b&gt;
            </button>
            <button
              type="button"
              class="tag-pill"
              @click="insertTag('<code>', '</code>')"
            >
              &lt;code&gt;代码/卡密&lt;/code&gt;
            </button>
            <button
              type="button"
              class="tag-pill"
              @click="insertTag('<i>', '</i>')"
            >
              &lt;i&gt;斜体&lt;/i&gt;
            </button>
            <button
              type="button"
              class="tag-pill"
              @click="insertTag('<blockquote>', '</blockquote>')"
            >
              &lt;blockquote&gt;引用&lt;/blockquote&gt;
            </button>
            <button
              type="button"
              class="tag-pill"
              @click="insertTag('<tg-spoiler>', '</tg-spoiler>')"
            >
              &lt;tg-spoiler&gt;剧透&lt;/tg-spoiler&gt;
            </button>
          </div>
        </div>

        <ElInput
          v-model="props.draft.content"
          type="textarea"
          :rows="7"
          placeholder="可直接粘贴 Google 设计的 Telegram HTML 结构（支持 <b>、<code>、<blockquote> 等原生标签）..."
          :disabled="props.readOnly"
          class="code-textarea"
        />
      </div>

      <!-- 可选备注 (仅纯文本模式生效) -->
      <div v-if="!props.draft.rawHtml" class="custom-note-row">
        <label class="input-label">可选附加备注说明</label>
        <ElInput
          v-model="props.draft.extraNote"
          placeholder="可选附加备注说明（如：预计维护时间、处理建议等）"
          :disabled="props.readOnly"
        />
      </div>

      <!-- 实时预览区 (针对 HTML 模式) -->
      <div v-if="props.draft.rawHtml && hasHtmlTags" class="preview-box">
        <div class="preview-label">
          <span>📱 Telegram 渲染仿真预览:</span>
        </div>
        <!-- eslint-disable-next-line vue/no-v-html -->
        <div class="tg-bubble-preview" v-html="props.draft.content" />
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <div class="footer-tip">
          <span v-if="props.draft.rawHtml" style="color: #0284c7;">
            💡 已开启原生 HTML 模式，Telegram 将直接解析代码块与加粗效果
          </span>
          <span v-else>
            💡 纯文本模式将自动包裹卡片与时间戳
          </span>
        </div>
        <div class="footer-btns">
          <ElButton @click="emit('update:modelValue', false)">取消</ElButton>
          <ElButton
            type="primary"
            :icon="Promotion"
            :loading="props.sending"
            :disabled="props.readOnly || !props.draft.content.trim()"
            @click="emit('send')"
          >
            立即向 Telegram 广播
          </ElButton>
        </div>
      </div>
    </template>
  </ElDialog>
</template>

<style scoped>
.custom-notice-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.quick-templates-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 8px 12px;
  background: var(--a-bg-subtle, #f8fafc);
  border-radius: 8px;
  border: 1px dashed var(--a-border, #e2e8f0);
}

.quick-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--a-text-2, #475569);
}

.templates-list {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.tpl-chip-btn {
  background: #ffffff;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
  color: #334155;
  transition: all 0.15s ease;
}

.tpl-chip-btn:hover {
  border-color: #0284c7;
  color: #0284c7;
  background: #f0f9ff;
}

.tpl-highlight {
  border-color: #38bdf8;
  background: #f0f9ff;
  color: #0284c7;
  font-weight: 600;
}

/* HTML 模式切换条 */
.html-mode-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 8px;
}

.html-mode-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.html-icon {
  font-size: 20px;
}

.html-mode-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.html-mode-title {
  font-size: 13px;
  font-weight: 700;
  color: #166534;
}

.html-mode-desc {
  font-size: 11.5px;
  color: #15803d;
}

.html-mode-desc code {
  font-family: 'JetBrains Mono', Consolas, monospace;
  background: #dcfce7;
  padding: 1px 4px;
  border-radius: 4px;
  font-size: 11px;
}

.custom-inputs-row {
  display: grid;
  grid-template-columns: 180px 1fr;
  gap: 14px;
}

@media (max-width: 600px) {
  .custom-inputs-row {
    grid-template-columns: 1fr;
  }
}

.input-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--a-text, #334155);
  margin-bottom: 6px;
}

.content-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 6px;
}

.content-header-row .input-label {
  margin-bottom: 0;
}

.tag-helpers {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.helper-hint {
  font-size: 11px;
  color: #64748b;
}

.tag-pill {
  background: #f1f5f9;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  font-size: 11px;
  font-family: 'JetBrains Mono', Consolas, monospace;
  color: #334155;
  padding: 2px 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.tag-pill:hover {
  background: #e0f2fe;
  color: #0284c7;
  border-color: #7dd3fc;
}

.code-textarea :deep(textarea) {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 12.5px;
  line-height: 1.6;
}

/* 实时预览气泡仿真 */
.preview-box {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.preview-label {
  font-size: 11.5px;
  font-weight: 600;
  color: #64748b;
}

.tg-bubble-preview {
  background: #ffffff;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 12px 14px;
  font-size: 13px;
  line-height: 1.65;
  color: #0f172a;
  white-space: pre-wrap;
  word-break: break-word;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.tg-bubble-preview :deep(b) {
  font-weight: 700;
  color: #0f172a;
}

.tg-bubble-preview :deep(code) {
  background: #f1f5f9;
  color: #0284c7;
  padding: 2px 5px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 12px;
}

.tg-bubble-preview :deep(blockquote) {
  border-left: 3px solid #0284c7;
  margin: 6px 0;
  padding: 4px 10px;
  background: #f0f9ff;
  border-radius: 0 4px 4px 0;
}

.dialog-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.footer-tip {
  font-size: 12px;
}

.footer-btns {
  display: flex;
  gap: 8px;
}
</style>
