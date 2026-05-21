/**
 * 接口人路由器 API 封装
 */
import apiClient from './client'

// ─────────── Types ───────────

export interface ContactInfo {
  id: number
  name: string
  display_name: string | null
  team: string | null
  role: string | null
  status: 'active' | 'vacation' | 'left'
  wecom_id: string | null
  phone: string | null
  note: string | null
  created_at: string
  updated_at: string
}

export interface RouteResult {
  category: string
  primary: ContactInfo[]
  backup: ContactInfo[]
  escalation: ContactInfo[]
  note: string | null
}

export interface RouteResponse {
  query: string
  results: RouteResult[]
  total: number
}

export interface ContactSearchResponse {
  query: string
  contacts: ContactInfo[]
  total: number
}

export interface CategoryInfo {
  id: number
  name: string
  parent_id: number | null
  description: string | null
  sort_order: number
  children: CategoryInfo[]
}

// ─────────── API Calls ───────────

/** 核心：接口人路由 — 输入场景描述，返回负责人 */
export async function routeContacts(query: string): Promise<RouteResponse> {
  const { data } = await apiClient.get<RouteResponse>('/api/v1/contacts/route', {
    params: { q: query },
  })
  return data
}

/** 模糊搜索接口人 */
export async function searchContacts(keyword: string): Promise<ContactSearchResponse> {
  const { data } = await apiClient.get<ContactSearchResponse>('/api/v1/contacts/search', {
    params: { q: keyword },
  })
  return data
}

/** 获取接口人列表 */
export async function listContacts(status?: string): Promise<ContactInfo[]> {
  const { data } = await apiClient.get<ContactInfo[]>('/api/v1/contacts', {
    params: status ? { status } : {},
  })
  return data
}

/** 获取事项分类列表 */
export async function listCategories(): Promise<CategoryInfo[]> {
  const { data } = await apiClient.get<CategoryInfo[]>('/api/v1/contacts/categories')
  return data
}
