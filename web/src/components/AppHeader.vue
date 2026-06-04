<template>
  <header class="app-header">
    <div class="app-header__left">
      <div class="app-header__logo" aria-hidden="true">
        <el-icon :size="22"><Cloudy /></el-icon>
      </div>
      <div class="app-header__title">{{ appStore.appName }}</div>
      <el-tag size="small" type="info" effect="plain" class="app-header__env"
        >内部使用 · v1.2.0</el-tag
      >
    </div>
    <div class="app-header__right">
      <el-tooltip content="问题反馈" placement="bottom">
        <el-button text :icon="ChatLineRound" />
      </el-tooltip>
      <el-dropdown trigger="click" @command="handleCommand">
        <span class="app-header__user">
          <el-avatar :size="28" class="app-header__avatar">{{ avatarText }}</el-avatar>
          <span class="app-header__user-name">{{ authStore.displayName }}</span>
          <el-icon><ArrowDown /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item disabled>
              <el-icon><User /></el-icon>
              角色: {{ roleLabel }}
            </el-dropdown-item>
            <el-dropdown-item command="settings">
              <el-icon><Setting /></el-icon>
              个人设置
            </el-dropdown-item>
            <el-dropdown-item divided command="logout">
              <el-icon><SwitchButton /></el-icon>
              退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowDown, ChatLineRound, Cloudy, User, SwitchButton, Setting } from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'

const appStore = useAppStore()
const authStore = useAuthStore()
const router = useRouter()

const avatarText = computed(() => (authStore.displayName?.[0] || 'U').toUpperCase())

const roleLabel = computed(() => {
  const map: Record<string, string> = { admin: '管理员', ops: '运维', viewer: '只读' }
  return map[authStore.role] || authStore.role
})

function handleCommand(cmd: string) {
  if (cmd === 'logout') {
    authStore.logout()
    router.replace('/login')
  } else if (cmd === 'settings') {
    router.push('/settings')
  }
}
</script>

<style scoped>
.app-header {
  height: var(--tez-header-h);
  background: #1f2937;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 18px;
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.1);
  flex: 0 0 auto;
}

.app-header__left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.app-header__logo {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(64, 158, 255, 0.18);
  color: #67aaff;
  border-radius: 6px;
}

.app-header__title {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.app-header__env {
  margin-left: 8px;
}

.app-header__right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.app-header__user {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: #e5e7eb;
  user-select: none;
}

.app-header__avatar {
  background: #409eff;
  color: #fff;
  font-weight: 600;
}

.app-header__user-name {
  font-size: 14px;
}
</style>
