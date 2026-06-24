<template>
  <div class="yunxiao-browse">
    <div class="yunxiao-browse__header">
      <div>
        <h2>云霄数据</h2>
        <p class="yunxiao-browse__subtitle">母机管理 · 新机型库存 · 历史趋势</p>
      </div>
      <el-button type="primary" :loading="syncing" :icon="Refresh" @click="onSync">
        全量同步
      </el-button>
    </div>

    <el-card shadow="never">
      <el-tabs v-model="activeTab">
        <!-- ──────── 母机管理 ──────── -->
        <el-tab-pane label="母机管理" name="hosts">
          <!-- 筛选栏 -->
          <div class="filter-bar">
            <el-select
              v-model="hostFilterZone"
              filterable
              clearable
              placeholder="选择可用区"
              style="width: 240px"
              @change="onHostQuery"
            >
              <el-option v-for="z in zoneOptions" :key="z" :label="z" :value="z" />
            </el-select>
            <el-select
              v-model="hostFilterType"
              filterable
              clearable
              placeholder="机型（可选）"
              style="width: 180px"
              @change="onHostQuery"
            >
              <el-option v-for="t in hostMachineTypes" :key="t" :label="t" :value="t" />
            </el-select>
            <el-input
              v-model="hostKeyword"
              placeholder="按固资号/IP 精确搜索"
              clearable
              style="width: 280px"
              @keyup.enter="onHostSearch"
            >
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-button type="primary" :loading="hostLoading" :icon="Search" @click="onHostSearch">
              搜索
            </el-button>
            <el-button :loading="hostLoading" @click="onHostQuery">查询全部</el-button>
            <span v-if="hostItems.length" class="result-hint">共 {{ hostTotal }} 条</span>
          </div>

          <div v-if="hostLoading" v-loading="hostLoading" style="min-height: 200px" />
          <el-empty v-else-if="hostSearched && !hostItems.length" description="未找到母机数据" :image-size="60" />

          <el-table
            v-else-if="hostItems.length"
            :data="hostItems"
            stripe
            border
            size="small"
            max-height="600"
            style="margin-top: 12px"
          >
            <el-table-column prop="asset_id" label="固资号" width="140" fixed />
            <el-table-column prop="ip" label="IP" width="130" />
            <el-table-column prop="zone" label="可用区" width="200" show-overflow-tooltip />
            <el-table-column prop="machine_model" label="机型" width="120" />
            <el-table-column prop="online_status" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.online_status === 'online' ? 'success' : 'danger'" size="small">
                  {{ row.online_status || '-' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="health_score" label="健康分" width="80" align="center" />
            <el-table-column label="CPU" width="120">
              <template #default="{ row }">
                <span v-if="row.cpu_total">
                  {{ row.cpu_available ?? '-' }} / {{ row.cpu_total }}
                  <span style="color:#909399; font-size:11px">核</span>
                </span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="内存" width="120">
              <template #default="{ row }">
                <span v-if="row.mem_total">
                  {{ row.mem_available ?? '-' }} / {{ row.mem_total }}
                  <span style="color:#909399; font-size:11px">G</span>
                </span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="instance_family" label="实例族" width="100" />
            <el-table-column prop="pool" label="资源池" width="90" />
            <el-table-column prop="is_empty_host" label="空母机" width="80" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.is_empty_host === '是' ? 'success' : 'info'">
                  {{ row.is_empty_host }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="is_cdh" label="CDH" width="70" align="center" />
            <el-table-column prop="exclusive_owner" label="独占Owner" width="130" show-overflow-tooltip />
            <el-table-column prop="kernel_version" label="内核版本" width="120" show-overflow-tooltip />
            <el-table-column prop="host_updated_at" label="更新时间" width="150">
              <template #default="{ row }">
                {{ formatTime(row.host_updated_at) }}
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- ──────── 库存查询 ──────── -->
        <el-tab-pane label="库存查询" name="inventory">
          <div class="filter-bar">
            <el-select
              v-model="invFilterZone"
              filterable
              clearable
              placeholder="选择可用区"
              style="width: 240px"
              @change="onInvQuery"
            >
              <el-option v-for="z in zoneOptions" :key="z" :label="z" :value="z" />
            </el-select>
            <el-select
              v-model="invFilterFamily"
              filterable
              clearable
              placeholder="实例族（可选）"
              style="width: 180px"
              @change="onInvQuery"
            >
              <el-option v-for="f in invFamilies" :key="f" :label="f" :value="f" />
            </el-select>
            <el-button type="primary" :loading="invLoading" @click="onInvQuery">查询</el-button>
            <span v-if="invItems.length" class="result-hint">共 {{ invTotal }} 条</span>
          </div>

          <div v-if="invLoading" v-loading="invLoading" style="min-height: 200px" />
          <el-empty v-else-if="invSearched && !invItems.length" description="未找到库存数据" :image-size="60" />

          <el-table
            v-else-if="invItems.length"
            :data="invItems"
            stripe
            border
            size="small"
            max-height="600"
            style="margin-top: 12px"
          >
            <el-table-column prop="zone" label="可用区" width="200" show-overflow-tooltip />
            <el-table-column prop="instance_type" label="实例类型" width="170" />
            <el-table-column prop="instance_family" label="实例族" width="120" />
            <el-table-column prop="pool" label="资源池" width="120" />
            <el-table-column prop="billing_type" label="计费" width="80" />
            <el-table-column prop="inventory" label="库存" width="70" align="center">
              <template #default="{ row }">
                <span
                  :style="{
                    color: (row.inventory ?? 0) <= (row.inventory_threshold ?? 0) ? '#f56c6c' : '#67c23a',
                    fontWeight: 'bold',
                  }"
                >{{ row.inventory ?? '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="inventory_threshold" label="阈值" width="70" align="center" />
            <el-table-column prop="safety_quota" label="安全配额" width="90" align="center" />
            <el-table-column prop="cpu" label="CPU" width="70" align="center" />
            <el-table-column prop="mem" label="内存(G)" width="80" align="center" />
            <el-table-column prop="gpu" label="GPU" width="70" align="center" />
            <el-table-column prop="device_type" label="设备类型" min-width="120" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="80" />
          </el-table>
        </el-tab-pane>

        <!-- ──────── 历史趋势 ──────── -->
        <el-tab-pane label="历史趋势" name="history">
          <div class="filter-bar">
            <el-select
              v-model="historyZone"
              filterable
              clearable
              placeholder="选择可用区（空=全部）"
              style="width: 240px"
              @change="onHistoryQuery"
            >
              <el-option v-for="z in zoneOptions" :key="z" :label="z" :value="z" />
            </el-select>
            <el-button type="primary" :loading="historyLoading" @click="onHistoryQuery">查询</el-button>
            <span v-if="historyData.length" class="result-hint">共 {{ historyData.length }} 条记录</span>
          </div>

          <div v-if="historyLoading" v-loading="historyLoading" style="min-height: 300px" />
          <el-empty v-else-if="historySearched && !historyData.length" description="暂无历史快照" :image-size="60" />

          <!-- 趋势折线图（简单 canvas 实现） -->
          <div v-else-if="historyChartVisible" class="chart-container">
            <div class="chart-title">母机数量趋势</div>
            <canvas ref="historyCanvas" width="900" height="300" style="width: 100%; max-width: 900px" />
            <div class="chart-legend">
              <span class="chart-legend__item chart-legend__item--total">总量</span>
              <span class="chart-legend__item chart-legend__item--online">在线</span>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { Search, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import {
  queryHostMachines,
  queryInventory,
  searchHostMachine,
  syncYunxiao,
  getHostHistory,
} from '@/api/yunxiao'
import type { HostMachineItem, InventoryItem } from '@/types/yunxiao'
import { formatTime } from '@/utils/formatters'
import { listZonesWithArch } from '@/api/hosts'

// ─── 路由 Tab ───
const activeTab = ref('hosts')

// ─── 可用区选项 ───
const zoneOptions = ref<string[]>([])
const invFamilies = ref<string[]>([])

onMounted(async () => {
  try {
    const zones = await listZonesWithArch()
    zoneOptions.value = zones.map((z) => z.zone)
  } catch {
    zoneOptions.value = []
  }
})

// ─── 全量同步 ───
const syncing = ref(false)
async function onSync() {
  syncing.value = true
  try {
    const { data } = await syncYunxiao()
    if (data.skipped) {
      ElMessage.warning('同步已跳过（当前模式不支持或无需同步）')
    } else {
      const h = data.hosts ?? 0
      const i = data.inventory ?? 0
      ElMessage.success(`同步完成：母机 ${h} 条，库存 ${i} 条，${data.zones_done} 个可用区`)
    }
  } catch {
    ElMessage.error('同步失败')
  } finally {
    syncing.value = false
  }
}

// ─── 母机管理 ───
const hostFilterZone = ref('')
const hostFilterType = ref('')
const hostKeyword = ref('')
const hostLoading = ref(false)
const hostItems = ref<HostMachineItem[]>([])
const hostTotal = ref(0)
const hostSearched = ref(false)
const hostMachineTypes = ref<string[]>([])

async function onHostQuery() {
  hostLoading.value = true
  hostKeyword.value = ''
  hostSearched.value = true
  try {
    const { data } = await queryHostMachines({
      zone: hostFilterZone.value || undefined,
      machine_type: hostFilterType.value || undefined,
    })
    hostItems.value = (data.items ?? []) as HostMachineItem[]
    hostTotal.value = data.total
    // 提取机型列表（去重）
    const types = new Set<string>()
    for (const h of hostItems.value) {
      if (h.machine_model) types.add(h.machine_model)
    }
    hostMachineTypes.value = [...types].sort()
  } catch {
    hostItems.value = []
    hostTotal.value = 0
    ElMessage.error('母机查询失败')
  } finally {
    hostLoading.value = false
  }
}

async function onHostSearch() {
  const kw = hostKeyword.value.trim()
  if (!kw) {
    await onHostQuery()
    return
  }
  hostLoading.value = true
  hostSearched.value = true
  try {
    const { data } = await searchHostMachine(kw)
    hostItems.value = (data.items ?? []) as HostMachineItem[]
    hostTotal.value = data.total
  } catch {
    hostItems.value = []
    hostTotal.value = 0
    ElMessage.error('搜索失败')
  } finally {
    hostLoading.value = false
  }
}

// ─── 库存查询 ───
const invFilterZone = ref('')
const invFilterFamily = ref('')
const invLoading = ref(false)
const invItems = ref<InventoryItem[]>([])
const invTotal = ref(0)
const invSearched = ref(false)

async function onInvQuery() {
  invLoading.value = true
  invSearched.value = true
  try {
    const { data } = await queryInventory({
      zone: invFilterZone.value || undefined,
      instance_family: invFilterFamily.value || undefined,
    })
    invItems.value = (data.items ?? []) as InventoryItem[]
    invTotal.value = data.total
    // 提取实例族列表
    const families = new Set<string>()
    for (const i of invItems.value) {
      if (i.instance_family) families.add(i.instance_family)
    }
    invFamilies.value = [...families].sort()
  } catch {
    invItems.value = []
    invTotal.value = 0
    ElMessage.error('库存查询失败')
  } finally {
    invLoading.value = false
  }
}

// ─── 历史趋势 ───
const historyZone = ref('')
const historyLoading = ref(false)
const historyData = ref<any[]>([])
const historySearched = ref(false)
const historyCanvas = ref<HTMLCanvasElement | null>(null)

const historyChartVisible = computed(() => historyData.value.length > 0)

function drawHistoryChart() {
  const canvas = historyCanvas.value
  if (!canvas || !historyData.value.length) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  // 数据：按 snapshot_time 分组统计总量和在线量
  const timeMap = new Map<
    string,
    { total: number; online: number }
  >()
  for (const h of historyData.value) {
    const t = h.snapshot_time?.slice(0, 16) || '未知'
    const entry = timeMap.get(t) || { total: 0, online: 0 }
    entry.total++
    if (h.online_status === 'online') entry.online++
    timeMap.set(t, entry)
  }
  const times = [...timeMap.keys()].sort()
  if (times.length < 2) {
    ctx.fillStyle = '#909399'
    ctx.font = '14px sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText('数据点不足，需至少两次快照才能绘制趋势', canvas.width / 2, canvas.height / 2)
    return
  }

  const totals = times.map((t) => timeMap.get(t)!.total)
  const onlines = times.map((t) => timeMap.get(t)!.online)
  const maxVal = Math.max(...totals) * 1.15 || 1

  const pad = { top: 20, right: 30, bottom: 50, left: 55 }
  const w = canvas.width - pad.left - pad.right
  const h = canvas.height - pad.top - pad.bottom

  ctx.clearRect(0, 0, canvas.width, canvas.height)

  // 网格
  ctx.strokeStyle = '#f0f0f0'
  ctx.lineWidth = 1
  for (let i = 0; i <= 4; i++) {
    const y = pad.top + (h / 4) * i
    ctx.beginPath()
    ctx.moveTo(pad.left, y)
    ctx.lineTo(pad.left + w, y)
    ctx.stroke()
  }

  // Y 轴刻度
  ctx.fillStyle = '#909399'
  ctx.font = '11px sans-serif'
  ctx.textAlign = 'right'
  for (let i = 0; i <= 4; i++) {
    const val = Math.round(maxVal - (maxVal / 4) * i)
    const y = pad.top + (h / 4) * i
    ctx.fillText(String(val), pad.left - 6, y + 4)
  }

  // X 轴刻度（最多显示 10 个）
  const xStep = Math.max(1, Math.floor(times.length / 10))
  ctx.textAlign = 'center'
  times.forEach((t, i) => {
    if (i % xStep !== 0 && i !== times.length - 1) return
    const x = pad.left + (w / (times.length - 1)) * i
    ctx.fillText(t.slice(5), x, pad.top + h + 16)
  })

  // 折线
  function drawLine(data: number[], color: string) {
    ctx.strokeStyle = color
    ctx.lineWidth = 2
    ctx.beginPath()
    data.forEach((val, i) => {
      const x = pad.left + (w / (data.length - 1)) * i
      const y = pad.top + h - (val / maxVal) * h
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })
    ctx.stroke()

    // 端点圆点
    data.forEach((val, i) => {
      const x = pad.left + (w / (data.length - 1)) * i
      const y = pad.top + h - (val / maxVal) * h
      ctx.fillStyle = color
      ctx.beginPath()
      ctx.arc(x, y, 3, 0, Math.PI * 2)
      ctx.fill()
    })
  }

  drawLine(totals, '#409eff')
  drawLine(onlines, '#67c23a')
}

watch(historyData, () => {
  if (historyChartVisible.value) {
    nextTick(() => drawHistoryChart())
  }
})

async function onHistoryQuery() {
  historyLoading.value = true
  historySearched.value = true
  try {
    const { data } = await getHostHistory(historyZone.value || undefined, 200)
    historyData.value = data.items || []
  } catch {
    historyData.value = []
    ElMessage.error('历史查询失败')
  } finally {
    historyLoading.value = false
  }
}
</script>

<style scoped>
.yunxiao-browse {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px;
}

.yunxiao-browse__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.yunxiao-browse__header h2 {
  margin: 0 0 4px 0;
  font-size: 22px;
  font-weight: 700;
  color: var(--tez-text-primary);
}

.yunxiao-browse__subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--tez-text-muted);
}

/* ─── 筛选栏 ─── */
.filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.result-hint {
  font-size: 13px;
  color: var(--tez-text-muted);
  margin-left: 8px;
}

/* ─── 图表 ─── */
.chart-container {
  margin-top: 16px;
  padding: 16px;
  background: #fafbfc;
  border-radius: var(--tez-radius);
  border: 1px solid var(--tez-border);
}

.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--tez-text-primary);
  margin-bottom: 12px;
}

.chart-legend {
  display: flex;
  gap: 20px;
  justify-content: center;
  margin-top: 8px;
}

.chart-legend__item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #606266;
}

.chart-legend__item::before {
  content: '';
  display: inline-block;
  width: 14px;
  height: 3px;
  border-radius: 2px;
}

.chart-legend__item--total::before {
  background: #409eff;
}

.chart-legend__item--online::before {
  background: #67c23a;
}
</style>
