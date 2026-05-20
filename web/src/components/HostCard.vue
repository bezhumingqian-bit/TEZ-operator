<template>
  <el-card shadow="never" class="host-card" body-class="host-card__body">
    <template #header>
      <div class="host-card__header">
        <div class="host-card__title">
          <el-icon><Monitor /></el-icon>
          <span>{{ host.asset_id }}</span>
          <el-tag :type="statusType" size="small" effect="dark" class="host-card__status">
            {{ statusLabel }}
          </el-tag>
        </div>
        <div class="host-card__meta">
          <el-tooltip v-if="host._meta?.from_cache" content="本次结果来自缓存">
            <el-tag size="small" type="info" effect="plain">缓存</el-tag>
          </el-tooltip>
          <el-tooltip v-if="host._meta?.partial" content="部分数据源失败，已降级返回">
            <el-tag size="small" type="warning" effect="plain">部分降级</el-tag>
          </el-tooltip>
          <el-tag
            v-for="src in host._meta?.data_sources || []"
            :key="src"
            size="small"
            type="info"
            effect="plain"
            class="host-card__src"
          >
            {{ src }}
          </el-tag>
        </div>
      </div>
    </template>

    <el-descriptions :column="2" size="default" border class="host-card__section">
      <template #title>
        <div class="host-card__section-title">
          <el-icon><Location /></el-icon>
          <span>基本信息</span>
        </div>
      </template>
      <el-descriptions-item label="固资号">{{ host.asset_id }}</el-descriptions-item>
      <el-descriptions-item label="IP">{{ host.ip || '-' }}</el-descriptions-item>
      <el-descriptions-item label="Zone">{{ host.zone || '-' }}</el-descriptions-item>
      <el-descriptions-item label="机型">{{ host.machine_type || '-' }}</el-descriptions-item>
      <el-descriptions-item label="使用年限">
        {{ host.use_years != null ? `${host.use_years} 年` : '-' }}
      </el-descriptions-item>
      <el-descriptions-item label="服务器类型">{{ host.server_type || '-' }}</el-descriptions-item>
    </el-descriptions>

    <el-descriptions :column="2" size="default" border class="host-card__section">
      <template #title>
        <div class="host-card__section-title">
          <el-icon><OfficeBuilding /></el-icon>
          <span>物理位置</span>
        </div>
      </template>
      <el-descriptions-item label="机房 IDC">{{ host.idc || '-' }}</el-descriptions-item>
      <el-descriptions-item label="所在城市">{{ host.city || '-' }}</el-descriptions-item>
      <el-descriptions-item label="机柜">{{ host.cabinet || '-' }}</el-descriptions-item>
      <el-descriptions-item label="位置">{{ host.position || '-' }}</el-descriptions-item>
      <el-descriptions-item label="模块" :span="2">{{ host.module || '-' }}</el-descriptions-item>
    </el-descriptions>

    <el-descriptions :column="2" size="default" border class="host-card__section">
      <template #title>
        <div class="host-card__section-title">
          <el-icon><Briefcase /></el-icon>
          <span>业务归属</span>
        </div>
      </template>
      <el-descriptions-item label="客户">{{ host.customer || '-' }}</el-descriptions-item>
      <el-descriptions-item label="AppID">{{ host.app_id || '-' }}</el-descriptions-item>
      <el-descriptions-item label="主负责人">{{ host.owner || '-' }}</el-descriptions-item>
      <el-descriptions-item label="备负责人">
        <span v-if="host.backup_owners?.length">
          <el-tag
            v-for="bk in host.backup_owners"
            :key="bk"
            size="small"
            effect="plain"
            class="host-card__owner-tag"
            >{{ bk }}</el-tag
          >
        </span>
        <span v-else>-</span>
      </el-descriptions-item>
      <el-descriptions-item label="是否含 TPC">
        {{ host.has_tpc == null ? '-' : host.has_tpc ? '是' : '否' }}
      </el-descriptions-item>
      <el-descriptions-item label="计费标签">
        <span v-if="billingTagPairs.length">
          <el-tag
            v-for="(p, idx) in billingTagPairs"
            :key="idx"
            size="small"
            effect="plain"
            class="host-card__owner-tag"
            >{{ p }}</el-tag
          >
        </span>
        <span v-else>-</span>
      </el-descriptions-item>
    </el-descriptions>

    <div v-if="host.history?.length" class="host-card__history">
      <div class="host-card__section-title">
        <el-icon><Clock /></el-icon>
        <span>历史轨迹（{{ host.history.length }} 条）</span>
      </div>
      <el-timeline>
        <el-timeline-item
          v-for="(ev, i) in host.history"
          :key="i"
          :timestamp="ev.event_at"
          placement="top"
        >
          <div class="host-card__event">
            <el-tag size="small" effect="plain">{{ ev.event_type }}</el-tag>
            <span v-if="ev.from_module || ev.to_module" class="host-card__event-flow">
              {{ ev.from_module || '-' }} → {{ ev.to_module || '-' }}
            </span>
          </div>
          <div v-if="ev.description" class="host-card__event-desc">{{ ev.description }}</div>
        </el-timeline-item>
      </el-timeline>
    </div>

    <div class="host-card__actions">
      <el-tooltip content="M2 接口人路由器上线后启用" placement="top">
        <span>
          <el-button :icon="Phone" disabled>联系负责人</el-button>
        </span>
      </el-tooltip>
      <el-tooltip content="M3 工单流上线后启用" placement="top">
        <span>
          <el-button :icon="Tickets" disabled>创建工单</el-button>
        </span>
      </el-tooltip>
      <el-button type="primary" :icon="Download" :loading="exporting" @click="onExport">
        导出 Excel
      </el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  Briefcase,
  Clock,
  Download,
  Location,
  Monitor,
  OfficeBuilding,
  Phone,
  Tickets,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { HostInfo } from '@/types/host'
