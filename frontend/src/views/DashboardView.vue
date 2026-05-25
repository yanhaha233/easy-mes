<template>
  <main class="page dashboard-page">
    <section class="page-hero">
      <div>
        <p class="eyebrow">Easy MES</p>
        <h1>生产执行台</h1>
        <p class="hero-copy">默认计划员下工单，默认操作员报工，先跑通最短主流程。</p>
      </div>
      <RouterLink to="/work-orders">
        <el-button type="primary" :icon="Tickets">创建工单</el-button>
      </RouterLink>
    </section>

    <section v-loading="loading" class="metrics" aria-label="生产概览">
      <RouterLink class="metric metric-link" :to="{ name: 'work-orders' }">
        <span>全部工单</span>
        <strong>{{ dashboard.total }}</strong>
      </RouterLink>
      <RouterLink class="metric metric-link" :to="{ name: 'work-orders', query: { status: 'in_progress' } }">
        <span>进行中</span>
        <strong>{{ dashboard.in_progress }}</strong>
      </RouterLink>
      <RouterLink class="metric metric-link" :to="{ name: 'work-orders', query: { operation_status: 'ready,in_progress' } }">
        <span>待报工工序</span>
        <strong>{{ dashboard.ready_operations + dashboard.in_progress_operations }}</strong>
      </RouterLink>
      <RouterLink class="metric metric-link" :to="{ name: 'work-orders', query: { status: 'completed' } }">
        <span>完工工单</span>
        <strong>{{ dashboard.completed }}</strong>
      </RouterLink>
    </section>

    <section class="section-header output-header">
      <div>
        <p class="eyebrow">产量报表</p>
        <h2>日产量</h2>
      </div>
      <div class="toolbar-actions output-actions">
        <el-date-picker
          v-model="outputDate"
          placeholder="选择日期"
          type="date"
          value-format="YYYY-MM-DD"
          @change="loadDailyReports"
        />
        <el-button :icon="Refresh" :loading="outputLoading || oeeLoading" @click="loadDailyReports">刷新</el-button>
      </div>
    </section>

    <section v-loading="outputLoading" class="metrics output-metrics" aria-label="日产量概览">
      <article class="metric">
        <span>总产出</span>
        <strong>{{ formatQty(outputReport.total_output_qty) }}</strong>
      </article>
      <article class="metric">
        <span>合格数</span>
        <strong>{{ formatQty(outputReport.total_good_qty) }}</strong>
      </article>
      <article class="metric">
        <span>不良数</span>
        <strong>{{ formatQty(outputReport.total_bad_qty) }}</strong>
      </article>
      <article class="metric">
        <span>良率</span>
        <strong>{{ yieldRate }}</strong>
      </article>
    </section>

    <section class="sheet output-report">
      <div class="output-grid">
        <div class="output-panel">
          <h3>按产品</h3>
          <el-table :data="outputReport.by_material" class="desktop-table">
            <el-table-column label="产品" min-width="170">
              <template #default="{ row }">
                {{ row.material_code }} {{ row.material_name }}
              </template>
            </el-table-column>
            <el-table-column label="总产出" min-width="90">
              <template #default="{ row }">
                {{ formatQty(row.total_qty) }} {{ row.material_unit }}
              </template>
            </el-table-column>
            <el-table-column label="合格" min-width="80">
              <template #default="{ row }">
                {{ formatQty(row.good_qty) }}
              </template>
            </el-table-column>
            <el-table-column label="不良" min-width="80">
              <template #default="{ row }">
                {{ formatQty(row.bad_qty) }}
              </template>
            </el-table-column>
          </el-table>
          <div class="mobile-records">
            <article v-for="row in outputReport.by_material" :key="row.material_code" class="record-row">
              <div class="record-main">
                <div>
                  <strong>{{ row.material_code }} {{ row.material_name }}</strong>
                  <span>{{ row.work_order_count }} 个工单</span>
                </div>
                <el-tag effect="plain">{{ formatQty(row.total_qty) }} {{ row.material_unit }}</el-tag>
              </div>
              <dl>
                <dt>合格</dt>
                <dd>{{ formatQty(row.good_qty) }}</dd>
                <dt>不良</dt>
                <dd>{{ formatQty(row.bad_qty) }}</dd>
              </dl>
            </article>
          </div>
        </div>

        <div class="output-panel">
          <h3>按工位</h3>
          <el-table :data="outputReport.by_work_center" class="desktop-table">
            <el-table-column label="工位" min-width="170">
              <template #default="{ row }">
                {{ row.work_center_code }} {{ row.work_center_name }}
              </template>
            </el-table-column>
            <el-table-column label="总产出" min-width="90">
              <template #default="{ row }">
                {{ formatQty(row.total_qty) }}
              </template>
            </el-table-column>
            <el-table-column label="报工次数" min-width="90" prop="clock_count" />
          </el-table>
          <div class="mobile-records">
            <article v-for="row in outputReport.by_work_center" :key="row.work_center_code" class="record-row">
              <div class="record-main">
                <div>
                  <strong>{{ row.work_center_code }} {{ row.work_center_name }}</strong>
                  <span>{{ row.clock_count }} 次报工</span>
                </div>
                <el-tag effect="plain">{{ formatQty(row.total_qty) }}</el-tag>
              </div>
              <dl>
                <dt>合格</dt>
                <dd>{{ formatQty(row.good_qty) }}</dd>
                <dt>不良</dt>
                <dd>{{ formatQty(row.bad_qty) }}</dd>
              </dl>
            </article>
          </div>
        </div>
      </div>
    </section>

    <section v-loading="oeeLoading" class="sheet oee-report">
      <div class="section-header">
        <div>
          <p class="eyebrow">工位稼动</p>
          <h2>简化 OEE</h2>
        </div>
        <el-tag effect="plain">计划 {{ oeeReport.planned_minutes_per_work_center }} 分钟 / 工位</el-tag>
      </div>

      <div v-if="oeeReport.items.length" class="oee-list">
        <article v-for="item in oeeReport.items" :key="item.work_center_code" class="oee-row">
          <div class="oee-main">
            <strong>{{ item.work_center_code }} {{ item.work_center_name }}</strong>
            <span>
              实际 {{ formatQty(item.actual_run_minutes) }} 分钟 · 报工 {{ item.clock_count }} 次 · 产出
              {{ formatQty(item.total_qty) }}
            </span>
          </div>
          <el-progress :color="oeeProgressColor(item.oee)" :percentage="oeePercent(item.oee)" />
          <b>{{ formatPercent(item.oee) }}</b>
        </article>
      </div>
      <el-empty v-else description="暂无工位数据" />
    </section>

    <section class="sheet">
      <div class="section-header">
        <div>
          <p class="eyebrow">当前阶段</p>
          <h2>主流程进度</h2>
        </div>
        <el-button :icon="Refresh" :loading="loading" @click="loadDashboard">刷新</el-button>
      </div>

      <div class="task-list">
        <article v-for="task in tasks" :key="task.name" class="task-row">
          <el-icon><component :is="task.icon" /></el-icon>
          <div>
            <strong>{{ task.name }}</strong>
            <span>{{ task.note }}</span>
          </div>
          <el-tag :type="task.type" effect="plain">{{ task.status }}</el-tag>
        </article>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Files, Finished, List, Refresh, Tickets, Warning } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getWorkOrderDashboard, type WorkOrderDashboard } from '../api/dashboard'
