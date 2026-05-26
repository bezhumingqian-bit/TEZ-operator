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
        <el-option label="投放" value="host_deploy" />
        <el-option label="搬迁" value="migration" />
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
      <el-table-column label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <el-popconfirm title="确定删除该工单？" @confirm="handleDelete(row)">
            <template #reference>
              <el-button type="danger" link size="small" @click.stop>删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建工单弹窗 -->
    <el-dialog v-model="showCreateDialog" title="新建工单" width="650px" destroy-on-close>
      <el-form :model="createForm" label-width="120px">
        <el-form-item label="工单类型" required>
          <el-select v-model="createForm.order_type" placeholder="选择类型" style="width: 100%">
            <el-option label="投放" value="host_deploy" />
            <el-option label="搬迁" value="migration" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题" required>
          <el-input v-model="createForm.title" placeholder="简述工单内容" />
        </el-form-item>
        <el-form-item label="是否紧急">
          <el-radio-group v-model="createForm.priority">
            <el-radio :value="1">紧急</el-radio>
            <el-radio :value="2">普通（慢慢安排）</el-radio>
            <el-radio :value="3">低</el-radio>
          </el-radio-group>
        </el-form-item>

        <!-- 投放类型字段 -->
        <template v-if="createForm.order_type === 'host_deploy'">
          <el-form-item label="需求类型">
            <el-select v-model="createForm.demand_type" placeholder="选择" style="width: 100%">
              <el-option label="ECM导出转到搬迁模块" value="ECM导出转到搬迁模块" />
              <el-option label="ECM-投放计算母机" value="ECM-投放计算母机" />
              <el-option label="TEZ-投放计算母机" value="TEZ-投放计算母机" />
              <el-option label="ECM-重装计算母机" value="ECM-重装计算母机" />
              <el-option label="TEZ-投放支撑母机" value="TEZ-投放支撑母机" />
              <el-option label="TEZ-重装支撑母机" value="TEZ-重装支撑母机" />
              <el-option label="TEZ-投放裸金属" value="TEZ-投放裸金属" />
              <el-option label="TEZ-下架导出" value="TEZ-下架导出" />
            </el-select>
          </el-form-item>
          <el-form-item label="固资号" required>
            <el-input v-model="createForm.asset_ids" type="textarea" :rows="4" placeholder="每行一个固资号" @blur="onAssetIdsBlur" />
          </el-form-item>
          <el-form-item v-if="assetLookupInfo" label="设备识别">
            <div class="asset-lookup-info">
              <el-tag v-for="(info, aid) in assetLookupInfo" :key="aid" :type="info ? 'success' : 'danger'" size="small" class="asset-tag">
                {{ aid }}: {{ info ? info.machine_type : '未识别' }}
              </el-tag>
            </div>
          </el-form-item>
          <el-form-item label="设备数量">
            <el-input-number v-model="createForm.device_count" :min="1" :max="100" />
          </el-form-item>
          <el-form-item label="设备类型/VS_Type">
            <el-input v-model="createForm.vs_type" placeholder="如 CG3-10G_LOCALDISK / Y0-MI32-25G_LOCALDISK" />
          </el-form-item>
          <el-form-item label="目标可用区">
            <el-select v-model="createForm.zone" placeholder="选择可用区" filterable style="width: 100%" @change="(v: string) => onZoneChange(v, 'zone')">
              <el-option v-for="z in zoneOptions" :key="z" :label="z" :value="z" />
            </el-select>
          </el-form-item>
          <el-form-item label="关联需求">
            <el-input v-model="createForm.related_demand" placeholder="如：客户补充资源需求" />
          </el-form-item>
          <el-form-item label="预期交付时间">
            <el-date-picker v-model="createForm.expected_date" type="date" placeholder="选择日期" style="width: 100%" />
          </el-form-item>
        </template>

        <!-- 搬迁类型字段 -->
        <template v-if="createForm.order_type === 'migration'">
          <el-form-item label="相关需求">
            <el-input v-model="createForm.related_demand" placeholder="如：优云、BIGO-补充资源" />
          </el-form-item>
          <el-form-item label="搬迁前可用区">
            <el-select v-model="createForm.source_zone" placeholder="选择来源可用区" filterable style="width: 100%" @change="(v: string) => onZoneChange(v, 'source_zone')">
              <el-option v-for="z in zoneOptions" :key="z" :label="z" :value="z" />
            </el-select>
          </el-form-item>
          <el-form-item label="搬迁前机房">
            <el-input v-model="createForm.source_idc" placeholder="选择可用区后自动填入" disabled />
          </el-form-item>
          <el-form-item label="目的可用区">
            <el-select v-model="createForm.zone" placeholder="选择目的可用区" filterable style="width: 100%" @change="(v: string) => onZoneChange(v, 'zone')">
              <el-option v-for="z in zoneOptions" :key="z" :label="z" :value="z" />
            </el-select>
          </el-form-item>
          <el-form-item label="目的机房">
            <el-input v-model="createForm.target_idc" placeholder="选择可用区后自动填入" disabled />
          </el-form-item>
          <!-- 空闲机位提示 -->
          <el-form-item v-if="freePositionInfo || checkingPositions" label="机位情况">
            <div v-if="checkingPositions" class="position-check">
              <el-icon class="is-loading"><Loading /></el-icon> 正在查询空闲机位...
            </div>
            <el-alert
              v-else-if="freePositionInfo"
              :title="freePositionInfo.message"
              :type="freePositionInfo.free_count === null ? 'warning' : (freePositionInfo.free_count > 0 ? 'success' : 'error')"
              show-icon
              :closable="false"
            />
          </el-form-item>
          <el-form-item label="搬迁数量">
            <el-input-number v-model="createForm.device_count" :min="1" :max="100" />
          </el-form-item>
          <el-form-item label="设备型号">
            <el-input v-model="createForm.vs_type" placeholder="如：Y0-MI32-25G / CG3-10G / BMD2i" />
          </el-form-item>
          <el-form-item label="固资号明细" required>
            <el-input v-model="createForm.asset_ids" type="textarea" :rows="4" placeholder="每行一个固资号" />
          </el-form-item>
          <el-form-item label="交付类型">
            <el-radio-group v-model="createForm.delivery_type">
              <el-radio value="TEZ">TEZ</el-radio>
              <el-radio value="ECM">ECM</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="重装需求">
            <el-select v-model="createForm.reinstall" placeholder="选择" style="width: 100%">
              <el-option label="需要安装 tlinux2.2-kvm3.0（TEZ）" value="tlinux2.2-kvm3.0_kernel-for_qcloud_test" />
              <el-option label="需要安装 tlinux release 2.2（ECM）" value="Tencent tlinux release 2.2 (tkernel3)" />
              <el-option label="不需要重装" value="none" />
            </el-select>
          </el-form-item>
          <el-form-item label="交付模块路径">
            <el-select v-model="createForm.module_path" placeholder="选择" style="width: 100%">
              <el-option label="[N][腾讯云边缘可用区]-[公有云]-[TEZ]-[线下资源][待上线]" value="[N][腾讯云边缘可用区] - [公有云] - [TEZ] - [线下资源][待上线]" />
              <el-option label="[腾讯云][边缘计算]-[边缘计算]-[OC]-[母机NODE][compute_未上线]" value="[腾讯云][边缘计算]-[边缘计算]-[OC]-[母机NODE][compute_未上线]" />
            </el-select>
          </el-form-item>
          <el-form-item label="预期交付时间">
            <el-date-picker v-model="createForm.expected_date" type="date" placeholder="选择日期" style="width: 100%" />
          </el-form-item>
        </template>

        <el-form-item label="备注">
          <el-input v-model="createForm.note" type="textarea" :rows="2" placeholder="其他说明（卡点/定制机位等）" />
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

        <!-- 工单详情字段 -->
        <div v-if="selectedOrder.detail && Object.keys(selectedOrder.detail).length" class="section">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <h4>工单内容</h4>
            <el-button v-if="!editingDetail" size="small" @click="startEditDetail">编辑</el-button>
            <div v-else>
              <el-button size="small" type="primary" @click="saveDetail" :loading="savingDetail">保存</el-button>
              <el-button size="small" @click="editingDetail = false">取消</el-button>
            </div>
          </div>

          <!-- 只读展示 -->
          <el-descriptions v-if="!editingDetail" :column="2" border size="small" style="margin-top:8px">
            <el-descriptions-item v-if="selectedOrder.detail.demand_type" label="需求类型">{{ selectedOrder.detail.demand_type }}</el-descriptions-item>
            <el-descriptions-item v-if="selectedOrder.detail.asset_ids" label="固资号">
              <pre style="margin:0;white-space:pre-wrap;font-size:12px">{{ selectedOrder.detail.asset_ids }}</pre>
            </el-descriptions-item>
            <el-descriptions-item v-if="selectedOrder.detail.device_count" label="设备数量">{{ selectedOrder.detail.device_count }}</el-descriptions-item>
            <el-descriptions-item v-if="selectedOrder.detail.vs_type" label="设备类型">{{ selectedOrder.detail.vs_type }}</el-descriptions-item>
            <el-descriptions-item v-if="selectedOrder.detail.zone" label="目标可用区">{{ selectedOrder.detail.zone }}</el-descriptions-item>
            <el-descriptions-item v-if="selectedOrder.detail.source_zone" label="搬迁前可用区">{{ selectedOrder.detail.source_zone }}</el-descriptions-item>
            <el-descriptions-item v-if="selectedOrder.detail.source_idc" label="搬迁前机房">{{ selectedOrder.detail.source_idc }}</el-descriptions-item>
            <el-descriptions-item v-if="selectedOrder.detail.target_idc" label="目的机房">{{ selectedOrder.detail.target_idc }}</el-descriptions-item>
            <el-descriptions-item v-if="selectedOrder.detail.delivery_type" label="交付类型">{{ selectedOrder.detail.delivery_type }}</el-descriptions-item>
            <el-descriptions-item v-if="selectedOrder.detail.expected_date" label="预期交付">{{ selectedOrder.detail.expected_date }}</el-descriptions-item>
            <el-descriptions-item v-if="selectedOrder.detail.related_demand" label="关联需求">{{ selectedOrder.detail.related_demand }}</el-descriptions-item>
            <el-descriptions-item v-if="selectedOrder.detail.reinstall" label="重装需求">{{ selectedOrder.detail.reinstall }}</el-descriptions-item>
          </el-descriptions>

          <!-- 编辑表单 -->
          <el-form v-else label-width="100px" size="small" style="margin-top:8px">
            <el-form-item v-if="selectedOrder.order_type === 'host_deploy'" label="需求类型">
              <el-input v-model="editDetail.demand_type" />
            </el-form-item>
            <el-form-item label="固资号">
              <el-input v-model="editDetail.asset_ids" type="textarea" :rows="3" />
            </el-form-item>
            <el-form-item label="设备数量">
              <el-input-number v-model="editDetail.device_count" :min="1" />
            </el-form-item>
            <el-form-item label="设备类型">
              <el-input v-model="editDetail.vs_type" />
            </el-form-item>
            <el-form-item label="目标可用区">
              <el-input v-model="editDetail.zone" />
            </el-form-item>
            <el-form-item v-if="selectedOrder.order_type === 'migration'" label="搬迁前可用区">
              <el-input v-model="editDetail.source_zone" />
            </el-form-item>
            <el-form-item v-if="selectedOrder.order_type === 'migration'" label="搬迁前机房">
              <el-input v-model="editDetail.source_idc" />
            </el-form-item>
            <el-form-item v-if="selectedOrder.order_type === 'migration'" label="目的机房">
              <el-input v-model="editDetail.target_idc" />
            </el-form-item>
            <el-form-item label="交付类型">
              <el-input v-model="editDetail.delivery_type" />
            </el-form-item>
            <el-form-item label="预期交付">
              <el-input v-model="editDetail.expected_date" placeholder="如 2026/6/5" />
            </el-form-item>
            <el-form-item label="关联需求">
              <el-input v-model="editDetail.related_demand" />
            </el-form-item>
          </el-form>
        </div>

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
import { Plus, CircleCheck, CircleClose, Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import {
  createOrder, listOrders, getOrderStats, getOrder, transitionOrder, deleteOrder,
  type OrderInfo, type StatsResponse
} from '@/api/workorders'

// ─── 常量映射 ───
const typeLabel: Record<string, string> = { host_deploy: '投放', migration: '搬迁' }
const typeTagMap: Record<string, string> = { host_deploy: 'success', migration: 'warning' }
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
const createForm = ref({
  order_type: '',
  title: '',
  priority: 2,
  // 通用
  asset_ids: '',
  zone: '',
  note: '',
  // 投放
  demand_type: '',
  device_count: 1,
  vs_type: '',
  related_demand: '',
  expected_date: '',
  // 搬迁
  source_zone: '',
  source_idc: '',
  target_idc: '',
  delivery_type: 'TEZ',
  reinstall: '',
  module_path: '',
  // 维修
  fault_desc: '',
})

const showDetailDialog = ref(false)
const selectedOrder = ref<OrderInfo | null>(null)
const editingDetail = ref(false)
const savingDetail = ref(false)
const editDetail = ref<Record<string, any>>({})

function startEditDetail() {
  editDetail.value = { ...(selectedOrder.value?.detail || {}) }
  editingDetail.value = true
}

async function saveDetail() {
  if (!selectedOrder.value) return
  savingDetail.value = true
  try {
    const resp = await fetch(`/api/v1/workorders/${selectedOrder.value.id}/detail`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ detail: editDetail.value })
    })
    if (resp.ok) {
      selectedOrder.value.detail = { ...editDetail.value }
      editingDetail.value = false
      ElMessage.success('保存成功')
    } else {
      ElMessage.error('保存失败')
    }
  } catch {
    ElMessage.error('保存失败')
  } finally {
    savingDetail.value = false
  }
}

