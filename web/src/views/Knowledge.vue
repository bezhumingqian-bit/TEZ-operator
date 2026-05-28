<template>
  <div class="knowledge-page">
    <!-- 顶部搜索 -->
    <el-card class="search-card" shadow="never">
      <template #header>
        <div class="card-header">
          <el-icon><Reading /></el-icon>
          <span>知识中枢</span>
          <el-tag size="small" type="success">M2</el-tag>
        </div>
      </template>

      <el-input
        v-model="searchQuery"
        placeholder="搜索知识手册、SOP、机型、接口人..."
        size="large"
        clearable
        @input="handleFilter"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
    </el-card>

    <!-- 知识分类 Tab -->
    <el-tabs v-model="activeTab" class="knowledge-tabs">
      <!-- 运营手册 -->
      <el-tab-pane label="运营手册" name="manuals">
        <div class="manual-grid">
          <el-card
            v-for="manual in filteredManuals"
            :key="manual.id"
            class="manual-card"
            shadow="hover"
            @click="openManual(manual)"
          >
            <div class="manual-icon">
              <el-icon :size="32" :color="manual.color"><component :is="manual.icon" /></el-icon>
            </div>
            <div class="manual-info">
              <h4>{{ manual.title }}</h4>
              <p>{{ manual.description }}</p>
            </div>
            <el-tag :type="manual.tagType" size="small">{{ manual.tag }}</el-tag>
          </el-card>
        </div>
      </el-tab-pane>

      <!-- 平台链接 -->
      <el-tab-pane label="平台链接" name="links">
        <el-table :data="filteredLinks" stripe style="width: 100%">
          <el-table-column prop="name" label="平台" width="200">
            <template #default="{ row }">
              <div class="link-name">
                <el-icon v-if="row.importance >= 3"><Star /></el-icon>
                <span>{{ row.name }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="purpose" label="用途" min-width="300" />
          <el-table-column prop="url" label="链接" width="100">
            <template #default="{ row }">
              <el-button type="primary" link size="small" @click="openUrl(row.url)">
                打开 ↗
              </el-button>
            </template>
          </el-table-column>
          <el-table-column prop="importance" label="重要度" width="100">
            <template #default="{ row }">
              <span>{{ '⭐'.repeat(row.importance) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- FAQ -->
      <el-tab-pane label="常见问题" name="faq">
        <el-collapse v-model="activeFaq">
          <el-collapse-item
            v-for="(faq, idx) in filteredFaqs"
            :key="idx"
            :title="faq.question"
            :name="idx"
          >
            <div class="faq-answer" v-html="faq.answer"></div>
          </el-collapse-item>
        </el-collapse>
      </el-tab-pane>
    </el-tabs>

    <!-- 手册详情弹窗 -->
    <el-dialog
      v-model="manualDialogVisible"
      :title="selectedManual?.title || ''"
      width="80%"
      top="5vh"
      destroy-on-close
    >
      <div v-if="selectedManual" class="manual-detail">
        <div class="manual-meta">
          <el-tag size="small" :type="selectedManual.tagType">{{ selectedManual.tag }}</el-tag>
          <span class="meta-desc">{{ selectedManual.description }}</span>
        </div>
        <el-divider />
        <div v-loading="manualLoading" class="manual-content">
          <div v-if="manualHtml" v-html="manualHtml" class="markdown-body"></div>
          <el-empty v-else-if="!manualLoading" description="暂无内容" />
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Search, Reading, Star, Document, DataAnalysis, Setting, Connection, Coin, Grid } from '@element-plus/icons-vue'
import { getArticleContent } from '@/api/knowledge'
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt({ html: true, breaks: true, linkify: true })

const searchQuery = ref('')
const activeTab = ref('manuals')
const activeFaq = ref<number[]>([])

// ─── 知识手册数据 ───
const manuals = ref([
  { id: 1, title: 'TEZ 产品背景', description: 'TEZ与ECM/CDC/CDZ关系、网络架构、支持能力', icon: 'Document', color: '#409EFF', tag: '必读', tagType: 'danger' as const },
  { id: 2, title: '周边系统集成', description: 'CMDB表结构、vstation API、云API 3.0', icon: 'Connection', color: '#67C23A', tag: '开发', tagType: '' as const },
  { id: 3, title: 'FAQ与使用', description: '运营FAQ、调账规则、大客户坑、报价折扣', icon: 'Document', color: '#E6A23C', tag: '运营', tagType: 'warning' as const },
  { id: 4, title: '接口人与协作', description: '30+接口人清单、场景化找人指南', icon: 'Connection', color: '#F56C6C', tag: '高频', tagType: 'danger' as const },
  { id: 5, title: '机型与成本', description: '机型成本表、计费标签、规格、适配流程', icon: 'Coin', color: '#909399', tag: '成本', tagType: 'info' as const },
  { id: 6, title: '机房与可用区规划', description: '32个TEZ节点分布、25年资源规划', icon: 'Grid', color: '#409EFF', tag: '规划', tagType: '' as const },
  { id: 7, title: '资源运营SOP', description: '找机器/投放/搬迁/模块ID速查', icon: 'Setting', color: '#67C23A', tag: 'SOP', tagType: 'success' as const },
  { id: 8, title: '交接清单与权限', description: '24个待办、26个系统入口、特殊红线', icon: 'DataAnalysis', color: '#E6A23C', tag: '接手', tagType: 'warning' as const },
])

// ─── 平台链接数据（URL 从环境变量/配置加载，此处为占位）───
const platformLinks = ref([
  { name: 'ECM 运营管理系统', purpose: '资源看板、机房数据、资源预留、配额策略、账单导出', url: '#', importance: 3 },
  { name: 'CMDB 服务器查询', purpose: '按固资号/模块查服务器', url: '#', importance: 3 },
  { name: 'TCUM CMDB', purpose: '按固资号查服务器（机房/模块/IP/状态）', url: '#', importance: 3 },
  { name: '数全通-机位列表', purpose: '机架机位查询（开区交付/搬迁必用）', url: '#', importance: 3 },
  { name: '云霄平台', purpose: '云霄入口（VS调度、机型配置、库存）', url: '#', importance: 3 },
  { name: '野鹤系统', purpose: '白名单管理（可用区+APPID开白）', url: '#', importance: 3 },
  { name: '磐石', purpose: '产品管理（上下架/定价）、客户查询', url: '#', importance: 2 },
  { name: 'QCC', purpose: '机型配置、上线', url: '#', importance: 2 },
  { name: '地域系统', purpose: '可用区上线管理', url: '#', importance: 2 },
  { name: 'OBS', purpose: '成本明细', url: '#', importance: 1 },
  { name: 'QFlow', purpose: '开区流程', url: '#', importance: 2 },
  { name: 'secmyadmin', purpose: 'CMDB母机查询导出', url: '#', importance: 2 },
  { name: '安灯工具', purpose: '库存可视化', url: '#', importance: 1 },
  { name: 'njecm', purpose: '母机剩余资源、可用装箱', url: '#', importance: 2 },
])

// ─── FAQ 数据（脱敏）───
const faqs = ref([
  { question: 'TEZ 有哪些机型比较充足？', answer: '<b>25G：</b>S5（Y0-MI32-25G / CG3-25G / Y0-MI52-25G）<br><b>10G：</b>S5nt（CG3-10G）<br>不充足的是 IT5C 和裸金属系列' },
  { question: '报价怎么报？', answer: '九部单独报价，其他人报刊例价。<br>低价：底价2折起；具体按客户体量沟通。' },
  { question: '某些区域有限制吗？', answer: '部分区域存在客户独占情况，对外售卖前需确认资源占用。' },
  { question: '搬迁前需要注意什么？', answer: '1. 搬迁裸金属时需确认目标机位 sideband 属性为"否"<br>2. 提单修改属性需要1天<br>3. 投放前要清 .backup<br>4. 确认TPC<br>5. 确认模块路径' },
  { question: 'S5nt 和 ECM S4 的区别？', answer: 'TEZ的S5nt对应ECM的S4。区别是S5nt<b>肯定是CG3-10G</b>生产，而ECM的S4有三种母机（CG1/CG2/CG3）都可以。<br>如果从ECM的CG1/CG2搬过来<b>无法</b>生产S5nt。' },
  { question: '什么情况下要主动扩容？', answer: '看商机，预留20台备机。空闲机位不够时提前拉起机位扩容评估流程（SLA 1.5个月）。' },
  { question: '调账有哪些客户需要做？', answer: '多个大客户需要月度调账（ECM导出对齐+手工调整），具体清单见运营SOP。' },
])

// ─── 搜索过滤 ───
const filteredManuals = computed(() => {
  if (!searchQuery.value) return manuals.value
  const q = searchQuery.value.toLowerCase()
  return manuals.value.filter(
    m => m.title.toLowerCase().includes(q) || m.description.toLowerCase().includes(q)
  )
})

const filteredLinks = computed(() => {
  if (!searchQuery.value) return platformLinks.value
  const q = searchQuery.value.toLowerCase()
  return platformLinks.value.filter(
    l => l.name.toLowerCase().includes(q) || l.purpose.toLowerCase().includes(q)
  )
})

const filteredFaqs = computed(() => {
  if (!searchQuery.value) return faqs.value
  const q = searchQuery.value.toLowerCase()
  return faqs.value.filter(
    f => f.question.toLowerCase().includes(q) || f.answer.toLowerCase().includes(q)
  )
})

function handleFilter() {
  // 触发 computed 重新计算
}

// ─── 手册详情弹窗 ───
const manualDialogVisible = ref(false)
const selectedManual = ref<typeof manuals.value[0] | null>(null)
const manualContent = ref('')
const manualHtml = ref('')
const manualLoading = ref(false)

async function openManual(manual: typeof manuals.value[0]) {
  selectedManual.value = manual
  manualDialogVisible.value = true
  manualContent.value = ''
  manualHtml.value = ''
  manualLoading.value = true
  try {
    const resp = await getArticleContent(manual.id)
    manualContent.value = resp.content
    manualHtml.value = md.render(resp.content)
  } catch {
    manualHtml.value = '<p style="color:#f56c6c">加载失败，请稍后重试</p>'
  } finally {
    manualLoading.value = false
  }
}

function openUrl(url: string) {
  window.open(url, '_blank')
}
</script>

<style scoped>
.knowledge-page {
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

.knowledge-tabs {
  margin-top: 16px;
}

.manual-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.manual-card {
  cursor: pointer;
  transition: transform 0.2s;
  display: flex;
  flex-direction: row;
  align-items: center;
}

.manual-card:hover {
  transform: translateY(-2px);
}

.manual-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
}

.manual-icon {
  flex-shrink: 0;
}

.manual-info {
  flex: 1;
  min-width: 0;
}

.manual-info h4 {
  margin: 0 0 4px 0;
  font-size: 14px;
  font-weight: 600;
}

.manual-info p {
  margin: 0;
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.link-name {
  display: flex;
  align-items: center;
  gap: 4px;
  font-weight: 500;
}

.link-name .el-icon {
  color: #e6a23c;
}

.faq-answer {
  padding: 8px 0;
  line-height: 1.8;
  color: #606266;
}

:deep(.el-collapse-item__header) {
  font-weight: 500;
}

.manual-detail {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.manual-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.meta-desc {
  color: #909399;
  font-size: 13px;
}

.manual-content {
  max-height: 65vh;
  overflow-y: auto;
}

.markdown-body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 14px;
  line-height: 1.8;
  color: #333;
  padding: 0;
  margin: 0;
}
.markdown-body :deep(h1) { font-size: 22px; margin: 24px 0 12px; padding-bottom: 8px; border-bottom: 1px solid #eee; }
.markdown-body :deep(h2) { font-size: 18px; margin: 20px 0 10px; padding-bottom: 6px; border-bottom: 1px solid #f0f0f0; }
.markdown-body :deep(h3) { font-size: 16px; margin: 16px 0 8px; }
.markdown-body :deep(h4) { font-size: 14px; margin: 12px 0 6px; font-weight: 600; }
.markdown-body :deep(p) { margin: 8px 0; }
.markdown-body :deep(ul), .markdown-body :deep(ol) { padding-left: 20px; margin: 8px 0; }
.markdown-body :deep(li) { margin: 4px 0; }
.markdown-body :deep(table) { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 13px; }
.markdown-body :deep(th), .markdown-body :deep(td) { border: 1px solid #e4e7ed; padding: 8px 12px; text-align: left; }
.markdown-body :deep(th) { background: #f5f7fa; font-weight: 600; }
.markdown-body :deep(tr:nth-child(2n)) { background: #fafafa; }
.markdown-body :deep(code) { background: #f5f7fa; padding: 2px 6px; border-radius: 3px; font-size: 13px; font-family: 'SF Mono', Monaco, monospace; }
.markdown-body :deep(pre) { background: #f5f7fa; padding: 12px 16px; border-radius: 6px; overflow-x: auto; margin: 12px 0; }
.markdown-body :deep(pre code) { padding: 0; background: none; }
.markdown-body :deep(blockquote) { border-left: 3px solid #409eff; padding: 8px 16px; margin: 12px 0; background: #f0f5ff; color: #606266; }
.markdown-body :deep(a) { color: #409eff; text-decoration: none; }
.markdown-body :deep(a:hover) { text-decoration: underline; }
.markdown-body :deep(hr) { border: none; border-top: 1px solid #eee; margin: 16px 0; }
.markdown-body :deep(strong) { font-weight: 600; color: #303133; }

.manual-tip {
  margin-top: 8px;
}
</style>
