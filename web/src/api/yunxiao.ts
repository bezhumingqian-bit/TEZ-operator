/** 云霄平台 — API 封装。 */
import apiClient from './client'
import type { YunxiaoQueryResponse } from '@/types/yunxiao'

export function queryHostMachines(params: {
  zone?: string
  machine_type?: string
  instance_family?: string
}) {
  // 后端为 POST 接口，筛选参数走 query string
  return apiClient.post<YunxiaoQueryResponse>('/api/v1/yunxiao/host-machines', null, { params })
}

export function queryInventory(params: {
  zone?: string
  instance_family?: string
  instance_type?: string
}) {
  return apiClient.post<YunxiaoQueryResponse>('/api/v1/yunxiao/inventory', null, { params })
}

export function searchHostMachine(keyword: string) {
  return apiClient.get<YunxiaoQueryResponse>('/api/v1/yunxiao/host-machines/search', {
    params: { keyword },
  })
}

export function syncYunxiao() {
  return apiClient.post<{ skipped: boolean; hosts?: number; inventory?: number; error?: string }>(
    '/api/v1/yunxiao/sync',
  )
}

export function getHostHistory(zone?: string, limit = 100) {
  return apiClient.get<{ items: any[]; total: number }>('/api/v1/yunxiao/host-machines/history', {
    params: { zone, limit },
  })
}
