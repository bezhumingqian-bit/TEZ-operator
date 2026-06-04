<template>
  <el-config-provider>
    <!-- 公开页面（登录/提单）：无 header/sidebar 布局 -->
    <router-view v-if="isPublicPage" />

    <!-- 主布局：header + sidebar + content -->
    <div v-else class="layout">
      <AppHeader />
      <div class="layout__body">
        <AppSidebar />
        <main class="layout__main">
          <router-view v-slot="{ Component }">
            <transition name="fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </main>
      </div>
    </div>
  </el-config-provider>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'
import AppSidebar from '@/components/AppSidebar.vue'

const route = useRoute()
const isPublicPage = computed(() => route.meta?.public === true)
</script>

<style scoped>
.layout {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
}

.layout__body {
  flex: 1;
  display: flex;
  min-height: 0;
}

.layout__main {
  flex: 1;
  min-width: 0;
  overflow: auto;
  background: var(--tez-bg);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.18s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
