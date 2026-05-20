<template>
  <div class="batch-table">
    <div class="batch-table__toolbar">
      <span class="batch-table__count"
        >共 <b>{{ items.length }}</b> 项 · 已选 <b>{{ selectedAssetIds.length }}</b></span
      >
      <el-button
        type="primary"
        :icon="Download"
        :disabled="!selectedAssetIds.length"
        @click="emit('export', selectedAssetIds)"
      >
        导出选中
      </el-button>
    </div>
    <el-table
      :data="items"
      border
      stripe
      size="small"
      max-height="540"
      @selection-change="onSelectionChange"
    >
      <el-table-column type="selection" width="44" :selectable="(row: BatchSearchItem) => row.success" />
      <el-table-column prop="query" label="查询输入" width="160">
        <template #default="{ row }">
          <span class="batch-table__mono">{{ row.query }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="query_type" label="类型" width="90">
        <template #default="{ row }">
          <el-tag size="small" effect="plain">{{ row.query_type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="结果" width="80">
        <template #default="{ row }">
          <el-tag size="small" :type="row.success ? 'success' : 'danger'" effect="dark">
            {{ row.success ? 'OK' : 'FAIL' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="固资号" width="160">
        <template #default="{ row }">
          <span class="batch-table__mono">{{ row.data?.asset_id || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="IP" width="140">
        <template #default="{ row }">
          <span class="batch-table__mono">{{ row.data?.ip || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="Zone" width="140">
        <template #default="{ row }">{{ row.data?.zone || '-' }}</template>
      </el-table-column>
      <el-table-column label="机型" width="140">
        <template #default="{ row }">{{ row.data?.machine_type || '-' }}</template>
      </el-table-column>
      <el-table-column label="客户" width="160">
        <template #default="{ row }">{{ row.data?.customer || '-' }}</template>
      </el-table-column>
      <el-table-column label="负责人" width="120">
        <template #default="{ row }">{{ row.data?.owner || '-' }}</template>
      </el-table-column>
      <el-table-column label="错误" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.error" class="batch-table__error">{{ row.error }}</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Download } from '@element-plus/icons-vue'
import type { BatchSearchItem } from '@/types/host'

defineProps<{
  items: BatchSearchItem[]
}>()

const emit = defineEmits<{
  (e: 'export', assetIds: string[]): void
}>()

const selectedRows = ref<BatchSearchItem[]>([])

const selectedAssetIds = computed<string[]>(() =>
  selectedRows.value
    .map((r) => r.data?.asset_id)
    .filter((x): x is string => Boolean(x)),
)

function onSelectionChange(rows: BatchSearchItem[]) {
  selectedRows.value = rows
}
</script>

<style scoped>
.batch-table__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 0 10px;
}

.batch-table__count {
  color: var(--tez-text-regular);
  font-size: 13px;
}

.batch-table__mono {
  font-family: ui-monospace, 'SF Mono', Menlo, Monaco, Consolas, monospace;
}

.batch-table__error {
  color: var(--tez-danger);
}
</style>
