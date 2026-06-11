<template>
  <div class="host-table">
    <div class="host-table__toolbar">
      <span class="host-table__count"
        >共 <b>{{ rows.length }}</b> 台 · 已选 <b>{{ selected.length }}</b></span
      >
      <el-button
        type="primary"
        :icon="Download"
        :disabled="!selected.length"
        @click="emit('export', selected)"
      >
        导出选中
      </el-button>
    </div>
    <el-table
      :data="rows"
      border
      stripe
      size="small"
      max-height="540"
      @selection-change="onSelectionChange"
    >
      <el-table-column type="selection" width="44" />
      <el-table-column prop="asset_id" label="固资号" width="160" fixed="left">
        <template #default="{ row }">
          <span class="host-table__mono">{{ row.asset_id }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="ip" label="IP" width="140">
        <template #default="{ row }">
          <span class="host-table__mono">{{ row.ip || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="zone" label="Zone" width="140" />
      <el-table-column prop="machine_type" label="机型" width="140" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="hostStatusType(row.status)" effect="plain">
            {{ row.status || '未知' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="idc" label="机房" width="160" />
      <el-table-column prop="customer" label="客户" width="160" />
      <el-table-column prop="owner" label="负责人" width="120" />
      <el-table-column prop="use_years" label="年限" width="80">
        <template #default="{ row }">
          {{ row.use_years != null ? `${row.use_years}` : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="module" label="模块" min-width="220" show-overflow-tooltip />
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Download } from '@element-plus/icons-vue'
import type { HostInfo } from '@/types/host'

defineProps<{
  rows: HostInfo[]
}>()

const emit = defineEmits<{
  (e: 'export', rows: HostInfo[]): void
}>()

const selected = ref<HostInfo[]>([])

function onSelectionChange(rows: HostInfo[]) {
  selected.value = rows
}

import { hostStatusType } from '@/utils/formatters'
</script>

<style scoped>
.host-table__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 0 10px;
}

.host-table__count {
  color: var(--tez-text-regular);
  font-size: 13px;
}

.host-table__mono {
  font-family: ui-monospace, 'SF Mono', Menlo, Monaco, Consolas, monospace;
}
</style>
