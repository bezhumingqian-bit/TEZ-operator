<template>
  <el-config-provider>
    <div class="layout">
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
import AppHeader from '@/components/AppHeader.vue'
import AppSidebar from '@/components/AppSidebar.vue'
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
