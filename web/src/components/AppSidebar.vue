<template>
  <aside class="app-sidebar">
    <el-menu
      :default-active="activeIndex"
      class="app-sidebar__menu"
      router
      background-color="#ffffff"
      text-color="#303133"
      active-text-color="#409eff"
    >
      <el-menu-item
        v-for="item in visibleMenus"
        :key="item.path"
        :index="item.path"
        :disabled="false"
      >
        <el-icon>
          <component :is="item.icon" />
        </el-icon>
        <template #title>
          <div class="app-sidebar__item">
            <span>{{ item.title }}</span>
          </div>
        </template>
      </el-menu-item>
    </el-menu>

    <div class="app-sidebar__footer">
      <div>TEZ Operator v{{ appVersion }}</div>
      <div class="app-sidebar__hint">{{ authStore.role }} · {{ authStore.displayName }}</div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { roleLabel } from '@/utils/role'

const appVersion = __APP_VERSION__

interface MenuItem {
  path: string
  title: string
  icon: string
  module: string
}

const route = useRoute()
const authStore = useAuthStore()

const allMenus: MenuItem[] = [
  { path: '/dashboard', title: '运维驾驶舱', icon: 'DataAnalysis', module: 'dashboard' },
  { path: '/hosts', title: '资源查询', icon: 'Search', module: 'hosts' },
  { path: '/water-level', title: '资源水位', icon: 'Odometer', module: 'hosts' },
  { path: '/yunxiao', title: '云霄数据', icon: 'Platform', module: 'hosts' },
  { path: '/workorder', title: '工单流转', icon: 'Tickets', module: 'workorder' },
  { path: '/cost', title: '成本一览', icon: 'Coin', module: 'cost' },
  { path: '/assistant', title: '运维助手', icon: 'MagicStick', module: 'assistant' },
  { path: '/knowledge', title: '知识库', icon: 'Reading', module: 'knowledge' },
  { path: '/competitive', title: '竞争分析', icon: 'TrendCharts', module: 'knowledge' },
  { path: '/ai', title: 'AI 助手', icon: 'ChatLineRound', module: 'users' },
  { path: '/users', title: '用户管理', icon: 'UserFilled', module: 'users' },
]

const visibleMenus = computed(() =>
  allMenus.filter((item) => authStore.hasPermission(item.module))
)

const activeIndex = computed(() => route.path)
</script>

<style scoped>
.app-sidebar {
  width: var(--tez-sidebar-w);
  flex: 0 0 var(--tez-sidebar-w);
  background: #ffffff;
  border-right: 1px solid var(--tez-border);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.app-sidebar__menu {
  border-right: none;
  flex: 1;
}

.app-sidebar__menu :deep(.el-menu-item) {
  margin: 4px 8px;
  border-radius: var(--tez-radius-sm);
  height: 40px;
  line-height: 40px;
}

.app-sidebar__menu :deep(.el-menu-item.is-active) {
  background: var(--tez-primary-light);
}

.app-sidebar__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.app-sidebar__footer {
  padding: 12px 16px;
  font-size: 12px;
  color: var(--tez-text-muted);
  border-top: 1px solid var(--tez-border);
}

.app-sidebar__hint {
  margin-top: 2px;
  color: var(--tez-text-muted);
  opacity: 0.8;
}
</style>
