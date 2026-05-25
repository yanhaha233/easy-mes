<template>
  <main class="page shop-page">
    <section class="page-hero compact">
      <div>
        <p class="eyebrow">{{ operatorLabel }}</p>
        <h1>车间报工</h1>
        <p class="hero-copy">系统会记住本人暂停和进行中的工序，待开工任务可直接领取。</p>
      </div>
    </section>

    <section class="sheet scan-sheet">
      <div class="scan-row">
        <el-input
          v-model="qrCode"
          :prefix-icon="Search"
          clearable
          placeholder="例如 WO-202605-0001"
          @keyup.enter="loadOperation"
        />
        <el-button type="primary" :loading="loading" @click="loadOperation">进入</el-button>
      </div>
    </section>

    <section class="sheet workbench-sheet">
      <div class="section-header">
        <div>
          <p class="eyebrow">我的任务</p>
          <h2>继续生产</h2>
        </div>
        <el-button :loading="workbenchLoading" :icon="Refresh" @click="loadWorkbench">刷新</el-button>
      </div>
      <div v-if="workbenchOperations.length" v-loading="workbenchLoading" class="workbench-list">
        <button
          v-for="item in workbenchOperations"
          :key="item.id"
          class="workbench-card"
          type="button"
          @click="selectWorkbenchOperation(item)"
        >
          <span class="workbench-card__main">
            <strong>{{ item.work_order_no }}</strong>
            <span>{{ item.seq }} {{ item.operation_name }} · {{ item.work_center_name }}</span>
            <small v-if="item.started_by_operator_name">操作员 {{ item.started_by_operator_name }}</small>
            <small v-if="item.assigned_operator_name">派工 {{ item.assigned_operator_name }}</small>
          </span>
          <el-tag :type="operationTag(item.status)" effect="plain">
            {{ item.status === 'paused' ? '暂停中' : operationStatusLabels[item.status] }}
          </el-tag>
        </button>
      </div>
      <el-empty v-else :image-size="80" description="暂无可继续的工序" />
    </section>

    <section v-if="operation" class="sheet operation-sheet">
      <div class="section-header">
        <div>
          <p class="eyebrow">{{ operation.work_order_no }}</p>
          <h2>{{ operation.seq }} {{ operation.operation_name }}</h2>
        </div>
        <el-tag :type="operationTag(operation.status)" effect="plain">
          {{ operationStatusLabels[operation.status] }}
        </el-tag>
      </div>

      <dl class="detail-grid">
        <dt>产品</dt>
        <dd>{{ operation.material_code }} {{ operation.material_name }}</dd>
        <dt>工位</dt>
        <dd>{{ operation.work_center_code }} {{ operation.work_center_name }}</dd>
        <dt>计划数</dt>
        <dd>{{ operation.planned_qty }}</dd>
        <dt>已报工</dt>
        <dd>合格 {{ operation.good_qty }} / 不良 {{ operation.bad_qty }}</dd>
      </dl>

      <div class="shop-actions">
        <el-button
          v-if="operation.status === 'ready'"
          size="large"
          type="primary"
          :loading="saving"
          @click="handleStart"
        >
          开工
        </el-button>
        <el-button
          v-if="operation.status === 'ready'"
          size="large"
          :loading="saving"
          @click="openBackfillDialog"
        >
          补录申请
        </el-button>
        <template v-else-if="operation.status === 'in_progress'">
          <div class="qty-grid">
            <el-form-item label="合格数">
              <el-input v-model="clockForm.good_qty" inputmode="decimal" />
            </el-form-item>
            <el-form-item label="不良数">
              <el-input v-model="clockForm.bad_qty" inputmode="decimal" />
            </el-form-item>
          </div>
          <el-form-item v-if="Number(clockForm.bad_qty) > 0" label="不良原因">
            <el-select v-model="clockForm.defect_reason_code" placeholder="选择原因">
              <el-option v-for="item in defectReasonOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="clockForm.remark" :rows="2" type="textarea" />
          </el-form-item>
          <el-button size="large" type="primary" :loading="saving" @click="handleClock">报工</el-button>
          <el-button size="large" :loading="saving" @click="handlePause">暂停</el-button>
        </template>
        <template v-else-if="operation.status === 'paused'">
          <el-alert :closable="false" show-icon title="工序已暂停，恢复后可继续报工" type="warning" />
          <el-button size="large" type="primary" :loading="saving" @click="handleResume">恢复生产</el-button>
        </template>
        <el-alert
          v-else
          :closable="false"
          show-icon
          title="当前工序暂不能操作"
          type="info"
        />
      </div>
    </section>

    <section v-else class="empty-workbench">
      <el-empty description="等待扫码或输入工单号" />
    </section>

    <el-dialog v-model="backfillDialogOpen" title="异常补录申请" width="520px">
      <el-form label-position="top" :model="backfillForm" @submit.prevent>
        <div class="qty-grid">
          <el-form-item label="开始时间" required>
            <el-date-picker
              v-model="backfillForm.started_at"
              type="datetime"
              value-format="YYYY-MM-DDTHH:mm:ssZ"
              placeholder="选择开始时间"
            />
          </el-form-item>
          <el-form-item label="结束时间" required>
            <el-date-picker
              v-model="backfillForm.ended_at"
              type="datetime"
              value-format="YYYY-MM-DDTHH:mm:ssZ"
              placeholder="选择结束时间"
            />
          </el-form-item>
          <el-form-item label="合格数" required>
            <el-input v-model="backfillForm.good_qty" inputmode="decimal" />
          </el-form-item>
          <el-form-item label="不良数" required>
            <el-input v-model="backfillForm.bad_qty" inputmode="decimal" />
          </el-form-item>
        </div>
        <el-form-item v-if="Number(backfillForm.bad_qty) > 0" label="不良原因">
          <el-select v-model="backfillForm.defect_reason_code" placeholder="选择原因">
            <el-option v-for="item in defectReasonOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="补录原因" required>
          <el-input v-model="backfillForm.reason" :rows="2" type="textarea" placeholder="例如现场先生产后补录" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="backfillForm.remark" :rows="2" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="backfillDialogOpen = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleBackfillRequest">提交申请</el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { ApiError } from '../api/client'
