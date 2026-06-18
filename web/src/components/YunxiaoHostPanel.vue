<template>
  <div class="yunxiao-panel">
    <div class="yunxiao-panel__bar">
      <el-select
        v-model="filterZone"
        filterable
        clearable
        size="large"
        placeholder="可用区"
        style="width: 200px"
      >
        <el-option v-for="z in zoneList" :key="z" :label="z" :value="z" />
      </el-select>
      <el-select
        v-model="filterFamily"
        filterable
        clearable
        size="large"
        placeholder="实例族"
        style="width: 160px; margin-left: 12px"
      >
        <el-option label="S1" value="S1"/>
        <el-option label="S5" value="S5"/>
        <el-option label="SN3ne" value="SN3ne"/>
        <el-option label="IT5" value="IT5"/>
        <el-option label="IT3" value="IT3"/>
      </el-select>
      <el-select
        v-model="filterMachine"
        filterable
        clearable
        size="large"
        placeholder="机型"
        style="width: 160px; margin-left: 12px"
      >
        <el-option label="M10" value="M10"/>
        <el-option label="CG3-10G" value="CG3-10G"/>
        <el-option label="Y0-MI52-25G" value="Y0-MI52-25G"/>
      </el-select>
      <el-button
        type="primary"
        size="large"
        :loading="loading"
        :icon="Search"
        @click="doQuery"
        style="margin-left: 12px"
      >
        查询母机
      </el-button>
      <el-tag
        v-if="resultMode"
        type="info"
        size="small"
        effect="plain"
        style="margin-left: 12px"
      >
        {{ resultMode }}
      </el-tag>
    </div>

    <el-table
      v-if="items.length > 0"
      :data="items"
      stripe
      border
      size="small"
      max-height="500"
      style="margin-top: 12px"
    >
      <el-table-column prop="asset_id" label="固资号" width="140" fixed />
      <el-table-column prop="ip" label="IP" width="140" />
      <el-table-column prop="instance_family" label="实例族" width="70" />
      <el-table-column prop="device_type" label="设备类型" width="80" />
      <el-table-column prop="zone" label="可用区" width="110" />
      <el-table-column prop="machine_model" label="机型" width="80" />
      <el-table-column prop="online_status" label="在线状态" width="90">
        <template #default="{ row }">
          <el-tag
            :type="row.online_status === 'ONLINE' ? 'success' : 'warning'"
            size="small"
            effect="plain"
          >
            {{ row.online_status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="health_score" label="健康度" width="75" />
      <el-table-column label="可用/总CPU" width="120">
        <template #default="{ row }">
          {{ row.cpu_available ?? '-' }} / {{ row.cpu_total ?? '-' }}
        </template>
      </el-table-column>
      <el-table-column label="可用/总内存(G)" width="130">
        <template #default="{ row }">
          {{ row.mem_available ?? '-' }} / {{ row.mem_total ?? '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="is_empty_host" label="空母机" width="70" />
      <el-table-column prop="is_cdh" label="CDH" width="60" />
      <el-table-column prop="host_updated_at" label="更新时间" width="160" />
    </el-table>

    <div v-if="!queried && !loading" style="margin-top: 24px; text-align: center; color: #909399">
      <el-icon :size="32" style="margin-bottom: 8px"><Search /></el-icon>
      <p>选择可用区/实例族/机型后，点击「查询母机」获取云霄平台数据</p>
    </div>
    <el-empty v-else-if="queried && !loading && items.length === 0" description="无数据" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { queryHostMachines } from '@/api/yunxiao'
import type { HostMachineItem } from '@/types/yunxiao'
import { listZones } from '@/api/hosts'

const filterZone = ref('')
const filterFamily = ref('')
const filterMachine = ref('')
const loading = ref(false)
const queried = ref(false)
const items = ref<HostMachineItem[]>([])
const resultMode = ref('')
const zoneList = ref<string[]>([])

onMounted(async () => {
  try {
    const res: any = await listZones()
    const zones = res.data?.zones ?? res.data ?? []
    zoneList.value = Array.isArray(zones) ? zones : []
  } catch {
    // ignore
  }
})

async function doQuery() {
  loading.value = true
  queried.value = false
  try {
    const res = await queryHostMachines({
      zone: filterZone.value || undefined,
      instance_family: filterFamily.value || undefined,
      machine_type: filterMachine.value || undefined,
    })
    items.value = (res.data?.items ?? []) as HostMachineItem[]
    resultMode.value = res.data?.mode ?? ''
    queried.value = true
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '查询失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.yunxiao-panel__bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}
</style>
