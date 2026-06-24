<template>
  <div class="water-level">
    <div class="water-level__header">
      <div>
        <h2>资源水位管理</h2>
        <p class="water-level__subtitle">各可用区机位容量与设备健康状况一目了然</p>
      </div>
      <el-button
        type="primary"
        :loading="syncAllLoading"
        :icon="Refresh"
        @click="syncAll"
      >
        刷新全部
      </el-button>
    </div>

    <!-- 顶部汇总 -->
    <div class="stat-row">
      <div class="stat-item">
        <span class="stat-item__value">{{ stats.total }}</span>
        <span class="stat-item__label">节点总数</span>
      </div>
      <div class="stat-item stat-item--critical">
        <span class="stat-item__value">{{ stats.critical }}</span>
        <span class="stat-item__label">紧张</span>
      </div>
      <div class="stat-item stat-item--warning">
        <span class="stat-item__value">{{ stats.warning }}</span>
        <span class="stat-item__label">预警</span>
      </div>
      <div class="stat-item stat-item--healthy">
        <span class="stat-item__value">{{ stats.healthy }}</span>
        <span class="stat-item__label">健康</span>
      </div>
      <div class="stat-item">
        <span class="stat-item__value">{{ stats.totalFree }}</span>
        <span class="stat-item__label">总空闲机位</span>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" v-loading="loading" style="min-height: 200px"></div>

    <!-- 空态 -->
    <el-empty
      v-else-if="!zones.length"
      description="暂无可用区数据"
      :image-size="80"
    >
      <template #description>
        <span style="color: #909399; font-size: 13px">
          请在驾驶舱执行「刷新全部」同步节点数据后查看
        </span>
      </template>
    </el-empty>

    <!-- 水位卡片墙 -->
    <div v-else class="zone-grid">
      <div
        v-for="z in sortedZones"
        :key="z.zone"
        class="zone-card"
        :class="`zone-card--${z.level}`"
        @click="goZoneDetail(z.zone)"
      >
        <!-- 顶部：名称 + 水位标签 -->
        <div class="zone-card__top">
          <span class="zone-card__name" :title="z.zone">{{ z.zone }}</span>
          <el-tag
            size="small"
            :type="levelTagType(z.level)"
            effect="dark"
            round
          >
            {{ z.level_label }}
          </el-tag>
        </div>

        <!-- 进度条 = 机位使用率 -->
        <div class="zone-card__bar">
          <el-progress
            :percentage="Math.round(z.usage_rate * 100)"
            :color="progressColor(z.level)"
            :stroke-width="10"
          >
            <span class="zone-card__bar-text">
              {{ Math.round(z.usage_rate * 100) }}%
            </span>
          </el-progress>
        </div>

        <!-- 关键指标 -->
        <div class="zone-card__metrics">
          <div class="zone-card__metric">
            <span class="zone-card__metric-label">空闲</span>
            <span
              class="zone-card__metric-value"
              :class="z.free_count === 0 ? 'text-danger' : 'text-success'"
            >{{ z.free_count }}</span>
          </div>
          <div class="zone-card__metric">
            <span class="zone-card__metric-label">总位</span>
            <span class="zone-card__metric-value">{{ z.total_positions }}</span>
          </div>
          <div class="zone-card__metric">
            <span class="zone-card__metric-label">在线</span>
            <span class="zone-card__metric-value text-success">{{ z.online_count }}</span>
          </div>
          <div class="zone-card__metric">
            <span class="zone-card__metric-label">离线</span>
            <span
              class="zone-card__metric-value"
              :class="z.offline_count > 0 ? 'text-warning' : ''"
            >{{ z.offline_count }}</span>
          </div>
        </div>

        <!-- 底部：同步时间 -->
        <div class="zone-card__footer">
          <span class="zone-card__sync">
            上次同步 {{ formatDistance(z.last_sync_at) }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const router = useRouter()

// ─── 类型定义 ───
interface ZoneWaterLevel {
  zone: string
  idc: string | null
  total_positions: number
  free_count: number
  used_count: number
  online_count: number
  offline_count: number
  last_sync_at: string | null
  usage_rate: number
  free_rate: number
  offline_rate: number
  level: 'critical' | 'warning' | 'healthy' | 'unknown'
  level_label: string
}

// ─── 状态 ───
const loading = ref(true)
const syncAllLoading = ref(false)
const zones = ref<ZoneWaterLevel[]>([])

// ─── 汇总统计 ───
const stats = computed(() => {
  const total = zones.value.length
  const critical = zones.value.filter((z) => z.level === 'critical').length
  const warning = zones.value.filter((z) => z.level === 'warning').length
  const healthy = zones.value.filter((z) => z.level === 'healthy').length
  const totalFree = zones.value.reduce((sum, z) => sum + z.free_count, 0)
  return { total, critical, warning, healthy, totalFree }
})

// ─── 排序：紧张 → 预警 → 健康 → 无数据（同等级按空闲率升序，紧张的在前）───
const levelOrder: Record<string, number> = { critical: 0, warning: 1, healthy: 2, unknown: 3 }
const sortedZones = computed(() =>
  [...zones.value].sort((a, b) => {
    const lo = levelOrder[a.level] ?? 99
    const ro = levelOrder[b.level] ?? 99
    if (lo !== ro) return lo - ro
    // 同等级按空闲率升序（空闲率越低越紧张，越排前面）
    return a.free_rate - b.free_rate
  })
)

// ─── 辅助 ───
function levelTagType(level: string): 'danger' | 'warning' | 'success' | 'info' {
  const map: Record<string, 'danger' | 'warning' | 'success' | 'info'> = {
    critical: 'danger',
    warning: 'warning',
    healthy: 'success',
    unknown: 'info',
  }
  return map[level] || 'info'
}

function progressColor(level: string): string {
  const map: Record<string, string> = {
    critical: '#f56c6c',
    warning: '#e6a23c',
    healthy: '#67c23a',
    unknown: '#909399',
  }
  return map[level] || '#909399'
}

/** 友好时间距离显示 */
function formatDistance(iso: string | null): string {
  if (!iso) return '未知'
  try {
    const diff = Date.now() - new Date(iso).getTime()
    const minutes = Math.floor(diff / 60000)
    if (minutes < 1) return '刚刚'
    if (minutes < 60) return `${minutes} 分钟前`
    const hours = Math.floor(minutes / 60)
    if (hours < 24) return `${hours} 小时前`
    const days = Math.floor(hours / 24)
    return `${days} 天前`
  } catch {
    return '未知'
  }
}

function goZoneDetail(zone: string) {
  router.push(`/hosts?zone=${encodeURIComponent(zone)}`)
}

// ─── 全量刷新 ───
async function syncAll() {
  syncAllLoading.value = true
  try {
    const resp = await fetch('/api/v1/zones/sync-all', { method: 'POST' }).then((r) => r.json())
    if (resp.success) {
      ElMessage.success(`已刷新 ${resp.zones_updated} 个可用区（共 ${resp.total_positions} 个机位）`)
      await loadData()
    } else {
      ElMessage.error(resp.message || '刷新失败')
    }
  } catch {
    ElMessage.error('刷新失败，请检查浏览器登录状态')
  } finally {
    syncAllLoading.value = false
  }
}

async function loadData() {
  try {
    const resp = await fetch('/api/v1/zones/snapshots').then((r) => r.json())
    zones.value = resp.items || []
  } catch {
    zones.value = []
    ElMessage.warning('加载失败，请检查网络或刷新重试')
  }
}

onMounted(async () => {
  loading.value = true
  await loadData()
  loading.value = false
})
</script>

<style scoped>
.water-level {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px;
}

.water-level__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.water-level__header h2 {
  margin: 0 0 4px 0;
  font-size: 22px;
  font-weight: 700;
  color: var(--tez-text-primary);
}

.water-level__subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--tez-text-muted);
}