import {
  clockOperation,
  createBackfillRequest,
  getOperationByQr,
  listOperationWorkbench,
  pauseOperation,
  resumeOperation,
  startOperation,
} from '../api/operations'
import { listQualityDefectReasons } from '../api/quality'
import { useAuthStore } from '../stores/auth'
import type { DefectReason } from '../types/masterData'
import type { OperationRead } from '../types/operation'
import type { OperationStatus } from '../types/workOrder'
import { operationStatusLabels } from '../utils/labels'

const qrCode = ref('')
const authStore = useAuthStore()
const loading = ref(false)
const saving = ref(false)
const workbenchLoading = ref(false)
const backfillDialogOpen = ref(false)
const operation = ref<OperationRead | null>(null)
const workbenchOperations = ref<OperationRead[]>([])
const defectReasons = ref<DefectReason[]>([])

const clockForm = reactive({
  good_qty: '1',
  bad_qty: '0',
  defect_reason_code: '',
  remark: '',
})

const backfillForm = reactive({
  started_at: '',
  ended_at: '',
  good_qty: '1',
  bad_qty: '0',
  defect_reason_code: '',
  reason: '',
  remark: '',
})

const defectReasonOptions = computed(() =>
  defectReasons.value.map((item) => ({ label: `${item.code} ${item.name}`, value: item.code })),
)
const operatorLabel = computed(() => {
  const user = authStore.user
  if (!user) {
    return '操作员'
  }
  return user.worker_name ? `${user.worker_name} / ${user.display_name}` : user.display_name
})

onMounted(() => {
  loadDefectReasons()
  loadWorkbench()
})

function showError(error: unknown) {
  if (error instanceof ApiError) {
    ElMessage.error(error.message)
    return
  }
  ElMessage.error('操作失败，请稍后重试')
}

async function loadDefectReasons() {
  try {
    defectReasons.value = await listQualityDefectReasons()
  } catch (error) {
    showError(error)
  }
}

async function loadWorkbench() {
  workbenchLoading.value = true
  try {
    workbenchOperations.value = await listOperationWorkbench()
  } catch (error) {
    showError(error)
  } finally {
    workbenchLoading.value = false
  }
}

function resetClockForm(nextOperation: OperationRead) {
  const remain = Number(nextOperation.planned_qty) - Number(nextOperation.good_qty) - Number(nextOperation.bad_qty)
  clockForm.good_qty = String(Math.max(remain, 1))
  clockForm.bad_qty = '0'
  clockForm.defect_reason_code = ''
  clockForm.remark = ''
}

function toIsoInput(value: Date) {
  const offsetMinutes = -value.getTimezoneOffset()
  const sign = offsetMinutes >= 0 ? '+' : '-'
  const absOffset = Math.abs(offsetMinutes)
  const offsetHours = String(Math.floor(absOffset / 60)).padStart(2, '0')
  const offsetRemainder = String(absOffset % 60).padStart(2, '0')
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  const hour = String(value.getHours()).padStart(2, '0')
  const minute = String(value.getMinutes()).padStart(2, '0')
  const second = String(value.getSeconds()).padStart(2, '0')
  return `${year}-${month}-${day}T${hour}:${minute}:${second}${sign}${offsetHours}:${offsetRemainder}`
}

function selectWorkbenchOperation(item: OperationRead) {
  operation.value = item
  qrCode.value = item.work_order_no
  resetClockForm(item)
}

async function loadOperation() {
  if (!qrCode.value.trim()) {
    ElMessage.warning('请先输入工单号或工序码')
    return
  }
  loading.value = true
  try {
    operation.value = await getOperationByQr(qrCode.value.trim())
    resetClockForm(operation.value)
  } catch (error) {
    showError(error)
  } finally {
    loading.value = false
  }
}

async function handleStart() {
  if (!operation.value) {
    return
  }
  saving.value = true
  try {
    operation.value = await startOperation(operation.value.id)
    await loadWorkbench()
    ElMessage.success('已开工')
  } catch (error) {
    showError(error)
  } finally {
    saving.value = false
  }
}

