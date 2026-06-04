/**
 * 主机查询接口封装
 *
 * 对应后端 app/routers/hosts.py：
 *   GET  /api/v1/hosts/search?q=...
 *   GET  /api/v1/hosts/{asset_id}
 *   POST /api/v1/hosts/batch_search
 *   GET  /api/v1/zones
 *   GET  /api/v1/zones/{zone}/hosts
 *   GET  /api/v1/hosts/export?asset_ids=...
 */
import apiClient, { type ApiRequestConfig } from './client'
import type {
  BatchSearchRequest,
  BatchSearchResponse,
  HostInfo,
  SearchResponse,
  ZoneHostsResponse,
  ZoneInstanceStatsResponse,
} from '@/types/host'

const PREFIX = '/api/v1'

interface ListZonesResponse {
  zones: string[]
  arch?: Record<string, string>
}

/** 单条查询：固资号 / IP / Zone */
export async function searchHost(q: string): Promise<SearchResponse> {
  const { data } = await apiClient.get<SearchResponse>(`${PREFIX}/hosts/search`, {
    params: { q },
  })
  return data
}

/** 详情查询（按固资号，含历史） */
export async function getHostDetail(assetId: string): Promise<SearchResponse> {
  const { data } = await apiClient.get<SearchResponse>(
    `${PREFIX}/hosts/${encodeURIComponent(assetId)}`,
  )
  return data
}

/** 批量查询（最多 100 条） */
export async function batchSearch(queries: string[]): Promise<BatchSearchResponse> {
  const payload: BatchSearchRequest = { queries }
  const { data } = await apiClient.post<BatchSearchResponse>(
    `${PREFIX}/hosts/batch_search`,
    payload,
  )
  return data
}

/** 列出所有可用 Zone */
export async function listZones(): Promise<string[]> {
  const config: ApiRequestConfig = { silent: true }
  const { data } = await apiClient.get<ListZonesResponse>(`${PREFIX}/zones`, config)
  return Array.isArray(data.zones) ? data.zones : []
}

/** 列出所有可用 Zone（带架构信息） */
export async function listZonesWithArch(): Promise<{ zone: string; arch: string }[]> {
  const config: ApiRequestConfig = { silent: true }
  const { data } = await apiClient.get<ListZonesResponse>(`${PREFIX}/zones`, config)
  const zones = Array.isArray(data.zones) ? data.zones : []
  const archMap = data.arch || {}
  return zones.map(z => ({ zone: z, arch: archMap[z] || '10G' }))
}

/** 按 Zone 列母机 */
export async function listZoneHosts(zone: string): Promise<ZoneHostsResponse> {
  const { data } = await apiClient.get<ZoneHostsResponse>(
    `${PREFIX}/zones/${encodeURIComponent(zone)}/hosts`,
  )
  return data
}

/** 按一个或多个 Zone 统计线上实例资源 */
export async function getZoneInstanceStats(zones: string[]): Promise<ZoneInstanceStatsResponse> {
  const { data } = await apiClient.get<ZoneInstanceStatsResponse>(`${PREFIX}/zones/instances/stats`, {
    params: { zones: zones.join(',') },
  })
  return data
}

/**
 * 导出 Excel
 * 后端契约（W3 待实现）：GET /api/v1/hosts/export?asset_ids=A,B,C
 * 返回 application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
 */
export async function exportHostsExcel(assetIds: string[]): Promise<void> {
  if (assetIds.length === 0) return
  const resp = await apiClient.get(`${PREFIX}/hosts/export`, {
    params: { asset_ids: assetIds.join(',') },
    responseType: 'blob',
  })
  const blob = new Blob([resp.data as Blob], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  const ts = new Date().toISOString().replace(/[:.]/g, '-')
  a.href = url
  a.download = `hosts-export-${ts}.xlsx`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

/** 占位/工具：从 SearchResponse 中提取单台 HostInfo（zone 类型时返回 null） */
export function pickSingleHost(resp: SearchResponse): HostInfo | null {
  if (!resp.data) return null
  if (Array.isArray(resp.data)) return null
  return resp.data
}
