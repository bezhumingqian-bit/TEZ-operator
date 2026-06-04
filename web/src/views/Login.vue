<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-card__header">
        <el-icon :size="36" color="#409eff"><Cloudy /></el-icon>
        <h1 class="login-card__title">边缘云资源运维平台</h1>
        <p class="login-card__subtitle">TEZ Operator · 内部使用</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent="handleLogin"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            :prefix-icon="User"
            size="large"
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            show-password
            size="large"
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            style="width: 100%"
            @click="handleLogin"
          >
            {{ loading ? '登录中...' : '登 录' }}
          </el-button>
        </el-form-item>
      </el-form>

      <div class="login-card__footer">
        <span>请联系管理员获取账号</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Cloudy, User, Lock } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await authStore.login(form.username, form.password)
    ElMessage.success(`欢迎回来，${authStore.displayName}`)
    const redirect = (router.currentRoute.value.query.redirect as string) || '/dashboard'
    router.replace(redirect)
  } catch (err: any) {
    // apiClient 已弹出 error message，这里不重复处理
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1f2937 0%, #374151 50%, #1f2937 100%);
}

.login-card {
  width: 400px;
  padding: 40px;
  background: #fff;
  border-radius: var(--tez-radius);
  box-shadow: var(--tez-shadow-lg);
}

.login-card__header {
  text-align: center;
  margin-bottom: 32px;
}

.login-card__title {
  font-size: 22px;
  font-weight: 700;
  color: var(--tez-text-primary);
  margin: 12px 0 4px;
}

.login-card__subtitle {
  font-size: 13px;
  color: var(--tez-text-muted);
  margin: 0;
}

.login-card__footer {
  text-align: center;
  font-size: 12px;
  color: var(--tez-text-muted);
  margin-top: 16px;
}
</style>
