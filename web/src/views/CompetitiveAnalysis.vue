<template>
  <div class="competitive-page">
    <!-- 顶部 Banner -->
    <div class="page-banner">
      <div class="page-banner__content">
        <h2>竞争分析</h2>
        <p>TEZ 与全球边缘计算厂商全方位对比 · IaaS / PaaS / GPU / 行业覆盖</p>
      </div>
      <el-radio-group v-model="market" class="market-switch">
        <el-radio-button value="global">
          <el-icon><Connection /></el-icon> 国际市场
        </el-radio-button>
        <el-radio-button value="domestic">
          <el-icon><OfficeBuilding /></el-icon> 国内市场
        </el-radio-button>
      </el-radio-group>
    </div>

    <!-- 卡片总览 -->
    <div class="vendor-cards">
      <div v-for="v in currentVendors" :key="v.name" class="vendor-card" :style="{ '--accent': v.color }">
        <div class="vendor-card__badge">
          <el-tag size="small" :type="v.tagType" effect="dark" round>{{ v.tag }}</el-tag>
        </div>
        <div class="vendor-card__name">{{ v.name }}</div>
        <div class="vendor-card__stats">
          <div class="vendor-card__stat">
            <div class="stat-value">{{ v.nodes }}</div>
            <div class="stat-label">节点</div>
          </div>
          <div class="vendor-card__divider"></div>
          <div class="vendor-card__stat">
            <div class="stat-value">{{ v.latency }}</div>
            <div class="stat-label">延迟</div>
          </div>
          <div class="vendor-card__divider"></div>
          <div class="vendor-card__stat">
            <div class="stat-value">{{ v.revenue }}</div>
            <div class="stat-label">营收</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 图表区 -->
    <div class="charts-row">
      <div class="chart-card">
        <div class="chart-card__title">综合能力雷达图</div>
        <v-chart :option="radarOption" style="height: 340px" autoresize />
      </div>
      <div class="chart-card">
        <div class="chart-card__title">各维度得分对比</div>
        <v-chart :option="barOption" style="height: 340px" autoresize />
      </div>
    </div>

    <!-- 详细对比表格 -->
    <div class="section-card">
      <div class="section-card__header">
        <span class="section-card__title">多维度详细对比</span>
        <span class="section-card__desc">产品形态 · 定价 · 合规 · 生态</span>
      </div>
      <el-table :data="comparisonTable" border stripe size="small" class="comparison-table">
        <el-table-column prop="dimension" label="评估维度" width="120" fixed>
          <template #default="{ row }">
            <span style="font-weight:600">{{ row.dimension }}</span>
          </template>
        </el-table-column>
        <el-table-column v-for="v in currentVendors" :key="v.name" :label="v.name" min-width="180">
          <template #header>
            <span :style="{ color: v.color, fontWeight: 600 }">{{ v.name }}</span>
          </template>
          <template #default="{ row }">
            <span v-html="row[v.key]"></span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 行业覆盖 -->
    <div class="section-card">
      <div class="section-card__header">
        <span class="section-card__title">行业场景覆盖</span>
        <span class="section-card__desc">各厂商在不同行业的竞争力评级</span>
      </div>
      <el-table :data="industryData" stripe size="small" class="industry-table">
        <el-table-column prop="industry" label="行业" width="120" fixed>
          <template #default="{ row }">
            <span style="font-weight:500">{{ row.industry }}</span>
          </template>
        </el-table-column>
        <el-table-column v-for="v in currentVendors" :key="v.name" :label="v.name" width="160" align="center">
          <template #header>
            <span :style="{ color: v.color, fontWeight: 600 }">{{ v.name }}</span>
          </template>
          <template #default="{ row }">
            <span class="industry-badge" :class="'industry-badge--' + (row[v.key] === '强' ? 'strong' : row[v.key] === '中' ? 'medium' : 'weak')">
              {{ row[v.key] }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 边缘AI推理对比 -->
    <div class="section-card">
      <div class="section-card__header">
        <span class="section-card__title">边缘AI推理能力</span>
        <span class="section-card__desc">各厂商在边缘侧的GPU/AI推理部署能力</span>
      </div>
      <el-table :data="aiInferenceData" border stripe size="small">
        <el-table-column prop="dimension" label="能力维度" width="140" fixed>
          <template #default="{ row }"><span style="font-weight:600">{{ row.dimension }}</span></template>
        </el-table-column>
        <el-table-column v-for="v in currentVendors" :key="v.name" :label="v.name" min-width="200">
          <template #header><span :style="{ color: v.color, fontWeight: 600 }">{{ v.name }}</span></template>
          <template #default="{ row }"><span v-html="row[v.key]"></span></template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 国家/地域维度 -->
    <div class="section-card">
      <div class="section-card__header">
        <span class="section-card__title">国家/地域厂商覆盖</span>
        <span class="section-card__desc">点击国家查看各厂商在该地域的能力上线情况</span>
      </div>
      <div class="country-tabs">
        <el-tag
          v-for="c in countries"
          :key="c.name"
          :type="selectedCountry === c.name ? '' : 'info'"
          :effect="selectedCountry === c.name ? 'dark' : 'plain'"
          class="country-tag"
          @click="selectedCountry = c.name"
        >
          {{ c.flag }} {{ c.name }}
        </el-tag>
      </div>
      <div v-if="selectedCountryData" class="country-detail">
        <el-table :data="selectedCountryData.vendors" border stripe size="small">
          <el-table-column prop="vendor" label="厂商" width="140">
            <template #default="{ row }"><span style="font-weight:600">{{ row.vendor }}</span></template>
          </el-table-column>
          <el-table-column prop="presence" label="是否有节点" width="100" align="center">
            <template #default="{ row }">
              <span :style="{ color: row.presence ? '#10b981' : '#ef4444' }">{{ row.presence ? '✓ 有' : '✗ 无' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="products" label="已上线产品" min-width="250">
            <template #default="{ row }">
              <el-tag v-for="p in row.products" :key="p" size="small" effect="plain" style="margin:2px 4px 2px 0">{{ p }}</el-tag>
              <span v-if="!row.products.length" style="color:#9ca3af">—</span>
            </template>
          </el-table-column>
          <el-table-column prop="note" label="备注" min-width="180" show-overflow-tooltip />
        </el-table>
      </div>
    </div>

    <!-- 厂商产品能力详情 -->
    <div class="section-card">
      <div class="section-card__header">
        <span class="section-card__title">产品能力详情</span>
        <span class="section-card__desc">IaaS · PaaS · GPU/AI · 覆盖区域</span>
      </div>
      <div class="vendor-detail-grid">
        <div v-for="v in currentVendorDetails" :key="v.name" class="vendor-detail-card">
          <div class="vendor-detail-card__header">
            <span class="vendor-detail-card__name">{{ v.name }}</span>
          </div>

          <!-- 营收 -->
          <div v-if="v.revenue" class="vendor-detail-card__section">
            <div class="section-title">营收</div>
            <div class="revenue-row">
              <div v-for="r in v.revenue" :key="r.label" class="revenue-chip">
                <span class="revenue-chip__value">{{ r.value }}</span>
                <span class="revenue-chip__label">{{ r.label }}</span>
              </div>
            </div>
          </div>

          <!-- IaaS -->
          <div class="vendor-detail-card__section">
            <div class="section-title">IaaS</div>
            <div class="cap-list">
              <div v-for="c in v.iaas" :key="c.name" class="cap-item" :class="{ 'cap-item--off': !c.available }">
                <span class="cap-dot" :class="c.available ? 'cap-dot--on' : 'cap-dot--off'"></span>
                <span class="cap-name">{{ c.name }}</span>
                <span v-if="c.note" class="cap-note">{{ c.note }}</span>
              </div>
            </div>
          </div>

          <!-- PaaS -->
          <div class="vendor-detail-card__section">
            <div class="section-title">PaaS</div>
            <div class="cap-list">
              <div v-for="c in v.paas" :key="c.name" class="cap-item" :class="{ 'cap-item--off': !c.available }">
                <span class="cap-dot" :class="c.available ? 'cap-dot--on' : 'cap-dot--off'"></span>
                <span class="cap-name">{{ c.name }}</span>
                <span v-if="c.note" class="cap-note">{{ c.note }}</span>
              </div>
            </div>
          </div>

          <!-- GPU/AI -->
          <div v-if="v.gpu && v.gpu.length" class="vendor-detail-card__section">
            <div class="section-title">GPU / AI</div>
            <div class="cap-list">
              <div v-for="c in v.gpu" :key="c.name" class="cap-item" :class="{ 'cap-item--off': !c.available }">
                <span class="cap-dot" :class="c.available ? 'cap-dot--on' : 'cap-dot--off'"></span>
                <span class="cap-name">{{ c.name }}</span>
                <span v-if="c.note" class="cap-note">{{ c.note }}</span>
              </div>
            </div>
          </div>

          <!-- 覆盖 -->
          <div v-if="v.regions" class="vendor-detail-card__section">
            <div class="section-title">覆盖区域</div>
            <p class="regions-text">{{ v.regions }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 竞分资料文档 -->
    <div class="section-card" v-if="competitiveArticles.length">
      <div class="section-card__header">
        <span class="section-card__title">竞分调研资料</span>
        <span class="section-card__desc">从知识库自动同步 · 上传新文档后自动刷新</span>
      </div>
      <el-table :data="competitiveArticles" stripe size="small">
        <el-table-column prop="title" label="标题" min-width="250" />
        <el-table-column prop="summary" label="摘要" min-width="300" show-overflow-tooltip />
        <el-table-column prop="tags" label="标签" width="180">
          <template #default="{ row }">
            <el-tag v-for="t in (row.tags || '').split(',').filter(Boolean)" :key="t" size="small" effect="plain" style="margin-right:4px">{{ t.trim() }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Connection, OfficeBuilding } from '@element-plus/icons-vue'
import { listArticles, type ArticleInfo } from '@/api/knowledge'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { RadarChart, BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([RadarChart, BarChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent, CanvasRenderer])

const market = ref<'global' | 'domestic'>('global')

// ─── 厂商数据 ───
interface VendorInfo {
  name: string
  key: string
  color: string
  tag: string
  tagType: '' | 'success' | 'warning' | 'info' | 'danger'
  nodes: string
  latency: string
  revenue: string
  // 雷达图维度得分(0-10)
  scores: number[]  // [IaaS能力, PaaS能力, GPU/AI, 全球覆盖, 定价竞争力, 合规成熟度, 行业生态]
}

const globalVendors: VendorInfo[] = [
  { name: 'TEZ（腾讯云）', key: 'tez', color: '#409EFF', tag: '我方', tagType: '', nodes: '0（规划中）', latency: '—', revenue: '规划中', scores: [3, 2, 1, 1, 5, 1, 2] },
  { name: 'AWS Local Zone', key: 'aws', color: '#FF9900', tag: '主要对手', tagType: 'danger', nodes: '33+', latency: '5-6ms', revenue: '~10亿$', scores: [9, 8, 8, 9, 4, 10, 9] },
  { name: '阿里云 ENS', key: 'ali', color: '#FF6A00', tag: '直接竞品', tagType: 'warning', nodes: '2300+', latency: '5-15ms', revenue: '~10亿¥', scores: [8, 7, 7, 9, 7, 7, 8] },
  { name: 'Cloudflare', key: 'cf', color: '#F38020', tag: '间接竞品', tagType: 'info', nodes: '330+', latency: '4-10ms', revenue: '未公开', scores: [1, 9, 6, 10, 9, 9, 7] },
]

const domesticVendors: VendorInfo[] = [
  { name: 'TEZ（腾讯云）', key: 'tez', color: '#409EFF', tag: '我方', tagType: '', nodes: '30+', latency: '5-10ms', revenue: '—', scores: [9, 3, 2, 8, 7, 10, 6] },
  { name: '阿里云 ENS', key: 'ali', color: '#FF6A00', tag: '主要对手', tagType: 'danger', nodes: '900+', latency: '5-15ms', revenue: '~8亿¥', scores: [8, 7, 6, 9, 7, 10, 8] },
  { name: '华为云 IEC', key: 'huawei', color: '#CF0A2C', tag: '竞品', tagType: 'warning', nodes: '200+', latency: '5-10ms', revenue: '未公开', scores: [8, 8, 8, 7, 6, 10, 8] },
  { name: '移动云 MEC', key: 'cmcc', color: '#00A5E0', tag: '运营商', tagType: 'info', nodes: '500+', latency: '3-8ms', revenue: '未公开', scores: [5, 4, 2, 8, 9, 10, 5] },
]

const currentVendors = computed(() => market.value === 'global' ? globalVendors : domesticVendors)

// ─── 雷达图 ───
const radarDimensions = ['IaaS能力', 'PaaS能力', 'GPU/AI', '全球覆盖', '定价竞争力', '合规成熟度', '行业生态']

const radarOption = computed(() => ({
  tooltip: {},
  legend: { bottom: 0, data: currentVendors.value.map(v => v.name) },
  radar: {
    indicator: radarDimensions.map(d => ({ name: d, max: 10 })),
    radius: '60%',
  },
  series: [{
    type: 'radar',
    data: currentVendors.value.map(v => ({
      name: v.name,
      value: v.scores,
      lineStyle: { color: v.color },
      itemStyle: { color: v.color },
      areaStyle: { color: v.color, opacity: 0.1 },
    })),
  }],
}))

// ─── 柱状图 ───
const barOption = computed(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  legend: { bottom: 0 },
  grid: { left: 80, right: 20, top: 20, bottom: 50 },
  xAxis: { type: 'value', max: 10 },
  yAxis: { type: 'category', data: [...radarDimensions].reverse() },
  series: currentVendors.value.map(v => ({
    name: v.name,
    type: 'bar',
    data: [...v.scores].reverse(),
    itemStyle: { color: v.color },
  })),
}))

// ─── 对比表格 ───
const globalComparison = [
  { dimension: '产品形态', tez: 'IaaS（CVM+裸金属+CLB）<br><i style="color:#909399">海外首期：CVM+CLB+EIP</i>', aws: 'IaaS+PaaS（EC2/ECS/EKS/RDS）', ali: 'IaaS+PaaS（ECS+容器+AI编解码）', cf: 'Serverless（Workers+KV+D1）' },
  { dimension: 'GPU/AI能力', tez: '无（规划中）', aws: 'NVIDIA Hopper推理，已商用', ali: 'GPU集群+本地推理（迪拜）', cf: 'Workers AI + LoRA推理' },
  { dimension: '海外节点', tez: '<b style="color:#f56c6c">0</b>（越南规划中）', aws: '33+ Local Zones', ali: '2300+ 海外节点，70国', cf: '330+ PoP 城市' },
  { dimension: '网络延迟', tez: '国内5-10ms，海外待验证', aws: '< 5-6ms', ali: '5-15ms', cf: '4-10ms（冷启动4.2ms）' },
  { dimension: '定价模式', tez: '预计与新加坡Region接近<br>（~25-29¥/核/月）', aws: '按需，价格较高', ali: '20-50美金/核/月，大客户7-8折', cf: '$0.50/百万请求' },
  { dimension: 'PaaS生态', tez: '首期仅CVM+CLB+EIP<br>后续扩展CBS/PaaS', aws: 'RDS/ElastiCache/EKS等完整', ali: '容器+对象存储+NAS', cf: 'KV/D1/R2/Queue/AI' },
  { dimension: '合规经验', tez: '首次出海，规划中', aws: '成熟，全球合规团队', ali: '借运营商合作解决', cf: 'CDN模式无重资产合规' },
  { dimension: '中资客户', tez: '<b style="color:#67c23a">天然优势</b>，中文+人民币', aws: '可用但沟通成本高', ali: '强，东南亚中资占70%', cf: '弱，面向欧美开发者' },
]

const domesticComparison = [
  { dimension: '产品形态', tez: 'CVM+裸金属+CLB', ali: 'ECS+容器+GPU', huawei: 'ECS+容器+函数计算', cmcc: 'VM+容器（轻量）' },
  { dimension: 'GPU/AI能力', tez: '规划中', ali: 'A10/V100可选', huawei: '昇腾NPU+GPU', cmcc: '无' },
  { dimension: '节点密度', tez: '30+ 一二线城市', ali: '900+ 下沉到县级', huawei: '200+ 一二三线', cmcc: '500+ 运营商侧' },
  { dimension: '网络延迟', tez: '5-10ms', ali: '5-15ms', huawei: '5-10ms', cmcc: '<b>3-8ms</b>（运营商内网）' },
  { dimension: '定价', tez: '标准云价格', ali: '比Region低30%', huawei: '标准价', cmcc: '<b>最低</b>（运营商补贴）' },
  { dimension: '裸金属', tez: '<b>支持</b>（BMD系列）', ali: '支持', huawei: '支持', cmcc: '不支持' },
  { dimension: '运营商合作', tez: '移动/联通/电信', ali: '全运营商', huawei: '联通深度合作', cmcc: '<b>自有网络</b>' },
  { dimension: '适用场景', tez: '游戏/音视频/CDN加速', ali: '全行业', huawei: '政企/工业互联', cmcc: '低延迟IoT/5G' },
]

const comparisonTable = computed(() => market.value === 'global' ? globalComparison : domesticComparison)

// ─── 行业覆盖 ───
const globalIndustry = [
  { industry: '游戏', tez: '弱（规划中）', aws: '强', ali: '强', cf: '中' },
  { industry: '音视频', tez: '弱（规划中）', aws: '强', ali: '强', cf: '中' },
  { industry: '金融', tez: '弱', aws: '强', ali: '中', cf: '弱' },
  { industry: '医疗健康', tez: '弱', aws: '强', ali: '中', cf: '弱' },
  { industry: 'AI推理', tez: '弱', aws: '强', ali: '强', cf: '中' },
  { industry: 'IoT/5G', tez: '弱', aws: '中', ali: '中', cf: '中' },
  { industry: 'CDN增强', tez: '弱', aws: '弱', ali: '中', cf: '强' },
  { industry: '电商/直播', tez: '弱', aws: '中', ali: '强', cf: '弱' },
]

const domesticIndustry = [
  { industry: '游戏', tez: '强', ali: '强', huawei: '中', cmcc: '弱' },
  { industry: '音视频', tez: '强', ali: '强', huawei: '中', cmcc: '中' },
  { industry: '金融', tez: '中', ali: '中', huawei: '强', cmcc: '中' },
  { industry: '工业互联', tez: '弱', ali: '中', huawei: '强', cmcc: '强' },
  { industry: 'AI推理', tez: '弱', ali: '中', huawei: '强', cmcc: '弱' },
  { industry: '政企', tez: '弱', ali: '中', huawei: '强', cmcc: '强' },
  { industry: 'CDN/直播', tez: '强', ali: '强', huawei: '中', cmcc: '中' },
  { industry: '自动驾驶', tez: '弱', ali: '中', huawei: '强', cmcc: '中' },
]

const industryData = computed(() => market.value === 'global' ? globalIndustry : domesticIndustry)

// ─── 边缘AI推理 ───
const globalAiInference = [
  { dimension: 'GPU型号', tez: '无（规划中）', aws: 'NVIDIA T4/A10G/H100', ali: 'NVIDIA A10/V100', cf: '无独立GPU' },
  { dimension: '推理框架', tez: '—', aws: 'TensorRT/ONNX/PyTorch', ali: 'PAI-EAS/TensorRT', cf: 'Workers AI（内置模型）' },
  { dimension: '大模型部署', tez: '—', aws: '支持（Bedrock边缘）', ali: '支持（通义千问边缘版）', cf: 'Workers AI + LoRA' },
  { dimension: '延迟', tez: '—', aws: '<10ms推理', ali: '10-20ms推理', cf: '4-10ms（轻量模型）' },
  { dimension: '最小规格', tez: '—', aws: 'g4dn.xlarge起', ali: '4核16G+A10', cf: '按请求计费' },
  { dimension: '典型场景', tez: '—', aws: '自动驾驶/医疗影像/实时翻译', ali: 'AI编解码/直播审核/NLP', cf: '文本生成/图像识别/RAG' },
  { dimension: '定价', tez: '—', aws: '$0.526/h起(g4dn)', ali: '约5元/核/时', cf: '免费额度+$0.01/1K tokens' },
]

const domesticAiInference = [
  { dimension: 'GPU/NPU', tez: '规划中', ali: 'NVIDIA A10/V100', huawei: '昇腾310/910', cmcc: '无' },
  { dimension: '推理框架', tez: '—', ali: 'PAI-EAS/ONNX', huawei: 'MindSpore/CANN', cmcc: '—' },
  { dimension: '大模型', tez: '—', ali: '通义千问边缘版', huawei: '盘古大模型边缘版', cmcc: '—' },
  { dimension: '典型场景', tez: '—', ali: 'AI编解码/直播/安防', huawei: '工业质检/安防/交通', cmcc: '—' },
  { dimension: '优势', tez: '—', ali: '节点多+模型丰富', huawei: '自研NPU+政企场景强', cmcc: '—' },
]

const aiInferenceData = computed(() => market.value === 'global' ? globalAiInference : domesticAiInference)

// ─── 国家/地域维度 ───
const selectedCountry = ref('越南')

interface CountryVendorInfo {
  vendor: string
  presence: boolean
  products: string[]
  note: string
}

interface CountryInfo {
  name: string
  flag: string
  vendors: CountryVendorInfo[]
}

const countries: CountryInfo[] = [
  {
    name: '越南', flag: '🇻🇳',
    vendors: [
      { vendor: 'TEZ（腾讯云）', presence: false, products: [], note: '2026 Q1 规划开区，首期 CVM+CLB+EIP' },
      { vendor: 'AWS', presence: true, products: ['EC2', 'EBS', 'VPC', 'ELB'], note: 'Local Zone 已上线，价格较高' },
      { vendor: '阿里云 ENS', presence: true, products: ['ECS', 'SLB', 'EIP'], note: '开区中（预计2026 H1），与本地ISP合作' },
      { vendor: 'Cloudflare', presence: true, products: ['Workers', 'CDN', 'R2'], note: 'PoP节点覆盖' },
    ],
  },
  {
    name: '印尼', flag: '🇮🇩',
    vendors: [
      { vendor: 'TEZ（腾讯云）', presence: false, products: [], note: '五部规划地域之一' },
      { vendor: 'AWS', presence: true, products: ['EC2', 'EBS', 'VPC', 'RDS', 'EKS'], note: 'Jakarta Region + Local Zone' },
      { vendor: '阿里云 ENS', presence: true, products: ['ECS', 'SLB', '容器', 'GPU'], note: '8个节点，覆盖多岛屿' },
      { vendor: 'Cloudflare', presence: true, products: ['Workers', 'CDN'], note: '多城市PoP' },
    ],
  },
  {
    name: '泰国', flag: '🇹🇭',
    vendors: [
      { vendor: 'TEZ（腾讯云）', presence: false, products: [], note: '未规划' },
      { vendor: 'AWS', presence: true, products: ['EC2', 'EBS', 'VPC'], note: 'Bangkok Local Zone' },
      { vendor: '阿里云 ENS', presence: true, products: ['ECS', 'SLB', 'EIP'], note: '按流量1Mbps 38元/月' },
      { vendor: 'Cloudflare', presence: true, products: ['Workers', 'CDN'], note: 'PoP覆盖' },
    ],
  },
  {
    name: '新加坡', flag: '🇸🇬',
    vendors: [
      { vendor: 'TEZ（腾讯云）', presence: false, products: [], note: '已有 Region，无边缘节点' },
      { vendor: 'AWS', presence: true, products: ['EC2', 'EBS', 'VPC', 'RDS', 'Lambda', 'EKS'], note: 'Region + Local Zone 全栈' },
      { vendor: '阿里云 ENS', presence: true, products: ['ECS', 'SLB', 'EIP', 'NAS'], note: '电费贵，定价较高' },
      { vendor: 'Cloudflare', presence: true, products: ['Workers', 'CDN', 'R2', 'D1'], note: '完整能力' },
    ],
  },
  {
    name: '土耳其', flag: '🇹🇷',
    vendors: [
      { vendor: 'TEZ（腾讯云）', presence: false, products: [], note: '2026 Q2 规划，需求8900核（PUBGM/Riot）' },
      { vendor: 'AWS', presence: false, products: [], note: '无 Local Zone' },
      { vendor: '阿里云 ENS', presence: true, products: ['ECS', 'SLB'], note: '有节点但货币风险大' },
      { vendor: 'Cloudflare', presence: true, products: ['Workers', 'CDN'], note: 'PoP覆盖' },
    ],
  },
  {
    name: '芬兰', flag: '🇫🇮',
    vendors: [
      { vendor: 'TEZ（腾讯云）', presence: false, products: [], note: '2026 Q2 规划，需求5560核（PUBGM/Riot）' },
      { vendor: 'AWS', presence: true, products: ['EC2', 'EBS', 'VPC'], note: 'Helsinki Local Zone' },
      { vendor: '阿里云 ENS', presence: false, products: [], note: '离德国近，未单独开' },
      { vendor: 'Cloudflare', presence: true, products: ['Workers', 'CDN'], note: 'PoP覆盖' },
    ],
  },
  {
    name: '法国', flag: '🇫🇷',
    vendors: [
      { vendor: 'TEZ（腾讯云）', presence: false, products: [], note: '2026 Q3-Q4 规划' },
      { vendor: 'AWS', presence: true, products: ['EC2', 'EBS', 'VPC', 'ELB'], note: 'Paris Local Zone' },
      { vendor: '阿里云 ENS', presence: true, products: ['ECS', 'SLB', '容器'], note: '40+节点（含德国）' },
      { vendor: 'Cloudflare', presence: true, products: ['Workers', 'CDN', 'R2', 'D1'], note: '完整能力' },
    ],
  },
  {
    name: '迪拜(UAE)', flag: '🇦🇪',
    vendors: [
      { vendor: 'TEZ（腾讯云）', presence: false, products: [], note: '未规划' },
      { vendor: 'AWS', presence: true, products: ['EC2', 'EBS', 'VPC', 'RDS'], note: 'UAE Region + Local Zone' },
      { vendor: '阿里云 ENS', presence: true, products: ['ECS', 'SLB', 'GPU', 'AI推理'], note: '迪拜GPU集群已商用' },
      { vendor: 'Cloudflare', presence: true, products: ['Workers', 'CDN'], note: 'PoP覆盖' },
    ],
  },
  {
    name: '巴西', flag: '🇧🇷',
    vendors: [
      { vendor: 'TEZ（腾讯云）', presence: false, products: [], note: '五部规划地域之一' },
      { vendor: 'AWS', presence: true, products: ['EC2', 'EBS', 'VPC', 'ELB'], note: 'São Paulo Local Zone' },
      { vendor: '阿里云 ENS', presence: true, products: ['ECS', 'SLB'], note: '2026启动圣保罗' },
      { vendor: 'Cloudflare', presence: true, products: ['Workers', 'CDN', 'R2'], note: '完整能力' },
    ],
  },
  {
    name: '韩国', flag: '🇰🇷',
    vendors: [
      { vendor: 'TEZ（腾讯云）', presence: false, products: [], note: '五部规划地域之一' },
      { vendor: 'AWS', presence: true, products: ['EC2', 'EBS', 'VPC', 'RDS', 'EKS'], note: 'Seoul Region + Local Zone' },
      { vendor: '阿里云 ENS', presence: true, products: ['ECS', 'SLB'], note: '有节点' },
      { vendor: 'Cloudflare', presence: true, products: ['Workers', 'CDN'], note: 'PoP覆盖' },
    ],
  },
]

const selectedCountryData = computed(() => countries.find(c => c.name === selectedCountry.value) || null)

// ─── 厂商产品能力详情 ───

interface Capability { name: string; available: boolean; note?: string }
interface RevenueItem { label: string; value: string }
interface VendorDetail {
  name: string
  revenue?: RevenueItem[]
  iaas: Capability[]
  paas: Capability[]
  gpu?: Capability[]
  regions?: string
}

const globalVendorDetails: VendorDetail[] = [
  {
    name: 'AWS Local Zone',
    revenue: [
      { label: '边缘总营收', value: '~10亿$' },
      { label: 'Local Zone占比', value: '80%' },
      { label: 'Wavelength占比', value: '20%' },
      { label: '收入排名', value: '游戏>音视频>内容>金融' },
    ],
    iaas: [
      { name: 'EC2 实例', available: true, note: 'C7i/R7i/M6i' },
      { name: 'EBS 块存储', available: true },
      { name: 'VPC', available: true },
      { name: 'ELB 负载均衡', available: true },
      { name: 'Direct Connect', available: true },
      { name: '裸金属 Bare Metal', available: true, note: 'i3.metal等' },
    ],
    paas: [
      { name: 'ECS 容器', available: true },
      { name: 'EKS', available: true },
      { name: 'RDS', available: true, note: '部分Zone' },
      { name: 'ElastiCache', available: true },
      { name: 'Lambda', available: false, note: '不支持' },
      { name: 'S3', available: false, note: '需跨Region' },
    ],
    gpu: [
      { name: 'NVIDIA Hopper', available: true, note: '推理' },
      { name: 'P4/G4 实例', available: true, note: '部分Zone' },
      { name: 'AI 训练', available: false, note: '需回Region' },
    ],
    regions: '北美（16个城市）、欧洲（6）、亚太（5）、拉美（3）、中东（2）、非洲（1）',
  },
  {
    name: '阿里云 ENS',
    revenue: [
      { label: '海外营收', value: '~10亿¥' },
      { label: '东南亚+中东', value: '占70%' },
      { label: 'IAAS占比', value: '55%' },
      { label: 'PAAS+AI占比', value: '45%' },
    ],
    iaas: [
      { name: 'ECS 实例', available: true, note: '4核16G起' },
      { name: '本地盘', available: true, note: '100G' },
      { name: '云硬盘', available: true, note: '单独购买' },
      { name: 'EIP', available: true },
      { name: 'SLB 负载均衡', available: true },
      { name: '裸金属', available: true },
    ],
    paas: [
      { name: '容器', available: true },
      { name: '对象存储（NAS挂载）', available: true },
      { name: 'AI编解码', available: true },
      { name: 'CDN融合', available: true },
      { name: '数据库', available: false, note: '不支持' },
      { name: '消息队列', available: false, note: '不支持' },
    ],
    gpu: [
      { name: 'GPU集群', available: true, note: '迪拜已商用' },
      { name: '本地AI推理', available: true },
      { name: 'AI训练', available: false },
    ],
    regions: '东南亚（印尼8、越南、泰国、菲律宾、马来、新加坡）、中东（迪拜、利雅得）、欧洲（德国40+法国、伦敦）、拉美（墨西哥、巴西）、非洲（埃及、尼日利亚）',
  },
  {
    name: 'Cloudflare',
    revenue: [
      { label: '边缘营收', value: '未单独披露' },
      { label: '总营收(FY25)', value: '~16亿$' },
      { label: '付费客户', value: '22万+' },
    ],
    iaas: [
      { name: 'Workers 函数', available: true, note: '无服务器' },
      { name: 'VM/裸金属', available: false, note: '不支持' },
      { name: 'VPC网络', available: false, note: '不支持' },
      { name: 'Tunnel', available: true },
      { name: 'Spectrum TCP/UDP', available: true },
    ],
    paas: [
      { name: 'KV 键值存储', available: true },
      { name: 'D1 数据库', available: true, note: 'SQLite边缘' },
      { name: 'R2 对象存储', available: true, note: '无出口费' },
      { name: 'Queue 消息', available: true },
      { name: 'Pub/Sub', available: true },
      { name: 'Stream 视频', available: true },
    ],
    gpu: [
      { name: 'Workers AI', available: true, note: 'LLM推理' },
      { name: 'LoRA微调', available: true },
      { name: 'GPU 独占', available: false },
    ],
    regions: '全球330+城市，100+国家覆盖，不区分具体Region概念',
  },
  {
    name: 'TEZ（腾讯云）',
    revenue: [
      { label: '海外营收', value: '0（规划中）' },
      { label: '目标市场', value: '越南首站' },
      { label: '预期年收入(越南)', value: '~100万¥' },
    ],
    iaas: [
      { name: 'CVM 实例', available: true, note: '首期支持' },
      { name: 'CLB 负载均衡', available: true, note: '首期支持' },
      { name: 'EIP', available: true, note: '首期支持' },
      { name: 'CBS 云硬盘', available: false, note: '二期规划' },
      { name: '裸金属', available: false, note: '后续规划' },
      { name: 'VPC', available: true },
    ],
    paas: [
      { name: '容器 TKE', available: false, note: '后续规划' },
      { name: '对象存储 COS', available: false, note: '后续规划' },
      { name: '数据库', available: false, note: '后续规划' },
      { name: 'CDN', available: false, note: '后续规划' },
    ],
    gpu: [
      { name: 'GPU实例', available: false, note: '规划中' },
      { name: 'AI推理', available: false, note: '规划中' },
    ],
    regions: '海外规划：越南（2026 Q1）→ 土耳其、芬兰（Q2）→ 法国等（Q3-Q4）',
  },
]

const domesticVendorDetails: VendorDetail[] = [
  {
    name: 'TEZ（腾讯云）',
    revenue: [
      { label: '国内节点', value: '30+' },
      { label: '覆盖城市', value: '一二线为主' },
      { label: '核心客户', value: '游戏/音视频/CDN' },
    ],
    iaas: [
      { name: 'CVM 实例', available: true, note: 'S5/S5nt/SN3ne' },
      { name: 'CLB 负载均衡', available: true },
      { name: 'EIP', available: true },
      { name: 'CBS 云硬盘', available: true },
      { name: '裸金属 BMD', available: true, note: 'BMD2/BMD3s' },
      { name: 'VPC', available: true },
      { name: '高IO IT5/IT3', available: true },
    ],
    paas: [
      { name: '容器', available: false, note: '不支持' },
      { name: '对象存储', available: false, note: '不支持' },
      { name: '数据库', available: false, note: '不支持' },
      { name: 'CDN联动', available: true },
    ],
    gpu: [
      { name: 'GPU实例', available: false, note: '规划中' },
    ],
    regions: '华北（北京周边）、华东（上海/南京/杭州）、华南（广州/深圳）、西南（成都/贵阳）、西北（中卫）等30+节点',
  },
  {
    name: '阿里云 ENS',
    revenue: [
      { label: '国内营收', value: '~8亿¥' },
      { label: '节点数', value: '900+' },
      { label: '下沉程度', value: '县级覆盖' },
    ],
    iaas: [
      { name: 'ECS 实例', available: true },
      { name: '本地SSD', available: true },
      { name: 'EIP', available: true },
      { name: 'SLB', available: true },
      { name: '裸金属', available: true },
      { name: 'VPC', available: true },
    ],
    paas: [
      { name: '容器', available: true },
      { name: '对象存储', available: true, note: 'NAS挂载' },
      { name: 'AI编解码', available: true },
      { name: 'CDN融合', available: true },
      { name: '边缘函数', available: true },
    ],
    gpu: [
      { name: 'A10/V100', available: true },
      { name: 'AI推理', available: true },
    ],
    regions: '覆盖全国34省、900+节点下沉到县级，含运营商合作节点',
  },
  {
    name: '华为云 IEC',
    revenue: [
      { label: '节点数', value: '200+' },
      { label: '核心市场', value: '政企/工业' },
    ],
    iaas: [
      { name: 'ECS 实例', available: true },
      { name: 'EVS 云硬盘', available: true },
      { name: 'EIP', available: true },
      { name: 'ELB', available: true },
      { name: '裸金属 BMS', available: true },
      { name: 'VPC', available: true },
    ],
    paas: [
      { name: '容器 CCE', available: true },
      { name: '函数计算', available: true },
      { name: 'IoT平台', available: true },
      { name: 'ModelArts', available: true, note: '边缘AI' },
      { name: '视频分析', available: true },
    ],
    gpu: [
      { name: '昇腾 NPU', available: true },
      { name: 'NVIDIA GPU', available: true },
      { name: '边缘AI推理', available: true },
    ],
    regions: '一二三线城市200+节点，与联通深度合作，政企专线覆盖',
  },
  {
    name: '移动云 MEC',
    revenue: [
      { label: '节点数', value: '500+' },
      { label: '网络优势', value: '运营商内网3-8ms' },
    ],
    iaas: [
      { name: 'VM 实例', available: true, note: '轻量级' },
      { name: '容器', available: true, note: '轻量级' },
      { name: 'EIP', available: true },
      { name: '裸金属', available: false },
      { name: 'VPC', available: true, note: '简化版' },
    ],
    paas: [
      { name: '5G MEC平台', available: true },
      { name: 'IoT Hub', available: true },
      { name: '视频监控', available: true },
      { name: '数据库', available: false },
      { name: '对象存储', available: false },
    ],
    gpu: [],
    regions: '依托中国移动基站，覆盖500+城市，延迟最低（3-8ms），适合5G/IoT场景',
  },
]

const currentVendorDetails = computed(() => market.value === 'global' ? globalVendorDetails : domesticVendorDetails)

// ─── 竞分文档列表（从知识库同步） ───
const competitiveArticles = ref<ArticleInfo[]>([])

onMounted(async () => {
  try {
    competitiveArticles.value = await listArticles('competitive')
  } catch {
    // handled by interceptor
  }
})
</script>

<style scoped>
.competitive-page { padding: 24px; max-width: 1400px; margin: 0 auto; }

/* Banner */
.page-banner { display: flex; align-items: center; justify-content: space-between; background: var(--tez-surface); border: 1px solid var(--tez-border); border-radius: 12px; padding: 20px 28px; margin-bottom: 24px; }
.page-banner__content h2 { font-size: 22px; font-weight: 700; margin: 0 0 4px; color: var(--tez-text-primary); }
.page-banner__content p { margin: 0; font-size: 13px; color: #9ca3af; }
.market-switch :deep(.el-radio-button__inner) { }
.market-switch :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) { background: #409eff; border-color: #409eff; color: #fff; }

/* 厂商总览卡片 */
.vendor-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-bottom: 24px; }
.vendor-card { position: relative; background: #fff; border-radius: 12px; padding: 20px; border: 1px solid #e5e7eb; transition: all 0.2s; overflow: hidden; }
.vendor-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: var(--accent, #409eff); }
.vendor-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.08); transform: translateY(-2px); }
.vendor-card__badge { margin-bottom: 8px; }
.vendor-card__name { font-size: 15px; font-weight: 600; color: #1f2937; margin-bottom: 14px; }
.vendor-card__stats { display: flex; align-items: center; gap: 12px; }
.vendor-card__stat { flex: 1; text-align: center; }
.vendor-card__divider { width: 1px; height: 28px; background: #e5e7eb; }
.stat-value { font-size: 14px; font-weight: 700; color: #1f2937; white-space: nowrap; }
.stat-label { font-size: 11px; color: #9ca3af; margin-top: 2px; }

/* 图表区 */
.charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }
.chart-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 20px; }
.chart-card__title { font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; }

/* Section Card */
.section-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 20px 24px; margin-bottom: 20px; }
.section-card__header { display: flex; align-items: baseline; gap: 12px; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #f3f4f6; }
.section-card__title { font-size: 16px; font-weight: 600; color: #1f2937; }
.section-card__desc { font-size: 12px; color: #9ca3af; }

/* 行业 Badge */
.industry-badge { display: inline-block; padding: 2px 10px; border-radius: 10px; font-size: 12px; font-weight: 500; }
.industry-badge--strong { background: #ecfdf5; color: #059669; }
.industry-badge--medium { background: #fffbeb; color: #d97706; }
.industry-badge--weak { background: #f9fafb; color: #9ca3af; }

/* 厂商详情并排卡片 */
.vendor-detail-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
.vendor-detail-card { border: 1px solid #f3f4f6; border-radius: 10px; padding: 16px; background: #f9fafb; transition: box-shadow 0.2s; }
.vendor-detail-card:hover { box-shadow: 0 2px 12px rgba(0,0,0,0.05); }
.vendor-detail-card__header { margin-bottom: 14px; padding-bottom: 10px; border-bottom: 2px solid #e5e7eb; }
.vendor-detail-card__name { font-size: 14px; font-weight: 700; color: #1f2937; }
.vendor-detail-card__section { margin-bottom: 14px; }
.section-title { font-size: 11px; font-weight: 700; color: #6b7280; text-transform: uppercase; margin-bottom: 6px; letter-spacing: 1px; }
.revenue-row { display: flex; flex-wrap: wrap; gap: 6px; }
.revenue-chip { display: flex; flex-direction: column; align-items: center; padding: 6px 10px; background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; min-width: 60px; }
.revenue-chip__value { font-size: 12px; font-weight: 700; color: #2563eb; }
.revenue-chip__label { font-size: 10px; color: #9ca3af; margin-top: 1px; }
.cap-list { display: flex; flex-direction: column; gap: 5px; }
.cap-item { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #374151; padding: 3px 0; }
.cap-item--off { color: #d1d5db; }
.cap-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.cap-dot--on { background: #10b981; box-shadow: 0 0 4px rgba(16,185,129,0.4); }
.cap-dot--off { background: #e5e7eb; }
.cap-name { flex: 1; }
.cap-note { font-size: 11px; color: #9ca3af; background: #f3f4f6; padding: 1px 6px; border-radius: 4px; }
.regions-text { font-size: 12px; color: #6b7280; margin: 0; line-height: 1.6; }

/* Table */
.comparison-table :deep(th), .industry-table :deep(th) { background: #f9fafb !important; }

/* 国家/地域标签 */
.country-tabs { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.country-tag { cursor: pointer; font-size: 13px; padding: 6px 14px; transition: all 0.2s; }
.country-tag:hover { transform: translateY(-1px); box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.country-detail { animation: fadeIn 0.2s ease; }
.country-detail :deep(.el-table) { border-radius: 8px; overflow: hidden; }

@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
</style>
