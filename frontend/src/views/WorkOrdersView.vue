<template>
  <main class="page work-order-page">
    <section class="page-hero compact">
      <div>
        <p class="eyebrow">计划员</p>
        <h1>工单管理</h1>
        <p class="hero-copy">第一版只做工单创建：按激活 BOM 和工艺路线展开，不排产、不扣料。</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="openCreate">新建工单</el-button>
    </section>

    <section class="sheet">
      <div class="list-toolbar">
        <div>
          <h2>工单列表</h2>
          <p>默认计划员创建，手工工单进入草稿，ERP 工单进入待排产。</p>
        </div>
        <div class="toolbar-actions">
          <el-input
            v-model="state.keyword"
            :prefix-icon="Search"
            clearable
            placeholder="工单 / 物料 / 客户"
            @keyup.enter="loadOrders"
            @clear="loadOrders"
          />
          <el-select v-model="state.status" clearable placeholder="状态" @change="loadOrders">
            <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-button :icon="Refresh" :loading="state.loading" @click="loadOrders">刷新</el-button>
        </div>
      </div>

      <el-table v-loading="state.loading" :data="state.items" class="desktop-table">
        <el-table-column prop="work_order_no" label="工单号" min-width="160" />
        <el-table-column label="物料" min-width="180">
          <template #default="{ row }">{{ row.material_code }} {{ row.material_name }}</template>
        </el-table-column>
        <el-table-column prop="planned_qty" label="数量" width="110" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="workOrderStatusTag(row.status)" effect="plain">{{ workOrderStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="优先级" width="100">
          <template #default="{ row }">{{ priorityText(row.priority) }}</template>
        </el-table-column>
        <el-table-column prop="due_date" label="交期" width="130" />
        <el-table-column prop="customer_name" label="客户" min-width="140" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'draft'" link type="primary" @click="confirmOrder(row)">确认</el-button>
            <el-button v-else-if="row.status === 'pending'" link type="primary" @click="scheduleOrder(row)">派工</el-button>
            <el-button v-else-if="row.status === 'completed'" link type="primary" @click="receiveOrder(row)">入库</el-button>
            <el-button v-if="canCancel(row.status)" link type="danger" @click="cancelOrder(row)">取消</el-button>
            <el-button link type="primary" :icon="View" @click="openDetail(row.id)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-loading="state.loading" class="mobile-records">
        <article v-for="row in state.items" :key="row.id" class="record-row">
          <div class="record-main">
            <div>
              <strong>{{ row.work_order_no }}</strong>
              <span>{{ row.material_code }} {{ row.material_name }}</span>
            </div>
            <el-tag :type="workOrderStatusTag(row.status)" effect="plain">{{ workOrderStatusText(row.status) }}</el-tag>
          </div>
          <dl>
            <dt>数量</dt>
            <dd>{{ row.planned_qty }}</dd>
            <dt>交期</dt>
            <dd>{{ row.due_date || '-' }}</dd>
            <dt>优先级</dt>
            <dd>{{ priorityText(row.priority) }}</dd>
            <dt>客户</dt>
            <dd>{{ row.customer_name || '-' }}</dd>
          </dl>
          <div class="record-actions">
            <el-button v-if="row.status === 'draft'" type="primary" @click="confirmOrder(row)">确认</el-button>
            <el-button v-else-if="row.status === 'pending'" type="primary" @click="scheduleOrder(row)">派工</el-button>
            <el-button v-else-if="row.status === 'completed'" type="primary" @click="receiveOrder(row)">入库</el-button>
            <el-button v-if="canCancel(row.status)" type="danger" plain @click="cancelOrder(row)">取消</el-button>
            <el-button :icon="View" @click="openDetail(row.id)">查看</el-button>
          </div>
        </article>
      </div>

      <el-empty v-if="!state.loading && state.items.length === 0" description="暂无工单" />

      <el-pagination
        v-model:current-page="state.page"
        background
        layout="prev, pager, next"
        :page-size="pageSize"
        :total="state.total"
        @current-change="loadOrders"
      />
    </section>

    <el-drawer v-model="createDrawerOpen" title="新建工单" size="560px" destroy-on-close>
      <el-form label-position="top" :model="form" @submit.prevent>
        <el-form-item label="生产物料" required>
          <el-select v-model="form.material_code" filterable placeholder="选择成品或半成品">
            <el-option v-for="item in producibleMaterials" :key="item.code" :label="`${item.code} ${item.name}`" :value="item.code" />
          </el-select>
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="数量" required>
            <el-input v-model="form.quantity" inputmode="decimal" placeholder="例如 100" />
          </el-form-item>
          <el-form-item label="交期">
            <el-date-picker v-model="form.due_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" />
          </el-form-item>
          <el-form-item label="优先级">
            <el-select v-model="form.priority">
              <el-option label="普通" value="normal" />
              <el-option label="高" value="high" />
              <el-option label="紧急" value="urgent" />
            </el-select>
          </el-form-item>
          <el-form-item label="来源">
            <el-select v-model="form.source">
              <el-option label="手工" value="manual" />
              <el-option label="ERP" value="erp" />
            </el-select>
          </el-form-item>
          <el-form-item label="外部单号">
            <el-input v-model="form.external_ref" placeholder="销售订单 / ERP 单号" />
          </el-form-item>
          <el-form-item label="客户">
            <el-input v-model="form.customer_name" />
          </el-form-item>
        </div>
        <el-form-item label="备注">
          <el-input v-model="form.remark" :rows="3" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDrawerOpen = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCreate">创建工单</el-button>
      </template>
    </el-drawer>

    <el-drawer v-model="detailDrawerOpen" :title="detail?.work_order_no || '工单详情'" size="680px" destroy-on-close>
      <div v-if="detail" class="detail-stack">
        <section class="detail-section">
          <div class="section-header">
            <div>
              <p class="eyebrow">工单</p>
              <h2>{{ detail.material.code }} {{ detail.material.name }}</h2>
            </div>
            <div class="detail-actions">
              <el-tag :type="workOrderStatusTag(detail.status)" effect="plain">{{ workOrderStatusLabels[detail.status] }}</el-tag>
              <el-button v-if="detail.status === 'completed'" size="small" type="primary" @click="receiveOrder(detail)">入库关单</el-button>
              <el-button v-if="canCancel(detail.status)" size="small" type="danger" plain @click="cancelOrder(detail)">取消工单</el-button>
            </div>
          </div>
          <dl class="detail-grid">
            <dt>数量</dt>
            <dd>{{ detail.planned_qty }} {{ detail.material.unit }}</dd>
            <dt>来源</dt>
            <dd>{{ workOrderSourceLabels[detail.source] }}</dd>
            <dt>BOM</dt>
            <dd>{{ detail.bom.version || '-' }} / {{ detail.bom.material_lines }} 行</dd>
            <dt>工艺路线</dt>
            <dd>{{ detail.routing.version || '-' }} / {{ detail.routing.operation_lines }} 道</dd>
          </dl>
        </section>

        <section class="detail-section">
          <h2>物料需求</h2>
          <article v-for="line in detail.materials_required" :key="line.id" class="detail-line">
            <div>
              <strong>{{ line.material_code }} {{ line.material_name }}</strong>
              <span>{{ line.material_spec || '-' }}</span>
            </div>
            <b>{{ line.required_qty }} {{ line.unit }}</b>
          </article>
          <el-empty v-if="detail.materials_required.length === 0" description="无物料需求" />
        </section>

        <section class="detail-section">
          <h2>工序任务</h2>
          <article v-for="operation in detail.operations" :key="operation.id" class="detail-line">
            <div>
              <strong>{{ operation.seq }} {{ operation.operation_name }}</strong>
              <span>{{ operation.work_center_code }} {{ operation.work_center_name }}</span>
            </div>
            <el-tag effect="plain">{{ operationStatusLabels[operation.status] }}</el-tag>
          </article>
        </section>

        <section v-if="trace?.receipts.length" class="detail-section">
          <h2>完工入库</h2>
          <article v-for="receipt in trace.receipts" :key="receipt.id" class="detail-line">
            <div>
              <strong>{{ receipt.receipt_no }}</strong>
              <span>批次 {{ receipt.lot_no || '-' }} · {{ formatTime(receipt.received_at) }}</span>
            </div>
            <b>{{ receipt.good_qty }} {{ receipt.material.unit }}</b>
          </article>
        </section>

        <section class="detail-section">
          <div class="section-header">
            <div>
              <p class="eyebrow">Traceability</p>
              <h2>追溯流水</h2>
            </div>
            <el-button size="small" :loading="traceLoading" @click="loadTrace(detail.work_order_no)">刷新追溯</el-button>
          </div>
          <div v-if="trace?.timeline.length" class="timeline-list">
            <article v-for="event in trace.timeline" :key="`${event.event_type}-${event.occurred_at}-${event.title}`" class="timeline-item">
              <span class="timeline-dot" />
              <div>
                <strong>{{ event.title }}</strong>
                <span>{{ formatTime(event.occurred_at) }} · {{ event.actor_code || 'system' }}</span>
                <p v-if="timelineDetailText(event)">{{ timelineDetailText(event) }}</p>
              </div>
            </article>
          </div>
          <el-empty v-else description="暂无追溯流水" />
        </section>
      </div>
    </el-drawer>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search, View } from '@element-plus/icons-vue'
import { ApiError } from '../api/client'
import { listMaster } from '../api/masterData'
import {
  cancelWorkOrder,
  confirmWorkOrder,
  createWorkOrder,
  getWorkOrder,
  getWorkOrderTraceability,
  listWorkOrders,
  receiveWorkOrder,
  scheduleWorkOrder,
} from '../api/workOrders'
import type { Material } from '../types/masterData'
import type {
  Priority,
  TraceTimelineEvent,
  WorkOrder,
  WorkOrderListItem,
  WorkOrderSource,
  WorkOrderStatus,
  WorkOrderTraceability,
} from '../types/workOrder'
import {
  operationStatusLabels,
  priorityLabels,
  workOrderSourceLabels,
  workOrderStatusLabels,
} from '../utils/labels'

const pageSize = 20
const createDrawerOpen = ref(false)
const detailDrawerOpen = ref(false)
const saving = ref(false)
const traceLoading = ref(false)
const detail = ref<WorkOrder | null>(null)
const trace = ref<WorkOrderTraceability | null>(null)
const materials = ref<Material[]>([])

const state = reactive({
  items: [] as WorkOrderListItem[],
  total: 0,
  loading: false,
  page: 1,
  keyword: '',
  status: '',
})

const form = reactive({
  material_code: '',
  quantity: '1',
  due_date: '',
  priority: 'normal' as Priority,
  source: 'manual' as WorkOrderSource,
  external_ref: '',
  customer_name: '',
  remark: '',
})

const statusOptions = Object.entries(workOrderStatusLabels).map(([value, label]) => ({ value, label }))

const producibleMaterials = computed(() =>
  materials.value.filter((item) => item.is_active && ['product', 'semi_finished'].includes(item.material_type)),
)

onMounted(async () => {
  await Promise.all([loadMaterials(), loadOrders()])
})

function showError(error: unknown) {
  if (error instanceof ApiError) {
    ElMessage.error(error.message)
    return
  }
  ElMessage.error('操作失败，请稍后重试')
}

function emptyToNull(value: string) {
  const trimmed = value.trim()
  return trimmed ? trimmed : null
}

async function loadMaterials() {
  try {
    const page = await listMaster('materials', { is_active: true, limit: 100, offset: 0 })
    materials.value = page.items
  } catch (error) {
    showError(error)
  }
}

async function loadOrders() {
  state.loading = true
  try {
    const page = await listWorkOrders({
      keyword: state.keyword,
      status: state.status,
      limit: pageSize,
      offset: (state.page - 1) * pageSize,
    })
    state.items = page.items
    state.total = page.total
  } catch (error) {
    showError(error)
  } finally {
    state.loading = false
  }
}

function openCreate() {
  form.material_code = producibleMaterials.value[0]?.code || ''
  form.quantity = '1'
  form.due_date = ''
  form.priority = 'normal'
  form.source = 'manual'
  form.external_ref = ''
  form.customer_name = ''
  form.remark = ''
  createDrawerOpen.value = true
}

function validateForm() {
  if (!form.material_code) {
    ElMessage.warning('请选择生产物料')
    return false
  }
  const quantity = Number(form.quantity)
  if (!Number.isFinite(quantity) || quantity <= 0) {
    ElMessage.warning('数量必须大于 0')
    return false
  }
  return true
}

async function submitCreate() {
  if (!validateForm()) {
    return
  }
  saving.value = true
  try {
    const created = await createWorkOrder({
      material_code: form.material_code,
      quantity: form.quantity,
      due_date: form.due_date || null,
      priority: form.priority,
      source: form.source,
      external_ref: emptyToNull(form.external_ref),
      customer_name: emptyToNull(form.customer_name),
      remark: emptyToNull(form.remark),
    })
    ElMessage.success(`已创建 ${created.work_order_no}`)
    createDrawerOpen.value = false
    state.page = 1
    await loadOrders()
    detail.value = created
    await loadTrace(created.work_order_no)
    detailDrawerOpen.value = true
  } catch (error) {
    showError(error)
  } finally {
    saving.value = false
  }
}

async function openDetail(id: string) {
  try {
    detail.value = await getWorkOrder(id)
    await loadTrace(detail.value.work_order_no)
    detailDrawerOpen.value = true
  } catch (error) {
    showError(error)
  }
}

async function confirmOrder(row: WorkOrderListItem) {
  try {
    const updated = await confirmWorkOrder(row.work_order_no)
    ElMessage.success(`${updated.work_order_no} 已确认`)
    await loadOrders()
    detail.value = updated
    await loadTrace(updated.work_order_no)
  } catch (error) {
    showError(error)
  }
}

async function scheduleOrder(row: WorkOrderListItem) {
  try {
    const updated = await scheduleWorkOrder(row.work_order_no)
    ElMessage.success(`${updated.work_order_no} 已派工`)
    await loadOrders()
    detail.value = updated
    await loadTrace(updated.work_order_no)
  } catch (error) {
    showError(error)
  }
}

async function cancelOrder(row: WorkOrderListItem | WorkOrder) {
  try {
    const { value } = await ElMessageBox.prompt('请输入取消原因', `取消 ${row.work_order_no}`, {
      confirmButtonText: '确认取消',
      cancelButtonText: '返回',
      inputPattern: /\S+/,
      inputErrorMessage: '取消原因不能为空',
    })
    const updated = await cancelWorkOrder(row.work_order_no, value.trim())
    ElMessage.success(`${updated.work_order_no} 已取消`)
    await loadOrders()
    detail.value = updated
    await loadTrace(updated.work_order_no)
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    showError(error)
  }
}

async function receiveOrder(row: WorkOrderListItem | WorkOrder) {
  try {
    const { value } = await ElMessageBox.prompt(
      `默认入库合格数量 ${row.actual_good_qty}，请输入入库批次号`,
      '完工入库',
      {
        confirmButtonText: '入库关单',
        cancelButtonText: '取消',
        inputValue: `LOT-${row.work_order_no}`,
        inputPattern: /\S+/,
        inputErrorMessage: '批次号不能为空',
      },
    )
    const response = await receiveWorkOrder(row.work_order_no, {
      good_qty: null,
      lot_no: value.trim(),
      warehouse_code: 'FG-DEFAULT',
      remark: null,
    })
    ElMessage.success(`${response.receipt.receipt_no} 已入库，工单已关单`)
    await loadOrders()
    detail.value = response.work_order
    await loadTrace(response.work_order.work_order_no)
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    showError(error)
  }
}

async function loadTrace(workOrderNo: string) {
  traceLoading.value = true
  try {
    trace.value = await getWorkOrderTraceability(workOrderNo)
  } catch (error) {
    showError(error)
  } finally {
    traceLoading.value = false
  }
}

function formatTime(value: string) {
  return new Date(value).toLocaleString()
}

function timelineDetailText(event: TraceTimelineEvent) {
  if (event.good_qty !== null || event.bad_qty !== null) {
    return `合格 ${event.good_qty || 0} / 不良 ${event.bad_qty || 0}`
  }
  if (event.detail?.work_center) {
    return String(event.detail.work_center)
  }
  return ''
}

function workOrderStatusTag(status: WorkOrderStatus) {
  if (status === 'draft') {
    return 'warning'
  }
  if (['pending', 'scheduled'].includes(status)) {
    return 'info'
  }
  if (['completed', 'closed'].includes(status)) {
    return 'success'
  }
  if (status === 'cancelled') {
    return 'danger'
  }
  return 'primary'
}

function workOrderStatusText(status: WorkOrderStatus) {
  return workOrderStatusLabels[status] || status
}

function canCancel(status: WorkOrderStatus) {
  return ['draft', 'pending', 'scheduled', 'in_progress', 'paused'].includes(status)
}

function priorityText(priority: Priority) {
  return priorityLabels[priority] || priority
}
</script>
