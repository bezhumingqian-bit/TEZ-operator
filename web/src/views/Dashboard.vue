<template>
  <div class="dashboard">
    <!-- 顶部欢迎 + 运维助手搜索 -->
    <div class="dashboard__header">
      <div class="dashboard__title-row">
        <h2>运维驾驶舱</h2>
        <span class="dashboard__time">{{ currentTime }}</span>
      </div>
      <div class="dashboard__search">
        <el-input
          v-model="assistantQuery"
          placeholder="有问题？输入关键词快速找答案（如：母机故障 / 搬迁 / 找机器）"
          size="large"
          clearable
          @keyup.enter="goAssistant"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
          <template #append>
            <el-button @click="goAssistant">搜索</el-button>
          </template>
        </el-input>
      </div>
    </div>

    <!-- 工单统计卡片 -->
    <div class="stat-grid">
      <div v-for="item in statCards" :key="item.label" class="stat-card" :style="{ '--card-color': item.color, '--card-bg': item.bg }">
        <div class="stat-card__icon">
          <el-icon :size="24"><component :is="item.icon" /></el-icon>
        </div>
        <div class="stat-card__content">
          <div class="stat-card__number">{{ item.value }}</div>
          <div class="stat-card__label">{{ item.label }}</div>
        </div>
      </div>
    </div>

    <!-- 主内容区 -->
    <el-row :gutter="16" style="margin-top: 20px">
      <!-- 左侧：最近工单 -->
      <el-col :span="14">
        <el-card shadow="never" class="content-card">
          <template #header>
            <div class="card-header">
              <b>最近工单</b>
              <el-button text type="primary" size="small" @click="$router.push('/workorder')">查看全部 →</el-button>
            </div>
          </template>
          <el-table :data="recentOrders" size="small" v-loading="ordersLoading" :show-header="true" class="order-table">
            <el-table-column width="4">
              <template #default="{ row }">
                <div class="status-bar" :class="'status-bar--' + row.status"></div>
              </template>
            </el-table-column>
            <el-table-column prop="order_no" label="工单号" width="145">
              <template #default="{ row }">
                <span class="order-no">{{ row.order_no }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="title" label="标题" min-width="150" show-overflow-tooltip />
            <el-table-column prop="order_type" label="类型" width="70" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.order_type === 'migration' ? 'warning' : 'primary'" effect="plain">
                  {{ row.order_type === 'migration' ? '搬迁' : '投放' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="statusType(row.status)" effect="dark" round>{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="时间" width="120">
              <template #default="{ row }">
                <span class="time-text">{{ formatTime(row.created_at) }}</span>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!ordersLoading && recentOrders.length === 0" description="暂无工单" :image-size="60" />
        </el-card>
      </el-col>

      <!-- 右侧 -->
      <el-col :span="10">
        <!-- 快捷入口 -->
        <el-card shadow="never" class="content-card" style="margin-bottom: 16px">
          <template #header><b>快捷操作</b></template>
          <div class="quick-grid">
            <div class="quick-item" @click="$router.push('/workorder')">
              <el-icon :size="22" color="#409eff"><Tickets /></el-icon>
              <span>提交工单</span>
            </div>
            <div class="quick-item" @click="$router.push('/hosts')">
              <el-icon :size="22" color="#67c23a"><Search /></el-icon>
              <span>资源查询</span>
            </div>
            <div class="quick-item" @click="$router.push('/assistant')">
              <el-icon :size="22" color="#e6a23c"><User /></el-icon>
              <span>找接口人</span>
            </div>
            <div class="quick-item" @click="$router.push('/knowledge')">
              <el-icon :size="22" color="#909399"><Reading /></el-icon>
              <span>知识库</span>
            </div>
          </div>
        </el-card>

        <!-- 节点概览 -->
        <el-card shadow="never" class="content-card">
          <template #header>
            <div class="card-header">
              <b>节点资源</b>
              <div>
                <el-button size="small" :loading="syncAllLoading" @click="syncAllZones">
                  🔄 刷新全部
                </el-button>
                <el-button text type="primary" size="small" @click="$router.push('/hosts')">详细 →</el-button>
              </div>
            </div>
          </template>
          <el-table :data="zoneSnapshots" size="small" v-loading="zonesLoading" class="zone-table">
            <el-table-column prop="zone" label="可用区" min-width="130" show-overflow-tooltip />
            <el-table-column prop="free_count" label="空闲" width="60" align="center">
              <template #default="{ row }">
                <span class="cell-highlight" :class="{ 'cell-highlight--danger': row.free_count === 0, 'cell-highlight--success': row.free_count > 0 }">
                  {{ row.free_count }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="total_positions" label="总位" width="60" align="center" />
            <el-table-column prop="online_count" label="在线" width="60" align="center">
              <template #default="{ row }">
                <span style="color:#67c23a">{{ row.online_count }}</span>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!zonesLoading && zoneSnapshots.length === 0" description="暂无数据" :image-size="50">
            <template #description>
              <span style="color:#909399;font-size:12px">在「资源查询 → 节点资源概况」中查询后自动缓存</span>
            </template>
          </el-empty>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Tickets, Search, User, Reading, Timer, CircleCheck, Loading, WarningFilled, SuccessFilled, CircleClose } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const router = useRouter()

// ─── 运维助手搜索 ───
const assistantQuery = ref('')
function goAssistant() {
  const q = assistantQuery.value.trim()
  if (q) {
    router.push({ path: '/assistant', query: { q } })
  } else {
    router.push('/assistant')
  }
}

// ─── 时间显示 ───
const currentTime = ref('')
let timer: number | null = null
function updateTime() {
  currentTime.value = new Date().toLocaleString('zh-CN', { month: 'long', day: 'numeric', weekday: 'long', hour: '2-digit', minute: '2-digit' })
}
onMounted(() => { updateTime(); timer = window.setInterval(updateTime, 60000) })
onUnmounted(() => { if (timer) clearInterval(timer) })

// ─── 全量刷新 ───
const syncAllLoading = ref(false)
async function syncAllZones() {
  syncAllLoading.value = true
  try {
    const resp = await fetch('/api/v1/zones/sync-all', { method: 'POST' }).then(r => r.json())
    if (resp.success) {
      ElMessage.success(`已刷新 ${resp.zones_updated} 个可用区（共 ${resp.total_positions} 个机位）`)
      // 重新加载节点数据
      const zonesResp = await fetch('/api/v1/zones/snapshots').then(r => r.json())
      zoneSnapshots.value = zonesResp.items || []
    } else {
      ElMessage.error(resp.message || '刷新失败')
    }
  } catch {
    ElMessage.error('刷新失败，请检查浏览器登录状态')
  } finally {
    syncAllLoading.value = false
  }
}

// ─── 工单统计 ───
interface Stats {
  submitted: number; pending: number; processing: number
  verifying: number; completed: number; rejected: number; total: number
}
const stats = ref<Stats>({ submitted: 0, pending: 0, processing: 0, verifying: 0, completed: 0, rejected: 0, total: 0 })
const ordersLoading = ref(false)
const zonesLoading = ref(false)

const statCards = computed(() => [
  { label: '总工单', value: stats.value.total, color: '#409eff', bg: 'rgba(64,158,255,0.08)', icon: 'Tickets' },
  { label: '待受理', value: stats.value.submitted, color: '#e6a23c', bg: 'rgba(230,162,60,0.08)', icon: 'Timer' },
  { label: '处理中', value: stats.value.processing, color: '#409eff', bg: 'rgba(64,158,255,0.08)', icon: 'Loading' },
  { label: '待验证', value: stats.value.verifying, color: '#909399', bg: 'rgba(144,147,153,0.08)', icon: 'WarningFilled' },
  { label: '已完成', value: stats.value.completed, color: '#67c23a', bg: 'rgba(103,194,58,0.08)', icon: 'SuccessFilled' },
  { label: '已驳回', value: stats.value.rejected, color: '#f56c6c', bg: 'rgba(245,108,108,0.08)', icon: 'CircleClose' },
])

// ─── 最近工单 ───
interface OrderBrief { order_no: string; title: string; order_type: string; status: string; created_at: string }
const recentOrders = ref<OrderBrief[]>([])

function statusType(s: string) {
  const map: Record<string, string> = { submitted: 'warning', pending: 'info', processing: '', verifying: 'info', completed: 'success', rejected: 'danger' }
  return map[s] || ''
}
function statusLabel(s: string) {
  const map: Record<string, string> = { submitted: '待受理', pending: '待处理', processing: '处理中', verifying: '待验证', completed: '已完成', rejected: '已驳回' }
  return map[s] || s
}
function formatTime(t: string) {
  if (!t) return ''
  return new Date(t).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

// ─── 节点概览 ───
interface ZoneSnapshotBrief { zone: string; idc: string; total_positions: number; free_count: number; online_count: number; offline_count: number }
const zoneSnapshots = ref<ZoneSnapshotBrief[]>([])

// ─── 加载 ───
onMounted(async () => {
  ordersLoading.value = true
  zonesLoading.value = true

  const [statsResp, ordersResp, zonesResp] = await Promise.allSettled([
    fetch('/api/v1/workorders/stats').then(r => r.json()),
    fetch('/api/v1/workorders?limit=8').then(r => r.json()),
    fetch('/api/v1/zones/snapshots').then(r => r.json()),
  ])

  if (statsResp.status === 'fulfilled') stats.value = statsResp.value
  if (ordersResp.status === 'fulfilled') recentOrders.value = ordersResp.value.items || []
  if (zonesResp.status === 'fulfilled') zoneSnapshots.value = zonesResp.value.items || []

  ordersLoading.value = false
  zonesLoading.value = false
})
</script>

<style scoped>
.dashboard {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px;
}

.dashboard__header {
  margin-bottom: 24px;
}
.dashboard__title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.dashboard__header h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
}
.dashboard__time {
  color: #909399;
  font-size: 14px;
}
.dashboard__search {
  max-width: 700px;
}

/* ─── 统计卡片网格 ─── */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
}
.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-radius: 10px;
  background: var(--card-bg);
  border: 1px solid rgba(0,0,0,0.04);
  transition: transform 0.2s, box-shadow 0.2s;
  cursor: default;
}
.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.06);
}
.stat-card__icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--card-bg);
  color: var(--card-color);
}
.stat-card__number {
  font-size: 24px;
  font-weight: 700;
  color: var(--card-color);
  line-height: 1.1;
}
.stat-card__label {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

/* ─── 内容卡片 ─── */
.content-card {
  border-radius: 10px;
}
.content-card :deep(.el-card__header) {
  padding: 14px 20px;
  border-bottom: 1px solid #f0f0f0;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* ─── 工单表格 ─── */
.order-table :deep(.el-table__row) {
  cursor: pointer;
  transition: background 0.15s;
}
.order-table :deep(.el-table__row:hover > td) {
  background: #f5f8ff !important;
}
.order-no {
  font-family: 'SF Mono', 'Monaco', monospace;
  font-size: 12px;
  color: #606266;
}
.time-text {
  font-size: 12px;
  color: #909399;
}
.status-bar {
  width: 3px;
  height: 24px;
  border-radius: 2px;
  background: #ddd;
}
.status-bar--submitted { background: #e6a23c; }
.status-bar--processing { background: #409eff; }
.status-bar--verifying { background: #909399; }
.status-bar--completed { background: #67c23a; }
.status-bar--rejected { background: #f56c6c; }
.status-bar--pending { background: #c0c4cc; }

/* ─── 快捷操作网格 ─── */
.quick-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}
.quick-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 16px 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
  font-size: 13px;
  color: #606266;
}
.quick-item:hover {
  background: #f5f7fa;
}

/* ─── 节点表格 ─── */
.cell-highlight {
  font-weight: 600;
}
.cell-highlight--danger { color: #f56c6c; }
.cell-highlight--success { color: #67c23a; }
</style>
