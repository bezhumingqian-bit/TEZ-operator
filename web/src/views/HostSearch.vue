<template>
  <div class="tez-page host-search">
    <h2 class="tez-page__title">
      <el-icon><Search /></el-icon>
      <span>资源查询</span>
      <el-tag size="small" type="success" effect="plain">M1 · 模块 4</el-tag>
    </h2>

    <el-card shadow="never" class="host-search__panel">
      <el-tabs v-model="activeTab" class="host-search__tabs">
        <!-- ─────────── 单条查询 ─────────── -->
        <el-tab-pane label="单条查询" name="single">
          <div class="host-search__bar">
            <el-input
              v-model="singleQuery"
              size="large"
              clearable
              placeholder="输入固资号 / IP / Zone（如 TYSV00000001、10.0.0.5、zone_a）"
              :prefix-icon="Search"
              @keyup.enter="onSingleSearch"
            />
            <el-button
              type="primary"
              size="large"
              :loading="singleLoading"
              :icon="Search"
              @click="onSingleSearch"
            >
              查询
            </el-button>
          </div>
          <div class="host-search__hint">
            支持识别：固资号 <code>TYSV*</code>、IPv4、Zone <code>zone_*</code>
            / <code>ap-*-*-N</code>。Enter 直接搜索。
          </div>

          <!-- 最近查询 -->
          <div v-if="appStore.recentQueries.length" class="host-search__recent">
            <span class="host-search__recent-label">最近查询：</span>
            <el-tag
              v-for="r in appStore.recentQueries"
              :key="r.q + r.at"
              class="host-search__recent-item"
              effect="plain"
              @click="useRecent(r.q)"
            >
              {{ r.q }}
            </el-tag>
            <el-button text size="small" @click="appStore.clearRecentQueries">清空</el-button>
          </div>

          <!-- 结果展示 -->
          <div class="host-search__result">
            <el-skeleton v-if="singleLoading" :rows="6" animated />

            <template v-else>
              <!-- zone 类型：返回列表 -->
              <div v-if="singleZoneList && singleZoneList.length" class="host-search__zone-result">
                <el-alert
                  type="info"
                  :closable="false"
                  show-icon
                  :title="`识别为 Zone 查询，共找到 ${singleZoneList.length} 台母机`"
                  class="host-search__zone-alert"
                />
                <HostTable
                  :rows="singleZoneList"
                  @export="onTableExport"
                />
              </div>

              <!-- 单台主机 -->
              <HostCard v-else-if="singleHost" :host="singleHost" />

              <!-- 错误 -->
              <el-result
                v-else-if="singleError"
                icon="warning"
                :title="singleError"
                sub-title="请检查输入是否正确，或换一种方式查询"
              />

              <el-empty
                v-else
                description="输入固资号 / IP / Zone 后回车即可查询"
                class="host-search__empty"
              />
            </template>
          </div>
        </el-tab-pane>

        <!-- ─────────── 批量查询 ─────────── -->
        <el-tab-pane label="批量查询" name="batch">
          <div class="host-search__batch">
            <div class="host-search__batch-form">
              <el-input
                v-model="batchInput"
                type="textarea"
                :rows="8"
                placeholder="每行一个，固资号或 IP，最多 100 条
