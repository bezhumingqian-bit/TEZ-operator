<template>
  <div class="settings-page">
    <h2>个人设置</h2>

    <!-- 基本信息卡片 -->
    <el-card class="settings-card">
      <template #header>
        <span>基本信息</span>
      </template>
      <el-form label-width="80px">
        <el-form-item label="用户名">
          <el-input :model-value="authStore.user?.username" disabled />
        </el-form-item>
        <el-form-item label="角色">
          <el-tag :type="roleTagType">{{ roleLabel }}</el-tag>
        </el-form-item>
        <el-form-item label="显示名">
          <div class="settings-inline">
            <el-input v-model="displayName" placeholder="输入新显示名" />
            <el-button type="primary" :loading="savingName" @click="saveDisplayName">保存</el-button>
          </div>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 修改密码卡片 -->
    <el-card class="settings-card">
      <template #header>
        <span>修改密码</span>
      </template>
      <el-form
        ref="pwdFormRef"
        :model="pwdForm"
        :rules="pwdRules"
        label-width="100px"
      >
        <el-form-item label="当前密码" prop="old_password">
          <el-input
            v-model="pwdForm.old_password"
            type="password"
            show-password
            placeholder="输入当前密码"
          />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input
            v-model="pwdForm.new_password"
            type="password"
            show-password
            placeholder="至少 4 个字符"
          />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirm_password">
          <el-input
            v-model="pwdForm.confirm_password"
            type="password"
            show-password
            placeholder="再次输入新密码"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="savingPwd" @click="changePassword">
            修改密码
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import apiClient from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

// ─── 显示名 ───
const displayName = ref(authStore.user?.display_name || '')
const savingName = ref(false)

async function saveDisplayName() {
  if (!displayName.value.trim()) {
    ElMessage.warning('显示名不能为空')
    return
  }
  savingName.value = true
  try {
    await apiClient.put('/api/v1/auth/me/profile', { display_name: displayName.value.trim() })
    // 更新本地状态
    if (authStore.user) {
      authStore.user.display_name = displayName.value.trim()
      localStorage.setItem('tez-ops:user', JSON.stringify(authStore.user))
    }
    ElMessage.success('显示名已更新')
  } catch {
    // interceptor handles
  } finally {
    savingName.value = false
  }
}

// ─── 修改密码 ───
const pwdFormRef = ref<FormInstance>()
const savingPwd = ref(false)

const pwdForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const pwdRules: FormRules = {
  old_password: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 4, message: '至少 4 个字符', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    {
      validator: (_rule: any, value: string, callback: any) => {
        if (value !== pwdForm.new_password) {
          callback(new Error('两次密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

async function changePassword() {
  if (!pwdFormRef.value) return
  const valid = await pwdFormRef.value.validate().catch(() => false)
  if (!valid) return

  savingPwd.value = true
  try {
    await apiClient.put('/api/v1/auth/me/password', {
      old_password: pwdForm.old_password,
      new_password: pwdForm.new_password,
    })
    ElMessage.success('密码修改成功，下次登录请使用新密码')
    pwdForm.old_password = ''
    pwdForm.new_password = ''
    pwdForm.confirm_password = ''
  } catch {
    // interceptor handles
  } finally {
    savingPwd.value = false
  }
}

// ─── 角色显示 ───
const roleLabel = computed(() => {
  const map: Record<string, string> = { admin: '管理员', ops: '运维', viewer: '只读' }
  return map[authStore.role] || authStore.role
})

const roleTagType = computed(() => {
  const map: Record<string, string> = { admin: 'danger', ops: '', viewer: 'info' }
  return (map[authStore.role] || 'info') as '' | 'success' | 'warning' | 'info' | 'danger'
})
</script>

<style scoped>
.settings-page {
  padding: 24px;
  max-width: 600px;
}

.settings-page h2 {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 20px;
}

.settings-card {
  margin-bottom: 20px;
}

.settings-inline {
  display: flex;
  gap: 8px;
  width: 100%;
}

.settings-inline .el-input {
  flex: 1;
}
</style>
