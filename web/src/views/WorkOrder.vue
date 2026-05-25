<template>
  <div class="workorder-page">
    <!-- 顶部统计 -->
    <div class="stats-bar">
      <div class="stat-item" v-for="s in statItems" :key="s.key" :class="s.key">
        <div class="stat-value">{{ stats[s.key] || 0 }}</div>
        <div class="stat-label">{{ s.label }}</div>
      </div>
    </div>

    <!-- 操作栏 -->
    <div class="toolbar">
      <el-button type="primary" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon> 新建工单
      </el-button>
      <el-select v-model="filterStatus" placeholder="状态筛选" clearable size="default" style="width: 140px">
        <el-option label="待受理" value="submitted" />
        <el-option label="处理中" value="processing" />
        <el-option label="待验证" value="verifying" />
        <el-option label="已完成" value="completed" />
        <el-option label="已驳回" value="rejected" />
      </el-select>
      <el-select v-model="filterType" placeholder="类型筛选" clearable size="default" style="width: 140px">
        <el-option label="ECM导出" value="ecm_export" />
        <el-option label="母机投放" value="host_deploy" />
        <el-option label="搬迁" value="migration" />
        <el-option label="维修" value="repair" />
      </el-select>
    </div>

    <!-- 工单列表 -->
    <el-table :data="orders" stripe style="width: 100%" v-loading="listLoading" @row-click="openDetail">
      <el-table-column prop="order_no" label="工单号" width="160" />
      <el-table-column prop="order_type" label="类型" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="typeTagMap[row.order_type]">{{ typeLabel[row.order_type] }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="title" label="标题" min-width="200" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="statusTagMap[row.status]">{{ statusLabel[row.status] }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="creator" label="提交人" width="110" />
      <el-table-column prop="assignee" label="处理人" width="110" />
      <el-table-column prop="priority" label="优先级" width="80">
        <template #default="{ row }">
          <span :class="'priority-' + row.priority">{{ priorityLabel[row.priority] }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="160">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
    </el-table>

    <!-- 新建工单弹窗 -->
    <el-dialog v-model="showCreateDialog" title="新建工单" width="600px" destroy-on-close>
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="工单类型" required>
          <el-select v-model="createForm.order_type" placeholder="选择类型" style="width: 100%">
            <el-option label="ECM导出转TEZ" value="ecm_export" />
            <el-option label="母机投放" value="host_deploy" />
            <el-option label="搬迁" value="migration" />
            <el-option label="维修" value="repair" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题" required>
          <el-input v-model="createForm.title" placeholder="简述工单内容" />
        </el-form-item>
        <el-form-item label="固资号/IP">
          <el-input v-model="createForm.asset_ids" placeholder="多个用分号分隔" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="目标Zone">
          <el-input v-model="createForm.zone" placeholder="如：池州边缘一区（电信）" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-radio-group v-model="createForm.priority">
            <el-radio :value="1">紧急</el-radio>
            <el-radio :value="2">普通</el-radio>
            <el-radio :value="3">低</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="createForm.note" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="creating">提交工单</el-button>
      </template>
    </el-dialog>

    <!-- 工单详情弹窗 -->
    <el-dialog v-model="showDetailDialog" :title="'工单详情 - ' + (selectedOrder?.order_no || '')" width="700px" destroy-on-close>
      <div v-if="selectedOrder" class="order-detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="工单号">{{ selectedOrder.order_no }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ typeLabel[selectedOrder.order_type] }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTagMap[selectedOrder.status]">{{ statusLabel[selectedOrder.status] }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="优先级">{{ priorityLabel[selectedOrder.priority] }}</el-descriptions-item>
          <el-descriptions-item label="提交人">{{ selectedOrder.creator }}</el-descriptions-item>
          <el-descriptions-item label="处理人">{{ selectedOrder.assignee || '-' }}</el-descriptions-item>
          <el-descriptions-item label="标题" :span="2">{{ selectedOrder.title }}</el-descriptions-item>
        </el-descriptions>

        <!-- 前置校验 -->
        <div v-if="selectedOrder.pre_checks && Object.keys(selectedOrder.pre_checks).length" class="section">
          <h4>前置校验</h4>
          <div v-for="(check, key) in selectedOrder.pre_checks" :key="key" class="check-item">
            <el-icon :color="check.passed ? '#67c23a' : '#f56c6c'">
              <component :is="check.passed ? 'CircleCheck' : 'CircleClose'" />
            </el-icon>
            <span>{{ check.message }}</span>
          </div>
        </div>

        <!-- 操作日志 -->
        <div class="section">
          <h4>操作记录</h4>
          <el-timeline>
            <el-timeline-item
              v-for="log in selectedOrder.logs"
              :key="log.id"
              :timestamp="formatTime(log.created_at)"
              placement="top"
            >
              <strong>{{ log.operator }}</strong> {{ actionLabel[log.action] || log.action }}
              <span v-if="log.content"> — {{ log.content }}</span>
            </el-timeline-item>
          </el-timeline>
        </div>

        <!-- 状态流转按钮 -->
        <div v-if="nextStatuses.length" class="section">
          <h4>操作</h4>
          <el-button
            v-for="ns in nextStatuses"
            :key="ns"
            :type="ns === 'rejected' ? 'danger' : 'primary'"
            @click="handleTransition(ns)"
          >
            {{ statusLabel[ns] || ns }}
          </el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, computed } from 'vue'
import { Plus, CircleCheck, CircleClose } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import {
  createOrder, listOrders, getOrderStats, getOrder, transitionOrder,
  type OrderInfo, type StatsResponse
} from '@/api/workorders'

// ─── 常量映射 ───
const typeLabel: Record<string, string> = { ecm_export: 'ECM导出', host_deploy: '母机投放', migration: '搬迁', repair: '维修' }
const typeTagMap: Record<string, string> = { ecm_export: '', host_deploy: 'success', migration: 'warning', repair: 'danger' }
const statusLabel: Record<string, string> = { submitted: '已提交', pending: '待受理', processing: '处理中', verifying: '待验证', completed: '已完成', rejected: '已驳回' }
const statusTagMap: Record<string, string> = { submitted: 'info', pending: 'warning', processing: '', verifying: 'warning', completed: 'success', rejected: 'danger' }
const priorityLabel: Record<number, string> = { 1: '紧急', 2: '普通', 3: '低' }
const actionLabel: Record<string, string> = { create: '创建工单', assign: '受理', process: '开始处理', verify: '提交验证', complete: '完成', reject: '驳回', resubmit: '重新提交' }
const validTransitions: Record<string, string[]> = { submitted: ['pending', 'rejected'], pending: ['processing', 'rejected'], processing: ['verifying', 'rejected'], verifying: ['completed', 'processing'] }
const statItems = [
  { key: 'total', label: '全部' },
  { key: 'submitted', label: '已提交' },
  { key: 'processing', label: '处理中' },
  { key: 'verifying', label: '待验证' },
  { key: 'completed', label: '已完成' },
]

// ─── 状态 ───
const stats = ref<StatsResponse>({ submitted: 0, pending: 0, processing: 0, verifying: 0, completed: 0, rejected: 0, total: 0 })
const orders = ref<OrderInfo[]>([])
const listLoading = ref(false)
const filterStatus = ref('')
const filterType = ref('')

const showCreateDialog = ref(false)
const creating = ref(false)
const createForm = ref({ order_type: '', title: '', asset_ids: '', zone: '', priority: 2, note: '' })

const showDetailDialog = ref(false)
const selectedOrder = ref<OrderInfo | null>(null)

const nextStatuses = computed(() => {
  if (!selectedOrder.value) return []
  return validTransitions[selectedOrder.value.status] || []
})

// ─── 方法 ───
async function loadStats() {
  try { stats.value = await getOrderStats() } catch {}
}

async function loadOrders() {
  listLoading.value = true
  try {
    const resp = await listOrders({
      status: filterStatus.value || undefined,
      order_type: filterType.value || undefined,
    })
    orders.value = resp.items
  } finally { listLoading.value = false }
}

async function handleCreate() {
  if (!createForm.value.order_type || !createForm.value.title) {
    ElMessage.warning('请填写工单类型和标题')
    return
  }
  creating.value = true
  try {
    await createOrder({
      order_type: createForm.value.order_type,
      title: createForm.value.title,
      creator: 'current_user', // TODO: 接入真实登录用户
      detail: {
        asset_ids: createForm.value.asset_ids,
        zone: createForm.value.zone,
      },
      note: createForm.value.note,
      priority: createForm.value.priority,
    })
    ElMessage.success('工单创建成功')
    showCreateDialog.value = false
    createForm.value = { order_type: '', title: '', asset_ids: '', zone: '', priority: 2, note: '' }
    await loadOrders()
    await loadStats()
  } finally { creating.value = false }
}

async function openDetail(row: OrderInfo) {
  try {
    selectedOrder.value = await getOrder(row.id)
    showDetailDialog.value = true
  } catch {}
}

async function handleTransition(toStatus: string) {
  if (!selectedOrder.value) return
  try {
    selectedOrder.value = await transitionOrder(selectedOrder.value.id, {
      to_status: toStatus,
      operator: 'current_user',
      comment: undefined,
    })
    ElMessage.success(`已流转为: ${statusLabel[toStatus]}`)
    await loadOrders()
    await loadStats()
  } catch {}
}

function formatTime(t: string) {
  if (!t) return '-'
  return t.replace('T', ' ').slice(0, 16)
}

// ─── 生命周期 ───
onMounted(() => { loadStats(); loadOrders() })
watch([filterStatus, filterType], () => loadOrders())
</script>

<style scoped>
.workorder-page { padding: 20px; max-width: 1200px; margin: 0 auto; }

.stats-bar { display: flex; gap: 16px; margin-bottom: 20px; }
.stat-item { flex: 1; text-align: center; padding: 16px; border-radius: 8px; background: #f5f7fa; border: 1px solid #ebeef5; }
.stat-value { font-size: 28px; font-weight: 700; color: #303133; }
.stat-label { font-size: 13px; color: #909399; margin-top: 4px; }
.stat-item.processing { border-color: #409eff; background: #ecf5ff; }
.stat-item.processing .stat-value { color: #409eff; }

.toolbar { display: flex; gap: 12px; margin-bottom: 16px; }

.priority-1 { color: #f56c6c; font-weight: 600; }
.priority-2 { color: #303133; }
.priority-3 { color: #909399; }

.order-detail .section { margin-top: 20px; }
.order-detail .section h4 { margin-bottom: 8px; font-size: 14px; color: #606266; }
.check-item { display: flex; align-items: center; gap: 6px; padding: 4px 0; }
</style>
