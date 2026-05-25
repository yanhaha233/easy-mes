export type UUID = string

export type MaterialType = 'product' | 'semi_finished' | 'raw_material' | 'packing' | 'tooling'
export type WorkCenterType = 'workstation' | 'equipment' | 'line' | 'inspection'
export type WorkerType = 'operator' | 'inspector' | 'planner' | 'manager'
export type MasterStatus = 'draft' | 'active' | 'inactive'

export interface EntityRead {
  id: UUID
  tenant_id: UUID
  created_at: string
  updated_at: string
  deleted_at: string | null
}

export interface Page<T> {
  total: number
  items: T[]
}

export interface Material extends EntityRead {
  code: string
  name: string
  spec: string | null
  unit: string
  material_type: MaterialType
  is_active: boolean
  allow_empty_bom: boolean
  remark: string | null
}

export interface WorkCenter extends EntityRead {
  code: string
  name: string
  work_center_type: WorkCenterType
  location: string | null
  is_active: boolean
  remark: string | null
}

export interface Team extends EntityRead {
  code: string
  name: string
  leader_name: string | null
  is_active: boolean
  remark: string | null
}

export interface Worker extends EntityRead {
  code: string
  name: string
  worker_type: WorkerType
  team_id: UUID | null
  is_active: boolean
  remark: string | null
}

export interface OperationSkillOption {
  operation_code: string
  operation_name: string
}

export interface WorkerOperationSkill extends EntityRead {
  worker_id: UUID
  operation_code: string
  operation_name: string | null
  is_active: boolean
  remark: string | null
}

export interface DefectReason extends EntityRead {
  code: string
  name: string
  category: string | null
  is_active: boolean
  remark: string | null
}

export interface BomLine extends EntityRead {
  component_material_id: UUID
  component_material_code: string | null
  component_material_name: string | null
  line_no: number
  qty_per: string
  loss_rate: string
  remark: string | null
}

export interface Bom extends EntityRead {
  material_id: UUID
  version: string
  status: MasterStatus
  remark: string | null
  lines: BomLine[]
}

export interface RoutingOperation extends EntityRead {
  seq: number
  operation_code: string
  operation_name: string
  work_center_id: UUID
  work_center_code: string | null
  work_center_name: string | null
  setup_time_sec: number
  unit_time_sec: number
  is_active: boolean
  remark: string | null
}

export interface Routing extends EntityRead {
  material_id: UUID
  version: string
  status: MasterStatus
  remark: string | null
  operations: RoutingOperation[]
}

export type SimpleEntity = Material | WorkCenter | Team | Worker | DefectReason
