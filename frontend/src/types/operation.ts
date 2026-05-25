import type { EntityRead, UUID } from './masterData'
import type { OperationStatus, WorkOrderStatus } from './workOrder'

export interface OperationRead extends EntityRead {
  work_order_id: UUID
  work_order_no: string
  work_order_status: WorkOrderStatus
  material_code: string
  material_name: string
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

export interface OperationClockResponse {
  operation: OperationRead
  work_order_status: WorkOrderStatus
  next_operation_id: UUID | null
  clock_record_id: UUID
  elapsed_seconds: number | null
  time_anomaly: boolean
  time_anomaly_reason: string | null
  time_anomaly_detail: Record<string, unknown> | null
}

export type BackfillStatus = 'pending' | 'approved' | 'rejected'

export interface OperationBackfillPayload {
  started_at: string
  ended_at: string
  good_qty: string
  bad_qty: string
  defects: Array<{ reason_code: string; qty: string }>
  actual_materials: Array<{ material_code: string; qty: string; lot_no?: string | null }>
  operator_code?: string | null
  reason: string
  remark: string | null
}

export interface OperationBackfillReviewPayload {
  review_remark: string | null
}

export interface OperationBackfillRequestRead extends EntityRead {
  work_order_id: UUID
  operation_id: UUID
  clock_record_id: UUID | null
  work_order_no: string
  operation_seq: number
  operation_code: string
  operation_name: string
  work_center_id: UUID
  work_center_code: string
  work_center_name: string
  applicant_code: string
  applicant_name: string
  operator_code: string
  operator_name: string
  started_at: string
  ended_at: string
  elapsed_seconds: number
  good_qty: string
  bad_qty: string
  defects: Array<Record<string, unknown>>
  material_consumed: Array<Record<string, unknown>>
  reason: string
  remark: string | null
  status: BackfillStatus
  reviewed_by: string | null
  reviewed_at: string | null
  review_remark: string | null
}