// 可用区下拉选项（从后端 API 加载）
const zoneOptions = ref<string[]>([])
const zoneIdcMapping = ref<Record<string, string>>({})

async function loadZones() {
  try {
    const resp = await fetch('/api/v1/zones')
    if (resp.ok) {
      const data = await resp.json()
      zoneOptions.value = data.zones || []
      zoneIdcMapping.value = data.mapping || {}
    }
  } catch {}
}

// zone 选择联动机房 + 查空闲机位
const freePositionInfo = ref<{zone: string; idc: string; free_count: number | null; message: string} | null>(null)
const checkingPositions = ref(false)

function onZoneChange(zone: string, field: 'zone' | 'source_zone') {
  if (field === 'zone') {
    createForm.value.zone = zone
    const idc = zoneIdcMapping.value[zone]
    if (idc) createForm.value.target_idc = idc
    // 搬迁单选了目的可用区 → 自动查空闲机位
    if (createForm.value.order_type === 'migration') {
      checkFreePositions(zone)
    }
  } else {
    createForm.value.source_zone = zone
    const idc = zoneIdcMapping.value[zone]
    if (idc) createForm.value.source_idc = idc
  }
}

async function checkFreePositions(zone: string) {
  checkingPositions.value = true
  freePositionInfo.value = null
  try {
    const resp = await fetch(`/api/v1/zones/${encodeURIComponent(zone)}/free_positions`)
    if (resp.ok) {
      freePositionInfo.value = await resp.json()
    }
  } catch {} finally {
    checkingPositions.value = false
  }
}

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
  const f = createForm.value
  if (!f.order_type || !f.title) {
    ElMessage.warning('请填写工单类型和标题')
    return
  }

  // 固资号校验
  if (f.asset_ids) {
    const lines = f.asset_ids.split('\n').map(l => l.trim()).filter(l => l)
    const invalidAssets = lines.filter(l => !/^TYSV[0-9A-Z]{6,}$/i.test(l))
    if (invalidAssets.length > 0) {
      ElMessage.error(`固资号格式错误（需 TYSV 开头）: ${invalidAssets.slice(0, 3).join(', ')}`)
      return
    }
    // 数量校验
    if (f.device_count && f.device_count !== lines.length) {
      ElMessage.warning(`设备数量(${f.device_count})与固资号行数(${lines.length})不一致，已自动修正`)
      f.device_count = lines.length
    }
  } else if (['host_deploy', 'migration'].includes(f.order_type)) {
    ElMessage.warning('请填写固资号')
    return
  }

  // 可用区校验（搬迁/投放必填）
  if (f.order_type === 'host_deploy' && !f.zone) {
    ElMessage.warning('请选择目标可用区')
    return
  }
  if (f.order_type === 'migration') {
    if (!f.source_zone) { ElMessage.warning('请填写搬迁前可用区'); return }
    if (!f.zone) { ElMessage.warning('请填写目的可用区'); return }
    if (f.source_zone === f.zone) { ElMessage.error('来源和目的可用区不能相同'); return }
  }

  creating.value = true
  try {
    const f = createForm.value
    await createOrder({
      order_type: f.order_type,
      title: f.title,
      creator: 'current_user',
      detail: {
        asset_ids: f.asset_ids,
        zone: f.zone,
        demand_type: f.demand_type,
        device_count: f.device_count,
        vs_type: f.vs_type,
        related_demand: f.related_demand,
        expected_date: f.expected_date,
        source_zone: f.source_zone,
        source_idc: f.source_idc,
        target_idc: f.target_idc,
        delivery_type: f.delivery_type,
        reinstall: f.reinstall,
        module_path: f.module_path,
        fault_desc: f.fault_desc,
      },
      note: f.note,
      priority: f.priority,
    })
    ElMessage.success('工单创建成功，正在后台同步到OnePage')
    showCreateDialog.value = false
    createForm.value = { order_type: '', title: '', priority: 2, asset_ids: '', zone: '', note: '', demand_type: '', device_count: 1, vs_type: '', related_demand: '', expected_date: '', source_zone: '', source_idc: '', target_idc: '', delivery_type: 'TEZ', reinstall: '', module_path: '', fault_desc: '' }
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

async function handleDelete(row: OrderInfo) {
  try {
    await deleteOrder(row.id)
    ElMessage.success('工单已删除')
    await loadOrders()
    await loadStats()
  } catch {}
}

// ─── 固资号自动查设备型号 ───
const assetLookupInfo = ref<Record<string, {ip: string; machine_type: string; zone: string} | null> | null>(null)

async function onAssetIdsBlur() {
  const raw = createForm.value.asset_ids.trim()
  if (!raw) { assetLookupInfo.value = null; return }

  const lines = raw.split('\n').map(l => l.trim()).filter(l => /^TYSV/i.test(l))
  if (!lines.length) { assetLookupInfo.value = null; return }

  try {
    const resp = await fetch('/api/v1/hosts/lookup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ asset_ids: lines }),
    })
    if (resp.ok) {
      const data = await resp.json()
      assetLookupInfo.value = data.results
      // 自动回填设备型号（取第一个有效的）
      const types = Object.values(data.results).filter((v: any) => v?.machine_type).map((v: any) => v.machine_type)
      if (types.length && !createForm.value.vs_type) {
        const unique = [...new Set(types)]
        createForm.value.vs_type = unique.join(' / ')
      }
      // 自动修正数量
      createForm.value.device_count = lines.length
    }
  } catch {}
}

function formatTime(t: string) {
  if (!t) return '-'
  return t.replace('T', ' ').slice(0, 16)
}

// ─── 生命周期 ───
onMounted(() => { loadStats(); loadOrders(); loadZones() })
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

.asset-lookup-info { display: flex; flex-wrap: wrap; gap: 6px; }
.asset-tag { font-family: monospace; }
</style>
