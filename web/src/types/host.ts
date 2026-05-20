/**
 * 主机相关 TypeScript 类型定义
 *
 * 字段对齐 app/schemas/host.py（HostInfo / SearchResponse 等）
 * 任何字段调整必须同步修改后端 schema，反之亦然。
 */

export type QueryType = 'asset_id' | 'ip' | 'zone' | 'unknown'
export type HostStatus = 'online' | 'offline' | 'maintenance' | string

export interface HostHistoryEvent {
  event_type: string
  event_at: string
  from_module?: string | null
  to_module?: string | null
  description?: string | null
  source?: string | null
}

export interface HostMeta {
  from_cache: boolean
  data_sources: string[]
  last_sync_at?: string | null
  partial: boolean
  errors: Record<string, string>
}

export interface HostInfo {
  asset_id: string
  ip?: string | null
  zone?: string | null
  machine_type?: string | null
  status?: HostStatus | null
  idc?: string | null
  cabinet?: string | null
  position?: string | null
  module?: string | null
  customer?: string | null
  app_id?: string | null
  has_tpc?: boolean | null
  billing_tags: Record<string, string>

  owner?: string | null
  backup_owners: string[]
  city?: string | null
  server_type?: string | null
  use_years?: number | null

  history: HostHistoryEvent[]
  _meta?: HostMeta
}

export interface SearchResponse {
  code: number
  message: string
  query_type: QueryType
  data: HostInfo | HostInfo[] | null
}

export interface BatchSearchRequest {
  queries: string[]
}

export interface BatchSearchItem {
  query: string
  query_type: QueryType
  success: boolean
  data?: HostInfo | null
  error?: string | null
}

export interface BatchSearchResponse {
  code: number
  message: string
  total: number
  success_count: number
  items: BatchSearchItem[]
}

export interface ZoneHostsResponse {
  code: number
  message: string
  zone: string
  total: number
  items: HostInfo[]
}
