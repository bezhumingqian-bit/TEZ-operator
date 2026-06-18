/** 云霄平台 — API 封装。 */
import apiClient from './client'
import type { YunxiaoQueryResponse } from '@/types/yunxiao'

export function queryHostMachines(params: {
  zone?: string
  machine_type?: string
  instance_family?: string
}) {
  return apiClient.get<YunxiaoQueryResponse>('/api/v1/yunxiao/host-machines', { params })
}

export function queryInventory(params: {
  zone?: string
  instance_family?: string
  instance_type?: string
}) {
  return apiClient.get<YunxiaoQueryResponse>('/api/v1/yunxiao/inventory', { params })
}

export function getHostHistory(zone?: string, limit = 100) {
  return apiClient.get<{ items: any[]; total: number }>('/api/v1/yunxiao/host-machines/history', {
    params: { zone, limit },
  })
}
