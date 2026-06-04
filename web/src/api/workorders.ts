/**
 * 工单流 API 封装
 */
import apiClient from './client'

export interface OrderDetail {
  asset_ids?: string
  zone?: string
  module_path?: string
  target_idc?: string
  target_cabinet?: string
  description?: string
  [key: string]: unknown
}

export interface OrderLogInfo {
  id: number
  action: string
  operator: string
  content: string | null
  from_status: string | null
  to_status: string | null
  created_at: string
}

export interface OrderInfo {
  id: number
  order_no: string
  order_type: string
  title: string
  status: string
  creator: string
  assignee: string | null
  detail: OrderDetail | null
  pre_checks: Record<string, { passed: boolean; message: string }> | null
  note: string | null
  priority: number
  created_at: string
  updated_at: string
  completed_at: string | null
  logs: OrderLogInfo[]
}

export interface OrderListResponse {
  items: OrderInfo[]
  total: number
}

export interface StatsResponse {
  submitted: number
  pending: number
  processing: number
  verifying: number
  completed: number
  rejected: number
  total: number
}

/** 创建工单 */
export async function createOrder(data: {
  order_type: string
  title: string
  creator: string
  detail?: OrderDetail
  note?: string
  priority?: number
}): Promise<OrderInfo & { push_success?: boolean; push_error?: string }> {
  const { data: resp } = await apiClient.post<OrderInfo & { push_success?: boolean; push_error?: string }>('/api/v1/workorders', data)
  return resp
}

/** 工单列表 */
export async function listOrders(params?: {
  status?: string
  order_type?: string
  creator?: string
  assignee?: string
  limit?: number
  offset?: number
}): Promise<OrderListResponse> {
  const { data } = await apiClient.get<OrderListResponse>('/api/v1/workorders', { params })
  return data
}

/** 工单统计 */
export async function getOrderStats(): Promise<StatsResponse> {
  const { data } = await apiClient.get<StatsResponse>('/api/v1/workorders/stats')
  return data
}

/** 工单详情 */
export async function getOrder(orderId: number): Promise<OrderInfo> {
  const { data } = await apiClient.get<OrderInfo>(`/api/v1/workorders/${orderId}`)
  return data
}

/** 状态流转 */
export async function transitionOrder(orderId: number, body: {
  to_status: string
  operator: string
  comment?: string
}): Promise<OrderInfo> {
  const { data } = await apiClient.post<OrderInfo>(`/api/v1/workorders/${orderId}/transition`, body)
  return data
}

/** 删除工单 */
export async function deleteOrder(orderId: number): Promise<void> {
  await apiClient.delete(`/api/v1/workorders/${orderId}`)
}
