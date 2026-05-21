<template>
  <div class="people-page">
    <!-- 顶部搜索区 -->
    <el-card class="search-card" shadow="never">
      <template #header>
        <div class="card-header">
          <el-icon><User /></el-icon>
          <span>接口人路由器</span>
          <el-tag size="small" type="success">M2</el-tag>
        </div>
      </template>

      <div class="search-area">
        <el-input
          v-model="query"
          placeholder="输入场景描述，如「母机故障」「搬迁服务器」「要机器」「IPv6」..."
          size="large"
          clearable
          @keyup.enter="handleRoute"
          class="search-input"
        >
          <template #prepend>这事找谁</template>
          <template #append>
            <el-button :icon="Search" @click="handleRoute" :loading="routeLoading" />
          </template>
        </el-input>

        <div class="quick-tags">
          <span class="tag-label">快捷：</span>
          <el-tag
            v-for="tag in quickTags"
            :key="tag"
            class="quick-tag"
            effect="plain"
            @click="quickSearch(tag)"
          >
            {{ tag }}
          </el-tag>
        </div>
      </div>
    </el-card>

    <!-- 路由结果 -->
    <div v-if="routeResults.length > 0" class="results-section">
      <el-card
        v-for="result in routeResults"
        :key="result.category"
        class="result-card"
        shadow="hover"
      >
        <template #header>
          <div class="result-header">
            <el-icon><Folder /></el-icon>
            <span class="category-name">{{ result.category }}</span>
            <el-tag v-if="result.note" size="small" type="info">{{ result.note }}</el-tag>
          </div>
        </template>

        <div class="contacts-grid">
          <!-- 主负责人 -->
          <div v-if="result.primary.length" class="contact-group">
            <div class="group-label">
              <el-tag type="danger" size="small">主负责人</el-tag>
            </div>
            <div class="contact-list">
              <div v-for="c in result.primary" :key="c.id" class="contact-item primary">
                <el-avatar :size="32" class="avatar">{{ c.name[0].toUpperCase() }}</el-avatar>
                <div class="contact-info">
                  <span class="contact-name">{{ c.name }}</span>
                  <span class="contact-meta">{{ c.team }} · {{ c.role }}</span>
                </div>
                <el-tag :type="statusTagType(c.status)" size="small">{{ statusLabel(c.status) }}</el-tag>
              </div>
            </div>
          </div>

          <!-- 备份接口人 -->
          <div v-if="result.backup.length" class="contact-group">
            <div class="group-label">
              <el-tag type="warning" size="small">备份</el-tag>
            </div>
            <div class="contact-list">
              <div v-for="c in result.backup" :key="c.id" class="contact-item backup">
                <el-avatar :size="28" class="avatar">{{ c.name[0].toUpperCase() }}</el-avatar>
                <div class="contact-info">
                  <span class="contact-name">{{ c.name }}</span>
                  <span class="contact-meta">{{ c.team }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 升级路径 -->
          <div v-if="result.escalation.length" class="contact-group">
            <div class="group-label">
              <el-tag type="info" size="small">升级路径</el-tag>
            </div>
            <div class="contact-list">
              <div v-for="(c, idx) in result.escalation" :key="c.id" class="contact-item escalation">
                <span class="level-badge">L{{ idx + 1 }}</span>
                <span class="contact-name">{{ c.name }}</span>
                <span class="contact-meta">{{ c.role }}</span>
              </div>
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 无结果提示 -->
    <el-empty v-else-if="searched && routeResults.length === 0" description="未匹配到相关接口人，试试换个关键词？" />

    <!-- 分割线 -->
    <el-divider v-if="routeResults.length > 0 || searched" />

    <!-- 接口人通讯录 -->
    <el-card class="directory-card" shadow="never">
      <template #header>
        <div class="card-header">
          <el-icon><Notebook /></el-icon>
          <span>通讯录</span>
          <el-input
            v-model="searchKeyword"
            placeholder="搜索姓名/团队/职责..."
            size="small"
            clearable
            style="width: 240px; margin-left: auto"
            @input="handleSearch"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </div>
      </template>

      <el-table :data="displayContacts" stripe style="width: 100%" max-height="500">
        <el-table-column prop="name" label="英文名" width="140" />
        <el-table-column prop="team" label="团队" width="120" />
        <el-table-column prop="role" label="职责" min-width="200" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Search, User, Folder, Notebook } from '@element-plus/icons-vue'
import {
  routeContacts,
  searchContacts,
  listContacts,
  type ContactInfo,
  type RouteResult,
} from '@/api/contacts'

const query = ref('')
const routeLoading = ref(false)
const routeResults = ref<RouteResult[]>([])
const searched = ref(false)

const searchKeyword = ref('')
const allContacts = ref<ContactInfo[]>([])
const filteredContacts = ref<ContactInfo[]>([])
const displayContacts = ref<ContactInfo[]>([])

const quickTags = ['母机故障', '搬迁', '要机器', 'IPv6', '机型改造', '配额', '机位扩容', '开区']

// ─── 路由查询 ───
async function handleRoute() {
  if (!query.value.trim()) return
  routeLoading.value = true
  searched.value = true
  try {
    const resp = await routeContacts(query.value.trim())
    routeResults.value = resp.results.filter(r => r.primary.length > 0 || r.backup.length > 0)
  } catch {
    routeResults.value = []
  } finally {
    routeLoading.value = false
  }
}

function quickSearch(tag: string) {
  query.value = tag
  handleRoute()
}

// ─── 通讯录搜索 ───
async function handleSearch() {
  const kw = searchKeyword.value.trim()
  if (!kw) {
    displayContacts.value = allContacts.value
    return
  }
  try {
    const resp = await searchContacts(kw)
    displayContacts.value = resp.contacts
  } catch {
    displayContacts.value = allContacts.value
  }
}

// ─── 工具 ───
function statusTagType(status: string) {
  if (status === 'active') return 'success'
  if (status === 'vacation') return 'warning'
  return 'info'
}

function statusLabel(status: string) {
  if (status === 'active') return '在岗'
  if (status === 'vacation') return '休假'
  return '离职'
}

// ─── 初始化 ───
onMounted(async () => {
  try {
    allContacts.value = await listContacts()
    displayContacts.value = allContacts.value
  } catch {
    // silent
  }
})
</script>

<style scoped>
.people-page {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.search-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
}

.search-area {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.search-input {
  width: 100%;
}

.quick-tags {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.tag-label {
  color: #909399;
  font-size: 13px;
}

.quick-tag {
  cursor: pointer;
  transition: all 0.2s;
}

.quick-tag:hover {
  transform: scale(1.05);
  color: var(--el-color-primary);
}

.results-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
}

.result-card {
  border-left: 3px solid var(--el-color-primary);
}

.result-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.category-name {
  font-weight: 600;
  font-size: 15px;
}

.contacts-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.contact-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.group-label {
  margin-bottom: 4px;
}

.contact-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.contact-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  background: #f5f7fa;
  min-width: 200px;
}

.contact-item.primary {
  background: #fef0f0;
  border: 1px solid #fde2e2;
}

.contact-item.backup {
  background: #fdf6ec;
  border: 1px solid #faecd8;
}

.contact-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.contact-name {
  font-weight: 600;
  font-size: 14px;
}

.contact-meta {
  font-size: 12px;
  color: #909399;
}

.avatar {
  background: var(--el-color-primary);
  color: white;
  font-size: 14px;
}

.level-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #909399;
  color: white;
  font-size: 11px;
  font-weight: bold;
}

.directory-card {
  margin-top: 20px;
}
</style>
