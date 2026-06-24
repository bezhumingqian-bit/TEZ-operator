<template>
  <div class="tez-page host-search">
    <h2 class="tez-page__title">
      <el-icon><Search /></el-icon>
      <span>资源查询</span>
      <el-tag size="small" type="success" effect="plain">M1 · 模块 4</el-tag>
    </h2>

    <el-card shadow="never" class="host-search__panel">
      <el-tabs v-model="activeTab" class="host-search__tabs">
        <!-- ─────────── 节点资源概况 ─────────── -->
        <el-tab-pane label="节点资源概况" name="node_overview">
          <div class="host-search__bar">
            <el-select
              v-model="nodeZoneSelected"
              filterable
              size="large"
              placeholder="选择可用区"
              style="width: 420px"
            >
              <el-option v-for="z in zoneOptionsWithArch" :key="z.zone" :label="z.zone" :value="z.zone">
                <div style="display:flex; justify-content:space-between; align-items:center; width:100%">
                  <span>{{ z.zone }}</span>
                  <el-tag :type="z.arch === '25G' ? 'success' : 'info'" size="small" effect="plain">{{ z.arch }}</el-tag>
                </div>
              </el-option>
            </el-select>
            <el-button
              type="primary"
              size="large"
              :loading="nodeLoading"
              :disabled="!nodeZoneSelected"
              @click="onNodeOverview"
            >
              查询资源概况
            </el-button>
            <el-button
              size="large"
              :loading="nodeRefreshing"
              :disabled="!nodeZoneSelected"
              @click="onNodeForceRefresh"
            >
              🔄 强制刷新
            </el-button>
          </div>

          <div class="host-search__result">
            <!-- 等待登录提示（可取消） -->
            <div v-if="nodeWaitingLogin" style="text-align:center; padding: 40px 0;">
              <el-icon class="is-loading" :size="32" style="margin-bottom:12px"><Loading /></el-icon>
              <p style="color:#606266; margin-bottom:16px">等待浏览器登录验证中，请在弹出的浏览器窗口完成扫码...</p>
              <el-button @click="cancelNodeQuery">取消查询</el-button>
            </div>
            <el-skeleton v-else-if="nodeLoading || nodeRefreshing" :rows="6" animated />
            <template v-else-if="nodeOverviewData">
              <!-- 数据来源提示 -->
              <el-alert
                v-if="nodeOverviewData.from_cache"
                :title="`本地缓存数据（上次同步: ${nodeOverviewData.last_sync_at || '未知'}）`"
                type="info"
                show-icon
                :closable="false"
                style="margin-bottom: 12px"
              />

              <!-- 机位概况 -->
              <el-card shadow="never" class="node-section">
                <template #header><b>机位概况</b></template>
                <el-descriptions :column="2" border size="small" style="margin-bottom: 12px">
                  <el-descriptions-item label="总机位">{{ nodeOverviewData.positions.total_positions ?? '-' }}</el-descriptions-item>
                  <el-descriptions-item label="空闲机位">
                    <span :style="{ color: nodeOverviewData.positions.free_count > 0 ? '#67c23a' : '#f56c6c', fontWeight: 'bold' }">
                      {{ nodeOverviewData.positions.free_count ?? '-' }}
                    </span>
                  </el-descriptions-item>
                  <el-descriptions-item label="已用机位">{{ nodeOverviewData.positions.used_count ?? '-' }}</el-descriptions-item>
                  <el-descriptions-item label="TEZ设备">{{ (nodeOverviewData.online_devices?.length || 0) + (nodeOverviewData.offline_devices?.length || 0) }} 台</el-descriptions-item>
                  <el-descriptions-item label="未识别设备">
                    <span v-if="(nodeOverviewData.unclassified_count || 0) > 0" style="color: #e6a23c; font-weight: bold">
                      {{ nodeOverviewData.unclassified_count }} 台
                    </span>
                    <span v-else style="color: #67c23a">0</span>
                    <el-tooltip v-if="(nodeOverviewData.unclassified_count || 0) > 0" content="已用机位上有设备，但 IDCRM 未提取到固资号或 TCUM 未查到信息" placement="top">
                      <el-icon style="margin-left:4px; color:#909399; cursor:help"><QuestionFilled /></el-icon>
                    </el-tooltip>
                  </el-descriptions-item>
                </el-descriptions>
                <el-alert
                  :title="nodeOverviewData.positions.message"
                  :type="nodeOverviewData.positions.free_count === null ? 'warning' : (nodeOverviewData.positions.free_count > 0 ? 'success' : 'error')"
                  show-icon
                  :closable="false"
                />
                <div v-if="nodeOverviewData.positions.idc" class="node-info">
                  机房：{{ nodeOverviewData.positions.idc }}
                </div>
              </el-card>

              <!-- 库存管理（该区可售卖库存，来自云霄） -->
              <el-card shadow="never" class="node-section" style="margin-top: 16px">
                <template #header>
                  <div class="node-section__header">
                    <div>
                      <b>库存管理</b>
                      <el-tag size="small" type="info" style="margin-left: 8px">
                        {{ nodeInventory.length }} 条
                      </el-tag>
                      <span style="color:#909399; font-size:12px; margin-left:8px">（该区各实例类型可售卖库存）</span>
                      <el-tooltip v-if="yunxiaoEnriched !== null" content="云霄数据对齐状态" placement="top">
                        <el-tag size="small" :type="yunxiaoEnriched ? 'success' : 'warning'" effect="plain" style="margin-left:6px; cursor:help">
                          {{ yunxiaoEnriched ? '✓ 已对齐' : '⚠ 未对齐' }}
                        </el-tag>
                      </el-tooltip>
                    </div>
                  </div>
                </template>
                <el-table v-if="nodeInventory.length" :data="nodeInventory" stripe size="small" max-height="420">
                  <el-table-column prop="instance_family" label="实例族" width="100" />
                  <el-table-column prop="instance_type" label="实例类型" width="160" />
                  <el-table-column prop="pool" label="资源池" width="120" show-overflow-tooltip />
                  <el-table-column label="库存" width="80">
                    <template #default="{ row }">
                      <span :style="{ color: (row.inventory ?? 0) <= (row.inventory_threshold ?? 0) ? '#f56c6c' : '#67c23a', fontWeight: 'bold' }">
                        {{ row.inventory ?? '-' }}
                      </span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="inventory_threshold" label="阈值" width="70" />
                  <el-table-column prop="safety_quota" label="安全配额" width="80" />
                  <el-table-column prop="billing_type" label="计费" width="70" />
                  <el-table-column prop="cpu" label="CPU" width="70" />
                  <el-table-column prop="gpu" label="GPU" width="70" />
                  <el-table-column prop="mem" label="内存" width="80" />
                  <el-table-column prop="device_type" label="设备类型" min-width="100" show-overflow-tooltip />
                </el-table>
                <el-empty v-else :image-size="60">
                  <template #description>
                    <div>
                      <p style="margin: 0 0 4px 0">该区暂无库存数据</p>
                      <p style="margin: 0; font-size: 12px; color: #909399">
                        可能原因：可用区在云霄未上线、未配置实例类型，或数据源暂未覆盖
                      </p>
                    </div>
                  </template>
                </el-empty>
              </el-card>

              <!-- 已上线设备（已对齐云霄母机资源） -->
              <el-card v-if="nodeOverviewData.online_devices && nodeOverviewData.online_devices.length" shadow="never" class="node-section" style="margin-top: 16px">
                <template #header>
                  <div class="node-section__header">
                    <div>
                      <b>已上线设备</b>
                      <el-tag size="small" type="success" style="margin-left: 8px">
                        {{ nodeOverviewData.online_devices.length }} 台
                      </el-tag>
                    </div>
                    <div>
                      <el-button v-if="onlineSelection.length" size="small" type="primary" @click="copyAssetIds(onlineSelection)">
                        复制选中 ({{ onlineSelection.length }})
                      </el-button>
                      <el-button size="small" text type="primary" @click="copyAssetIds(nodeOverviewData.online_devices)">
                        复制全部
                      </el-button>
                    </div>
                  </div>
                </template>
                <el-table :data="nodeOverviewData.online_devices" stripe size="small" @selection-change="(rows: any[]) => onlineSelection = rows">
                  <el-table-column type="selection" width="40" fixed />
                  <el-table-column prop="asset_id" label="固资号" width="150" fixed />
                  <el-table-column prop="module" label="模块" min-width="280" show-overflow-tooltip />
                </el-table>
              </el-card>

              <!-- 未上线设备 -->
              <el-card shadow="never" class="node-section" style="margin-top: 16px">
                <template #header>
                  <div class="node-section__header">
                    <div>
                      <b>未上线设备</b>
                      <el-tag size="small" type="warning" style="margin-left: 8px">
                        {{ nodeOverviewData.offline_devices.length }} 台
                      </el-tag>
                    </div>
                    <div v-if="nodeOverviewData.offline_devices.length">
                      <el-button size="small" type="warning" @click="submitDeployOrder">
                        提交投放单
                      </el-button>
                      <el-button v-if="offlineSelection.length" size="small" type="primary" @click="copyAssetIds(offlineSelection)">
                        复制选中 ({{ offlineSelection.length }})
                      </el-button>
                      <el-button size="small" text type="primary" @click="copyAssetIds(nodeOverviewData.offline_devices)">
                        复制全部
                      </el-button>
                    </div>
                  </div>
                </template>
                <el-table v-if="nodeOverviewData.offline_devices.length" :data="nodeOverviewData.offline_devices" stripe size="small" @selection-change="(rows: any[]) => offlineSelection = rows">
                  <el-table-column type="selection" width="40" />
                  <el-table-column prop="asset_id" label="固资号" width="140" />
                  <el-table-column prop="ip" label="IP" width="130" />
                  <el-table-column prop="machine_type" label="机型" width="130" />
                  <el-table-column prop="module" label="模块" width="200" />
                  <el-table-column prop="reason" label="未上线原因" min-width="200" />
                </el-table>
                <el-empty v-else description="该节点没有未上线设备" />
              </el-card>



              <!-- 批量复制选中浮动条 -->
              <div v-if="totalSelected > 0" class="node-selection-bar">
                <span>已选 {{ totalSelected }} 台设备</span>
                <el-button type="primary" size="small" @click="copyAllSelected">复制选中固资号</el-button>
              </div>
            </template>
            <el-empty v-else description="选择可用区后查询资源概况" />
          </div>
        </el-tab-pane>

        <!-- ─────────── 机型库存查询 ─────────── -->
        <el-tab-pane label="机型库存" name="machine_type">
          <div class="host-search__bar">
            <el-select
              v-model="mtSelected"
              filterable
              size="large"
              placeholder="选择或搜索机型"
              style="width: 480px"
            >
              <el-option
                v-for="t in machineTypeOptions"
                :key="t.value"
                :label="t.label"
                :value="t.value"
              >
                <div style="display:flex; justify-content:space-between; align-items:center; width:100%">
                  <span style="font-weight:600">{{ t.value }}</span>
                  <span style="font-size:12px; color:#909399">{{ t.instances }}</span>
                </div>
              </el-option>
            </el-select>
            <el-button
              type="primary"
              size="large"
              :loading="mtLoading"
              :disabled="!mtSelected"
              @click="onMachineTypeQuery"
            >
              查询库存
            </el-button>
          </div>

          <div class="host-search__result">
            <el-skeleton v-if="mtLoading" :rows="4" animated />
            <template v-else-if="mtResult">
              <el-alert
                type="success"
                :closable="false"
                show-icon
                style="margin-bottom: 16px"
              >
                <template #title>
                  机型 <b>{{ mtResult.machine_type }}</b>：共 {{ mtResult.total }} 台，分布在 {{ mtResult.zone_count }} 个可用区
                </template>
              </el-alert>

              <!-- 按区域分组展示 -->
              <el-card v-for="zg in mtResult.zones" :key="zg.zone" shadow="never" class="node-section" style="margin-bottom: 12px">
                <template #header>
                  <div class="node-section__header">
                    <div>
                      <b>{{ zg.zone }}</b>
                      <el-tag size="small" style="margin-left: 8px">{{ zg.count }} 台</el-tag>
                    </div>
                    <el-button size="small" text type="primary" @click="copyAssetIds(zg.devices)">
                      复制固资号
                    </el-button>
                  </div>
                </template>
                <el-table :data="zg.devices" stripe size="small" @selection-change="(rows: any[]) => mtSelections[zg.zone] = rows">
                  <el-table-column type="selection" width="40" />
                  <el-table-column prop="asset_id" label="固资号" width="150" />
                  <el-table-column prop="ip" label="IP" width="140" />
                  <el-table-column prop="status" label="状态" width="80">
                    <template #default="{ row }">
                      <el-tag :type="row.status === 'online' ? 'success' : row.category === 'non_tez' ? 'info' : 'warning'" size="small">
                        {{ row.status === 'online' ? '在线' : row.category === 'non_tez' ? '非TEZ' : '离线' }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="module" label="模块" min-width="250" show-overflow-tooltip />
                </el-table>
              </el-card>

              <!-- 批量复制浮动条 -->
              <div v-if="mtTotalSelected > 0" class="node-selection-bar">
                <span>已选 {{ mtTotalSelected }} 台设备</span>
                <el-button type="primary" size="small" @click="copyMtSelected">复制选中固资号</el-button>
              </div>
            </template>
            <el-empty v-else description="选择机型后查询全平台库存分布" />
          </div>
        </el-tab-pane>

        <!-- ─────────── 设备查询（合并单条+批量） ─────────── -->
        <el-tab-pane label="设备查询" name="search">
          <div class="host-search__bar">
            <el-input
              v-model="singleQuery"
              size="large"
              clearable
              placeholder="输入固资号 / IP / Zone，支持多个（换行或逗号分隔）"
              :prefix-icon="Search"
              @keyup.enter="onSingleSearch"
            />
            <el-button
              type="primary"
              size="large"
              :loading="singleLoading || batchLoading"
              :icon="Search"
              @click="onSingleSearch"
            >
              查询
            </el-button>
            <el-button
              v-if="!showBatchInput"
              size="large"
              @click="showBatchInput = true"
            >
              批量输入
            </el-button>
          </div>

          <!-- 批量输入框（展开） -->
          <div v-if="showBatchInput" class="host-search__batch-expand">
            <el-input
              v-model="batchInput"
              type="textarea"
              :rows="6"
              placeholder="每行一个固资号或 IP，最多 100 条"
            />
            <div class="host-search__batch-toolbar">
              <span class="host-search__batch-count">已输入：<b>{{ batchQueries.length }}</b> / 100</span>
              <div>
                <el-button size="small" @click="showBatchInput = false; batchInput = ''">收起</el-button>
                <el-button type="primary" size="small" :loading="batchLoading" :disabled="!batchQueries.length" @click="onBatchSearch">
                  批量查询
                </el-button>
              </div>
            </div>
          </div>

          <div class="host-search__hint">
            支持：固资号 <code>TYSV*</code>、IPv4、Zone <code>zone_*</code> / <code>ap-*-*-N</code>。多个用换行或逗号分隔自动识别为批量。
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
                v-else-if="!batchResp"
                description="输入固资号 / IP / Zone 后回车即可查询"
                class="host-search__empty"
              />
            </template>

            <!-- 批量结果 -->
            <template v-if="batchResp">
              <el-skeleton v-if="batchLoading" :rows="5" animated />
              <template v-else>
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
            </template>
          </div>
        </el-tab-pane>

        <!-- ─────────── 可用区信息 ─────────── -->
        <el-tab-pane label="可用区信息" name="zone">
          <el-alert
            class="host-search__zone-alert"
            type="info"
            :closable="false"
            show-icon
            title="多选可用区查看详细信息（Region、机房、架构等），方便去星云查询"
          />
          <div class="host-search__bar">
            <el-select
              v-model="zoneInfoSelected"
              filterable
              multiple
              collapse-tags
              collapse-tags-tooltip
              size="large"
              placeholder="搜索并多选可用区"
              style="width: 500px"
            >
              <el-option v-for="z in zoneOptions" :key="z" :label="z" :value="z" />
            </el-select>
            <el-button
              type="primary"
              size="large"
              :loading="zoneInfoLoading"
              :disabled="!zoneInfoSelected.length"
              @click="onZoneInfoQuery"
            >
              查询信息
            </el-button>
          </div>

          <div class="host-search__result">
            <el-skeleton v-if="zoneInfoLoading" :rows="4" animated />
            <template v-else-if="zoneInfoData && zoneInfoData.length">
              <el-table :data="zoneInfoData" border stripe size="small" style="margin-top: 12px">
                <el-table-column prop="zone" label="可用区" min-width="180" />
                <el-table-column prop="nebula_region" label="星云地域" width="140">
                  <template #default="{ row }">
                    <el-tag v-if="row.nebula_region" size="small" type="primary">{{ row.nebula_region }}</el-tag>
                    <span v-else style="color: #999">未上线</span>
                  </template>
                </el-table-column>
                <el-table-column prop="city" label="城市" width="80" />
                <el-table-column prop="isp" label="运营商" width="70" />
                <el-table-column prop="idc" label="机房(IDC)" min-width="220" />
                <el-table-column prop="arch" label="架构" width="60">
                  <template #default="{ row }">
                    <el-tag :type="row.arch === '25G' ? 'success' : 'info'" size="small">{{ row.arch }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="status" label="状态" width="80">
                  <template #default="{ row }">
                    <el-tag :type="row.status === '已开区' ? 'success' : row.status === '已下线' ? 'danger' : 'warning'" size="small">{{ row.status }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="models" label="支持机型" min-width="180" />
              </el-table>
            </template>
            <el-empty v-else description="选择可用区后查询信息" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Search, Loading, QuestionFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import HostCard from '@/components/HostCard.vue'
import HostTable from '@/components/HostTable.vue'
import BatchTable from '@/components/BatchTable.vue'
import { ApiError } from '@/api/client'
import {
  batchSearch,
  exportHostsExcel,
  getZoneInstanceStats,
  listZoneHosts,
  listZones,
  listZonesWithArch,
  pickSingleHost,
  searchHost,
} from '@/api/hosts'
import { queryHostMachines, queryInventory } from '@/api/yunxiao'
import type { HostMachineItem, InventoryItem } from '@/types/yunxiao'
import type {
  BatchSearchResponse,
  HostInfo,
  ZoneHostsResponse,
  ZoneInstanceStatsResponse,
} from '@/types/host'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()
const router = useRouter()
const route = useRoute()
const activeTab = ref('node_overview')
const fallbackZoneOptions: string[] = []

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
const showBatchInput = ref(false)
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

// ─── 可用区信息 ───
const zoneOptions = ref<string[]>([...fallbackZoneOptions])
const zoneInfoSelected = ref<string[]>([])
const zoneInfoLoading = ref(false)
const zoneInfoData = ref<any[] | null>(null)

async function onZoneInfoQuery() {
  if (!zoneInfoSelected.value.length) return
  zoneInfoLoading.value = true
  zoneInfoData.value = null
  try {
    const zonesParam = zoneInfoSelected.value.join(',')
    const resp = await fetch(`/api/v1/zones/info?zones=${encodeURIComponent(zonesParam)}`).then(r => r.json())
    zoneInfoData.value = resp.items || []
  } catch {
    ElMessage.error('查询可用区信息失败')
  } finally {
    zoneInfoLoading.value = false
  }
}
const zoneStatsResp = ref<ZoneInstanceStatsResponse | null>(null)

const zoneOptionsWithArch = ref<{ zone: string; arch: string }[]>([])

async function loadZoneOptions() {
  try {
    const zonesWithArch = await listZonesWithArch()
    zoneOptionsWithArch.value = zonesWithArch
    zoneOptions.value = zonesWithArch.map(z => z.zone)
  } catch {
    zoneOptions.value = []
    zoneOptionsWithArch.value = []
  }
}

onMounted(async () => {
  await loadZoneOptions()
  void loadMachineTypes()
  // 外部跳转（如资源水位页点卡片）带 zone 参数时，自动查
  const zoneParam = route.query.zone as string | undefined
  if (zoneParam) {
    activeTab.value = 'node_overview'
    nodeZoneSelected.value = zoneParam
    await onNodeOverview()
  }
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

// ─── 机型库存查询 ───
const mtSelected = ref('')
const mtLoading = ref(false)
const machineTypes = ref<string[]>([])
const mtResult = ref<{ machine_type: string; total: number; zone_count: number; zones: { zone: string; count: number; devices: any[] }[] } | null>(null)
const mtSelections = ref<Record<string, any[]>>({})

// 机型 → 可生产实例映射
const machineInstanceMap: Record<string, string> = {
  'CG3-25G': 'S5、SN3ne（标准型）',
  'CG3-10G': 'S5nt（标准型10G）',
  'Y0-MI52-25G': 'SN3ne、IT5（高IO）',
  'Y0-MI32-25G': 'IT3（高IO）',
  'SH5-10G': 'IT5c（高IO 10G）',
  'Y0-BI03-10G': 'D3nt（大数据型）',
  'Y0-BI02-10G': 'D3nt（大数据型）',
  'Y0-MD53M-25G': 'BMD2/BMD2i（裸金属）',
  'T0-MD42M-25G': 'BMD2/BMD2i（裸金属）',
  'Y0-MS31-25G': 'TOC/TPC管控（VSELF_3）',
  'DS4A-100G': 'TGW网关（TEZ_TGW）',
  'DS3-40G': 'TGW网关（TEZ_TGW_INTEL）',
  'CG1-10G': 'TOC/TPC管控（VSELF_3）',
  'CG2-10G': 'S4（ECM标准型）',
  'Y0-GG52R-10G': 'GPU实例',
  'Y0-SH11-10G': '存储型',
  'Y0-SW13-10G': '存储型',
}

const machineTypeOptions = computed(() =>
  machineTypes.value.map(t => ({
    value: t,
    label: `${t} - ${machineInstanceMap[t] || '通用'}`,
    instances: machineInstanceMap[t] || '通用',
  }))
)

const mtTotalSelected = computed(() => Object.values(mtSelections.value).reduce((sum, arr) => sum + arr.length, 0))

function copyMtSelected() {
  const all = Object.values(mtSelections.value).flat()
  copyAssetIds(all)
}

async function loadMachineTypes() {
  try {
    const resp = await fetch('/api/v1/zones/devices/types')
    const data = await resp.json()
    machineTypes.value = data.types || []
  } catch {}
}

async function onMachineTypeQuery() {
  if (!mtSelected.value) return
  mtLoading.value = true
  mtResult.value = null
  mtSelections.value = {}
  try {
    const resp = await fetch(`/api/v1/zones/devices/by-type?machine_type=${encodeURIComponent(mtSelected.value)}`)
    mtResult.value = await resp.json()
  } catch {
    ElMessage.error('查询失败')
  } finally {
    mtLoading.value = false
  }
}

// ─── 一键提交投放单 ───
function submitDeployOrder() {
  if (!nodeOverviewData.value) return

  // 优先用选中的，没选就用全部未上线设备
  const devices = offlineSelection.value.length > 0
    ? offlineSelection.value
    : nodeOverviewData.value.offline_devices

  if (!devices.length) {
    ElMessage.warning('没有未上线设备')
    return
  }

  const assetIds = devices.map((d: any) => d.asset_id).filter(Boolean).join('\n')
  const zone = nodeOverviewData.value.positions.zone || ''
  const count = devices.length

  // 跳转到工单页面，带上预填参数
  router.push({
    path: '/workorder',
    query: {
      action: 'create',
      type: 'host_deploy',
      asset_ids: assetIds,
      zone: zone,
      count: String(count),
      title: `${zone} 投放 ${count} 台设备`,
    },
  })
}

// ─── 节点资源概况 ───
type OnlineDevice = {
  asset_id: string
  ip: string
  machine_type: string
  module?: string
  // 以下为按固资号对齐的云霄母机资源（可能缺失）
  cpu_available?: number
  cpu_total?: number
  mem_available?: number
  mem_total?: number
  health_score?: number
  is_empty_host?: string
  is_cdh?: string
}

interface NodeOverviewData {
  positions: { zone: string; idc: string | null; free_count: number | null; used_count?: number | null; total_positions?: number; message: string }
  offline_devices: { asset_id: string; ip: string; machine_type: string; module?: string; reason: string }[]
  online_devices: OnlineDevice[]
  non_tez_devices?: { asset_id: string; ip: string; machine_type: string; module?: string }[]
  non_tez_count?: number
  unclassified_count?: number
  from_cache?: boolean
  last_sync_at?: string
}

const nodeZoneSelected = ref('')
const nodeLoading = ref(false)
const nodeRefreshing = ref(false)
const nodeOverviewData = ref<NodeOverviewData | null>(null)
const nodeInventory = ref<InventoryItem[]>([])
// null=未查询, true=已成功对齐云霄, false=云霄数据获取失败
const yunxiaoEnriched = ref<boolean | null>(null)
const nodeWaitingLogin = ref(false)
let nodeAbortController: AbortController | null = null

async function fetchNodeOverview(forceRefresh = false) {
  const zone = nodeZoneSelected.value
  if (!zone) return

  nodeAbortController = new AbortController()
  const signal = nodeAbortController.signal

  // 5秒后如果还没返回，提示"等待登录中"
  const loginHintTimer = setTimeout(() => {
    if (nodeLoading.value || nodeRefreshing.value) {
      nodeWaitingLogin.value = true
    }
  }, 5000)

  try {
    const url = `/api/v1/zones/${encodeURIComponent(zone)}/overview${forceRefresh ? '?force_refresh=true' : ''}`
    // 并行抓取：物理资源概况 + 云霄母机 + 云霄库存（云霄失败不影响物理概况展示）
    const [overviewRes, hostRes, invRes] = await Promise.allSettled([
      fetch(url, { signal }).then(r => r.json()),
      queryHostMachines({ zone }),
      queryInventory({ zone }),
    ])

    if (overviewRes.status === 'rejected') throw overviewRes.reason
    const resp = overviewRes.value

    // 按固资号对齐云霄母机资源
    let online: OnlineDevice[] = resp.online_devices || []
    if (hostRes.status === 'fulfilled') {
      const hostItems = (hostRes.value.data?.items ?? []) as HostMachineItem[]
      const hostMap = new Map<string, HostMachineItem>()
      for (const h of hostItems) {
        if (h.asset_id) hostMap.set(h.asset_id, h)
      }
      online = online.map((d) => {
        const m = hostMap.get(d.asset_id)
        if (!m) return d
        return {
          ...d,
          cpu_available: m.cpu_available,
          cpu_total: m.cpu_total,
          mem_available: m.mem_available,
          mem_total: m.mem_total,
          health_score: m.health_score,
          is_empty_host: m.is_empty_host,
          is_cdh: m.is_cdh,
        }
      })
      yunxiaoEnriched.value = true
    } else {
      yunxiaoEnriched.value = false
    }

    // 库存（来自云霄）
    nodeInventory.value = invRes.status === 'fulfilled'
      ? ((invRes.value.data?.items ?? []) as InventoryItem[])
      : []

    nodeOverviewData.value = {
      positions: {
        zone: resp.zone,
        idc: resp.idc,
        free_count: resp.free_count,
        used_count: resp.used_count,
        total_positions: resp.total_positions,
        message: resp.message || '',
      },
      offline_devices: resp.offline_devices || [],
      online_devices: online,
      non_tez_devices: resp.non_tez_devices || [],
      non_tez_count: resp.non_tez_count || 0,
      unclassified_count: resp.unclassified_count || 0,
      from_cache: resp.from_cache,
      last_sync_at: resp.last_sync_at,
    }
  } finally {
    clearTimeout(loginHintTimer)
    nodeWaitingLogin.value = false
    nodeAbortController = null
  }
}

function cancelNodeQuery() {
  if (nodeAbortController) {
    nodeAbortController.abort()
    nodeAbortController = null
  }
  nodeLoading.value = false
  nodeRefreshing.value = false
  nodeWaitingLogin.value = false
  ElMessage.info('已取消查询')
}

function copyAssetIds(devices: { asset_id: string }[]) {
  const ids = devices.map(d => d.asset_id).filter(Boolean)
  if (!ids.length) {
    ElMessage.warning('没有可复制的固资号')
    return
  }
  const text = ids.join('\n')
  navigator.clipboard.writeText(text).then(() => {
    ElMessage.success(`已复制 ${ids.length} 个固资号`)
  }).catch(() => {
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    ElMessage.success(`已复制 ${ids.length} 个固资号`)
  })
}

// 批量选择
const onlineSelection = ref<any[]>([])
const offlineSelection = ref<any[]>([])
const nonTezSelection = ref<any[]>([])

const totalSelected = computed(() => onlineSelection.value.length + offlineSelection.value.length + nonTezSelection.value.length)

function copyAllSelected() {
  const all = [...onlineSelection.value, ...offlineSelection.value, ...nonTezSelection.value]
  copyAssetIds(all)
}

async function onNodeOverview() {
  if (!nodeZoneSelected.value) return
  nodeLoading.value = true
  nodeOverviewData.value = null
  try {
    await fetchNodeOverview(false)
  } catch (e: any) {
    if (e?.name !== 'AbortError') ElMessage.error('查询失败')
  } finally {
    nodeLoading.value = false
    nodeWaitingLogin.value = false
  }
}

async function onNodeForceRefresh() {
  if (!nodeZoneSelected.value) return
  nodeRefreshing.value = true
  try {
    await fetchNodeOverview(true)
    ElMessage.success('数据已从云端刷新')
  } catch (e: any) {
    if (e?.name !== 'AbortError') ElMessage.error('刷新失败')
  } finally {
    nodeRefreshing.value = false
    nodeWaitingLogin.value = false
  }
}
</script>

<style scoped>
.host-search {
  max-width: 1280px;
  margin: 0 auto;
}

.host-search__panel {
  border-radius: var(--tez-radius-sm);
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

.host-search__stats-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(120px, 1fr));
  gap: 16px;
  padding: 16px;
  margin-bottom: 12px;
  background: #f8fafc;
  border: 1px solid var(--tez-border);
  border-radius: var(--tez-radius-sm);
}

.host-search__stats-table {
  width: 100%;
}

.host-search__mini-tag {
  margin: 2px 4px 2px 0;
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

.host-search__batch-expand {
  margin-top: 12px;
  padding: 12px;
  background: #f9fafb;
  border: 1px solid var(--tez-border);
  border-radius: var(--tez-radius-sm);
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

.node-section {
  margin-bottom: 0;
}

.node-section__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.node-selection-bar {
  position: sticky;
  bottom: 0;
  margin-top: 16px;
  padding: 12px 16px;
  background: #ecf5ff;
  border: 1px solid #b3d8ff;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
  color: #409eff;
}

.node-info {
  margin-top: 8px;
  font-size: 13px;
  color: var(--tez-text-regular);
}
</style>