/* ─── 顶部汇总行 ─── */
.stat-row {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
}

.stat-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 12px;
  background: #f9fafb;
  border-radius: var(--tez-radius);
  border: 1px solid var(--tez-border);
}

.stat-item__value {
  font-size: 28px;
  font-weight: 700;
  color: #374151;
}

.stat-item__label {
  font-size: 12px;
  color: var(--tez-text-muted);
  margin-top: 4px;
}

.stat-item--critical .stat-item__value { color: var(--tez-danger); }
.stat-item--warning .stat-item__value { color: var(--tez-warning); }
.stat-item--healthy .stat-item__value { color: var(--tez-success); }

/* ─── 水位卡片墙 ─── */
.zone-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.zone-card {
  padding: 20px;
  border-radius: var(--tez-radius);
  border: 1px solid var(--tez-border);
  background: #fff;
  cursor: pointer;
  transition: transform var(--tez-transition), box-shadow var(--tez-transition), border-color var(--tez-transition);
}

.zone-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--tez-shadow-md);
}

.zone-card--critical {
  border-left: 4px solid var(--tez-danger);
}

.zone-card--warning {
  border-left: 4px solid var(--tez-warning);
}

.zone-card--healthy {
  border-left: 4px solid var(--tez-success);
}

.zone-card__top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.zone-card__name {
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.zone-card__bar {
  margin-bottom: 14px;
}

.zone-card__bar-text {
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
}

.zone-card__metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-bottom: 12px;
}

.zone-card__metric {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.zone-card__metric-label {
  font-size: 11px;
  color: #9ca3af;
}

.zone-card__metric-value {
  font-size: 17px;
  font-weight: 700;
  color: #374151;
}

.zone-card__footer {
  padding-top: 10px;
  border-top: 1px solid #f3f4f6;
}

.zone-card__sync {
  font-size: 11px;
  color: #b0b7c3;
}

/* ─── 文本颜色 ─── */
.text-danger { color: var(--tez-danger) !important; }
.text-success { color: var(--tez-success) !important; }
.text-warning { color: var(--tez-warning) !important; }
</style>
