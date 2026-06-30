/** 可观测性 API */
import { apiClient } from './client'

export interface ObservabilitySummary {
  api: {
    total_requests: number
    errors_4xx_5xx: number
    slow_requests_gt3s: number
    avg_duration_ms: number
  }
  browser: {
    total_operations: number
    success: number
    failures: number
    login_required: number
    success_rate: number
  }
  os_distribution: Record<string, number>
}

export interface ApiLogEntry {
  ts: string
  method: string
  path: string
  status: number
  duration_ms: number
  client_ip: string
  user_agent: string
  os: string
  error: string
}

export interface BrowserAuditEntry {
  ts: string
  session: string
  platform: string
  operation: string
  status: string
  duration_ms: number
  rows: number
  error: string
}

export interface ScreenshotInfo {
  filename: string
  size_kb: number
  ts: string
}

export async function fetchSummary(): Promise<ObservabilitySummary> {
  const { data } = await apiClient.get<ObservabilitySummary>('/api/v1/observability/summary')
  return data
}

export async function fetchApiLogs(limit = 200): Promise<ApiLogEntry[]> {
  const { data } = await apiClient.get<ApiLogEntry[]>('/api/v1/observability/api-logs', {
    params: { limit },
  })
  return data
}

export async function fetchBrowserAudit(limit = 200): Promise<BrowserAuditEntry[]> {
  const { data } = await apiClient.get<BrowserAuditEntry[]>(
    '/api/v1/observability/browser-audit',
    { params: { limit } }
  )
  return data
}

export async function fetchScreenshots(limit = 50): Promise<ScreenshotInfo[]> {
  const { data } = await apiClient.get<ScreenshotInfo[]>('/api/v1/observability/screenshots', {
    params: { limit },
  })
  return data
}

export function screenshotUrl(filename: string): string {
  return `/api/v1/observability/screenshots/${filename}`
}