例：
TYSV00000001
TYSV00000002
10.0.0.5"
              />
              <div class="host-search__batch-toolbar">
                <span class="host-search__batch-count"
                  >已输入：<b>{{ batchQueries.length }}</b> / 100</span
                >
                <div>
                  <el-button @click="batchInput = ''">清空</el-button>
                  <el-button
                    type="primary"
                    :loading="batchLoading"
                    :icon="Search"
                    :disabled="!batchQueries.length"
                    @click="onBatchSearch"
                  >
                    批量查询
                  </el-button>
                </div>
              </div>
            </div>

            <div class="host-search__batch-result">
              <el-skeleton v-if="batchLoading" :rows="5" animated />
              <template v-else-if="batchResp">
                <div class="host-search__batch-summary">
                  <el-statistic title="总数" :value="batchResp.total" />
                  <el-statistic title="成功" :value="batchResp.success_count" />
                  <el-statistic
                    title="失败"
                    :value="batchResp.total - batchResp.success_count"
                    value-style="color: var(--tez-danger)"
                  />
                </div>
                <BatchTable :items="batchResp.items" @export="onBatchTableExport" />
              </template>
              <el-empty v-else description="批量结果将显示于此" />
            </div>
          </div>
        </el-tab-pane>

        <!-- ─────────── 按 Zone 列表 ─────────── -->
        <el-tab-pane label="按 Zone 列表" name="zone">
          <div class="host-search__bar">
            <el-select
              v-model="zoneSelected"
              filterable
              allow-create
              default-first-option
              size="large"
              placeholder="选择或输入 Zone（来自后端，失败时使用占位列表）"
              style="width: 360px"
            >
              <el-option v-for="z in zoneOptions" :key="z" :label="z" :value="z" />
            </el-select>
            <el-button
              type="primary"
              size="large"
              :loading="zoneLoading"
              :icon="Search"
              :disabled="!zoneSelected"
              @click="onZoneSearch"
            >
              查询
            </el-button>
          </div>
          <div class="host-search__hint">
            Zone 列表来自后端，失败时使用占位列表 <code>zone_a</code> / <code>zone_b</code> /
            <code>zone_c</code>。
          </div>

          <div class="host-search__result">
            <el-skeleton v-if="zoneLoading" :rows="6" animated />
            <template v-else-if="zoneResp">
              <el-alert
                :title="`Zone ${zoneResp.zone} 共 ${zoneResp.total} 台母机`"
                type="success"
                :closable="false"
                show-icon
                class="host-search__zone-alert"
              />
              <HostTable :rows="zoneResp.items" @export="onTableExport" />
            </template>
            <el-empty v-else description="选择一个 Zone 查询" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import HostCard from '@/components/HostCard.vue'
import HostTable from '@/components/HostTable.vue'
import BatchTable from '@/components/BatchTable.vue'
import { ApiError } from '@/api/client'
import {
  batchSearch,
  exportHostsExcel,
  listZoneHosts,
  listZones,
  pickSingleHost,
  searchHost,
} from '@/api/hosts'
import type { BatchSearchResponse, HostInfo, ZoneHostsResponse } from '@/types/host'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()
const activeTab = ref<'single' | 'batch' | 'zone'>('single')
const fallbackZoneOptions = ['zone_a', 'zone_b', 'zone_c']

// ─── 单条 ───
const singleQuery = ref('')
const singleLoading = ref(false)
const singleHost = ref<HostInfo | null>(null)
const singleZoneList = ref<HostInfo[] | null>(null)
const singleError = ref<string>('')

async function onSingleSearch() {
  const q = singleQuery.value.trim()
  if (!q) {
    ElMessage.warning('请输入查询内容')
    return
  }
  singleLoading.value = true
  singleHost.value = null
  singleZoneList.value = null
  singleError.value = ''
  try {
    const resp = await searchHost(q)
    appStore.pushRecentQuery(q)
    if (resp.query_type === 'zone') {
      singleZoneList.value = (Array.isArray(resp.data) ? resp.data : []) as HostInfo[]
    } else {
      const host = pickSingleHost(resp)
      if (host) singleHost.value = host
      else singleError.value = '未找到该资源'
    }
  } catch (e) {
    singleError.value = (e as Error).message || '查询失败'
  } finally {
    singleLoading.value = false
  }
}

function useRecent(q: string) {
  singleQuery.value = q
  onSingleSearch()
}

// ─── 批量 ───
const batchInput = ref('')
const batchLoading = ref(false)
const batchResp = ref<BatchSearchResponse | null>(null)

const batchQueries = computed<string[]>(() =>
  batchInput.value
    .split(/[\r\n,;\s]+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 100),
)

