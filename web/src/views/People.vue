<template>
  <div class="assistant-page">
    <!-- 搜索区 -->
    <div class="search-section">
      <h2 class="page-title">
        <el-icon><Search /></el-icon>
        运维助手
      </h2>
      <p class="page-desc">输入问题，3 秒得到答案：找谁、怎么做、去哪操作</p>

      <el-input
        v-model="query"
        placeholder="例：母机故障 / 搬迁 / 要机器 / 开区 / IPv6..."
        size="large"
        clearable
        class="search-input"
        @keyup.enter="handleSearch"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
        <template #append>
          <el-button @click="handleSearch" :loading="loading">搜索</el-button>
        </template>
      </el-input>
    </div>

    <!-- 搜索结果区 -->
    <div v-if="hasResults" class="results-section">
      <!-- 接口人结果 -->
      <div v-if="contactResults.length" class="result-block">
        <h3 class="block-title"><el-icon><User /></el-icon> 找谁</h3>
        <div class="contact-results">
          <div v-for="result in contactResults" :key="result.category" class="contact-card">
            <div class="card-header">{{ result.category }}</div>
            <div class="card-body">
              <div v-for="c in result.primary" :key="c.id" class="contact-row primary">
                <el-tag type="danger" size="small">主</el-tag>
                <a class="name clickable" @click="openWecom(c.name)" :title="'点击打开企微聊天：' + c.name">{{ c.name }}</a>
                <span class="role">{{ c.team }} · {{ c.role }}</span>
              </div>
              <div v-for="c in result.backup" :key="c.id" class="contact-row backup">
                <el-tag type="warning" size="small">备</el-tag>
                <a class="name clickable" @click="openWecom(c.name)" :title="'点击打开企微聊天：' + c.name">{{ c.name }}</a>
                <span class="role">{{ c.team }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- SOP/文章结果 -->
      <div v-if="articleResults.length" class="result-block">
        <h3 class="block-title"><el-icon><Document /></el-icon> 怎么做</h3>
        <div class="article-results">
          <el-card
            v-for="art in articleResults"
            :key="art.id"
            shadow="hover"
            class="article-card"
            @click="openArticle(art)"
          >
            <div class="article-title">{{ art.title }}</div>
            <div class="article-summary">{{ art.summary }}</div>
            <el-tag v-if="art.tags" size="small" type="info">{{ art.tags?.split(',')[0] }}</el-tag>
          </el-card>
        </div>
      </div>

      <!-- 平台链接结果 -->
      <div v-if="linkResults.length" class="result-block">
        <h3 class="block-title"><el-icon><Link /></el-icon> 去哪操作</h3>
        <div class="link-results">
          <el-button
            v-for="link in linkResults"
            :key="link.id"
            @click="openUrl(link.url)"
            class="link-btn"
          >
            {{ link.name }}
            <el-icon class="el-icon--right"><TopRight /></el-icon>
          </el-button>
        </div>
      </div>

      <!-- FAQ 结果 -->
      <div v-if="faqResults.length" class="result-block">
        <h3 class="block-title"><el-icon><QuestionFilled /></el-icon> 常见问答</h3>
        <el-collapse>
          <el-collapse-item v-for="faq in faqResults" :key="faq.id" :title="faq.question">
            <div v-html="faq.answer" class="faq-answer"></div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </div>

    <!-- 无结果 -->
    <el-empty v-else-if="searched && !hasResults" description="没找到相关内容，试试换个关键词？" />

    <!-- 快捷场景区（未搜索时展示）-->
    <div v-if="!searched" class="scenes-section">
      <!-- 热门搜索 -->
      <div class="hot-tags">
        <span class="hot-label">热门：</span>
        <el-tag
          v-for="tag in hotTags"
          :key="tag"
          size="small"
          effect="plain"
          class="hot-tag"
          @click="query = tag; handleSearch()"
        >{{ tag }}</el-tag>
      </div>

      <h3 class="section-title">高频场景</h3>
      <div class="scene-grid">
        <div
          v-for="scene in scenes"
          :key="scene.title"
          class="scene-card"
          @click="enterScene(scene)"
        >
          <div class="scene-icon">{{ scene.icon }}</div>
          <div class="scene-info">
            <div class="scene-title">{{ scene.title }}</div>
            <div class="scene-desc">{{ scene.desc }}</div>
          </div>
        </div>
      </div>

      <!-- 平台导航 -->
      <h3 class="section-title" style="margin-top: 32px">平台导航</h3>
      <div class="platform-grid">
        <div v-for="group in platformGroups" :key="group.label" class="platform-group">
          <div class="group-label">{{ group.label }}</div>
          <div class="group-links">
            <el-button
              v-for="link in group.links"
              :key="link.name"
              size="small"
              @click="openUrl(link.url)"
              class="platform-btn"
            >
              {{ link.name }}
              <el-icon v-if="link.importance >= 3" class="star"><Star /></el-icon>
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 文章详情弹窗 -->
    <el-dialog
      v-model="articleDialogVisible"
      :title="selectedArticle?.title || ''"
      width="80%"
      top="5vh"
      destroy-on-close
    >
      <div v-loading="articleLoading" class="article-content">
        <div v-if="articleHtml" v-html="articleHtml" class="markdown-body"></div>
        <el-empty v-else-if="!articleLoading" description="暂无内容" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Search, User, Document, Link, TopRight, Star, QuestionFilled } from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import { routeContacts, type RouteResult } from '@/api/contacts'