import { exportHostsExcel } from '@/api/hosts'

const props = defineProps<{
  host: HostInfo
}>()

const exporting = ref(false)

const statusType = computed<'success' | 'warning' | 'danger' | 'info'>(() => {
  const s = (props.host.status || '').toLowerCase()
  if (s === 'online' || s === '运营中') return 'success'
  if (s === 'maintenance' || s === '维护中' || s === '告警') return 'warning'
  if (s === 'offline' || s === '故障') return 'danger'
  return 'info'
})

const statusLabel = computed(() => {
  const s = props.host.status
  if (!s) return '未知'
  const map: Record<string, string> = {
    online: '运营中',
    offline: '已下线',
    maintenance: '维护中',
  }
  return map[s.toLowerCase()] || s
})

const billingTagPairs = computed(() => {
  const tags = props.host.billing_tags || {}
  return Object.entries(tags).map(([k, v]) => `${k}=${v}`)
})

async function onExport() {
  exporting.value = true
  try {
    await exportHostsExcel([props.host.asset_id])
    ElMessage.success('已触发导出')
  } catch {
    // 后端导出接口 W3 才落地，这里仅做兜底
    ElMessage.warning('导出接口尚未就绪（GET /api/v1/hosts/export，W3 后端实现中）')
  } finally {
    exporting.value = false
  }
}
</script>

<style scoped>
.host-card {
  border-radius: 8px;
}

.host-card :deep(.host-card__body) {
  padding: 18px;
}

.host-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}

.host-card__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
}

.host-card__status {
  margin-left: 4px;
}

.host-card__meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.host-card__src {
  margin-left: 0;
}

.host-card__section {
  margin-top: 14px;
}

.host-card__section-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  color: var(--tez-text-primary);
}

.host-card__owner-tag {
  margin-right: 4px;
  margin-bottom: 4px;
}

.host-card__history {
  margin-top: 18px;
}

.host-card__event {
  display: flex;
  align-items: center;
  gap: 8px;
}

.host-card__event-flow {
  color: var(--tez-text-regular);
  font-size: 13px;
}

.host-card__event-desc {
  margin-top: 4px;
  color: var(--tez-text-secondary);
  font-size: 13px;
}

.host-card__actions {
  margin-top: 18px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  border-top: 1px solid var(--tez-border);
  padding-top: 14px;
}
</style>
