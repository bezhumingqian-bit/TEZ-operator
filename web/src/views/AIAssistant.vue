<template>
  <div class="ai-page">
    <div class="ai-header">
      <h2>AI 助手</h2>
      <p>基于知识库和竞分资料的智能问答</p>
    </div>

    <!-- 模式选择 -->
    <div class="ai-mode">
      <el-radio-group v-model="contextMode" size="default">
        <el-radio-button value="competitive">竞争分析</el-radio-button>
        <el-radio-button value="knowledge">运维知识</el-radio-button>
        <el-radio-button value="none">自由对话</el-radio-button>
      </el-radio-group>
      <el-tag v-if="!aiConfigured" type="danger" size="small">未配置 API Key</el-tag>
    </div>

    <!-- 对话区 -->
    <div class="ai-chat" ref="chatContainer">
      <div v-if="!messages.length" class="ai-empty">
        <div class="ai-empty__icon">🤖</div>
        <p>选择模式后输入问题开始对话</p>
        <div class="ai-suggestions">
          <el-button v-for="s in suggestions" :key="s" size="small" round @click="sendMessage(s)">{{ s }}</el-button>
        </div>
      </div>

      <div v-for="(msg, idx) in messages" :key="idx" class="ai-message" :class="'ai-message--' + msg.role">
        <div class="ai-message__avatar">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
        <div class="ai-message__content">
          <div v-if="msg.role === 'assistant'" v-html="renderMarkdown(msg.content)" class="ai-message__md"></div>
          <div v-else>{{ msg.content }}</div>
        </div>
      </div>

      <div v-if="loading" class="ai-message ai-message--assistant">
        <div class="ai-message__avatar">🤖</div>
        <div class="ai-message__content">
          <el-icon class="is-loading"><Loading /></el-icon> 思考中...
        </div>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="ai-input">
      <el-input
        v-model="inputText"
        type="textarea"
        :rows="2"
        placeholder="输入问题...（Enter 发送，Shift+Enter 换行）"
        @keydown.enter.exact.prevent="sendMessage()"
        :disabled="loading"
      />
      <el-button type="primary" :loading="loading" :disabled="!inputText.trim()" @click="sendMessage()">
        发送
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const route = useRoute()
import apiClient from '@/api/client'
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt({ html: false, breaks: true, linkify: true })

const contextMode = ref<'competitive' | 'knowledge' | 'none'>('competitive')
const inputText = ref('')
const loading = ref(false)
const aiConfigured = ref(false)
const chatContainer = ref<HTMLElement | null>(null)

interface Message {
  role: 'user' | 'assistant'
  content: string
}
const messages = ref<Message[]>([])

const suggestions = [
  'TEZ 与 AWS Local Zone 的核心差异是什么？',
  '阿里云 ENS 在东南亚的定价策略？',
  '越南开区的风险和建议？',
  '母机搬迁的标准流程是什么？',
]

function renderMarkdown(text: string) {
  return md.render(text)
}

async function sendMessage(text?: string) {
  const msg = text || inputText.value.trim()
  if (!msg) return

  messages.value.push({ role: 'user', content: msg })
  inputText.value = ''
  loading.value = true
  scrollToBottom()

  try {
    const history = messages.value.slice(0, -1).map(m => ({
      role: m.role,
      content: m.content,
    }))

    const resp = await apiClient.post('/api/v1/ai/chat', {
      message: msg,
      context_type: contextMode.value === 'none' ? null : contextMode.value,
      history: history.length > 0 ? history.slice(-8) : null,
    })

    messages.value.push({ role: 'assistant', content: resp.data.reply })
  } catch {
    messages.value.push({ role: 'assistant', content: '请求失败，请检查 AI 配置或网络' })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

onMounted(async () => {
  try {
    const resp = await apiClient.get('/api/v1/ai/status')
    aiConfigured.value = resp.data.configured
  } catch {}

  // 如果从驾驶舱搜索跳转过来，自动发送问题
  const q = route.query.q as string | undefined
  if (q && q.trim()) {
    await nextTick()
    sendMessage(q.trim())
  }
})
</script>

<style scoped>
.ai-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - var(--tez-header-h) - 48px);
  padding: 24px;
  max-width: 900px;
  margin: 0 auto;
}

.ai-header h2 {
  font-size: 20px;
  font-weight: 700;
  margin: 0 0 4px;
}

.ai-header p {
  font-size: 13px;
  color: var(--tez-text-muted);
  margin: 0 0 16px;
}

.ai-mode {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.ai-chat {
  flex: 1;
  overflow-y: auto;
  background: var(--tez-surface);
  border: 1px solid var(--tez-border);
  border-radius: var(--tez-radius);
  padding: 20px;
  margin-bottom: 16px;
}

.ai-empty {
  text-align: center;
  padding: 60px 0;
  color: var(--tez-text-muted);
}

.ai-empty__icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.ai-suggestions {
  margin-top: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}

.ai-message {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.ai-message--user {
  flex-direction: row-reverse;
}

.ai-message__avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
  background: var(--tez-bg);
}

.ai-message__content {
  max-width: 75%;
  padding: 10px 14px;
  border-radius: var(--tez-radius-sm);
  font-size: 14px;
  line-height: 1.6;
}

.ai-message--user .ai-message__content {
  background: #409eff;
  color: #fff;
  border-top-right-radius: 2px;
}

.ai-message--assistant .ai-message__content {
  background: var(--tez-bg);
  color: var(--tez-text-primary);
  border-top-left-radius: 2px;
}

.ai-message__md :deep(p) { margin: 0 0 8px; }
.ai-message__md :deep(p:last-child) { margin: 0; }
.ai-message__md :deep(ul), .ai-message__md :deep(ol) { margin: 4px 0; padding-left: 20px; }
.ai-message__md :deep(table) { border-collapse: collapse; margin: 8px 0; font-size: 12px; }
.ai-message__md :deep(th), .ai-message__md :deep(td) { border: 1px solid var(--tez-border); padding: 4px 8px; }
.ai-message__md :deep(code) { background: rgba(0,0,0,0.06); padding: 1px 4px; border-radius: 3px; font-size: 12px; }

.ai-input {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.ai-input .el-input {
  flex: 1;
}
</style>
