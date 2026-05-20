import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/hosts',
  },
  {
    path: '/hosts',
    name: 'hosts',
    component: () => import('@/views/HostSearch.vue'),
    meta: { title: '资源查询', icon: 'Search', module: 4 },
  },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { title: '运维驾驶舱', icon: 'DataAnalysis', module: 1, milestone: 'M4' },
  },
  {
    path: '/workorder',
    name: 'workorder',
    component: () => import('@/views/WorkOrder.vue'),
    meta: { title: '工单流转', icon: 'Tickets', module: 2, milestone: 'M3' },
  },
  {
    path: '/people',
    name: 'people',
    component: () => import('@/views/People.vue'),
    meta: { title: '接口人路由器', icon: 'User', module: 3, milestone: 'M2' },
  },
  {
    path: '/knowledge',
    name: 'knowledge',
    component: () => import('@/views/Knowledge.vue'),
    meta: { title: '知识中枢', icon: 'Reading', module: 5, milestone: 'M2' },
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/hosts',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((to) => {
  const baseTitle = '边缘云资源运维平台'
  const t = (to.meta?.title as string | undefined) || ''
  document.title = t ? `${t} · ${baseTitle}` : baseTitle
})

export default router
