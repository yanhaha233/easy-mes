<template>
  <main class="page master-page">
    <section class="page-hero compact">
      <div>
        <p class="eyebrow">主数据</p>
        <h1>基础档案</h1>
        <p class="hero-copy">先维护物料、工位、人员、BOM 和工艺路线，后续工单才能稳定展开。</p>
      </div>
      <el-button :icon="Refresh" :loading="refreshing" @click="refreshActive">刷新</el-button>
    </section>

    <section class="sheet master-sheet">
      <el-tabs v-model="activeTab" class="master-tabs">
        <el-tab-pane v-for="config in simpleConfigList" :key="config.key" :label="config.title" :name="config.key" />
        <el-tab-pane label="BOM" name="boms" />
        <el-tab-pane label="工艺路线" name="routings" />
      </el-tabs>

      <template v-if="currentSimpleConfig">
        <div class="list-toolbar">
          <div>
            <h2>{{ currentSimpleConfig.title }}</h2>
            <p>{{ currentSimpleConfig.description }}</p>
          </div>
          <div class="toolbar-actions">
            <el-input
              v-model="activeSimpleState.keyword"
              :prefix-icon="Search"
              clearable
              placeholder="编码 / 名称"
              @keyup.enter="loadActiveSimple"
              @clear="loadActiveSimple"
            />
            <el-select v-model="activeSimpleState.is_active" placeholder="状态" @change="loadActiveSimple">
              <el-option label="全部" value="" />
              <el-option label="启用" :value="true" />
              <el-option label="停用" :value="false" />
            </el-select>
            <el-button type="primary" :icon="Plus" @click="openSimpleCreate">
              新增{{ currentSimpleConfig.title }}
            </el-button>
          </div>
        </div>

        <el-table v-loading="activeSimpleState.loading" :data="activeSimpleState.items" class="desktop-table">
          <el-table-column prop="code" label="编码" min-width="140" />
          <el-table-column prop="name" label="名称" min-width="160" />
          <el-table-column
            v-for="column in currentSimpleConfig.columns"
            :key="column.label"
            :label="column.label"
            :min-width="column.minWidth ?? 120"
          >
            <template #default="{ row }">{{ column.format(row) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" effect="plain">
                {{ row.is_active ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" :icon="Edit" @click="openSimpleEdit(row)">编辑</el-button>
              <el-button link type="danger" :icon="Delete" @click="removeSimple(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-loading="activeSimpleState.loading" class="mobile-records">
          <article v-for="row in activeSimpleState.items" :key="row.id" class="record-row">
            <div class="record-main">
              <div>
                <strong>{{ row.name }}</strong>
                <span>{{ row.code }}</span>
              </div>
              <el-tag :type="row.is_active ? 'success' : 'info'" effect="plain">
                {{ row.is_active ? '启用' : '停用' }}
              </el-tag>
            </div>
            <dl>
              <template v-for="column in currentSimpleConfig.columns" :key="column.label">
                <dt>{{ column.label }}</dt>
                <dd>{{ column.format(row) }}</dd>
              </template>
            </dl>
            <div class="record-actions">
              <el-button :icon="Edit" @click="openSimpleEdit(row)">编辑</el-button>
              <el-button :icon="Delete" type="danger" plain @click="removeSimple(row)">删除</el-button>
            </div>
          </article>
        </div>

        <el-empty v-if="!activeSimpleState.loading && activeSimpleState.items.length === 0" description="暂无数据" />

        <el-pagination
          v-model:current-page="activeSimpleState.page"
          background
          layout="prev, pager, next"
          :page-size="pageSize"
          :total="activeSimpleState.total"
          @current-change="loadActiveSimple"
        />
      </template>

      <template v-else-if="activeTab === 'boms'">
        <div class="list-toolbar">
          <div>
            <h2>BOM</h2>
            <p>定义每个成品或半成品的一层用料，工单创建时按激活版本展开。</p>
          </div>
          <div class="toolbar-actions">
            <el-select v-model="bomState.material_id" clearable filterable placeholder="物料" @change="loadBoms">
              <el-option v-for="item in materialOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
            <el-select v-model="bomState.status" clearable placeholder="状态" @change="loadBoms">
              <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
            <el-button type="primary" :icon="Plus" @click="openBomCreate">新增 BOM</el-button>
          </div>
        </div>

        <el-table v-loading="bomState.loading" :data="bomState.items" class="desktop-table">
          <el-table-column label="物料" min-width="200">
            <template #default="{ row }">{{ materialLabel(row.material_id) }}</template>
          </el-table-column>
          <el-table-column prop="version" label="版本" width="120" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="statusTag(row.status)" effect="plain">{{ statusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="子件" min-width="220">
            <template #default="{ row }">
              {{ bomLineSummary(row) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" :icon="Edit" @click="openBomEdit(row)">编辑</el-button>
              <el-button link type="danger" :icon="Delete" @click="removeBom(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-loading="bomState.loading" class="mobile-records">
          <article v-for="row in bomState.items" :key="row.id" class="record-row">
            <div class="record-main">
              <div>
                <strong>{{ materialLabel(row.material_id) }}</strong>
                <span>版本 {{ row.version }}</span>
              </div>
              <el-tag :type="statusTag(row.status)" effect="plain">{{ statusText(row.status) }}</el-tag>
            </div>
            <dl>
              <dt>子件数</dt>
              <dd>{{ row.lines.length }}</dd>
              <dt>备注</dt>
              <dd>{{ row.remark || '-' }}</dd>
            </dl>
            <div class="record-actions">
              <el-button :icon="Edit" @click="openBomEdit(row)">编辑</el-button>
              <el-button :icon="Delete" type="danger" plain @click="removeBom(row)">删除</el-button>
            </div>
          </article>
        </div>

        <el-empty v-if="!bomState.loading && bomState.items.length === 0" description="暂无 BOM" />

        <el-pagination
          v-model:current-page="bomState.page"
          background
          layout="prev, pager, next"
          :page-size="pageSize"
          :total="bomState.total"
          @current-change="loadBoms"
        />
      </template>

      <template v-else>
        <div class="list-toolbar">
          <div>
            <h2>工艺路线</h2>
            <p>定义物料的工序顺序、工位和标准工时，后续工单按这里拆分任务。</p>
          </div>
          <div class="toolbar-actions">
            <el-select v-model="routingState.material_id" clearable filterable placeholder="物料" @change="loadRoutings">
              <el-option v-for="item in materialOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
            <el-select v-model="routingState.status" clearable placeholder="状态" @change="loadRoutings">
              <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
            <el-button type="primary" :icon="Plus" @click="openRoutingCreate">新增工艺路线</el-button>
          </div>
        </div>

        <el-table v-loading="routingState.loading" :data="routingState.items" class="desktop-table">
          <el-table-column label="物料" min-width="200">
            <template #default="{ row }">{{ materialLabel(row.material_id) }}</template>
          </el-table-column>
          <el-table-column prop="version" label="版本" width="120" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="statusTag(row.status)" effect="plain">{{ statusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="工序" min-width="260">
            <template #default="{ row }">
              {{ routingOperationSummary(row) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" :icon="Edit" @click="openRoutingEdit(row)">编辑</el-button>
              <el-button link type="danger" :icon="Delete" @click="removeRouting(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-loading="routingState.loading" class="mobile-records">
          <article v-for="row in routingState.items" :key="row.id" class="record-row">
            <div class="record-main">
              <div>
                <strong>{{ materialLabel(row.material_id) }}</strong>
                <span>版本 {{ row.version }}</span>
              </div>
              <el-tag :type="statusTag(row.status)" effect="plain">{{ statusText(row.status) }}</el-tag>
            </div>
            <dl>
              <dt>工序数</dt>
              <dd>{{ row.operations.length }}</dd>
              <dt>备注</dt>
              <dd>{{ row.remark || '-' }}</dd>
            </dl>
            <div class="record-actions">
              <el-button :icon="Edit" @click="openRoutingEdit(row)">编辑</el-button>
              <el-button :icon="Delete" type="danger" plain @click="removeRouting(row)">删除</el-button>
            </div>
          </article>
        </div>

        <el-empty v-if="!routingState.loading && routingState.items.length === 0" description="暂无工艺路线" />

        <el-pagination
          v-model:current-page="routingState.page"
          background
          layout="prev, pager, next"
          :page-size="pageSize"
          :total="routingState.total"
          @current-change="loadRoutings"
        />
      </template>
    </section>

    <el-drawer
      v-model="simpleDrawerOpen"
      :title="simpleEditingId ? `编辑${currentSimpleConfig?.title}` : `新增${currentSimpleConfig?.title}`"
      size="560px"
      destroy-on-close
    >
      <el-form label-position="top" :model="simpleForm" @submit.prevent>
        <el-form-item v-for="field in currentSimpleConfig?.fields" :key="field.prop" :label="field.label" :required="field.required">
          <el-input
            v-if="field.kind === 'text'"
            v-model="simpleForm[field.prop]"
            :disabled="Boolean(simpleEditingId && field.disabledOnEdit)"
            :placeholder="field.placeholder"
          />
          <el-input
            v-else-if="field.kind === 'textarea'"
            v-model="simpleForm[field.prop]"
            :rows="3"
            type="textarea"
            :placeholder="field.placeholder"
          />
          <el-select v-else-if="field.kind === 'select'" v-model="simpleForm[field.prop]" clearable filterable>
            <el-option v-for="item in resolveOptions(field)" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-select
            v-else-if="field.kind === 'multi-select'"
            v-model="simpleForm[field.prop]"
            clearable
            filterable
            multiple
          >
            <el-option v-for="item in resolveOptions(field)" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-switch v-else v-model="simpleForm[field.prop]" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="simpleDrawerOpen = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveSimple">保存</el-button>
      </template>
    </el-drawer>

    <el-drawer v-model="bomDrawerOpen" :title="bomEditingId ? '编辑 BOM' : '新增 BOM'" size="640px" destroy-on-close>
      <el-form label-position="top" :model="bomForm" @submit.prevent>
        <div class="form-grid">
          <el-form-item label="物料" required>
            <el-select v-model="bomForm.material_id" :disabled="Boolean(bomEditingId)" filterable placeholder="选择成品或半成品">
              <el-option v-for="item in materialOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="版本" required>
            <el-input v-model="bomForm.version" :disabled="Boolean(bomEditingId)" placeholder="例如 V1" />
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="bomForm.status">
              <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="备注">
          <el-input v-model="bomForm.remark" :rows="2" type="textarea" />
        </el-form-item>

        <div class="nested-header">
          <strong>子件明细</strong>
          <el-button :icon="Plus" @click="addBomLine">增加子件</el-button>
        </div>
        <div v-for="(line, index) in bomForm.lines" :key="line.client_id" class="nested-line">
          <div class="nested-title">
            <span>第 {{ index + 1 }} 行</span>
            <el-button :icon="Delete" link type="danger" @click="removeBomLine(index)">删除</el-button>
          </div>
          <div class="form-grid">
            <el-form-item label="行号" required>
              <el-input-number v-model="line.line_no" :min="1" :step="10" controls-position="right" />
            </el-form-item>
            <el-form-item label="子件物料" required>
              <el-select v-model="line.component_material_id" filterable placeholder="选择子件">
                <el-option v-for="item in materialOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="单位用量" required>
              <el-input v-model="line.qty_per" inputmode="decimal" />
            </el-form-item>
            <el-form-item label="损耗率">
              <el-input v-model="line.loss_rate" inputmode="decimal" />
            </el-form-item>
          </div>
          <el-form-item label="备注">
            <el-input v-model="line.remark" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="bomDrawerOpen = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveBom">保存</el-button>
      </template>
    </el-drawer>

    <el-drawer
      v-model="routingDrawerOpen"
      :title="routingEditingId ? '编辑工艺路线' : '新增工艺路线'"
      size="680px"
      destroy-on-close
    >
      <el-form label-position="top" :model="routingForm" @submit.prevent>
        <div class="form-grid">
          <el-form-item label="物料" required>
            <el-select
              v-model="routingForm.material_id"
              :disabled="Boolean(routingEditingId)"
              filterable
              placeholder="选择成品或半成品"
            >
              <el-option v-for="item in materialOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="版本" required>
            <el-input v-model="routingForm.version" :disabled="Boolean(routingEditingId)" placeholder="例如 V1" />
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="routingForm.status">
              <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="备注">
          <el-input v-model="routingForm.remark" :rows="2" type="textarea" />
        </el-form-item>

        <div class="nested-header">
          <strong>工序明细</strong>
          <el-button :icon="Plus" @click="addRoutingOperation">增加工序</el-button>
        </div>
        <div v-for="(operation, index) in routingForm.operations" :key="operation.client_id" class="nested-line">
          <div class="nested-title">
            <span>工序 {{ index + 1 }}</span>
            <el-button :icon="Delete" link type="danger" @click="removeRoutingOperation(index)">删除</el-button>
          </div>
          <div class="form-grid">
            <el-form-item label="序号" required>
              <el-input-number v-model="operation.seq" :min="1" :step="10" controls-position="right" />
            </el-form-item>
            <el-form-item label="工序编码" required>
              <el-input v-model="operation.operation_code" placeholder="OP-10" />
            </el-form-item>
            <el-form-item label="工序名称" required>
              <el-input v-model="operation.operation_name" placeholder="例如 CNC 加工" />
            </el-form-item>
            <el-form-item label="工位" required>
              <el-select v-model="operation.work_center_id" filterable placeholder="选择工位">
                <el-option v-for="item in workCenterOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="准备工时(秒)">
              <el-input-number v-model="operation.setup_time_sec" :min="0" controls-position="right" />
            </el-form-item>
            <el-form-item label="单件工时(秒)">
              <el-input-number v-model="operation.unit_time_sec" :min="0" controls-position="right" />
            </el-form-item>
          </div>
          <el-form-item label="备注">
            <el-input v-model="operation.remark" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="routingDrawerOpen = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveRouting">保存</el-button>
      </template>
    </el-drawer>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { Delete, Edit, Plus, Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ApiError } from '../api/client'
import {
  createMaster,
  deleteMaster,
  getWorkerOperationSkills,
  listMaster,
  loadLookups,
  updateMaster,
  updateWorkerOperationSkills,
  type Bom,
  type DefectReason,
  type Material,
  type Routing,
  type SimpleEntity,
  type SimpleResource,
  type Team,
  type WorkCenter,
  type Worker,
} from '../api/masterData'
import type { MasterStatus } from '../types/masterData'
import {
  booleanLabels,
  materialTypeLabels,
  statusLabels,
  workCenterTypeLabels,
  workerTypeLabels,
} from '../utils/labels'

type Option = { label: string; value: string | boolean }
type FieldKind = 'text' | 'textarea' | 'select' | 'multi-select' | 'switch'
type SimpleKey = SimpleResource
type FormRecord = Record<string, unknown>

interface FieldConfig {
  prop: string
  label: string
  kind: FieldKind
  required?: boolean
  disabledOnEdit?: boolean
  placeholder?: string
  options?: Option[] | (() => Option[])
}

interface ColumnConfig {
  label: string
  minWidth?: number
  format: (row: SimpleEntity) => string
}

interface SimpleConfig {
  key: SimpleKey
  title: string
  description: string
  columns: ColumnConfig[]
  fields: FieldConfig[]
  defaults: () => FormRecord
  nullableFields: string[]
}

interface SimpleState {
  items: SimpleEntity[]
  total: number
  loading: boolean
  keyword: string
  is_active: boolean | ''
  page: number
}

interface BomLineForm {
  client_id: string
  component_material_id: string
  line_no: number
  qty_per: string
  loss_rate: string
  remark: string
}

interface RoutingOperationForm {
  client_id: string
  seq: number
  operation_code: string
  operation_name: string
  work_center_id: string
  setup_time_sec: number
  unit_time_sec: number
  remark: string
}

const pageSize = 20
const activeTab = ref<SimpleKey | 'boms' | 'routings'>('materials')
const refreshing = ref(false)
const saving = ref(false)
const simpleDrawerOpen = ref(false)
const simpleEditingId = ref<string | null>(null)
const simpleForm = ref<FormRecord>({})
const bomDrawerOpen = ref(false)
const bomEditingId = ref<string | null>(null)
const routingDrawerOpen = ref(false)
const routingEditingId = ref<string | null>(null)

const lookups = reactive({
  materials: [] as Material[],
  workCenters: [] as WorkCenter[],
  teams: [] as Team[],
  operationSkillOptions: [] as { operation_code: string; operation_name: string }[],
})

const materialTypeOptions = Object.entries(materialTypeLabels).map(([value, label]) => ({ value, label }))
const workCenterTypeOptions = Object.entries(workCenterTypeLabels).map(([value, label]) => ({ value, label }))
const workerTypeOptions = Object.entries(workerTypeLabels).map(([value, label]) => ({ value, label }))
const statusOptions = Object.entries(statusLabels).map(([value, label]) => ({ value, label }))

const teamOptions = computed<Option[]>(() => [
  { label: '不分班组', value: '' },
  ...lookups.teams.map((team) => ({ label: `${team.code} ${team.name}`, value: team.id })),
])

const materialOptions = computed(() => lookups.materials.map((item) => ({ label: `${item.code} ${item.name}`, value: item.id })))
const workCenterOptions = computed(() =>
  lookups.workCenters.map((item) => ({ label: `${item.code} ${item.name}`, value: item.id })),
)
const operationSkillOptions = computed<Option[]>(() =>
  lookups.operationSkillOptions.map((item) => ({
    label: `${item.operation_code} ${item.operation_name}`,
    value: item.operation_code,
  })),
)

const simpleConfigs: Record<SimpleKey, SimpleConfig> = {
  materials: {
    key: 'materials',
    title: '物料',
    description: '维护成品、半成品、原材料和包材，是 BOM 与工单展开的基础。',
    columns: [
      { label: '类型', format: (row) => materialTypeLabels[(row as Material).material_type] },
      { label: '规格', minWidth: 160, format: (row) => (row as Material).spec || '-' },
      { label: '单位', format: (row) => (row as Material).unit },
      { label: '允许空 BOM', minWidth: 120, format: (row) => ((row as Material).allow_empty_bom ? '允许' : '不允许') },
    ],
    fields: [
      { prop: 'code', label: '物料编码', kind: 'text', required: true, disabledOnEdit: true },
      { prop: 'name', label: '物料名称', kind: 'text', required: true },
      { prop: 'material_type', label: '物料类型', kind: 'select', required: true, options: materialTypeOptions },
      { prop: 'spec', label: '规格型号', kind: 'text' },
      { prop: 'unit', label: '单位', kind: 'text', required: true },
      { prop: 'allow_empty_bom', label: '允许空 BOM', kind: 'switch' },
      { prop: 'is_active', label: '状态', kind: 'switch' },
      { prop: 'remark', label: '备注', kind: 'textarea' },
    ],
    defaults: () => ({
      code: '',
      name: '',
      material_type: 'product',
      spec: '',
      unit: '件',
      allow_empty_bom: false,
      is_active: true,
      remark: '',
    }),
    nullableFields: ['spec', 'remark'],
  },
  workCenters: {
    key: 'workCenters',
    title: '工位',
    description: '维护车间里的工位、设备、产线和检验点，后续工序任务会派到这里。',
    columns: [
      { label: '类型', format: (row) => workCenterTypeLabels[(row as WorkCenter).work_center_type] },
      { label: '位置', minWidth: 160, format: (row) => (row as WorkCenter).location || '-' },
    ],
    fields: [
      { prop: 'code', label: '工位编码', kind: 'text', required: true, disabledOnEdit: true },
      { prop: 'name', label: '工位名称', kind: 'text', required: true },
      { prop: 'work_center_type', label: '工位类型', kind: 'select', required: true, options: workCenterTypeOptions },
      { prop: 'location', label: '位置', kind: 'text' },
      { prop: 'is_active', label: '状态', kind: 'switch' },
      { prop: 'remark', label: '备注', kind: 'textarea' },
    ],
    defaults: () => ({
      code: '',
      name: '',
      work_center_type: 'workstation',
      location: '',
      is_active: true,
      remark: '',
    }),
    nullableFields: ['location', 'remark'],
  },
  teams: {
    key: 'teams',
    title: '班组',
    description: '维护班组和班组长，先满足默认操作员的归属和后续报工统计。',
    columns: [{ label: '班组长', minWidth: 140, format: (row) => (row as Team).leader_name || '-' }],
    fields: [
      { prop: 'code', label: '班组编码', kind: 'text', required: true, disabledOnEdit: true },
      { prop: 'name', label: '班组名称', kind: 'text', required: true },
      { prop: 'leader_name', label: '班组长', kind: 'text' },
      { prop: 'is_active', label: '状态', kind: 'switch' },
      { prop: 'remark', label: '备注', kind: 'textarea' },
    ],
    defaults: () => ({ code: '', name: '', leader_name: '', is_active: true, remark: '' }),
    nullableFields: ['leader_name', 'remark'],
  },
  workers: {
    key: 'workers',
    title: '人员',
    description: '维护操作员、质检员和计划员；操作员需要配置可做工序后才能被派工。',
    columns: [
      { label: '角色', format: (row) => workerTypeLabels[(row as Worker).worker_type] },
      { label: '班组', minWidth: 160, format: (row) => teamLabel((row as Worker).team_id) },
    ],
    fields: [
      { prop: 'code', label: '人员编码', kind: 'text', required: true, disabledOnEdit: true },
      { prop: 'name', label: '姓名', kind: 'text', required: true },
      { prop: 'worker_type', label: '角色', kind: 'select', required: true, options: workerTypeOptions },
      { prop: 'team_id', label: '班组', kind: 'select', options: () => teamOptions.value },
      { prop: 'operation_skill_codes', label: '可做工序', kind: 'multi-select', options: () => operationSkillOptions.value },
      { prop: 'is_active', label: '状态', kind: 'switch' },
      { prop: 'remark', label: '备注', kind: 'textarea' },
    ],
    defaults: () => ({
      code: '',
      name: '',
      worker_type: 'operator',
      team_id: '',
      operation_skill_codes: [],
      is_active: true,
      remark: '',
    }),
    nullableFields: ['team_id', 'remark'],
  },
  defectReasons: {
    key: 'defectReasons',
    title: '不良原因',
    description: '报工和质检共用的不良原因字典，先保持简单可选。',
    columns: [{ label: '分类', minWidth: 140, format: (row) => (row as DefectReason).category || '-' }],
    fields: [
      { prop: 'code', label: '原因编码', kind: 'text', required: true, disabledOnEdit: true },
      { prop: 'name', label: '原因名称', kind: 'text', required: true },
      { prop: 'category', label: '分类', kind: 'text' },
      { prop: 'is_active', label: '状态', kind: 'switch' },
      { prop: 'remark', label: '备注', kind: 'textarea' },
    ],
    defaults: () => ({ code: '', name: '', category: '', is_active: true, remark: '' }),
    nullableFields: ['category', 'remark'],
  },
}

const simpleConfigList = Object.values(simpleConfigs)
const simpleStates = reactive<Record<SimpleKey, SimpleState>>({
  materials: makeSimpleState(),
  workCenters: makeSimpleState(),
  teams: makeSimpleState(),
  workers: makeSimpleState(),
  defectReasons: makeSimpleState(),
})

const bomState = reactive({
  items: [] as Bom[],
  total: 0,
  loading: false,
  page: 1,
  material_id: '',
  status: '',
})

const bomForm = reactive({
  material_id: '',
  version: 'V1',
  status: 'draft' as MasterStatus,
  remark: '',
  lines: [] as BomLineForm[],
})

const routingState = reactive({
  items: [] as Routing[],
  total: 0,
  loading: false,
  page: 1,
  material_id: '',
  status: '',
})

const routingForm = reactive({
  material_id: '',
  version: 'V1',
  status: 'draft' as MasterStatus,
  remark: '',
  operations: [] as RoutingOperationForm[],
})

const currentSimpleConfig = computed(() => {
  if (activeTab.value === 'boms' || activeTab.value === 'routings') {
    return null
  }
  return simpleConfigs[activeTab.value]
})

const activeSimpleState = computed(() => simpleStates[activeTab.value as SimpleKey])

watch(activeTab, async () => {
  simpleDrawerOpen.value = false
  if (currentSimpleConfig.value) {
    await loadActiveSimple()
  } else if (activeTab.value === 'boms') {
    await loadBoms()
  } else {
    await loadRoutings()
  }
})

onMounted(async () => {
  await refreshLookups()
  await loadActiveSimple()
})

function makeSimpleState(): SimpleState {
  return {
    items: [],
    total: 0,
    loading: false,
    keyword: '',
    is_active: '',
    page: 1,
  }
}

function resolveOptions(field: FieldConfig) {
  if (!field.options) {
    return []
  }
  return typeof field.options === 'function' ? field.options() : field.options
}

function showError(error: unknown) {
  if (error instanceof ApiError) {
    ElMessage.error(error.message)
    return
  }
  ElMessage.error('操作失败，请稍后重试')
}

function normalizeNullable(payload: FormRecord, fields: string[]) {
  for (const field of fields) {
    if (payload[field] === '') {
      payload[field] = null
    }
  }
  return payload
}

function requiredText(value: unknown) {
  return typeof value === 'string' ? value.trim().length > 0 : Boolean(value)
}

function validateSimple(config: SimpleConfig) {
  for (const field of config.fields) {
    if (field.required && !requiredText(simpleForm.value[field.prop])) {
      ElMessage.warning(`请填写${field.label}`)
      return false
    }
  }
  return true
}

async function refreshLookups() {
  const data = await loadLookups()
  lookups.materials = data.materials
  lookups.workCenters = data.workCenters
  lookups.teams = data.teams
  lookups.operationSkillOptions = data.operationSkillOptions
}

async function refreshActive() {
  refreshing.value = true
  try {
    await refreshLookups()
    if (currentSimpleConfig.value) {
      await loadActiveSimple()
    } else if (activeTab.value === 'boms') {
      await loadBoms()
    } else {
      await loadRoutings()
    }
  } catch (error) {
    showError(error)
  } finally {
    refreshing.value = false
  }
}

async function loadActiveSimple() {
  const config = currentSimpleConfig.value
  if (!config) {
    return
  }
  const state = activeSimpleState.value
  state.loading = true
  try {
    const page = await listMaster(config.key, {
      keyword: state.keyword,
      is_active: state.is_active,
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

function openSimpleCreate() {
  const config = currentSimpleConfig.value
  if (!config) {
    return
  }
  simpleEditingId.value = null
  simpleForm.value = config.defaults()
  simpleDrawerOpen.value = true
}

async function openSimpleEdit(row: SimpleEntity) {
  const config = currentSimpleConfig.value
  if (!config) {
    return
  }
  simpleEditingId.value = row.id
  simpleForm.value = { ...config.defaults(), ...row }
  if (config.key === 'workers' && (row as Worker).worker_type === 'operator') {
    try {
      const skills = await getWorkerOperationSkills(row.id)
      simpleForm.value.operation_skill_codes = skills.map((item) => item.operation_code)
    } catch (error) {
      showError(error)
    }
  }
  simpleDrawerOpen.value = true
}

async function saveSimple() {
  const config = currentSimpleConfig.value
  if (!config || !validateSimple(config)) {
    return
  }
  saving.value = true
  try {
    const payload = normalizeNullable({ ...simpleForm.value }, config.nullableFields)
    const operationSkillCodes = Array.isArray(payload.operation_skill_codes)
      ? (payload.operation_skill_codes as string[])
      : []
    delete payload.operation_skill_codes
    delete payload.id
    delete payload.tenant_id
    delete payload.created_at
    delete payload.updated_at
    delete payload.deleted_at
    const shouldSaveSkills = config.key === 'workers' && payload.worker_type === 'operator'
    let saved: SimpleEntity
    if (simpleEditingId.value) {
      delete payload.code
      saved = await updateMaster(config.key, simpleEditingId.value, payload)
      if (shouldSaveSkills) {
        await updateWorkerOperationSkills(simpleEditingId.value, operationSkillCodes)
      }
      ElMessage.success('已保存')
    } else {
      saved = await createMaster(config.key, payload)
      if (shouldSaveSkills) {
        await updateWorkerOperationSkills(saved.id, operationSkillCodes)
      }
      ElMessage.success('已新增')
    }
    simpleDrawerOpen.value = false
    await refreshLookups()
    await loadActiveSimple()
  } catch (error) {
    showError(error)
  } finally {
    saving.value = false
  }
}

async function removeSimple(row: SimpleEntity) {
  const config = currentSimpleConfig.value
  if (!config) {
    return
  }
  try {
    await ElMessageBox.confirm(`确认删除 ${row.code} ${row.name}？`, '删除确认', { type: 'warning' })
    await deleteMaster(config.key, row.id)
    ElMessage.success('已删除')
    await refreshLookups()
    await loadActiveSimple()
  } catch (error) {
    if (error !== 'cancel') {
      showError(error)
    }
  }
}

function emptyToNull(value: string) {
  const trimmed = value.trim()
  return trimmed ? trimmed : null
}

function resetBomForm() {
  bomForm.material_id = ''
  bomForm.version = 'V1'
  bomForm.status = 'draft'
  bomForm.remark = ''
  bomForm.lines = [makeBomLine(10)]
}

function makeBomLine(lineNo: number): BomLineForm {
  return {
    client_id: crypto.randomUUID(),
    component_material_id: '',
    line_no: lineNo,
    qty_per: '1',
    loss_rate: '0',
    remark: '',
  }
}

function openBomCreate() {
  bomEditingId.value = null
  resetBomForm()
  bomDrawerOpen.value = true
}

function openBomEdit(row: Bom) {
  bomEditingId.value = row.id
  bomForm.material_id = row.material_id
  bomForm.version = row.version
  bomForm.status = row.status
  bomForm.remark = row.remark || ''
  bomForm.lines = row.lines.map((line) => ({
    client_id: crypto.randomUUID(),
    component_material_id: line.component_material_id,
    line_no: line.line_no,
    qty_per: String(line.qty_per),
    loss_rate: String(line.loss_rate),
    remark: line.remark || '',
  }))
  if (bomForm.lines.length === 0) {
    bomForm.lines = [makeBomLine(10)]
  }
  bomDrawerOpen.value = true
}

function addBomLine() {
  const nextLineNo = (bomForm.lines.at(-1)?.line_no ?? 0) + 10
  bomForm.lines.push(makeBomLine(nextLineNo))
}

function removeBomLine(index: number) {
  bomForm.lines.splice(index, 1)
  if (bomForm.lines.length === 0) {
    addBomLine()
  }
}

function validateBom() {
  if (!bomForm.material_id) {
    ElMessage.warning('请选择物料')
    return false
  }
  if (!bomForm.version.trim()) {
    ElMessage.warning('请填写版本')
    return false
  }
  for (const line of bomForm.lines) {
    if (!line.component_material_id) {
      ElMessage.warning('请选择子件物料')
      return false
    }
    if (!Number(line.qty_per) || Number(line.qty_per) <= 0) {
      ElMessage.warning('子件单位用量必须大于 0')
      return false
    }
  }
  return true
}

async function saveBom() {
  if (!validateBom()) {
    return
  }
  saving.value = true
  try {
    const payload = {
      material_id: bomForm.material_id,
      version: bomForm.version.trim(),
      status: bomForm.status,
      remark: emptyToNull(bomForm.remark),
      lines: bomForm.lines.map((line) => ({
        component_material_id: line.component_material_id,
        line_no: Number(line.line_no),
        qty_per: line.qty_per,
        loss_rate: line.loss_rate || '0',
        remark: emptyToNull(line.remark),
      })),
    }
    if (bomEditingId.value) {
      await updateMaster('boms', bomEditingId.value, payload)
      ElMessage.success('已保存')
    } else {
      await createMaster('boms', payload)
      ElMessage.success('已新增')
    }
    bomDrawerOpen.value = false
    await loadBoms()
  } catch (error) {
    showError(error)
  } finally {
    saving.value = false
  }
}

async function loadBoms() {
  bomState.loading = true
  try {
    const page = await listMaster('boms', {
      material_id: bomState.material_id,
      status: bomState.status,
      limit: pageSize,
      offset: (bomState.page - 1) * pageSize,
    })
    bomState.items = page.items
    bomState.total = page.total
  } catch (error) {
    showError(error)
  } finally {
    bomState.loading = false
  }
}

async function removeBom(row: Bom) {
  try {
    await ElMessageBox.confirm(`确认删除 ${materialLabel(row.material_id)} 的 BOM ${row.version}？`, '删除确认', { type: 'warning' })
    await deleteMaster('boms', row.id)
    ElMessage.success('已删除')
    await loadBoms()
  } catch (error) {
    if (error !== 'cancel') {
      showError(error)
    }
  }
}

function resetRoutingForm() {
  routingForm.material_id = ''
  routingForm.version = 'V1'
  routingForm.status = 'draft'
  routingForm.remark = ''
  routingForm.operations = [makeRoutingOperation(10)]
}

function makeRoutingOperation(seq: number): RoutingOperationForm {
  return {
    client_id: crypto.randomUUID(),
    seq,
    operation_code: `OP-${seq}`,
    operation_name: '',
    work_center_id: '',
    setup_time_sec: 0,
    unit_time_sec: 0,
    remark: '',
  }
}

function openRoutingCreate() {
  routingEditingId.value = null
  resetRoutingForm()
  routingDrawerOpen.value = true
}

function openRoutingEdit(row: Routing) {
  routingEditingId.value = row.id
  routingForm.material_id = row.material_id
  routingForm.version = row.version
  routingForm.status = row.status
  routingForm.remark = row.remark || ''
  routingForm.operations = row.operations.map((operation) => ({
    client_id: crypto.randomUUID(),
    seq: operation.seq,
    operation_code: operation.operation_code,
    operation_name: operation.operation_name,
    work_center_id: operation.work_center_id,
    setup_time_sec: operation.setup_time_sec,
    unit_time_sec: operation.unit_time_sec,
    remark: operation.remark || '',
  }))
  if (routingForm.operations.length === 0) {
    routingForm.operations = [makeRoutingOperation(10)]
  }
  routingDrawerOpen.value = true
}

function addRoutingOperation() {
  const nextSeq = (routingForm.operations.at(-1)?.seq ?? 0) + 10
  routingForm.operations.push(makeRoutingOperation(nextSeq))
}

function removeRoutingOperation(index: number) {
  routingForm.operations.splice(index, 1)
  if (routingForm.operations.length === 0) {
    addRoutingOperation()
  }
}

function validateRouting() {
  if (!routingForm.material_id) {
    ElMessage.warning('请选择物料')
    return false
  }
  if (!routingForm.version.trim()) {
    ElMessage.warning('请填写版本')
    return false
  }
  for (const operation of routingForm.operations) {
    if (!operation.operation_code.trim() || !operation.operation_name.trim() || !operation.work_center_id) {
      ElMessage.warning('请完整填写工序编码、名称和工位')
      return false
    }
  }
  return true
}

async function saveRouting() {
  if (!validateRouting()) {
    return
  }
  saving.value = true
  try {
    const payload = {
      material_id: routingForm.material_id,
      version: routingForm.version.trim(),
      status: routingForm.status,
      remark: emptyToNull(routingForm.remark),
      operations: routingForm.operations.map((operation) => ({
        seq: Number(operation.seq),
        operation_code: operation.operation_code.trim(),
        operation_name: operation.operation_name.trim(),
        work_center_id: operation.work_center_id,
        setup_time_sec: Number(operation.setup_time_sec) || 0,
        unit_time_sec: Number(operation.unit_time_sec) || 0,
        is_active: true,
        remark: emptyToNull(operation.remark),
      })),
    }
    if (routingEditingId.value) {
      await updateMaster('routings', routingEditingId.value, payload)
      ElMessage.success('已保存')
    } else {
      await createMaster('routings', payload)
      ElMessage.success('已新增')
    }
    routingDrawerOpen.value = false
    await loadRoutings()
  } catch (error) {
    showError(error)
  } finally {
    saving.value = false
  }
}

async function loadRoutings() {
  routingState.loading = true
  try {
    const page = await listMaster('routings', {
      material_id: routingState.material_id,
      status: routingState.status,
      limit: pageSize,
      offset: (routingState.page - 1) * pageSize,
    })
    routingState.items = page.items
    routingState.total = page.total
  } catch (error) {
    showError(error)
  } finally {
    routingState.loading = false
  }
}

async function removeRouting(row: Routing) {
  try {
    await ElMessageBox.confirm(`确认删除 ${materialLabel(row.material_id)} 的工艺路线 ${row.version}？`, '删除确认', {
      type: 'warning',
    })
    await deleteMaster('routings', row.id)
    ElMessage.success('已删除')
    await loadRoutings()
  } catch (error) {
    if (error !== 'cancel') {
      showError(error)
    }
  }
}

function materialLabel(id: string | null | undefined) {
  if (!id) {
    return '-'
  }
  const material = lookups.materials.find((item) => item.id === id)
  return material ? `${material.code} ${material.name}` : id.slice(0, 8)
}

function teamLabel(id: string | null | undefined) {
  if (!id) {
    return '不分班组'
  }
  const team = lookups.teams.find((item) => item.id === id)
  return team ? `${team.code} ${team.name}` : id.slice(0, 8)
}

function bomLineSummary(row: Bom) {
  return row.lines.map((line) => line.component_material_code || line.component_material_name).join('，') || '-'
}

function routingOperationSummary(row: Routing) {
  return row.operations.map((operation) => `${operation.seq}-${operation.operation_name}`).join('，') || '-'
}

function statusText(status: MasterStatus) {
  return statusLabels[status] || status
}

function statusTag(status: MasterStatus) {
  if (status === 'active') {
    return 'success'
  }
  if (status === 'draft') {
    return 'warning'
  }
  return 'info'
}
</script>
