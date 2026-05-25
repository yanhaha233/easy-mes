<template>
  <main class="page quality-page">
    <section class="page-hero compact">
      <div>
        <p class="eyebrow">质量</p>
        <h1>质量记录</h1>
        <p class="hero-copy">先记录首件、巡检、终检，再从报工流水汇总不良原因。</p>
      </div>
      <el-button type="primary" @click="openQualityDrawer">新增质检</el-button>
    </section>

    <section class="sheet quality-filter">
      <div class="toolbar-actions quality-actions">
        <el-date-picker
          v-model="dateRange"
          end-placeholder="结束日期"
          range-separator="至"
          start-placeholder="开始日期"
          type="daterange"
          value-format="YYYY-MM-DD"
          @change="loadReport"
        />
        <el-button :icon="Refresh" :loading="loading" @click="loadReport">刷新不良统计</el-button>
      </div>
    </section>

    <section v-loading="loading" class="metrics" aria-label="质量概览">
      <article class="metric">
        <span>不良总数</span>
        <strong>{{ formatQty(report.total_bad_qty) }}</strong>
      </article>
      <article class="metric">
        <span>不良报工</span>
        <strong>{{ report.total_clock_records }}</strong>
      </article>
      <article class="metric">
        <span>质检记录</span>
        <strong>{{ qualityRecords.length }}</strong>
      </article>
      <article class="metric">
        <span>TOP 原因</span>
        <strong class="metric-text">{{ topReason }}</strong>
      </article>
    </section>

    <section class="sheet quality-rank-sheet">
      <div class="section-header">
        <div>
          <p class="eyebrow">原因排行</p>
          <h2>不良集中点</h2>
        </div>
      </div>

      <div v-if="report.items.length" class="defect-rank">
        <article v-for="item in report.items" :key="item.reason_code" class="defect-rank-row">
          <div class="defect-rank-title">
            <strong>{{ item.reason_name }}</strong>
            <span>{{ item.reason_code }}{{ item.category ? ` · ${item.category}` : '' }}</span>
          </div>
          <div class="defect-bar-wrap">
            <el-progress :percentage="rankPercent(item.bad_qty)" :show-text="false" />
            <b>{{ formatQty(item.bad_qty) }}</b>
          </div>
          <el-tag effect="plain">{{ item.clock_count }} 次</el-tag>
        </article>
      </div>
      <el-empty v-else description="暂无不良记录" />
    </section>

    <section class="sheet">
      <div class="section-header">
        <div>
          <p class="eyebrow">三检记录</p>
          <h2>最近质检</h2>
        </div>
        <el-button :loading="qualityLoading" @click="loadQualityRecords">刷新</el-button>
      </div>

      <el-table v-loading="qualityLoading" :data="qualityRecords" class="desktop-table">
        <el-table-column label="工单" min-width="150" prop="work_order_no" />
        <el-table-column label="类型" min-width="110">
          <template #default="{ row }">{{ inspectTypeText(row.inspect_type) }}</template>
        </el-table-column>
        <el-table-column label="结果" min-width="100">
          <template #default="{ row }">
            <el-tag :type="resultTag(row.result)" effect="plain">{{ resultText(row.result) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="抽样" min-width="140">
          <template #default="{ row }">
            {{ formatQty(row.sample_qty) }} / 合格 {{ formatQty(row.pass_qty) }} / 不合格
            {{ formatQty(row.fail_qty) }}
          </template>
        </el-table-column>
        <el-table-column label="检验时间" min-width="180">
          <template #default="{ row }">{{ formatDateTime(row.inspected_at) }}</template>
        </el-table-column>
      </el-table>

      <div class="mobile-records">
        <article v-for="row in qualityRecords" :key="row.id" class="record-row">
          <div class="record-main">
            <div>
              <strong>{{ row.work_order_no }}</strong>
              <span>{{ inspectTypeText(row.inspect_type) }} · {{ formatDateTime(row.inspected_at) }}</span>
            </div>
            <el-tag :type="resultTag(row.result)" effect="plain">{{ resultText(row.result) }}</el-tag>
          </div>
          <dl>
            <dt>抽样</dt>
            <dd>{{ formatQty(row.sample_qty) }}</dd>
            <dt>合格</dt>
            <dd>{{ formatQty(row.pass_qty) }}</dd>
            <dt>不合格</dt>
            <dd>{{ formatQty(row.fail_qty) }}</dd>
            <dt>处置</dt>
            <dd>{{ row.disposition || '-' }}</dd>
          </dl>
        </article>
      </div>
    </section>

    <el-drawer v-model="qualityDrawerOpen" title="新增质检记录" size="520px" destroy-on-close>
      <el-form label-position="top" :model="qualityForm" @submit.prevent>
        <el-form-item label="检验类型">
          <el-select v-model="qualityForm.inspect_type">
            <el-option label="首件" value="first_article" />
            <el-option label="巡检" value="patrol" />
            <el-option label="终检" value="final" />
          </el-select>
        </el-form-item>
        <el-form-item label="工单号" required>
          <el-input v-model="qualityForm.work_order_no" placeholder="WO-202605-0001" />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="抽样数" required>
            <el-input v-model="qualityForm.sample_qty" inputmode="decimal" />
          </el-form-item>
          <el-form-item label="合格数" required>
            <el-input v-model="qualityForm.pass_qty" inputmode="decimal" />
          </el-form-item>
          <el-form-item label="不合格数" required>
            <el-input v-model="qualityForm.fail_qty" inputmode="decimal" />
          </el-form-item>
          <el-form-item label="结果">
            <el-select v-model="qualityForm.result">
              <el-option label="合格" value="pass" />
              <el-option label="不合格" value="fail" />
              <el-option label="让步接收" value="concession" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="不良处置">
          <el-select v-model="qualityForm.disposition" clearable placeholder="有不良时选择">
            <el-option label="返修" value="rework" />
            <el-option label="让步接收" value="concession" />
            <el-option label="报废" value="scrap" />
            <el-option label="退料" value="return-to-vendor" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="qualityForm.remark" :rows="3" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="qualityDrawerOpen = false">取消</el-button>
        <el-button type="primary" :loading="qualitySaving" @click="submitQualityRecord">保存</el-button>
      </template>
    </el-drawer>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { createQualityRecord, listQualityRecords } from '../api/quality'
import { getDefectReport } from '../api/reports'
import { useAuthStore } from '../stores/auth'
import type { InspectResult, InspectType, QualityRecord } from '../types/quality'
import type { DefectReport } from '../types/report'

const authStore = useAuthStore()
const loading = ref(false)
const qualityLoading = ref(false)
const qualitySaving = ref(false)
const qualityDrawerOpen = ref(false)
const dateRange = ref<[string, string] | null>(null)
const qualityRecords = ref<QualityRecord[]>([])

const inspectTypeLabels: Record<InspectType, string> = {
  first_article: '首件',
  patrol: '巡检',
  final: '终检',
}

const resultLabels: Record<InspectResult, string> = {
  pass: '合格',
  fail: '不合格',
  concession: '让步接收',
}

const qualityForm = reactive({
  inspect_type: 'first_article' as InspectType,
  work_order_no: '',
  sample_qty: '1',
  pass_qty: '1',
  fail_qty: '0',
  result: 'pass' as InspectResult,
  disposition: '',
  remark: '',
})

const report = reactive<DefectReport>({
  date_from: null,
  date_to: null,
  total_bad_qty: '0',
  total_clock_records: 0,
  items: [],
  recent_records: [],
})

const topReason = computed(() => report.items[0]?.reason_name || '无')

onMounted(() => {
  loadReport()
  loadQualityRecords()
})

async function loadReport() {
  loading.value = true
  try {
    const params = Array.isArray(dateRange.value)
      ? { date_from: dateRange.value[0], date_to: dateRange.value[1] }
      : {}
    Object.assign(report, await getDefectReport(params))
  } catch {
    ElMessage.error('不良统计读取失败')
  } finally {
    loading.value = false
  }
}

async function loadQualityRecords() {
  qualityLoading.value = true
  try {
    const page = await listQualityRecords({ limit: 20, offset: 0 })
    qualityRecords.value = page.items
  } catch {
    ElMessage.error('质检记录读取失败')
  } finally {
    qualityLoading.value = false
  }
}

function openQualityDrawer() {
  qualityDrawerOpen.value = true
}

function validateQualityForm() {
  const sampleQty = Number(qualityForm.sample_qty)
  const passQty = Number(qualityForm.pass_qty)
  const failQty = Number(qualityForm.fail_qty)
  if (!qualityForm.work_order_no.trim()) {
    ElMessage.warning('请输入工单号')
    return false
  }
  if (!Number.isFinite(sampleQty) || sampleQty <= 0) {
    ElMessage.warning('抽样数必须大于 0')
    return false
  }
  if (!Number.isFinite(passQty) || !Number.isFinite(failQty) || passQty + failQty !== sampleQty) {
    ElMessage.warning('合格数 + 不合格数必须等于抽样数')
    return false
  }
  if (failQty > 0 && qualityForm.result === 'pass') {
    ElMessage.warning('存在不合格数时，结果不能选合格')
    return false
  }
  return true
}

async function submitQualityRecord() {
  if (!validateQualityForm()) {
    return
  }
  qualitySaving.value = true
  try {
    await createQualityRecord(qualityForm.inspect_type, {
      work_order_no: qualityForm.work_order_no.trim(),
      sample_qty: qualityForm.sample_qty,
      pass_qty: qualityForm.pass_qty,
      fail_qty: qualityForm.fail_qty,
      result: qualityForm.result,
      inspector_code: authStore.user?.worker_code || null,
      disposition: qualityForm.disposition || null,
      remark: qualityForm.remark.trim() || null,
    })
    ElMessage.success('质检记录已保存')
    qualityDrawerOpen.value = false
    await loadQualityRecords()
  } catch {
    ElMessage.error('质检记录保存失败')
  } finally {
    qualitySaving.value = false
  }
}

function formatQty(value: string | number | null | undefined) {
  const numberValue = Number(value ?? 0)
  if (!Number.isFinite(numberValue)) {
    return String(value ?? '0')
  }
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 4 }).format(numberValue)
}

function rankPercent(value: string) {
  const maxQty = Math.max(...report.items.map((item) => Number(item.bad_qty) || 0), 1)
  return Math.round(((Number(value) || 0) / maxQty) * 100)
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function resultTag(result: InspectResult) {
  if (result === 'pass') {
    return 'success'
  }
  if (result === 'concession') {
    return 'warning'
  }
  return 'danger'
}

function inspectTypeText(value: InspectType) {
  return inspectTypeLabels[value] || value
}

function resultText(value: InspectResult) {
  return resultLabels[value] || value
}
</script>
