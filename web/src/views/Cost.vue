<template>
  <div class="cost-page">
    <h2>机型成本一览</h2>
    <div class="cost-toolbar">
      <el-radio-group v-model="filter" size="default">
        <el-radio-button value="expired">过保机型</el-radio-button>
        <el-radio-button value="normal">正常机型</el-radio-button>
        <el-radio-button value="all">全部</el-radio-button>
      </el-radio-group>
      <span class="cost-toolbar__count">共 {{ filteredData.length }} 条</span>
    </div>

    <el-table :data="filteredData" border stripe size="small" style="width: 100%" max-height="calc(100vh - 220px)">
      <el-table-column prop="model" label="型号" width="150" fixed />
      <el-table-column prop="physical_machine" label="物理机" width="180">
        <template #default="{ row }">
          <span>{{ row.physical_machine }}</span>
          <el-tag v-if="isExpired(row)" type="warning" size="small" style="margin-left: 6px">过保</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="machine_cost" label="物理机成本" width="100" align="right">
        <template #default="{ row }">{{ row.machine_cost || '-' }}</template>
      </el-table-column>
      <el-table-column prop="rack_power" label="机位+电费" width="90" align="right" />
      <el-table-column prop="ops_cost" label="运营成本(6%)" width="100" align="right" />
      <el-table-column prop="total_excl_tax" label="总成本(不含税)" width="120" align="right" />
      <el-table-column prop="total_incl_tax" label="总成本(含税)" width="110" align="right" />
      <el-table-column prop="list_price" label="刊例价" width="100" align="right" />
      <el-table-column prop="sell_price_5g" label="售卖价(一台5G)" width="120" align="right">
        <template #default="{ row }">{{ row.sell_price_5g || '-' }}</template>
      </el-table-column>
      <el-table-column prop="cost_ratio_sell" label="成本比例-竞价" width="110" align="right">
        <template #default="{ row }">
          <span :style="{ color: ratioColor(row.cost_ratio_sell, 5, 15) }">
            {{ row.cost_ratio_sell ? row.cost_ratio_sell + '%' : '-' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="cost_ratio_ondemand" label="成本比例-按量" width="110" align="right">
        <template #default="{ row }">
          <span :style="{ color: ratioColor(row.cost_ratio_ondemand, 5, 15) }">
            {{ row.cost_ratio_ondemand ? row.cost_ratio_ondemand + '%' : '-' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="cost_ratio_monthly" label="成本比例-包月" width="110" align="right">
        <template #default="{ row }">
          <span :style="{ color: row.cost_ratio_monthly && row.cost_ratio_monthly > 30 ? '#e6a23c' : '#303133' }">
            {{ row.cost_ratio_monthly ? row.cost_ratio_monthly + '%' : '-' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="note" label="备注" min-width="100" />
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import apiClient from '@/api/client'

interface CostItem {
  model: string
  physical_machine: string
  machine_cost: number
  rack_power: number
  ops_cost: number
  total_excl_tax: number
  total_incl_tax: number
  list_price: number
  sell_price_5g: number | null
  cost_ratio_sell: number | null
  cost_ratio_ondemand: number | null
  cost_ratio_monthly: number | null
  note: string
}

const costData = ref<CostItem[]>([])
const filter = ref<'expired' | 'normal' | 'all'>('expired')

function isExpired(row: CostItem): boolean {
  return row.physical_machine.includes('过保')
}

const filteredData = computed(() => {
  if (filter.value === 'expired') return costData.value.filter(isExpired)
  if (filter.value === 'normal') return costData.value.filter((r) => !isExpired(r))
  return costData.value
})

function ratioColor(value: number | null, low: number, high: number): string {
  if (!value) return '#303133'
  if (value < low) return '#67c23a'
  if (value > high) return '#e6a23c'
  return '#303133'
}

onMounted(async () => {
  try {
    const resp = await apiClient.get('/api/v1/cost/machines')
    costData.value = resp.data.items || []
  } catch {
    // handled by interceptor
  }
})
</script>

<style scoped>
.cost-page {
  padding: 24px;
}

.cost-page h2 {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 16px;
}

.cost-toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.cost-toolbar__count {
  font-size: 13px;
  color: var(--tez-text-muted);
}
</style>
