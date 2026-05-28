<template>
  <div class="dashboard">
    <h2 style="margin-bottom: 20px">运维驾驶舱</h2>

    <!-- 工单统计卡片 -->
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="4" v-for="item in statCards" :key="item.label">
        <el-card shadow="hover" class="stat-card" :body-style="{ padding: '16px' }">
          <div class="stat-number" :style="{ color: item.color }">{{ item.value }}</div>
          <div class="stat-label">{{ item.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 主内容区 -->
    <el-row :gutter="16">
      <!-- 左侧：最近工单 -->
      <el-col :span="14">
        <el-card shadow="never">
          <template #header>
            <div style="display:flex; justify-content:space-between; align-items:center">
              <b>最近工单</b>
              <el-button text type="primary" @click="$router.push('/workorder')">查看全部</el-button>
            </div>
          </template>
          <el-table :data="recentOrders" stripe size="small" v-loading="ordersLoading">
            <el-table-column prop="order_no" label="工单号" width="150" />
            <el-table-column prop="title" label="标题" min-width="150" show-overflow-tooltip />
            <el-table-column prop="order_type" label="类型" width="80">
              <template #default="{ row }">
                <el-tag size="small" :type="row.order_type === 'migration' ? 'warning' : 'primary'">
                  {{ row.order_type === 'migration' ? '搬迁' : '投放' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="80">
              <template #default="{ row }">
                <el-tag size="small" :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="150">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!ordersLoading && recentOrders.length === 0" description="暂无工单" />
        </el-card>
      </el-col>

      <!-- 右侧：节点概览 + 快捷入口 -->
      <el-col :span="10">
        <!-- 快捷入口 -->
        <el-card shadow="never" style="margin-bottom: 16px">
          <template #header><b>快捷入口</b></template>
          <div class="quick-links">
            <el-button @click="$router.push('/workorder')">提交工单</el-button>
            <el-button @click="$router.push('/hosts')">资源查询</el-button>
            <el-button @click="$router.push('/assistant')">找接口人</el-button>
            <el-button @click="$router.push('/knowledge')">知识库</el-button>
          </div>
        </el-card>

        <!-- 已同步节点概览 -->
        <el-card shadow="never">
          <template #header>
            <div style="display:flex; justify-content:space-between; align-items:center">
              <b>节点资源概览</b>
              <el-button text type="primary" @click="$router.push('/hosts')">详细查询</el-button>
            </div>
          </template>
          <el-table :data="zoneSnapshots" stripe size="small" v-loading="zonesLoading">
            <el-table-column prop="zone" label="可用区" min-width="140" show-overflow-tooltip />
            <el-table-column prop="free_count" label="空闲机位" width="80" align="center">
              <template #default="{ row }">
                <span :style="{ color: row.free_count > 0 ? '#67c23a' : '#f56c6c', fontWeight: 'bold' }">
                  {{ row.free_count }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="total_positions" label="总机位" width="70" align="center" />
            <el-table-column prop="online_count" label="TEZ在线" width="80" align="center" />
          </el-table>
          <el-empty v-if="!zonesLoading && zoneSnapshots.length === 0" description="暂无已同步节点，请先在资源查询中查询" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

// ─── 工单统计 ───
interface Stats {
  submitted: number
  pending: number
  processing: number
  verifying: number
  completed: number
  rejected: number
  total: number
}

const stats = ref<Stats>({ submitted: 0, pending: 0, processing: 0, verifying: 0, completed: 0, rejected: 0, total: 0 })
const ordersLoading = ref(false)
const zonesLoading = ref(false)

const statCards = computed(() => [
  { label: '总工单', value: stats.value.total, color: '#409eff' },
  { label: '待受理', value: stats.value.submitted, color: '#e6a23c' },
  { label: '处理中', value: stats.value.processing, color: '#409eff' },
  { label: '待验证', value: stats.value.verifying, color: '#909399' },
  { label: '已完成', value: stats.value.completed, color: '#67c23a' },
  { label: '已驳回', value: stats.value.rejected, color: '#f56c6c' },
])

// ─── 最近工单 ───
interface OrderBrief {
  order_no: string
  title: string
  order_type: string
  status: string
  created_at: string
}
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
interface ZoneSnapshotBrief {
  zone: string
  idc: string
  total_positions: number
  free_count: number
  online_count: number
  offline_count: number
}
const zoneSnapshots = ref<ZoneSnapshotBrief[]>([])

// ─── 加载数据 ───
onMounted(async () => {
  // 并行加载
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
  padding: 20px;
}
.stat-card {
  text-align: center;
}
.stat-number {
  font-size: 28px;
  font-weight: bold;
  line-height: 1.2;
}
.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}
.quick-links {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
