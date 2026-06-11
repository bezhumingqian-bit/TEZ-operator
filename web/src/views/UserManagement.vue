<template>
  <div class="user-mgmt">
    <div class="user-mgmt__header">
      <h2>用户管理</h2>
      <el-button type="primary" :icon="Plus" @click="openCreateDialog">新建用户</el-button>
    </div>

    <el-table :data="users" v-loading="loading" stripe style="width: 100%">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="username" label="用户名" width="140" />
      <el-table-column prop="display_name" label="显示名" width="140" />
      <el-table-column prop="role" label="角色" width="100">
        <template #default="{ row }">
          <el-tag :type="roleTagType(row.role)" size="small">{{ roleLabel(row.role) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="is_active" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
            {{ row.is_active ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="permissions" label="权限模块">
        <template #default="{ row }">
          <el-tag
            v-for="p in row.permissions"
            :key="p"
            size="small"
            effect="plain"
            style="margin-right: 4px; margin-bottom: 2px"
          >{{ p }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="last_login_at" label="最后登录" width="160">
        <template #default="{ row }">
          {{ row.last_login_at ? formatTime(row.last_login_at) : '从未登录' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button text type="primary" size="small" @click="openEditDialog(row)">编辑</el-button>
          <el-button
            text
            type="danger"
            size="small"
            :disabled="row.username === currentUsername"
            @click="handleDelete(row)"
          >删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑用户' : '新建用户'"
      width="460px"
      destroy-on-close
    >
      <el-form
        ref="dialogFormRef"
        :model="dialogForm"
        :rules="dialogRules"
        label-width="80px"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="dialogForm.username"
            :disabled="isEdit"
            placeholder="2-50 个字符"
          />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="dialogForm.password"
            type="password"
            show-password
            :placeholder="isEdit ? '留空则不修改' : '至少 4 个字符'"
          />
        </el-form-item>
        <el-form-item label="显示名" prop="display_name">
          <el-input v-model="dialogForm.display_name" placeholder="可选" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="dialogForm.role" style="width: 100%">
            <el-option label="管理员 (admin)" value="admin" />
            <el-option label="运维 (ops)" value="ops" />
            <el-option label="只读 (viewer)" value="viewer" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="isEdit" label="状态">
          <el-switch v-model="dialogForm.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          {{ isEdit ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import apiClient from '@/api/client'
import { useAuthStore } from '@/stores/auth'

interface UserRow {
  id: number
  username: string
  display_name: string
  role: string
  is_active: boolean
  permissions: string[]
  last_login_at: string | null
}

const authStore = useAuthStore()
const currentUsername = computed(() => authStore.user?.username || '')

const loading = ref(false)
const users = ref<UserRow[]>([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const editingId = ref<number | null>(null)
const submitting = ref(false)
const dialogFormRef = ref<FormInstance>()

const dialogForm = reactive({
  username: '',
  password: '',
  display_name: '',
  role: 'viewer',
  is_active: true,
})

const dialogRules = computed<FormRules>(() => ({
  username: isEdit.value
    ? []
    : [
        { required: true, message: '请输入用户名', trigger: 'blur' },
        { min: 2, max: 50, message: '2-50 个字符', trigger: 'blur' },
      ],
  password: isEdit.value
    ? []
    : [
        { required: true, message: '请输入密码', trigger: 'blur' },
        { min: 4, message: '至少 4 个字符', trigger: 'blur' },
      ],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
}))

import { formatTime } from '@/utils/formatters'
import { roleLabel, roleTagType } from '@/utils/role'

async function fetchUsers() {
  loading.value = true
  try {
    const resp = await apiClient.get('/api/v1/auth/users')
    users.value = resp.data.items
  } catch {
    // error already handled by interceptor
  } finally {
    loading.value = false
  }
}

function openCreateDialog() {
  isEdit.value = false
  editingId.value = null
  dialogForm.username = ''
  dialogForm.password = ''
  dialogForm.display_name = ''
  dialogForm.role = 'viewer'
  dialogForm.is_active = true
  dialogVisible.value = true
}

function openEditDialog(row: UserRow) {
  isEdit.value = true
  editingId.value = row.id
  dialogForm.username = row.username
  dialogForm.password = ''
  dialogForm.display_name = row.display_name
  dialogForm.role = row.role
  dialogForm.is_active = row.is_active
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!dialogFormRef.value) return
  const valid = await dialogFormRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (isEdit.value && editingId.value) {
      const payload: Record<string, any> = {
        display_name: dialogForm.display_name,
        role: dialogForm.role,
        is_active: dialogForm.is_active,
      }
      if (dialogForm.password) {
        payload.password = dialogForm.password
      }
      await apiClient.put(`/api/v1/auth/users/${editingId.value}`, payload)
      ElMessage.success('用户已更新')
    } else {
      await apiClient.post('/api/v1/auth/users', {
        username: dialogForm.username,
        password: dialogForm.password,
        display_name: dialogForm.display_name || dialogForm.username,
        role: dialogForm.role,
      })
      ElMessage.success('用户已创建')
    }
    dialogVisible.value = false
    await fetchUsers()
  } catch {
    // error already handled
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: UserRow) {
  try {
    await ElMessageBox.confirm(
      `确定要删除用户「${row.display_name || row.username}」吗？此操作不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    await apiClient.delete(`/api/v1/auth/users/${row.id}`)
    ElMessage.success('已删除')
    await fetchUsers()
  } catch {
    // cancelled or error
  }
}

onMounted(fetchUsers)
</script>

<style scoped>
.user-mgmt {
  padding: 24px;
}

.user-mgmt__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.user-mgmt__header h2 {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
}
</style>
