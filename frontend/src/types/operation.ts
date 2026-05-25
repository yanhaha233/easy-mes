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
