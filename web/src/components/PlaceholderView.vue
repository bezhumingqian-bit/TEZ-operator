<template>
  <div class="placeholder">
    <el-result :icon="icon" :title="title" :sub-title="subTitle">
      <template #extra>
        <div class="placeholder__extra">
          <el-tag size="small" type="info" effect="plain">里程碑：{{ milestone }}</el-tag>
          <el-button type="primary" @click="$router.push('/hosts')">
            返回资源查询
          </el-button>
        </div>
      </template>
    </el-result>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string
    subTitle?: string
    milestone?: string
    icon?: 'info' | 'success' | 'warning' | 'error'
  }>(),
  {
    subTitle: '',
    milestone: '—',
    icon: 'info',
  },
)
</script>

<style scoped>
.placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - var(--tez-header-h));
}
.placeholder__extra {
  display: inline-flex;
  align-items: center;
  gap: 12px;
}
</style>
