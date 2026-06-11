<template>
  <div class="ops-logs-page">
    <div class="header">
      <h2>运维日志</h2>
      <div class="stats">
        <span class="stat ok">✅ {{ stats.ok_count || 0 }}</span>
        <span class="stat warn">⚠️ {{ stats.warn_count || 0 }}</span>
        <span class="stat fail">❌ {{ stats.fail_count || 0 }}</span>
      </div>
    </div>

    <div class="toolbar">
      <el-select v-model="filterStatus" placeholder="状态筛选" clearable size="default" style="width:120px">
        <el-option label="成功" value="ok" />
        <el-option label="警告" value="warn" />
        <el-option label="失败" value="fail" />
      </el-select>
      <el-select v-model="filterAction" placeholder="操作类型" clearable size="default" style="width:120px">
        <el-option label="推送文档" value="push_doc" />
        <el-option label="添加行" value="add_rows" />
        <el-option label="切换Sheet" value="switch_sheet" />
      </el-select>
      <el-button @click="refresh" :loading="loading">刷新</el-button>
    </div>

    <el-table :data="logs" stripe v-loading="loading" empty-text="暂无日志" size="small" highlight-current-row @row-click="showDetail">
      <el-table-column prop="created_at" label="时间" width="160">
        <template #default="{ row }">{{ fmt(row.created_at) }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="70">
        <template #default="{ row }">
          <el-tag size="small" :type="row.status === 'ok' ? 'success' : row.status === 'warn' ? 'warning' : 'danger'">
            {{ row.status === 'ok' ? '成功' : row.status === 'warn' ? '警告' : '失败' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="action" label="操作" width="90">
        <template #default="{ row }">{{ actionLabel[row.action] || row.action }}</template>
      </el-table-column>
      <el-table-column prop="target" label="目标" width="140" show-overflow-tooltip />
      <el-table-column prop="workorder_no" label="工单号" width="150" show-overflow-tooltip />
      <el-table-column prop="message" label="消息" min-width="200" show-overflow-tooltip />
    </el-table>

    <div class="pager">
      <el-pagination background layout="prev, next, total" :total="total" v-model:current-page="page"
        :page-size="50" @current-change="loadLogs" />
    </div>

    <!-- 详细弹窗 -->
    <el-dialog v-model="showDialog" title="日志详情" width="600px">
      <el-descriptions v-if="selected" :column="1" border size="small">
        <el-descriptions-item label="时间">{{ fmt(selected.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag size="small" :type="selected.status === 'ok' ? 'success' : selected.status === 'warn' ? 'warning' : 'danger'">
            {{ selected.status }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="操作">{{ actionLabel[selected.action] || selected.action }}</el-descriptions-item>
        <el-descriptions-item label="目标">{{ selected.target }}</el-descriptions-item>
        <el-descriptions-item label="工单号">{{ selected.workorder_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="消息">{{ selected.message || '-' }}</el-descriptions-item>
      </el-descriptions>

      <div v-if="selected?.detail?.mismatches" class="mismatch-section">
        <h4>不一致列 ({{ selected.detail.mismatches.length }})</h4>
        <el-table :data="selected.detail.mismatches" size="small" max-height="300">
          <el-table-column prop="col" label="列" width="60" />
          <el-table-column prop="label" label="名称" width="90" v-if="selected.detail.mismatches[0]?.label" />
          <el-table-column prop="expected" label="期望值" min-width="120" show-overflow-tooltip />
          <el-table-column prop="actual" label="实际值" min-width="120" show-overflow-tooltip />
        </el-table>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'

const actionLabel: Record<string, string> = { push_doc: '推送文档', add_rows: '添加行', switch_sheet: '切换Sheet' }

interface OpLog {
  id: number; action: string; target: string; status: string
  message: string | null; detail: any; workorder_no: string | null; created_at: string
}

const logs = ref<OpLog[]>([])
const loading = ref(false)
const total = ref(0)
const stats = ref({ ok_count: 0, warn_count: 0, fail_count: 0 })
const filterStatus = ref('')
const filterAction = ref('')
const page = ref(1)
const showDialog = ref(false)
const selected = ref<OpLog | null>(null)

async function loadLogs() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (filterStatus.value) params.set('status', filterStatus.value)
    if (filterAction.value) params.set('action', filterAction.value)
    params.set('limit', '50')
    params.set('offset', String((page.value - 1) * 50))
    const resp = await fetch(`/api/v1/op-logs?${params}`)
    const data = await resp.json()
    logs.value = data.items || []
    total.value = data.total || 0
    stats.value = { ok_count: data.ok_count, warn_count: data.warn_count, fail_count: data.fail_count }
  } finally { loading.value = false }
}

function refresh() { page.value = 1; loadLogs() }
function showDetail(row: OpLog) { selected.value = row; showDialog.value = true }
function fmt(t: string) { return t ? t.replace('T', ' ').slice(0, 19) : '-' }

onMounted(loadLogs)
watch([filterStatus, filterAction], refresh)
</script>

<style scoped>
.ops-logs-page { padding: 20px; max-width: 1200px; margin: 0 auto; }
.header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.header h2 { margin: 0; font-size: 18px; }
.stats { display: flex; gap: 12px; }
.stat { padding: 4px 12px; border-radius: 6px; font-size: 14px; font-weight: 600; }
.stat.ok { background: #f0f9eb; color: #67c23a; }
.stat.warn { background: #fdf6ec; color: #e6a23c; }
.stat.fail { background: #fef0f0; color: #f56c6c; }
.toolbar { display: flex; gap: 12px; margin-bottom: 16px; }
.pager { margin-top: 16px; display: flex; justify-content: center; }
.mismatch-section { margin-top: 16px; }
.mismatch-section h4 { margin-bottom: 8px; font-size: 14px; }
</style>
