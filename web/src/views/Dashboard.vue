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
          placeholder="搜索母机故障、搬迁、找机器等关键词"
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
      <div
        v-for="item in statCards"
        :key="item.label"
        class="stat-card"
        :class="{ 'stat-card--clickable': item.link }"
        :style="{ '--card-color': item.color, '--card-bg': item.bg }"
        @click="item.link && $router.push(item.link)"
      >
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
          <el-table v-if="recentOrders.length" :data="recentOrders" size="small" v-loading="ordersLoading" :show-header="true" class="order-table" @row-click="() => $router.push('/workorder')">
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
            <el-table-column prop="order_type" label="类型" width="70" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.order_type === 'migration' ? 'warning' : 'primary'" effect="plain">
                  {{ row.order_type === 'migration' ? '搬迁' : '投放' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="固资号" width="120" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="key-info">{{ extractAssets(row) || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="型号" width="100" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="key-info">{{ extractVsType(row) || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="可用区" width="95" show-overflow-tooltip>
              <template #default="{ row }">
                <el-tag size="small" type="success" effect="plain" v-if="extractZone(row)">{{ extractZone(row) }}</el-tag>
                <span v-else style="color:#c0c4cc">-</span>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="orderStatusType(row.status)" effect="dark" round>{{ orderStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="时间" width="120">
              <template #default="{ row }">
                <span class="time-text">{{ formatTime(row.created_at) }}</span>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else-if="!ordersLoading" description="暂无工单" :image-size="60" />
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
            <div class="quick-item" @click="openDemandForm">
              <el-icon :size="22" color="#8b5cf6"><ChatDotRound /></el-icon>
              <span>行业提单</span>
            </div>
            <div class="quick-item" @click="$router.push('/knowledge')">
              <el-icon :size="22" color="#909399"><Reading /></el-icon>
              <span>知识库</span>
            </div>
          </div>
        </el-card>

        <!-- 行业需求单 -->
        <el-card shadow="never" class="content-card" style="margin-bottom: 16px">
          <template #header>
            <div class="card-header">
              <b>行业需求单</b>
              <div>
                <el-button text type="primary" size="small" @click="copyDemandLink">复制提单链接</el-button>
                <el-button text type="primary" size="small" @click="$router.push('/workorder?type=demand_request')">查看全部 →</el-button>
              </div>
            </div>
          </template>
          <div v-if="demandOrders.length" class="demand-list">
            <div v-for="d in demandOrders" :key="d.order_no" class="demand-item">
              <div class="demand-item__title">{{ d.title }}</div>
              <div class="demand-item__meta">
                <span>{{ d.creator }}</span>
                <span>{{ formatTime(d.created_at) }}</span>
              </div>
            </div>
          </div>
          <el-empty v-else description="暂无行业需求单" :image-size="60">
            <el-button type="primary" size="small" @click="openDemandForm">去提单</el-button>
          </el-empty>
        </el-card>

        <!-- 节点概览 -->
        <el-card shadow="never" class="content-card">
          <template #header>
            <div class="card-header">
              <b>节点资源</b>
              <div>
                <el-button size="small" :loading="syncAllLoading" @click="syncAllZones">
                  <el-icon><Refresh /></el-icon> 刷新全部
                </el-button>
                <el-button text type="primary" size="small" @click="$router.push('/hosts')">详细 →</el-button>
              </div>
            </div>
          </template>

          <div v-if="zonesLoading" v-loading="zonesLoading" style="min-height: 80px"></div>

          <template v-else-if="zoneSnapshots.length">
            <!-- Zone 数量 ≤ 3：紧凑卡片模式 -->
            <div v-if="zoneSnapshots.length <= 3" class="zone-cards">
              <div v-for="z in zoneSnapshots" :key="z.zone" class="zone-card">
                <div class="zone-card__name" :title="z.zone">{{ z.zone }}</div>
                <div class="zone-card__stats">
                  <span class="zone-card__stat">
                    <span class="zone-card__label">空闲</span>
                    <span class="zone-card__value" :class="z.free_count === 0 ? 'text-danger' : 'text-success'">{{ z.free_count }}</span>
                  </span>
                  <span class="zone-card__stat">
                    <span class="zone-card__label">总位</span>
                    <span class="zone-card__value">{{ z.total_positions }}</span>
                  </span>
                  <span class="zone-card__stat">
                    <span class="zone-card__label">在线</span>
                    <span class="zone-card__value text-success">{{ z.online_count }}</span>
                  </span>
                </div>
              </div>
            </div>

            <!-- Zone 数量 > 3：表格模式 -->
            <el-table v-else :data="zoneSnapshots" size="small" class="zone-table">
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
          </template>

          <el-empty v-else description="暂无数据" :image-size="50">
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
import { Tickets, Search, User, Reading, Timer, CircleCheck, Loading, WarningFilled, SuccessFilled, CircleClose, ChatDotRound, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const router = useRouter()

// ─── AI 助手搜索 ───
const assistantQuery = ref('')
function goAssistant() {
  const q = assistantQuery.value.trim()
  if (q) {
    router.push({ path: '/ai', query: { q } })
  } else {
    router.push('/ai')
  }
}

function copyDemandLink() {
  const link = `${window.location.origin}/demand-request`
  navigator.clipboard.writeText(link).then(() => {
    ElMessage.success(`已复制提单链接：${link}`)
  }).catch(() => {
    ElMessage.info(`提单链接：${link}`)
  })
}

function openDemandForm() {
  window.open('/demand-request', '_blank')
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
const demandPending = ref(0)
const ordersLoading = ref(false)
const zonesLoading = ref(false)

const statCards = computed(() => [
  { label: '总工单', value: stats.value.total, color: '#409eff', bg: 'rgba(64,158,255,0.08)', icon: 'Tickets', link: '/workorder' },
  { label: '待受理', value: stats.value.submitted, color: '#e6a23c', bg: 'rgba(230,162,60,0.08)', icon: 'Timer', link: '/workorder?status=submitted' },
  { label: '处理中', value: stats.value.processing, color: '#409eff', bg: 'rgba(64,158,255,0.08)', icon: 'Loading', link: '/workorder?status=processing' },
  { label: '行业需求', value: demandPending.value, color: '#8b5cf6', bg: 'rgba(139,92,246,0.08)', icon: 'ChatDotRound', link: '/workorder?type=demand_request' },
  { label: '已完成', value: stats.value.completed, color: '#67c23a', bg: 'rgba(103,194,58,0.08)', icon: 'SuccessFilled', link: '/workorder?status=completed' },
  { label: '已驳回', value: stats.value.rejected, color: '#f56c6c', bg: 'rgba(245,108,108,0.08)', icon: 'CircleClose', link: '/workorder?status=rejected' },
])

// ─── 最近工单 ───
interface OrderBrief { order_no: string; title: string; order_type: string; status: string; created_at: string; creator: string; detail?: Record<string, any> }
const recentOrders = ref<OrderBrief[]>([])
const demandOrders = ref<OrderBrief[]>([])

// 从 detail 提取关键字段
function extractAssets(row: OrderBrief): string {
  const d = row.detail || {}
  const raw = d.asset_ids || ''
  // 取前两行固资号，每行截断
  const lines = String(raw).split('\n').filter(Boolean)
  const preview = lines.slice(0, 2).map((l: string) => l.trim().slice(0, 18)).join(', ')
  return lines.length > 2 ? preview + '…' : preview
}
import { formatTime, orderStatusType, orderStatusLabel, extractZone } from '@/utils/formatters'

// ─── 节点概览 ───
interface ZoneSnapshotBrief { zone: string; idc: string; total_positions: number; free_count: number; online_count: number; offline_count: number }
const zoneSnapshots = ref<ZoneSnapshotBrief[]>([])

// ─── 加载 ───
onMounted(async () => {
  ordersLoading.value = true
  zonesLoading.value = true

  const [statsResp, ordersResp, zonesResp, demandResp] = await Promise.allSettled([
    fetch('/api/v1/workorders/stats').then(r => r.json()),
    fetch('/api/v1/workorders?limit=8').then(r => r.json()),
    fetch('/api/v1/zones/snapshots').then(r => r.json()),
    fetch('/api/v1/workorders?order_type=demand_request&status=submitted&limit=5').then(r => r.json()),
  ])

  if (statsResp.status === 'fulfilled') stats.value = statsResp.value
  if (ordersResp.status === 'fulfilled') recentOrders.value = ordersResp.value.items || []
  if (zonesResp.status === 'fulfilled') zoneSnapshots.value = zonesResp.value.items || []
  if (demandResp.status === 'fulfilled') {
    demandPending.value = demandResp.value.total || 0
    demandOrders.value = demandResp.value.items || []
  }

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
  font-weight: 700;
  color: var(--tez-text-primary);
}
.dashboard__time {
  color: var(--tez-text-muted);
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
  border-radius: var(--tez-radius);
  background: var(--card-bg);
  border: 1px solid var(--tez-border);
  transition: transform var(--tez-transition), box-shadow var(--tez-transition);
  cursor: default;
}
.stat-card--clickable {
  cursor: pointer;
}
.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--tez-shadow-md);
}
.stat-card__icon {
  width: 40px;
  height: 40px;
  border-radius: var(--tez-radius-sm);
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
  color: var(--tez-text-muted);
  margin-top: 2px;
}

/* ─── 内容卡片 ─── */
.content-card {
  border-radius: var(--tez-radius) !important;
}
.content-card :deep(.el-card__header) {
  padding: 14px 20px;
  border-bottom: 1px solid var(--tez-border-light);
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
  background: var(--tez-primary-light) !important;
}
.order-no {
  font-family: 'SF Mono', 'Monaco', monospace;
  font-size: 12px;
  color: var(--tez-text-regular);
}
.time-text {
  font-size: 12px;
  color: var(--tez-text-muted);
}
.status-bar {
  width: 3px;
  height: 24px;
  border-radius: 2px;
  background: #ddd;
}
.status-bar--submitted { background: var(--tez-warning); }
.status-bar--processing { background: var(--tez-primary); }
.status-bar--verifying { background: var(--tez-text-muted); }
.status-bar--completed { background: var(--tez-success); }
.status-bar--rejected { background: var(--tez-danger); }
.status-bar--pending { background: #d1d5db; }

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
  border-radius: var(--tez-radius-sm);
  cursor: pointer;
  transition: background var(--tez-transition);
  font-size: 13px;
  color: var(--tez-text-regular);
}
.quick-item:hover {
  background: var(--tez-bg);
}

/* ─── 节点紧凑卡片 ─── */
.zone-cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.zone-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: #f9fafb;
  border-radius: 8px;
  border: 1px solid #f3f4f6;
  transition: background 0.15s;
}
.zone-card:hover {
  background: #f0f4ff;
}
.zone-card__name {
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.zone-card__stats {
  display: flex;
  gap: 20px;
}
.zone-card__stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.zone-card__label {
  font-size: 11px;
  color: #9ca3af;
}
.zone-card__value {
  font-size: 18px;
  font-weight: 700;
  color: #374151;
}
.text-danger { color: var(--tez-danger) !important; }
.text-success { color: var(--tez-success) !important; }

/* ─── 节点表格 ─── */
.cell-highlight {
  font-weight: 600;
}
.cell-highlight--danger { color: var(--tez-danger); }
.cell-highlight--success { color: var(--tez-success); }

/* ─── 行业需求列表 ─── */
.demand-list { display: flex; flex-direction: column; gap: 10px; }
.demand-item { padding: 10px 12px; background: #f9fafb; border-radius: 8px; border: 1px solid #f3f4f6; }
.demand-item__title { font-size: 13px; font-weight: 500; color: #1f2937; margin-bottom: 4px; }
.demand-item__meta { font-size: 11px; color: #9ca3af; display: flex; gap: 12px; }
</style>
