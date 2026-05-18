import type { MasterStatus, MaterialType, WorkerType, WorkCenterType } from '../types/masterData'
import type { OperationStatus, Priority, WorkOrderSource, WorkOrderStatus } from '../types/workOrder'

export const materialTypeLabels: Record<MaterialType, string> = {
  product: '成品',
  semi_finished: '半成品',
  raw_material: '原材料',
  packing: '包材',
  tooling: '工装夹具',
}

export const workCenterTypeLabels: Record<WorkCenterType, string> = {
  workstation: '工位',
  equipment: '设备',
  line: '产线',
  inspection: '检验点',
}

export const workerTypeLabels: Record<WorkerType, string> = {
  operator: '操作员',
  inspector: '质检员',
  planner: '计划员',
  manager: '管理者',
}

export const statusLabels: Record<MasterStatus, string> = {
  draft: '草稿',
  active: '启用',
  inactive: '停用',
}

export const booleanLabels = {
  active: '启用',
  inactive: '停用',
}

export const priorityLabels: Record<Priority, string> = {
  normal: '普通',
  high: '高',
  urgent: '紧急',
}

export const workOrderSourceLabels: Record<WorkOrderSource, string> = {
  manual: '手工',
  erp: 'ERP',
}

export const workOrderStatusLabels: Record<WorkOrderStatus, string> = {
  draft: '草稿',
  pending: '待排产',
  scheduled: '已排产',
  in_progress: '进行中',
  paused: '暂停',
  completed: '已完工',
  closed: '已关单',
  cancelled: '已取消',
}

export const operationStatusLabels: Record<OperationStatus, string> = {
  pending: '待处理',
  ready: '可开工',
  in_progress: '进行中',
  reporting: '报工中',
  paused: '暂停',
  done: '已完成',
  cancelled: '已取消',
}

export function formatSeconds(seconds: number | string | null | undefined) {
  const value = Number(seconds ?? 0)
  if (!Number.isFinite(value) || value <= 0) {
    return '0 秒'
  }
  if (value < 60) {
    return `${value} 秒`
  }
  const minutes = Math.floor(value / 60)
  const remain = value % 60
  return remain ? `${minutes} 分 ${remain} 秒` : `${minutes} 分`
}
