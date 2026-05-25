<template>
  <header class="app-header">
    <div class="app-header__left">
      <div class="app-header__logo" aria-hidden="true">
        <el-icon :size="22"><Cloudy /></el-icon>
      </div>
      <div class="app-header__title">{{ store.appName }}</div>
      <el-tag size="small" type="info" effect="plain" class="app-header__env"
        >内部使用 · v1.2.0</el-tag
      >
    </div>
    <div class="app-header__right">
      <el-tooltip content="问题反馈（占位）" placement="bottom">
        <el-button text :icon="ChatLineRound" />
      </el-tooltip>
      <el-dropdown trigger="click">
        <span class="app-header__user">
          <el-avatar :size="28" class="app-header__avatar">{{ avatarText }}</el-avatar>
          <span class="app-header__user-name">{{ store.currentUser.name }}</span>
          <el-icon><ArrowDown /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item disabled>身份: {{ store.currentUser.role }}</el-dropdown-item>
            <el-dropdown-item disabled>账户中心 (M2)</el-dropdown-item>
            <el-dropdown-item disabled>退出登录 (M2)</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ArrowDown, ChatLineRound, Cloudy } from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const avatarText = computed(() => (store.currentUser.name?.[0] || 'U').toUpperCase())
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