function openBackfillDialog() {
  if (!operation.value) {
    return
  }
  const endedAt = new Date()
  const startedAt = new Date(endedAt.getTime() - 30 * 60 * 1000)
  const remain = Number(operation.value.planned_qty) - Number(operation.value.good_qty) - Number(operation.value.bad_qty)
  backfillForm.started_at = toIsoInput(startedAt)
  backfillForm.ended_at = toIsoInput(endedAt)
  backfillForm.good_qty = String(Math.max(remain, 1))
  backfillForm.bad_qty = '0'
  backfillForm.defect_reason_code = ''
  backfillForm.reason = ''
  backfillForm.remark = ''
  backfillDialogOpen.value = true
}

async function handlePause() {
  if (!operation.value) {
    return
  }
  saving.value = true
  try {
    operation.value = await pauseOperation(operation.value.id)
    await loadWorkbench()
    ElMessage.success('已暂停')
  } catch (error) {
    showError(error)
  } finally {
    saving.value = false
  }
}

async function handleResume() {
  if (!operation.value) {
    return
  }
  saving.value = true
  try {
    operation.value = await resumeOperation(operation.value.id)
    await loadWorkbench()
    ElMessage.success('已恢复')
  } catch (error) {
    showError(error)
  } finally {
    saving.value = false
  }
}

function validateClock() {
  const goodQty = Number(clockForm.good_qty)
  const badQty = Number(clockForm.bad_qty)
  if (!Number.isFinite(goodQty) || !Number.isFinite(badQty) || goodQty + badQty <= 0) {
    ElMessage.warning('合格数和不良数合计必须大于 0')
    return false
  }
  if (badQty > 0 && !clockForm.defect_reason_code) {
    ElMessage.warning('有不良数时必须选择不良原因')
    return false
  }
  return true
}

function validateBackfill() {
  if (!backfillForm.started_at || !backfillForm.ended_at) {
    ElMessage.warning('请选择补录开始和结束时间')
    return false
  }
  if (new Date(backfillForm.ended_at).getTime() <= new Date(backfillForm.started_at).getTime()) {
    ElMessage.warning('结束时间必须晚于开始时间')
    return false
  }
  const goodQty = Number(backfillForm.good_qty)
  const badQty = Number(backfillForm.bad_qty)
  if (!Number.isFinite(goodQty) || !Number.isFinite(badQty) || goodQty + badQty <= 0) {
    ElMessage.warning('合格数和不良数合计必须大于 0')
    return false
  }
  if (badQty > 0 && !backfillForm.defect_reason_code) {
    ElMessage.warning('有不良数时必须选择不良原因')
    return false
  }
  if (!backfillForm.reason.trim()) {
    ElMessage.warning('请输入补录原因')
    return false
  }
  return true
}

async function handleBackfillRequest() {
  if (!operation.value || !validateBackfill()) {
    return
  }
  saving.value = true
  try {
    const badQty = Number(backfillForm.bad_qty)
    await createBackfillRequest(operation.value.id, {
      started_at: backfillForm.started_at,
      ended_at: backfillForm.ended_at,
      good_qty: backfillForm.good_qty,
      bad_qty: backfillForm.bad_qty,
      defects: badQty > 0 ? [{ reason_code: backfillForm.defect_reason_code, qty: backfillForm.bad_qty }] : [],
      actual_materials: [],
      reason: backfillForm.reason.trim(),
      remark: backfillForm.remark.trim() || null,
    })
    backfillDialogOpen.value = false
    await loadWorkbench()
    ElMessage.success('补录申请已提交，等待计划员审核')
  } catch (error) {
    showError(error)
  } finally {
    saving.value = false
  }
}

async function handleClock() {
  if (!operation.value || !validateClock()) {
    return
  }
  saving.value = true
  try {
    const badQty = Number(clockForm.bad_qty)
    const response = await clockOperation(operation.value.id, {
      good_qty: clockForm.good_qty,
      bad_qty: clockForm.bad_qty,
      defects: badQty > 0 ? [{ reason_code: clockForm.defect_reason_code, qty: clockForm.bad_qty }] : [],
      actual_materials: [],
      remark: clockForm.remark.trim() || null,
    })
    operation.value = response.operation
    await loadWorkbench()
    const successMessage =
      response.work_order_status === 'completed' ? '报工完成，工单已完工' : '报工完成，下一工序已就绪'
    if (response.time_anomaly) {
      ElMessage.warning(`${successMessage}；本次用时偏短，已标记到追溯流水`)
    } else {
      ElMessage.success(successMessage)
    }
  } catch (error) {
    showError(error)
  } finally {
    saving.value = false
  }
}

function operationTag(status: OperationStatus) {
  if (status === 'ready') {
    return 'warning'
  }
  if (status === 'in_progress') {
    return 'primary'
  }
  if (status === 'paused') {
    return 'warning'
  }
  if (status === 'done') {
    return 'success'
  }
  return 'info'
}
</script>
