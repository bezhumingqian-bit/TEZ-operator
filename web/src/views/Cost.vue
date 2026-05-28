<template>
  <div class="cost-page">
    <h2>机型成本一览</h2>
    <p class="subtitle">TEZ 边缘可用区各机型月度运营成本及售价比例</p>

    <el-table :data="costData" border stripe size="small" style="width: 100%" max-height="calc(100vh - 200px)">
      <el-table-column prop="model" label="型号" width="150" fixed />
      <el-table-column prop="physical_machine" label="物理机" width="180" />
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
          <span :style="{ color: row.cost_ratio_sell && row.cost_ratio_sell < 5 ? '#67c23a' : row.cost_ratio_sell > 15 ? '#e6a23c' : '#303133' }">
            {{ row.cost_ratio_sell ? row.cost_ratio_sell + '%' : '-' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="cost_ratio_ondemand" label="成本比例-按量" width="110" align="right">
        <template #default="{ row }">
          <span :style="{ color: row.cost_ratio_ondemand && row.cost_ratio_ondemand < 5 ? '#67c23a' : row.cost_ratio_ondemand > 15 ? '#e6a23c' : '#303133' }">
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
import { ref, onMounted } from 'vue'

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

onMounted(async () => {
  try {
    const resp = await fetch('/api/v1/cost/machines')
    if (resp.ok) {
      const data = await resp.json()
      costData.value = data.items || []
    }
  } catch {}
})
</script>

<style scoped>
.cost-page {
  padding: 20px;
}
.subtitle {
  color: #909399;
  margin-bottom: 16px;
}
</style>