import { searchKnowledge, getArticleContent, listLinks, type ArticleInfo, type LinkInfo, type FAQInfo } from '@/api/knowledge'

const md = new MarkdownIt({ html: true, breaks: true, linkify: true })

const query = ref('')
const loading = ref(false)
const searched = ref(false)

// 搜索结果
const contactResults = ref<RouteResult[]>([])
const articleResults = ref<ArticleInfo[]>([])
const linkResults = ref<LinkInfo[]>([])
const faqResults = ref<FAQInfo[]>([])

const hasResults = computed(() =>
  contactResults.value.length > 0 ||
  articleResults.value.length > 0 ||
  linkResults.value.length > 0 ||
  faqResults.value.length > 0
)

// 文章弹窗
const articleDialogVisible = ref(false)
const selectedArticle = ref<ArticleInfo | null>(null)
const articleHtml = ref('')
const articleLoading = ref(false)

// ─── 搜索 ───
async function handleSearch() {
  const q = query.value.trim()
  if (!q) return
  loading.value = true
  searched.value = true

  try {
    // 并发请求接口人 + 知识
    const [contactResp, knowledgeResp] = await Promise.allSettled([
      routeContacts(q),
      searchKnowledge(q),
    ])

    if (contactResp.status === 'fulfilled') {
      contactResults.value = contactResp.value.results.filter(r => r.primary.length > 0 || r.backup.length > 0)
    } else {
      contactResults.value = []
    }

    if (knowledgeResp.status === 'fulfilled') {
      articleResults.value = knowledgeResp.value.articles
      linkResults.value = knowledgeResp.value.links
      faqResults.value = knowledgeResp.value.faqs
    } else {
      articleResults.value = []
      linkResults.value = []
      faqResults.value = []
    }
  } finally {
    loading.value = false
  }
}

// ─── 快捷场景 ───
const hotTags = ['母机故障', '搬迁', '投放', '开区', '调账', '机型成本', '重装', 'IPv6']

