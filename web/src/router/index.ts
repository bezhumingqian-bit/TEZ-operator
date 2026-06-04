import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录', public: true },
  },
  {
    path: '/',
    redirect: '/dashboard',
  },
  {
    path: '/hosts',
    name: 'hosts',
    component: () => import('@/views/HostSearch.vue'),
    meta: { title: '资源查询', icon: 'Search', module: 'hosts' },
  },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { title: '运维驾驶舱', icon: 'DataAnalysis', module: 'dashboard' },
  },
  {
    path: '/workorder',
    name: 'workorder',
    component: () => import('@/views/WorkOrder.vue'),
    meta: { title: '工单流转', icon: 'Tickets', module: 'workorder' },
  },
  {
    path: '/demand-request',
    name: 'demand-request',
    component: () => import('@/views/DemandRequest.vue'),
    meta: { title: '需求提交表', public: true },
  },
  {
    path: '/cost',
    name: 'cost',
    component: () => import('@/views/Cost.vue'),
    meta: { title: '成本一览', icon: 'Coin', module: 'cost' },
  },
  {
    path: '/assistant',
    name: 'assistant',
    component: () => import('@/views/People.vue'),
    meta: { title: '运维助手', icon: 'MagicStick', module: 'assistant' },
  },
  {
    path: '/knowledge',
    name: 'knowledge',
    component: () => import('@/views/Knowledge.vue'),
    meta: { title: '知识库', icon: 'Reading', module: 'knowledge' },
  },
  {
    path: '/users',
    name: 'users',
    component: () => import('@/views/UserManagement.vue'),
    meta: { title: '用户管理', icon: 'UserFilled', module: 'users' },
  },
  {
    path: '/competitive',
    name: 'competitive',
    component: () => import('@/views/CompetitiveAnalysis.vue'),
    meta: { title: '竞争分析', icon: 'TrendCharts', module: 'knowledge' },
  },
  {
    path: '/ai',
    name: 'ai',
    component: () => import('@/views/AIAssistant.vue'),
    meta: { title: 'AI 助手', icon: 'ChatLineRound', module: 'users' },
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/views/Settings.vue'),
    meta: { title: '个人设置', icon: 'Setting' },
  },
  {
    // 兼容旧路径
    path: '/people',
    redirect: '/assistant',
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫：未登录跳转到 /login
router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()

  // 公开页面无需认证
  if (to.meta?.public) {
    // 已登录访问 login 页面，重定向到首页
    if (to.name === 'login' && authStore.isLoggedIn) {
      return next('/dashboard')
    }
    return next()
  }

  // 未登录 → 跳转登录
  if (!authStore.isLoggedIn) {
    return next({ path: '/login', query: { redirect: to.fullPath } })
  }

  // 权限检查：如果路由有 module 要求，检查用户是否有权限
  const requiredModule = to.meta?.module as string | undefined
  if (requiredModule && !authStore.hasPermission(requiredModule)) {
    return next('/dashboard')
  }

  next()
})

router.afterEach((to) => {
  const baseTitle = '边缘云资源运维平台'
  const t = (to.meta?.title as string | undefined) || ''
  document.title = t ? `${t} · ${baseTitle}` : baseTitle
})

export default router
