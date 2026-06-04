import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface RecentQuery {
  q: string
  at: number
}

const MAX_RECENT = 10
const STORAGE_KEY = 'tez-ops:recent-queries'

function loadRecent(): RecentQuery[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const arr = JSON.parse(raw) as RecentQuery[]
    return Array.isArray(arr) ? arr.slice(0, MAX_RECENT) : []
  } catch {
    return []
  }
}

function saveRecent(items: RecentQuery[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items))
  } catch {
    /* ignore quota */
  }
}

export const useAppStore = defineStore('app', () => {
  const appName = ref<string>(import.meta.env.VITE_APP_NAME || '边缘云资源运维平台')

  const recentQueries = ref<RecentQuery[]>(loadRecent())

  function pushRecentQuery(q: string) {
    const trimmed = q.trim()
    if (!trimmed) return
    const next: RecentQuery[] = [
      { q: trimmed, at: Date.now() },
      ...recentQueries.value.filter((r) => r.q !== trimmed),
    ].slice(0, MAX_RECENT)
    recentQueries.value = next
    saveRecent(next)
  }

  function clearRecentQueries() {
    recentQueries.value = []
    saveRecent([])
  }

  return {
    appName,
    recentQueries,
    pushRecentQuery,
    clearRecentQueries,
  }
})