const scenes = [
  { icon: '🔧', title: '母机故障', desc: '故障排查 → 值班运维 → 上升', keyword: '母机故障' },
  { icon: '🚚', title: '搬迁服务器', desc: '出入库 → 提单 → 模块转移', keyword: '搬迁' },
  { icon: '📦', title: '要机器', desc: 'CVM/异构/运管 → 云霄查空闲', keyword: '要机器' },
  { icon: '🌐', title: '开新区', desc: '需求确认 → 开区流程 → 部署', keyword: '开区' },
  { icon: '🔀', title: 'IPv6', desc: '母机支持 + VPC适配 + 网平实施', keyword: 'IPv6' },
  { icon: '💰', title: '成本/报价', desc: '机型成本 + 报价规则', keyword: '成本' },
  { icon: '⚙️', title: '机型改造', desc: '评估 → 执行 → 上线', keyword: '机型改造' },
  { icon: '📐', title: '机位扩容', desc: '评估供应商 → 建设 → 交付', keyword: '机位扩容' },
]

function enterScene(scene: typeof scenes[0]) {
  query.value = scene.keyword
  handleSearch()
}

// ─── 平台导航（从 API 加载）───
const platformGroups = ref([
  { label: '资源查询', links: [] as {name: string; url: string; importance: number}[] },
  { label: '运营管理', links: [] as {name: string; url: string; importance: number}[] },
  { label: '流程工具', links: [] as {name: string; url: string; importance: number}[] },
])

onMounted(async () => {
  try {
    const links = await listLinks()
    // 按关键词分组
    const queryKeywords = ['CMDB', 'TCUM', '数全通', '云霄', 'secmyadmin', 'njecm']
    const opsKeywords = ['ECM', '磐石', 'OBS', '安灯']
    const flowKeywords = ['野鹤', 'QFlow', 'QCC', '地域']

    for (const link of links) {
      const item = { name: link.name, url: link.url, importance: link.importance }
      if (queryKeywords.some(k => link.name.includes(k))) {
        platformGroups.value[0].links.push(item)
      } else if (opsKeywords.some(k => link.name.includes(k))) {
        platformGroups.value[1].links.push(item)
      } else {
        platformGroups.value[2].links.push(item)
      }
    }
  } catch {
    // 静态 fallback
  }
})

// ─── 文章详情 ───
async function openArticle(art: ArticleInfo) {
  selectedArticle.value = art
  articleDialogVisible.value = true
  articleHtml.value = ''
  articleLoading.value = true
  try {
    const resp = await getArticleContent(art.id)
    articleHtml.value = md.render(resp.content)
  } catch {
    articleHtml.value = '<p style="color: #f56c6c">加载失败</p>'
  } finally {
    articleLoading.value = false
  }
}

function openUrl(url: string) {
  if (!url || url === '#' || url.startsWith('#')) {
    import('element-plus').then(({ ElMessage }) => {
      ElMessage.info('该链接需在 .env 中配置真实内网地址后方可跳转')
    })
    return
  }
  window.open(url, '_blank')
}

function openWecom(username: string) {
  // 企业微信 URL Scheme：直接打开与该用户的聊天窗口
  window.location.href = `wxwork://message?username=${username}`
}
</script>

<style scoped>
.assistant-page {
  padding: 24px;
  max-width: 1100px;
  margin: 0 auto;
}

