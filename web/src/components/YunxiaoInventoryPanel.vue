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
        <el-option label="S1" value="S1" />
        <el-option label="S5" value="S5" />
        <el-option label="SN3ne" value="SN3ne" />
        <el-option label="IT5" value="IT5" />
        <el-option label="IT3" value="IT3" />
      </el-select>
      <el-select
        v-model="filterInstanceType"
        filterable
        clearable
        size="large"
        placeholder="实例类型"
        style="width: 160px; margin-left: 12px"
      >
        <el-option label="S1.MEDIUM2" value="S1.MEDIUM2" />
        <el-option label="S5.MEDIUM2" value="S5.MEDIUM2" />
        <el-option label="SN3ne.MEDIUM2" value="SN3ne.MEDIUM2" />
        <el-option label="IT5.MEDIUM2" value="IT5.MEDIUM2" />
        <el-option label="IT3.MEDIUM2" value="IT3.MEDIUM2" />
      </el-select>
      <el-button
        type="primary"
        size="large"
        :loading="loading"
        :icon="Search"
        style="margin-left: 12px"
        @click="doQuery"
      >
        查询库存
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

    <div
      v-if="!queried && !loading"
      style="margin-top: 24px; text-align: center; color: #909399"
    >
      <el-icon :size="32" style="margin-bottom: 8px"><Search /></el-icon>
      <p>选择可用区/实例族/实例类型后，点击「查询库存」获取云霄平台数据</p>
    </div>
    <el-empty
      v-else-if="queried && !loading && items.length === 0"
      description="无数据"
    />

    <el-table
      v-if="items.length > 0"
      :data="items"
      stripe
      border
      size="small"
      max-height="500"
      style="margin-top: 12px"
    >
      <el-table-column prop="zone" label="可用区" width="110" fixed />
      <el-table-column prop="instance_family" label="实例族" width="90" />
      <el-table-column prop="instance_type" label="实例类型" width="130" />
      <el-table-column prop="status" label="状态" width="80" />
      <el-table-column prop="pool" label="资源池" width="120" />
      <el-table-column prop="billing_type" label="计费类型" width="90" />
      <el-table-column prop="inventory" label="库存" width="80" />
      <el-table-column prop="inventory_threshold" label="库存阈值" width="90" />
      <el-table-column prop="safety_quota" label="安全配额" width="90" />
      <el-table-column prop="cpu" label="CPU" width="70" />
      <el-table-column prop="gpu" label="GPU" width="70" />
      <el-table-column prop="storage_block" label="存储块" width="80" />
      <el-table-column prop="mem" label="内存" width="80" />
      <el-table-column prop="device_type" label="设备类型" width="100" />
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { queryInventory } from '@/api/yunxiao'
import type { InventoryItem } from '@/types/yunxiao'
import { listZones } from '@/api/hosts'

const filterZone = ref('')
const filterFamily = ref('')
const filterInstanceType = ref('')
const loading = ref(false)
const queried = ref(false)
const items = ref<InventoryItem[]>([])
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
    const res = await queryInventory({
      zone: filterZone.value || undefined,
      instance_family: filterFamily.value || undefined,
      instance_type: filterInstanceType.value || undefined,
    })
    items.value = (res.data?.items ?? []) as InventoryItem[]
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
