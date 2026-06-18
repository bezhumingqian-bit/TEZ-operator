<template>
  <div class="ai-page">
    <div class="ai-header">
      <h2>AI 助手</h2>
      <p>智能问答 — 可查机器、知识库、可用区、成本数据</p>
    </div>
    <div class="ai-status">
      <el-tag v-if="!aiConfigured" type="danger" size="small">未配置 API Key</el-tag>
      <el-button size="small" text @click="clearHistory" style="margin-left:auto">清空对话</el-button>
    </div>

    <div class="ai-chat" ref="chatContainer">
      <div v-if="!messages.length" class="ai-empty">
        <div class="ai-empty__icon">🤖</div>
        <p>输入问题开始对话</p>
        <div class="ai-suggestions">
          <el-button v-for="s in suggestions" :key="s" size="small" round @click="sendMessage(s)">{{ s }}</el-button>
        </div>
      </div>

      <div v-for="(msg, idx) in messages" :key="idx" class="ai-message" :class="'ai-message--' + msg.role">
        <div class="ai-message__avatar">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
        <div class="ai-message__content">
          <div v-if="msg.tool_calls && msg.tool_calls.length" class="ai-tool-calls">
            <div class="ai-tool-calls__title">🛠️ 工具调用 ({{ msg.tool_calls.length }})</div>
            <div
              v-for="(tc, i) in msg.tool_calls"
              :key="i"
              class="ai-tool-call"
              :class="tc.ok ? 'ai-tool-call--ok' : 'ai-tool-call--err'"
            >
              <span class="ai-tool-call__name">{{ tc.name }}</span>
              <span class="ai-tool-call__args">{{ formatArgs(tc.args) }}</span>
              <span v-if="tc.source" class="ai-tool-call__source">📎 {{ tc.source }}</span>
            </div>
          </div>
          <div v-if="msg.role === 'assistant' && msg.content" v-html="renderMarkdown(msg.content)" class="ai-message__md"></div>
          <div v-else-if="msg.role === 'user'">{{ msg.content }}</div>
          <div v-else-if="msg.role === 'assistant' && !msg.content && (msg.tool_calls && msg.tool_calls.length)" class="ai-message__placeholder">（正在整理工具返回结果…）</div>
          <span v-if="msg.streaming" class="ai-cursor">|</span>
        </div>
      </div>

      <div v-if="loading" class="ai-message ai-message--assistant">
        <div class="ai-message__avatar">🤖</div>
        <div class="ai-message__content"><el-icon class="is-loading"><Loading /></el-icon> 思考中...</div>
      </div>
    </div>

    <div class="ai-input">
      <el-input
        v-model="inputText"
        type="textarea"
        :rows="2"
        placeholder="输入问题...（Enter 发送，Shift+Enter 换行）"
        @keydown.enter.exact.prevent="sendMessage()"
        :disabled="loading"
      />
      <el-button type="primary" :loading="loading" :disabled="!inputText.trim()" @click="sendMessage()">发送</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import apiClient from '@/api/client'
import MarkdownIt from 'markdown-it'

const route = useRoute()
const md = new MarkdownIt({ html: false, breaks: true, linkify: true })

const inputText = ref('')
const loading = ref(false)
const aiConfigured = ref(false)
const chatContainer = ref<HTMLElement | null>(null)

interface ToolCall {
  name: string
  args: Record<string, any>
  ok: boolean
  source?: string
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  tool_calls?: ToolCall[]
  streaming?: boolean
}
const messages = ref<Message[]>([])
let currentAbortController: AbortController | null = null

const STORAGE_KEY = 'tez_ai_messages'

const suggestions = [
  'TEZ 与 AWS Local Zone 的核心差异是什么？',
  '母机故障的标准处理流程？',
  '当前有哪些可用区？',
  '沈阳边缘一区有多少空闲机位',
]

function renderMarkdown(text: string) {
  return md.render(text)
}

function formatArgs(args: Record<string, any>): string {
  if (!args || Object.keys(args).length === 0) return '()'
  return Object.entries(args)
    .map(([k, v]) => `${k}=${typeof v === 'string' ? `"${v}"` : JSON.stringify(v)}`)
    .join(', ')
}

function saveMessages() {
  try {
    const cleaned = messages.value.map(m => ({ ...m, streaming: false }))
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cleaned))
  } catch {}
}

function loadMessages() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) messages.value = JSON.parse(raw)
  } catch {}
}

function clearHistory() {
  messages.value = []
  localStorage.removeItem(STORAGE_KEY)
}

