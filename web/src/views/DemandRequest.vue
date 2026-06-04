<template>
  <div class="demand-page">
    <div class="demand-card">
      <div class="demand-header">
        <h1>TEZ 搬迁需求提单</h1>
        <p>请填写以下信息，运维团队将尽快处理您的搬迁需求</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="130px"
        label-position="top"
        class="demand-form"
        :disabled="submitted"
      >
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="提单人姓名" prop="requester">
              <el-input v-model="form.requester" placeholder="请输入您的姓名" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系方式" prop="contact">
              <el-input v-model="form.contact" placeholder="企微ID 或 手机号" clearable />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="来源区域">
              <el-select v-model="form.source_zone" filterable clearable placeholder="选择或搜索区域（可不填）" style="width:100%">
                <el-option v-for="z in zoneOptions" :key="z.zone" :label="`${z.zone}（${z.city}）`" :value="z.zone" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="目标区域" prop="target_zone">
              <el-select v-model="form.target_zone" filterable placeholder="选择或搜索区域" style="width:100%">
                <el-option v-for="z in zoneOptions" :key="z.zone" :label="`${z.zone}（${z.city}）`" :value="z.zone" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="设备数量" prop="device_count">
              <el-input-number v-model="form.device_count" :min="1" :max="10000" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="机型要求" prop="machine_type">
              <el-select v-model="form.machine_type" filterable allow-create placeholder="选择或输入机型" style="width:100%">
                <el-option label="S5nt" value="S5nt" />
                <el-option label="SN3ne" value="SN3ne" />
                <el-option label="IT5" value="IT5" />
                <el-option label="IT5c" value="IT5c" />
                <el-option label="BMD3c" value="BMD3c" />
                <el-option label="BMD3s" value="BMD3s" />
                <el-option label="不限" value="不限" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="期望完成时间">
              <el-date-picker v-model="form.expected_date" type="date" placeholder="选择日期" value-format="YYYY-MM-DD" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="AppID / 客户名">
              <el-input v-model="form.appid" placeholder="AppID 或客户名称" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="业务用途说明">
              <el-input v-model="form.purpose" placeholder="简要描述业务用途" clearable />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="3" placeholder="其他需要补充的信息" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" size="large" @click="onSubmit" :loading="loading" :disabled="submitted">
            提交需求
          </el-button>
          <el-button size="large" @click="onReset" :disabled="submitted">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 成功提示 -->
      <div v-if="submitted" class="demand-success">
        <el-result icon="success" title="需求已提交" :sub-title="`需求编号：${orderNo}`">
          <template #extra>
            <p style="color:#6b7280; margin-bottom:16px">运维团队将尽快处理，如有疑问请通过上方联系方式沟通</p>
            <el-button type="primary" @click="onNewRequest">提交新需求</el-button>
          </template>
        </el-result>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE || ''

const formRef = ref<FormInstance>()
const loading = ref(false)
const submitted = ref(false)
const orderNo = ref('')

interface ZoneOption { zone: string; city: string }
const zoneOptions = ref<ZoneOption[]>([])

const form = reactive({
  requester: '',
  contact: '',
  source_zone: '',
  target_zone: '',
  device_count: 1,
  machine_type: '',
  appid: '',
  expected_date: '',
  purpose: '',
  remark: '',
})

const rules: FormRules = {
  requester: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  contact: [{ required: true, message: '请输入联系方式', trigger: 'blur' }],
  target_zone: [{ required: true, message: '请选择目标区域', trigger: 'change' }],
  device_count: [{ required: true, message: '请输入数量', trigger: 'blur' }],
}

onMounted(async () => {
  try {
    const { data } = await axios.get<ZoneOption[]>(`${API_BASE}/api/v1/zones/options`)
    zoneOptions.value = data
  } catch {
    ElMessage.warning('加载区域列表失败')
  }
})

async function onSubmit() {
  if (!formRef.value) return
  await formRef.value.validate()

  loading.value = true
  try {
    const { data } = await axios.post(`${API_BASE}/api/v1/workorders/demand`, {
      requester: form.requester,
      contact: form.contact,
      source_zone: form.source_zone,
      target_zone: form.target_zone,
      device_count: form.device_count,
      machine_type: form.machine_type,
      appid: form.appid,
      expected_date: form.expected_date,
      purpose: form.purpose,
      remark: form.remark,
    })
    orderNo.value = data.order_no
    submitted.value = true
    ElMessage.success('需求提交成功！')
  } catch (e: any) {
    const msg = e?.response?.data?.detail || '提交失败，请稍后重试'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

function onReset() {
  formRef.value?.resetFields()
}

function onNewRequest() {
  submitted.value = false
  orderNo.value = ''
  formRef.value?.resetFields()
}
</script>

<style scoped>
.demand-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #f0f5ff 0%, #e8f4f8 100%);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 40px 20px;
}

.demand-card {
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.06);
  padding: 40px 48px;
  max-width: 800px;
  width: 100%;
}

.demand-header {
  text-align: center;
  margin-bottom: 32px;
  padding-bottom: 24px;
  border-bottom: 1px solid #f3f4f6;
}

.demand-header h1 {
  font-size: 24px;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 8px;
}

.demand-header p {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}

.demand-form :deep(.el-form-item__label) {
  font-weight: 500;
  color: #374151;
}

.demand-success {
  margin-top: -20px;
}
</style>
