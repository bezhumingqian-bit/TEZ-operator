/**
 * Axios 全局封装
 *
 * - baseURL 走 import.meta.env.VITE_API_BASE，默认 http://localhost:8000
 * - 统一拦截错误并转化为可读消息（Element Plus Message）
 * - 不在前端硬编码任何真实内网域名
 */
import axios, { AxiosError, type AxiosInstance, type AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

export interface ApiRequestConfig extends AxiosRequestConfig {
  silent?: boolean
}

interface ErrorPayload {
  detail?: unknown
  message?: unknown
  request_id?: unknown
  requestId?: unknown
}

interface ApiErrorOptions {
  status?: number
  detail?: unknown
  response?: unknown
  requestId?: string
  original?: unknown
}

export class ApiError extends Error {
  status?: number
  detail?: unknown
  response?: unknown
  requestId?: string
  original?: unknown

  constructor(message: string, options: ApiErrorOptions = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = options.status
    this.detail = options.detail
    this.response = options.response
    this.requestId = options.requestId
    this.original = options.original
    Object.setPrototypeOf(this, ApiError.prototype)
  }
}

// 开发环境：baseURL 为空，请求走 Vite proxy(/api → localhost:8000)
// 生产环境：通过 VITE_API_BASE 环境变量指定
const baseURL = import.meta.env.VITE_API_BASE || ''

const TOKEN_KEY = 'tez-ops:token'

function toMessage(value: unknown): string | undefined {
  if (typeof value === 'string' && value.trim()) return value
  if (Array.isArray(value)) {
    const messages = value.map(toMessage).filter(Boolean)
    return messages.length ? messages.join('；') : undefined
  }
  if (value && typeof value === 'object') {
    const maybe = value as { msg?: unknown; message?: unknown }
    return toMessage(maybe.msg ?? maybe.message)
  }
  return undefined
}

export const apiClient: AxiosInstance = axios.create({
  baseURL,
  timeout: 180_000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截：自动附加 Authorization header
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers = config.headers || {}
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (resp) => resp,
  (error: AxiosError<ErrorPayload>) => {
    const status = error.response?.status
    const payload = error.response?.data
    const detail = payload?.detail ?? payload?.message
    const requestIdValue = payload?.request_id ?? payload?.requestId ?? error.response?.headers?.['x-request-id']
    const requestId = typeof requestIdValue === 'string' ? requestIdValue : undefined
    let msg = toMessage(detail) || error.message || '网络错误'

    if (status === 401) {
      // token 过期或无效 → 清除本地存储，跳转登录页
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem('tez-ops:user')
      const currentPath = window.location.pathname
      if (currentPath !== '/login') {
        window.location.href = `/login?redirect=${encodeURIComponent(currentPath)}`
      }
      msg = toMessage(detail) || '登录已过期，请重新登录'
    } else if (status === 404) {
      msg = toMessage(detail) || '未找到匹配资源'
    } else if (status === 400) {
      msg = toMessage(detail) || '请求参数有误'
    } else if (status === 500) {
      msg = '服务端异常，请稍后再试'
    } else if (error.code === 'ECONNABORTED') {
      msg = '请求超时'
    }

    const apiError = new ApiError(msg, {
      status,
      detail,
      response: error.response,
      requestId,
      original: error,
    })

    // 静默选项：调用方传 silent: true 时不弹 Message
    const silent = (error.config as ApiRequestConfig | undefined)?.silent
    if (!silent) {
      ElMessage.error(msg)
    }
    return Promise.reject(apiError)
  },
)

export default apiClient
