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
        v-for="item in menus"
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
            <el-tag
              v-if="item.milestone"
              size="small"
              effect="plain"
              type="info"
              class="app-sidebar__tag"
              >{{ item.milestone }}</el-tag
            >
          </div>
        </template>
      </el-menu-item>
    </el-menu>

    <div class="app-sidebar__footer">
      <div>M1 资源查询 · M2 运维助手</div>
      <div class="app-sidebar__hint">M3 工单流 · M4 驾驶舱</div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

interface MenuItem {
  path: string
  title: string
  icon: string
  milestone?: string
}

const route = useRoute()

const menus: MenuItem[] = [
  { path: '/hosts', title: '资源查询', icon: 'Search' },
  { path: '/assistant', title: '运维助手', icon: 'MagicStick' },
  { path: '/dashboard', title: '运维驾驶舱', icon: 'DataAnalysis', milestone: 'M4' },
  { path: '/workorder', title: '工单流转', icon: 'Tickets', milestone: 'M3' },
]

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
  border-radius: 4px;
  height: 40px;
  line-height: 40px;
}

.app-sidebar__menu :deep(.el-menu-item.is-active) {
  background: rgba(64, 158, 255, 0.1);
}

.app-sidebar__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.app-sidebar__tag {
  margin-left: 8px;
}

.app-sidebar__footer {
  padding: 12px 16px;
  font-size: 12px;
  color: var(--tez-text-secondary);
  border-top: 1px solid var(--tez-border);
}

.app-sidebar__hint {
  margin-top: 2px;
  color: var(--tez-text-secondary);
  opacity: 0.8;
}
</style>