async function sendMessage(text?: string) {
  const msg = text || inputText.value.trim()
  if (!msg || loading.value) return

  messages.value.push({ role: 'user', content: msg })
  inputText.value = ''
  loading.value = true
  scrollToBottom()

  // 构建历史
  const history = messages.value.slice(0, -1).map(m => ({
    role: m.role,
    content: m.content,
  })).slice(-8)

  // 创建 assistant 消息占位
  messages.value.push({ role: 'assistant', content: '', tool_calls: [], streaming: true })
  const aiMsg = messages.value[messages.value.length - 1]
  scrollToBottom()

  currentAbortController = new AbortController()

  try {
    const resp = await fetch('/api/v1/ai/agent/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg, history: history.length > 0 ? history : null }),
      signal: currentAbortController.signal,
    })

    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)

    const reader = resp.body?.getReader()
    if (!reader) throw new Error('No reader')

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      let currentEvent = ''
      for (const line of lines) {
        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7).trim()
        } else if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            if (currentEvent === 'text') {
              aiMsg.content += data
            } else if (currentEvent === 'tool_call' || currentEvent === 'tool_result') {
              if (!aiMsg.tool_calls) aiMsg.tool_calls = []
              const existing = aiMsg.tool_calls.find(
                t => t.name === data.name && JSON.stringify(t.args) === JSON.stringify(data.args)
              )
              if (!existing && data.name) {
                aiMsg.tool_calls.push({ name: data.name, args: data.args || {}, ok: true, source: data.source || '' })
              } else if (existing) {
                existing.ok = data.ok !== false
                existing.source = data.source || ''
              }
            } else if (currentEvent === 'error') {
              aiMsg.content = data.message || '出错了'
            } else if (currentEvent === 'done') {
              aiMsg.streaming = false
            }
            scrollToBottom()
          } catch {}
          currentEvent = ''
        }
      }
    }
  } catch (err: any) {
    if (err.name !== 'AbortError') {
      if (!aiMsg.content) aiMsg.content = '请求失败，请重试'
      console.error('Stream error:', err)
    }
  } finally {
    aiMsg.streaming = false
    loading.value = false
    currentAbortController = null
    saveMessages()
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
  loadMessages()

  try {
    const resp = await apiClient.get('/api/v1/ai/status')
    aiConfigured.value = resp.data.configured
  } catch {}

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
.ai-header h2 { font-size: 20px; font-weight: 700; margin: 0 0 4px; }
.ai-header p { font-size: 13px; color: var(--tez-text-muted); margin: 0 0 16px; }
.ai-status {
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
.ai-empty { text-align: center; padding: 60px 0; color: var(--tez-text-muted); }
.ai-empty__icon { font-size: 48px; margin-bottom: 12px; }
.ai-suggestions { margin-top: 16px; display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
.ai-message { display: flex; gap: 12px; margin-bottom: 16px; }
.ai-message--user { flex-direction: row-reverse; }
.ai-message__avatar {
  width: 32px; height: 32px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; flex-shrink: 0; background: var(--tez-bg);
}
.ai-message__content {
  max-width: 75%; padding: 10px 14px;
  border-radius: var(--tez-radius-sm); font-size: 14px; line-height: 1.6;
}
.ai-message--user .ai-message__content { background: #409eff; color: #fff; border-top-right-radius: 2px; }
.ai-message--assistant .ai-message__content { background: var(--tez-bg); color: var(--tez-text-primary); border-top-left-radius: 2px; }
.ai-message__md :deep(p) { margin: 0 0 8px; }
.ai-message__md :deep(p:last-child) { margin: 0; }
.ai-message__md :deep(ul), .ai-message__md :deep(ol) { margin: 4px 0; padding-left: 20px; }
.ai-message__md :deep(table) { border-collapse: collapse; margin: 8px 0; font-size: 12px; }
.ai-message__md :deep(th), .ai-message__md :deep(td) { border: 1px solid var(--tez-border); padding: 4px 8px; }
.ai-message__md :deep(code) { background: rgba(0,0,0,0.06); padding: 1px 4px; border-radius: 3px; font-size: 12px; }
.ai-tool-calls {
  margin-bottom: 10px; padding: 8px 10px;
  background: rgba(64, 158, 255, 0.08); border-left: 3px solid #409eff;
  border-radius: 4px; font-size: 12px;
}
.ai-tool-calls__title { font-weight: 600; margin-bottom: 6px; color: #409eff; }
.ai-tool-call { display: flex; gap: 6px; align-items: center; padding: 3px 0; flex-wrap: wrap; }
.ai-tool-call--ok { color: #67c23a; }
.ai-tool-call--err { color: #f56c6c; }
.ai-tool-call__name { font-weight: 600; }
.ai-tool-call__args { color: var(--tez-text-muted); font-size: 11px; font-family: 'SF Mono', Menlo, monospace; }
.ai-tool-call__source { font-size: 10px; color: var(--tez-text-muted); margin-left: 4px; }
.ai-message__placeholder { color: var(--tez-text-muted); font-style: italic; font-size: 12px; }
.ai-cursor { animation: blink 1s infinite; color: #409eff; font-weight: bold; }
@keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0; } }
.ai-input { display: flex; gap: 12px; align-items: flex-end; }
.ai-input .el-input { flex: 1; }
</style>
