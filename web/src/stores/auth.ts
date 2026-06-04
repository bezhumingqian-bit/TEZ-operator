/**
 * 认证状态管理
 *
 * 管理 token、用户信息、权限，提供 login/logout actions。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '@/api/client'

export interface UserInfo {
  id: number
  username: string
  display_name: string
  role: string
  permissions: string[]
}

const TOKEN_KEY = 'tez-ops:token'
const USER_KEY = 'tez-ops:user'

function loadToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}

function loadUser(): UserInfo | null {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(loadToken())
  const user = ref<UserInfo | null>(loadUser())

  const isLoggedIn = computed(() => !!token.value && !!user.value)
  const permissions = computed(() => user.value?.permissions || [])
  const role = computed(() => user.value?.role || '')
  const displayName = computed(() => user.value?.display_name || user.value?.username || '')

  function hasPermission(module: string): boolean {
    return permissions.value.includes(module)
  }

  async function login(username: string, password: string): Promise<void> {
    const resp = await apiClient.post('/api/v1/auth/login', { username, password })
    const data = resp.data
    token.value = data.token
    user.value = data.user as UserInfo
    localStorage.setItem(TOKEN_KEY, data.token)
    localStorage.setItem(USER_KEY, JSON.stringify(data.user))
  }

  async function fetchMe(): Promise<void> {
    try {
      const resp = await apiClient.get('/api/v1/auth/me')
      user.value = resp.data as UserInfo
      localStorage.setItem(USER_KEY, JSON.stringify(resp.data))
    } catch {
      // token 无效，清除登录态
      logout()
    }
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  }

  return {
    token,
    user,
    isLoggedIn,
    permissions,
    role,
    displayName,
    hasPermission,
    login,
    fetchMe,
    logout,
  }
})
