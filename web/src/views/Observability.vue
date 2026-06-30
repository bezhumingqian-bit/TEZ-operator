<template>
  <div class="observability-page">
    <h2 style="margin-bottom: 16px;">可观测性看板</h2>

    <!-- 概览卡片 -->
    <el-row :gutter="16" style="margin-bottom: 20px;">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">API 请求数</div>
          <div class="stat-value">{{ summary.api.total_requests }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card" :class="{ 'stat-warn': summary.api.errors_4xx_5xx > 0 }">
          <div class="stat-label">API 错误</div>
          <div class="stat-value">{{ summary.api.errors_4xx_5xx }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card" :class="{ 'stat-warn': summary.api.slow_requests_gt3s > 0 }">
          <div class="stat-label">慢请求 (&gt;3s)</div>
          <div class="stat-value">{{ summary.api.slow_requests_gt3s }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">API 平均耗时</div>
          <div class="stat-value">{{ summary.api.avg_duration_ms }}ms</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-bottom: 20px;">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">浏览器操作数</div>
          <div class="stat-value">{{ summary.browser.total_operations }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-success">
          <div class="stat-label">浏览器成功</div>
          <div class="stat-value">{{ summary.browser.success }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card" :class="{ 'stat-error': summary.browser.failures > 0 }">
          <div class="stat-label">浏览器失败</div>
          <div class="stat-value">{{ summary.browser.failures }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card" :class="{ 'stat-warn': summary.browser.login_required > 0 }">
          <div class="stat-label">需重新登录</div>
          <div class="stat-value">{{ summary.browser.login_required }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 操作系统分布 -->
    <el-row :gutter="16" style="margin-bottom: 20px;" v-if="osDistribution.length">
      <el-col :span="24">
        <el-card shadow="hover">
          <div style="font-size: 13px; color: #909399; margin-bottom: 8px;">客户端操作系统分布</div>
          <div style="display: flex; gap: 16px; flex-wrap: wrap;">
            <el-tag
              v-for="item in osDistribution"
              :key="item.os"
              :type="osTagType(item.os)"
              size="default"
              effect="plain"
            >
              {{ item.os }} · {{ item.count }}
            </el-tag>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Tab 切换 -->
    <el-tabs v-model="activeTab" type="border-card">
      <!-- API 访问日志 -->
      <el-tab-pane label="API 访问日志" name="api">
        <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
          <span style="color: #909399; font-size: 13px;">
            最近 {{ apiLogs.length }} 条请求
            <el-tag v-if="apiErrors.length" type="danger" size="small" style="margin-left: 8px;">
              {{ apiErrors.length }} 个错误
            </el-tag>
            <el-tag v-if="apiSlow.length" type="warning" size="small" style="margin-left: 4px;">
              {{ apiSlow.length }} 个慢请求
            </el-tag>
          </span>
          <el-button size="small" :icon="Refresh" @click="loadApiLogs" :loading="loadingApi">刷新</el-button>
        </div>

        <el-table :data="apiLogs" stripe size="small" max-height="500" style="width: 100%;">
          <el-table-column prop="ts" label="时间" width="180">
            <template #default="{ row }">
              {{ formatTime(row.ts) }}
            </template>
          </el-table-column>
          <el-table-column label="方法" width="70">
            <template #default="{ row }">
              <el-tag :type="methodTag(row.method)" size="small">{{ row.method }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="path" label="路径" min-width="220" show-overflow-tooltip />
          <el-table-column label="状态码" width="80">
            <template #default="{ row }">
              <el-tag :type="statusTag(row.status)" size="small">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="耗时" width="80">
            <template #default="{ row }">
              <span :style="{ color: row.duration_ms > 3000 ? '#e6a23c' : row.duration_ms > 10000 ? '#f56c6c' : '' }">
                {{ row.duration_ms }}ms
              </span>
            </template>
          </el-table-column>
          <el-table-column label="系统" width="80">
            <template #default="{ row }">
              <el-tag :type="osTagType(row.os)" size="small">{{ row.os || 'unknown' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="client_ip" label="客户端 IP" width="130" show-overflow-tooltip />
          <el-table-column prop="error" label="错误信息" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.error" style="color: #f56c6c;">{{ row.error }}</span>
              <span v-else style="color: #c0c4cc;">-</span>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 浏览器抓取审计 -->
      <el-tab-pane label="浏览器抓取审计" name="browser">
        <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
          <span style="color: #909399; font-size: 13px;">
            最近 {{ browserAudit.length }} 次操作
            <el-tag v-if="browserFailures.length" type="danger" size="small" style="margin-left: 8px;">
              {{ browserFailures.length }} 次失败
            </el-tag>
          </span>
          <el-button size="small" :icon="Refresh" @click="loadBrowserAudit" :loading="loadingBrowser">刷新</el-button>
        </div>

        <el-table :data="browserAudit" stripe size="small" max-height="500" style="width: 100%;">
          <el-table-column prop="ts" label="时间" width="180">
            <template #default="{ row }">
              {{ formatTime(row.ts) }}
            </template>
          </el-table-column>
          <el-table-column prop="platform" label="平台" width="80">
            <template #default="{ row }">
              <el-tag size="small">{{ row.platform }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="operation" label="操作" width="110" show-overflow-tooltip />
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag :type="auditStatusTag(row.status)" size="small">{{ auditStatusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="耗时" width="80">
            <template #default="{ row }">
              <span :style="{ color: row.duration_ms > 30000 ? '#f56c6c' : row.duration_ms > 10000 ? '#e6a23c' : '' }">
                {{ row.duration_ms }}ms
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="rows" label="数据行数" width="90" />
          <el-table-column prop="session" label="会话 ID" width="200" show-overflow-tooltip />
          <el-table-column prop="error" label="错误信息" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.error" style="color: #f56c6c;">{{ row.error }}</span>
              <span v-else style="color: #c0c4cc;">-</span>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 浏览器截图 -->
      <el-tab-pane label="浏览器截图" name="screenshots">
        <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
          <span style="color: #909399; font-size: 13px;">最近 {{ screenshots.length }} 张截图</span>
          <el-button size="small" :icon="Refresh" @click="loadScreenshots" :loading="loadingScreenshots">刷新</el-button>
        </div>

        <el-empty v-if="!screenshots.length" description="暂无截图" />

        <div v-else class="screenshot-grid">
          <div
            v-for="s in screenshots"
            :key="s.filename"
            class="screenshot-item"
            @click="previewScreenshot(s.filename)"
          >
            <img :src="screenshotUrl(s.filename)" :alt="s.filename" loading="lazy" />
            <div class="screenshot-info">
              <span class="screenshot-name">{{ s.filename }}</span>
              <span class="screenshot-meta">{{ formatTime(s.ts) }} · {{ s.size_kb }}KB</span>
            </div>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 截图预览弹窗 -->
    <el-dialog v-model="showPreview" title="截图预览" width="80%" top="5vh" destroy-on-close>
      <div style="text-align: center;">
        <img :src="previewUrl" style="max-width: 100%; max-height: 70vh; border: 1px solid #ebeef5; border-radius: 4px;" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import {
  fetchSummary,
  fetchApiLogs,
  fetchBrowserAudit,
  fetchScreenshots,
  screenshotUrl,
  type ObservabilitySummary,
  type ApiLogEntry,
  type BrowserAuditEntry,
  type ScreenshotInfo,
} from '@/api/observability'

const activeTab = ref('api')

// ── 数据 ──
const summary = ref<ObservabilitySummary>({
  api: { total_requests: 0, errors_4xx_5xx: 0, slow_requests_gt3s: 0, avg_duration_ms: 0 },
  browser: { total_operations: 0, success: 0, failures: 0, login_required: 0, success_rate: 0 },
  os_distribution: {},
})
const apiLogs = ref<ApiLogEntry[]>([])
const browserAudit = ref<BrowserAuditEntry[]>([])
const screenshots = ref<ScreenshotInfo[]>([])

const loadingApi = ref(false)
const loadingBrowser = ref(false)
const loadingScreenshots = ref(false)

// ── 计算 ──
const apiErrors = computed(() => apiLogs.value.filter(e => e.status >= 400))
const apiSlow = computed(() => apiLogs.value.filter(e => e.duration_ms > 3000))
const browserFailures = computed(() => browserAudit.value.filter(e => e.status === 'failure'))

const osDistribution = computed(() => {
  const dist = summary.value.os_distribution || {}
  return Object.entries(dist)
    .map(([os, count]) => ({ os, count }))
    .sort((a, b) => b.count - a.count)
})

// ── 截图预览 ──
const showPreview = ref(false)
const previewUrl = ref('')
function previewScreenshot(filename: string) {
  previewUrl.value = screenshotUrl(filename)
  showPreview.value = true
}

// ── 加载数据 ──
async function loadSummary() {
  try {
    summary.value = await fetchSummary()
  } catch { /* silent */ }
}

async function loadApiLogs() {
  loadingApi.value = true
  try {
    apiLogs.value = await fetchApiLogs(200)
  } finally {
    loadingApi.value = false
  }
}

async function loadBrowserAudit() {
  loadingBrowser.value = true
  try {
    browserAudit.value = await fetchBrowserAudit(200)
  } finally {
    loadingBrowser.value = false
  }
}

async function loadScreenshots() {
  loadingScreenshots.value = true
  try {
    screenshots.value = await fetchScreenshots(50)
  } finally {
    loadingScreenshots.value = false
  }
}

// ── 格式化 ──
function formatTime(ts: string): string {
  if (!ts) return '-'
  const d = new Date(ts)
  return d.toLocaleString('zh-CN', { hour12: false })
}

function methodTag(m: string): string {
  const map: Record<string, string> = { GET: '', POST: 'success', PUT: 'warning', PATCH: 'warning', DELETE: 'danger' }
  return map[m] || 'info'
}

function statusTag(code: number): string {
  if (code < 300) return 'success'
  if (code < 400) return 'warning'
  if (code < 500) return 'danger'
  return 'danger'
}

function auditStatusTag(s: string): string {
  const map: Record<string, string> = { success: 'success', failure: 'danger', login_required: 'warning' }
  return map[s] || 'info'
}

function auditStatusLabel(s: string): string {
  const map: Record<string, string> = { success: '成功', failure: '失败', login_required: '需登录' }
  return map[s] || s
}

function osTagType(os: string): string {
  const map: Record<string, string> = { Windows: '', macOS: 'success', Linux: 'warning', Android: 'success', iOS: '' }
  return map[os] || 'info'
}

// ── 初始化 ──
onMounted(() => {
  loadSummary()
  loadApiLogs()
  loadBrowserAudit()
  loadScreenshots()
})
</script>

<style scoped>
.observability-page {
  padding: 8px;
}

.stat-card {
  text-align: center;
  cursor: default;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
}

.stat-warn .stat-value { color: #e6a23c; }
.stat-error .stat-value { color: #f56c6c; }
.stat-success .stat-value { color: #67c23a; }

.screenshot-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.screenshot-item {
  cursor: pointer;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  overflow: hidden;
  transition: box-shadow 0.2s;
}

.screenshot-item:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.screenshot-item img {
  width: 100%;
  height: 140px;
  object-fit: cover;
  display: block;
}

.screenshot-info {
  padding: 8px;
  display: flex;
  flex-direction: column;
}

.screenshot-name {
  font-size: 12px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.screenshot-meta {
  font-size: 11px;
  color: #c0c4cc;
  margin-top: 4px;
}
</style>
