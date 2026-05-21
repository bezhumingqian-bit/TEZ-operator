/**
 * 知识中枢 API 封装
 */
import apiClient from './client'

export interface ArticleInfo {
  id: number
  title: string
  category: string
  summary: string | null
  tags: string | null
  url: string | null
  importance: number
}

export interface LinkInfo {
  id: number
  name: string
  purpose: string | null
  url: string
  importance: number
  category: string | null
}

export interface FAQInfo {
  id: number
  question: string
  answer: string
  category: string | null
  tags: string | null
}

export interface KnowledgeSearchResponse {
  query: string
  articles: ArticleInfo[]
  links: LinkInfo[]
  faqs: FAQInfo[]
  total: number
}

/** 全文搜索 */
export async function searchKnowledge(query: string): Promise<KnowledgeSearchResponse> {
  const { data } = await apiClient.get<KnowledgeSearchResponse>('/api/v1/knowledge/search', {
    params: { q: query },
  })
  return data
}

/** 文章列表 */
export async function listArticles(category?: string): Promise<ArticleInfo[]> {
  const { data } = await apiClient.get<ArticleInfo[]>('/api/v1/knowledge/articles', {
    params: category ? { category } : {},
  })
  return data
}

/** 平台链接列表 */
export async function listLinks(): Promise<LinkInfo[]> {
  const { data } = await apiClient.get<LinkInfo[]>('/api/v1/knowledge/links')
  return data
}

/** FAQ列表 */
export async function listFaqs(category?: string): Promise<FAQInfo[]> {
  const { data } = await apiClient.get<FAQInfo[]>('/api/v1/knowledge/faqs', {
    params: category ? { category } : {},
  })
  return data
}
