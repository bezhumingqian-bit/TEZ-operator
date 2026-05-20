/**
 * Axios 全局封装
 *
 * - baseURL 走 import.meta.env.VITE_API_BASE，默认 http://localhost:8000
 * - 统一拦截错误并转化为可读消息（Element Plus Message）
 * - 不在前端硬编码任何真实内网域名
 */
import axios, { AxiosError, type AxiosInstance, type AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

const baseURL = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export const apiClient: AxiosInstance = axios.create({
  baseURL,
  timeout: 30_000,
  headers: {
    'Content-Type': 'application/json',
  },
})

apiClient.interceptors.response.use(
  (resp) => resp,
  (error: AxiosError<{ detail?: string; message?: string }>) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail || error.response?.data?.message
    let msg = detail || error.message || '网络错误'

    if (status === 404) {
      msg = detail || '未找到匹配资源'
    } else if (status === 400) {
      msg = detail || '请求参数有误'
    } else if (status === 500) {
      msg = '服务端异常，请稍后再试'
    } else if (error.code === 'ECONNABORTED') {
      msg = '请求超时'
    }

    // 静默选项：调用方传 silent: true 时不弹 Message
    const silent = (error.config as AxiosRequestConfig & { silent?: boolean })?.silent
    if (!silent) {
      ElMessage.error(msg)
    }
    return Promise.reject(new Error(msg))
  },
)

export default apiClient