async function onBatchSearch() {
  if (!batchQueries.value.length) return
  if (batchQueries.value.length > 100) {
    ElMessage.warning('批量查询单次最多 100 条，已截断')
  }
  batchLoading.value = true
  batchResp.value = null
  try {
    batchResp.value = await batchSearch(batchQueries.value)
    ElMessage.success(`已查询 ${batchResp.value.total} 条，成功 ${batchResp.value.success_count}`)
  } finally {
    batchLoading.value = false
  }
}

// ─── Zone ───
const zoneOptions = ref<string[]>([...fallbackZoneOptions])
const zoneSelected = ref<string>('')
const zoneLoading = ref(false)
const zoneResp = ref<ZoneHostsResponse | null>(null)

async function loadZoneOptions() {
  try {
    const zones = await listZones()
    zoneOptions.value = zones.length ? zones : [...fallbackZoneOptions]
  } catch {
    zoneOptions.value = [...fallbackZoneOptions]
    ElMessage.warning('Zone 列表来自后端，失败时使用占位列表')
  }
}

async function onZoneSearch() {
  if (!zoneSelected.value) return
  zoneLoading.value = true
  zoneResp.value = null
  try {
    zoneResp.value = await listZoneHosts(zoneSelected.value)
  } finally {
    zoneLoading.value = false
  }
}

onMounted(() => {
  void loadZoneOptions()
})

// ─── 导出 ───
function formatExportError(error: unknown): string {
  if (error instanceof ApiError && error.status) {
    return `导出失败（HTTP ${error.status}），请稍后重试`
  }
  return '导出失败，请稍后重试'
}

async function onTableExport(rows: HostInfo[]) {
  if (!rows.length) {
    ElMessage.warning('请先勾选要导出的行')
    return
  }
  try {
    await exportHostsExcel(rows.map((r) => r.asset_id))
    ElMessage.success('已触发导出')
  } catch (error) {
    ElMessage.warning(formatExportError(error))
  }
}

async function onBatchTableExport(assetIds: string[]) {
  if (!assetIds.length) {
    ElMessage.warning('请先勾选要导出的行')
    return
  }
  try {
    await exportHostsExcel(assetIds)
    ElMessage.success('已触发导出')
  } catch (error) {
    ElMessage.warning(formatExportError(error))
  }
}
</script>

<style scoped>
.host-search {
  max-width: 1280px;
  margin: 0 auto;
}

.host-search__panel {
  border-radius: 8px;
}

.host-search__tabs :deep(.el-tabs__item) {
  font-size: 14px;
}

.host-search__bar {
  display: flex;
  gap: 12px;
  align-items: center;
}

.host-search__bar :deep(.el-input) {
  flex: 1;
  max-width: 720px;
}

.host-search__hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--tez-text-secondary);
}

.host-search__hint code {
  background: #f5f7fa;
  padding: 1px 4px;
  border-radius: 3px;
}

.host-search__recent {
  margin-top: 14px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.host-search__recent-label {
  color: var(--tez-text-secondary);
  font-size: 13px;
  margin-right: 4px;
}

.host-search__recent-item {
  cursor: pointer;
}

.host-search__result {
  margin-top: 18px;
  min-height: 200px;
}

.host-search__empty {
  margin: 40px 0;
}

.host-search__zone-alert {
  margin-bottom: 12px;
}

.host-search__batch {
  display: grid;
  grid-template-columns: minmax(320px, 1fr) 2fr;
  gap: 18px;
}

.host-search__batch-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.host-search__batch-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.host-search__batch-count {
  font-size: 13px;
  color: var(--tez-text-secondary);
}

.host-search__batch-result {
  min-height: 200px;
}

.host-search__batch-summary {
  display: flex;
  gap: 24px;
  padding: 12px 0;
  border-bottom: 1px solid var(--tez-border);
  margin-bottom: 12px;
}

@media (max-width: 1024px) {
  .host-search__batch {
    grid-template-columns: 1fr;
  }
}
</style>
