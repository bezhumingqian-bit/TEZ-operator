/**
 * 通用格式化工具函数
 *
 * 消除 Dashboard.vue / WorkOrder.vue / UserManagement.vue 中重复的
 * formatTime、extractZone、statusLabel 等函数。
 */

/** 将 ISO 时间格式化为「MM-DD HH:mm」的友好显示。 */
export function formatTime(iso: string | undefined | null): string {
  if (!iso) return '-'
  try {
    const d = new Date(iso)
    return d.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso.replace('T', ' ').slice(0, 16)
  }
}

/** 将 ISO 时间简化为「YYYY-MM-DD HH:mm」。 */
export function formatTimeShort(iso: string | undefined | null): string {
  if (!iso) return '-'
  return iso.replace('T', ' ').slice(0, 16)
}

// ─── 工单状态 ───

const ORDER_STATUS_LABEL_MAP: Record<string, string> = {
  submitted: '待受理',
  pending: '待处理',
  processing: '处理中',
  verifying: '待验证',
  completed: '已完成',
  rejected: '已驳回',
}

const ORDER_STATUS_TAG_MAP: Record<string, string> = {
  submitted: 'warning',
  pending: 'info',
  processing: '',
  verifying: 'info',
  completed: 'success',
  rejected: 'danger',
}

/** 工单状态 → 中文标签。 */
export function orderStatusLabel(s: string | undefined): string {
  return ORDER_STATUS_LABEL_MAP[s || ''] || s || ''
}

/** 工单状态 → Element Plus tag type。 */
export function orderStatusType(s: string | undefined): string {
  return ORDER_STATUS_TAG_MAP[s || ''] || ''
}

// ─── 设备状态（HostTable 用）───

const HOST_STATUS_TAG_MAP: Record<string, string> = {
  online: 'success',
  maintenance: 'warning',
  offline: 'danger',
  运营中: 'success',
  维护中: 'warning',
  故障: 'danger',
}

/** 设备/母机状态 → Element Plus tag type。 */
export function hostStatusType(s: string | undefined | null): 'success' | 'warning' | 'danger' | 'info' {
  const v = (s || '').toLowerCase()
  return (HOST_STATUS_TAG_MAP[v] as any) || 'info'
}

// ─── detail 字段提取（工单相关）───

interface DetailRow {
  detail?: Record<string, any>
}

/** 从工单的 detail 对象中提取指定字段。 */
export function extractField(row: DetailRow, key: string): string {
  const d = row.detail || {}
  const raw = d[key] || ''
  if (key === 'asset_ids') {
    const lines = String(raw)
      .split('\n')
      .filter(Boolean)
    const preview = lines
      .slice(0, 2)
      .map((l: string) => l.trim().slice(0, 18))
      .join(', ')
    return lines.length > 2 ? preview + '…' : preview
  }
  return raw
}

/** 从工单的 detail 中提取可用区（zone / target_zone / source_zone）。 */
export function extractZone(row: DetailRow): string {
  const d = row.detail || {}
  return d.zone || d.target_zone || d.source_zone || ''
}