import { getOeeReport, getOutputReport } from '../api/reports'
import type { OeeReport, OutputReport } from '../types/report'

const loading = ref(false)
const outputLoading = ref(false)
const oeeLoading = ref(false)
const outputDate = ref(formatLocalDate(new Date()))

const dashboard = reactive<WorkOrderDashboard>({
  total: 0,
  draft: 0,
  pending: 0,
  scheduled: 0,
  in_progress: 0,
  completed: 0,
  ready_operations: 0,
  in_progress_operations: 0,
  actual_good_qty: '0',
  actual_bad_qty: '0',
})

const outputReport = reactive<OutputReport>({
  report_date: outputDate.value,
  total_good_qty: '0',
  total_bad_qty: '0',
  total_output_qty: '0',
  clock_count: 0,
  work_order_count: 0,
  by_work_center: [],
  by_material: [],
  recent_records: [],
})

const oeeReport = reactive<OeeReport>({
  report_date: outputDate.value,
  planned_minutes_per_work_center: 480,
  total_actual_minutes: '0',
  average_oee: '0',
  items: [],
})

const yieldRate = computed(() => {
  const total = Number(outputReport.total_output_qty)
  if (!Number.isFinite(total) || total <= 0) {
    return '0%'
  }
  return `${((Number(outputReport.total_good_qty) / total) * 100).toFixed(1)}%`
})

const tasks = [
  {
    name: '基础档案',
    status: '已接入',
    type: 'success',
    icon: Files,
    note: '物料、工位、人员、BOM、工艺路线可维护。',
  },
  {
    name: '工单创建',
    status: '已接入',
    type: 'success',
    icon: Tickets,
    note: '按激活 BOM 和工艺路线展开工单。',
  },
  {
    name: '手机报工',
    status: '已接入',
    type: 'success',
    icon: Finished,
    note: '车间端支持开工、报工和完工流转。',
  },
  {
    name: '质量统计',
    status: '已接入',
    type: 'success',
    icon: Warning,
    note: '报工不良原因可汇总排行。',
  },
  {
    name: '简单追溯',
    status: '已接入',
    type: 'success',
    icon: List,
    note: '工单详情可查看操作与报工流水。',
  },
]

onMounted(() => {
  loadDashboard()
  loadDailyReports()
})

async function loadDashboard() {
  loading.value = true
  try {
    Object.assign(dashboard, await getWorkOrderDashboard())
  } catch {
    ElMessage.error('总览数据读取失败')
  } finally {
    loading.value = false
  }
}

async function loadOutputReport() {
  outputLoading.value = true
  try {
    Object.assign(outputReport, await getOutputReport({ date: outputDate.value }))
  } catch {
    ElMessage.error('产量报表读取失败')
  } finally {
    outputLoading.value = false
  }
}

async function loadOeeReport() {
  oeeLoading.value = true
  try {
    Object.assign(oeeReport, await getOeeReport({ date: outputDate.value, planned_minutes: 480 }))
  } catch {
    ElMessage.error('工位稼动读取失败')
  } finally {
    oeeLoading.value = false
  }
}

function loadDailyReports() {
  loadOutputReport()
  loadOeeReport()
}

function formatQty(value: string | number | null | undefined) {
  const numberValue = Number(value ?? 0)
  if (!Number.isFinite(numberValue)) {
    return String(value ?? '0')
  }
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 4 }).format(numberValue)
}

function formatLocalDate(value: Date) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function oeePercent(value: string) {
  const percent = Number(value) * 100
  if (!Number.isFinite(percent)) {
    return 0
  }
  return Math.min(Math.round(percent), 100)
}

function formatPercent(value: string) {
  const percent = Number(value) * 100
  if (!Number.isFinite(percent)) {
    return '0%'
  }
  return `${percent.toFixed(1)}%`
}

function oeeProgressColor(value: string) {
  const percent = Number(value) * 100
  if (percent >= 70) {
    return '#196b5f'
  }
  if (percent > 0) {
    return '#d9902f'
  }
  return '#a7b1bc'
}
</script>
