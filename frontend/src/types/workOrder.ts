import type { EntityRead, UUID } from './masterData'
import type { QualityRecord } from './quality'

export type Priority = 'normal' | 'high' | 'urgent'
export type WorkOrderSource = 'manual' | 'erp'
export type WorkOrderStatus =
  | 'draft'
  | 'pending'
  | 'scheduled'
  | 'in_progress'
  | 'paused'
  | 'completed'
  | 'closed'
  | 'cancelled'
export type OperationStatus = 'pending' | 'ready' | 'in_progress' | 'reporting' | 'paused' | 'done' | 'cancelled'

export interface WorkOrderMaterialSnapshot {
  code: string
  name: string
  spec: string | null
  unit: string
}

export interface WorkOrderBomSnapshot {
  id: UUID | null
  version: string | null
  material_lines: number
}

export interface WorkOrderRoutingSnapshot {
  id: UUID | null
  version: string | null
  operation_lines: number
}

export interface WorkOrderMaterial extends EntityRead {
  component_material_id: UUID
  material_code: string
  material_name: string
  material_spec: string | null
  unit: string
  qty_per: string
  loss_rate: string
  required_qty: string
  issued_qty: string
  consumed_qty: string
}

export interface WorkOrderOperation extends EntityRead {
  seq: number
  operation_code: string
  operation_name: string
  work_center_id: UUID
  work_center_code: string
  work_center_name: string
  setup_time_sec: number
  unit_time_sec: number
  planned_duration_sec: number
  planned_qty: string
  good_qty: string
  bad_qty: string
  status: OperationStatus
  assigned_operator_code: string | null
  assigned_operator_name: string | null
  started_at: string | null
  started_by_operator_code: string | null
  started_by_operator_name: string | null
}

export interface WorkOrder extends EntityRead {
  work_order_no: string
  source: WorkOrderSource
  external_ref: string | null
  material_id: UUID
  material: WorkOrderMaterialSnapshot
  planned_qty: string
  actual_good_qty: string
  actual_bad_qty: string
  due_date: string | null
  priority: Priority
  customer_name: string | null
  status: WorkOrderStatus
  bom: WorkOrderBomSnapshot
  routing: WorkOrderRoutingSnapshot
  created_by: string
  remark: string | null
  materials_required: WorkOrderMaterial[]
  operations: WorkOrderOperation[]
}

export interface WorkOrderListItem extends EntityRead {
  work_order_no: string
  material_code: string
  material_name: string
  planned_qty: string
  actual_good_qty: string
  actual_bad_qty: string
  due_date: string | null
  priority: Priority
  source: WorkOrderSource
  status: WorkOrderStatus
  customer_name: string | null
  created_by: string
  assigned_operator_codes: string[]
  assigned_operator_names: string[]
}

export interface WorkOrderCreatePayload {
  material_code: string
  quantity: string
  due_date: string | null
  priority: Priority
  source: WorkOrderSource
  external_ref: string | null
  customer_name: string | null
  remark: string | null
}

export interface WorkOrderSchedulePayload {
  operator_code: string | null
  operation_assignments?: Array<{
    operation_seq: number
    operator_code: string
  }>
}

export interface ProductionReceiptCreatePayload {
  good_qty: string | null
  lot_no: string | null
  warehouse_code: string | null
  remark: string | null
}

export interface ProductionReceipt extends EntityRead {
  receipt_no: string
  work_order_id: UUID
  work_order_no: string
  material_id: UUID
  material: WorkOrderMaterialSnapshot
  good_qty: string
  lot_no: string | null
  warehouse_code: string | null
  received_by: string
  received_at: string
  remark: string | null
}

export interface WorkOrderReceiptResponse {
  work_order: WorkOrder
  receipt: ProductionReceipt
}

export interface TraceClockRecord extends EntityRead {
  operation_id: UUID
  operation_seq: number | null
  operation_code: string | null
  operation_name: string | null
  work_center_id: UUID | null
  work_center_code: string | null
  work_center_name: string | null
  operator_id: UUID | null
  operator_code: string | null
  operator_name: string | null
  started_at: string
  ended_at: string
  elapsed_seconds: number | null
  time_anomaly: boolean
  time_anomaly_reason: string | null
  time_anomaly_detail: Record<string, unknown> | null
  good_qty: string
  bad_qty: string
  defects: unknown[]
  material_consumed: unknown[]
  remark: string | null
}

export interface TraceAuditEvent {
  id: UUID
  entity_type: string
  entity_id: UUID | null
  action: string
  actor_code: string
  actor_name: string | null
  from_state: string | null
  to_state: string | null
  detail: Record<string, unknown>
  created_at: string
}

export interface TraceTimelineEvent {
  event_type: string
  title: string
  occurred_at: string
  actor_code: string | null
  actor_name: string | null
  operation_seq: number | null
  good_qty: string | null
  bad_qty: string | null
  detail: Record<string, unknown>
}

export interface WorkOrderTraceability {
  work_order_no: string
  status: WorkOrderStatus
  material: WorkOrderMaterialSnapshot
  planned_qty: string
  actual_good_qty: string
  actual_bad_qty: string
  materials_required: WorkOrderMaterial[]
  operations: WorkOrderOperation[]
  clock_records: TraceClockRecord[]
  receipts: ProductionReceipt[]
  quality_records: QualityRecord[]
  audit_events: TraceAuditEvent[]
  timeline: TraceTimelineEvent[]
}