.search-section {
  text-align: center;
  padding: 40px 0 24px;
  background: linear-gradient(180deg, #f0f5ff 0%, transparent 100%);
  border-radius: 12px;
  margin: -24px -24px 0;
  padding-left: 24px;
  padding-right: 24px;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-bottom: 8px;
}

.page-desc {
  color: #909399;
  margin-bottom: 20px;
}

.search-input {
  max-width: 700px;
  margin: 0 auto;
}

/* 搜索结果 */
.results-section {
  margin-top: 24px;
}

.result-block {
  margin-bottom: 24px;
}

.block-title {
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
  color: #303133;
}

.contact-results {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.contact-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  overflow: hidden;
}

.contact-card .card-header {
  background: #f5f7fa;
  padding: 8px 12px;
  font-weight: 600;
  font-size: 13px;
  color: #606266;
}

.contact-card .card-body {
  padding: 8px 12px;
}

.contact-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.contact-row .name {
  font-weight: 600;
  font-size: 14px;
}

.contact-row .name.clickable {
  color: var(--el-color-primary);
  cursor: pointer;
  text-decoration: none;
}

.contact-row .name.clickable:hover {
  text-decoration: underline;
}

.contact-row .role {
  color: #909399;
  font-size: 12px;
}

.article-results {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.article-card {
  cursor: pointer;
  transition: transform 0.15s;
}

.article-card:hover {
  transform: translateY(-2px);
}

.article-title {
  font-weight: 600;
  margin-bottom: 4px;
}

.article-summary {
  font-size: 13px;
  color: #909399;
  margin-bottom: 6px;
}

.link-results {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.link-btn {
  font-size: 13px;
}

.faq-answer {
  line-height: 1.8;
  color: #606266;
}

/* 快捷场景 */
.scenes-section {
  margin-top: 32px;
}

.hot-tags {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 24px;
  padding: 12px 16px;
  background: #fafafa;
  border-radius: 8px;
}
.hot-label {
  font-size: 13px;
  color: #909399;
}
.hot-tag {
  cursor: pointer;
  transition: all 0.2s;
}
.hot-tag:hover {
  color: var(--el-color-primary);
  border-color: var(--el-color-primary);
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 16px;
  color: #303133;
}

.scene-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}

.scene-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border: 1px solid #ebeef5;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  background: #fff;
}

.scene-card:hover {
  border-color: var(--el-color-primary);
  box-shadow: 0 4px 16px rgba(64, 158, 255, 0.12);
  transform: translateY(-3px);
}

.scene-icon {
  font-size: 32px;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: #f5f7fa;
  flex-shrink: 0;
}

.scene-title {
  font-weight: 600;
  font-size: 14px;
}

.scene-desc {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

/* 平台导航 */
.platform-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.platform-group {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.group-label {
  min-width: 80px;
  font-weight: 600;
  font-size: 13px;
  color: #606266;
  padding-top: 6px;
}

.group-links {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.platform-btn .star {
  color: #e6a23c;
  margin-left: 4px;
}

/* 文章弹窗 */
.article-content {
  max-height: 70vh;
  overflow-y: auto;
  padding: 0 8px;
}

.markdown-body {
  font-size: 14px;
  line-height: 1.8;
  color: #303133;
}

.markdown-body :deep(h1) { font-size: 22px; margin: 24px 0 12px; border-bottom: 1px solid #ebeef5; padding-bottom: 8px; }
.markdown-body :deep(h2) { font-size: 18px; margin: 20px 0 10px; }
.markdown-body :deep(h3) { font-size: 15px; margin: 16px 0 8px; }
.markdown-body :deep(table) { border-collapse: collapse; width: 100%; margin: 12px 0; }
.markdown-body :deep(th), .markdown-body :deep(td) { border: 1px solid #dcdfe6; padding: 8px 12px; text-align: left; }
.markdown-body :deep(th) { background: #f5f7fa; font-weight: 600; }
.markdown-body :deep(code) { background: #f5f7fa; padding: 2px 6px; border-radius: 3px; font-size: 13px; }
.markdown-body :deep(pre) { background: #f5f7fa; padding: 12px 16px; border-radius: 6px; overflow-x: auto; }
.markdown-body :deep(pre code) { background: none; padding: 0; }
.markdown-body :deep(blockquote) { border-left: 4px solid #409eff; padding: 8px 16px; margin: 12px 0; background: #ecf5ff; color: #606266; }
.markdown-body :deep(ul), .markdown-body :deep(ol) { padding-left: 20px; }
.markdown-body :deep(li) { margin: 4px 0; }
.markdown-body :deep(hr) { border: none; border-top: 1px solid #ebeef5; margin: 20px 0; }
.markdown-body :deep(strong) { color: #303133; }
</style>
