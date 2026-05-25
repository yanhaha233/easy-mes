import { apiRequest } from './client'
import { withIdempotencyKey } from './idempotency'
import type { Page } from '../types/masterData'
import type {
  ProductionReceiptCreatePayload,
  WorkOrder,
  WorkOrderCreatePayload,
  WorkOrderImportResponse,
  WorkOrderImportRowPayload,
  WorkOrderListItem,
  WorkOrderReceiptResponse,
  WorkOrderSchedulePayload,
  WorkOrderTraceability,
} from '../types/workOrder'

export interface WorkOrderListParams {
  keyword?: string
  status?: string
  operation_status?: string
  limit?: number
  offset?: number
}

export async function listWorkOrders(params: WorkOrderListParams = {}) {
  return apiRequest<Page<WorkOrderListItem>>('/work-orders', { query: { ...params } })
}

export async function getWorkOrder(id: string) {
  return apiRequest<WorkOrder>(`/work-orders/${id}`)
}

export async function createWorkOrder(payload: WorkOrderCreatePayload) {
  return withIdempotencyKey('work-order:create', (idempotencyKey) =>
    apiRequest<WorkOrder>('/work-orders', {
      method: 'POST',
      headers: {
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify(payload),
    }),
  )
}

export async function importWorkOrders(rows: WorkOrderImportRowPayload[]) {
  return withIdempotencyKey('work-order:import', (idempotencyKey) =>
    apiRequest<WorkOrderImportResponse>('/work-orders/import', {
      method: 'POST',
      headers: {
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify({ rows }),
    }),
  )
}

export async function confirmWorkOrder(workOrderNo: string) {
  return withIdempotencyKey(`work-order:${workOrderNo}:confirm`, (idempotencyKey) =>
    apiRequest<WorkOrder>(`/work-orders/${workOrderNo}/confirm`, {
      method: 'POST',
      headers: {
        'Idempotency-Key': idempotencyKey,
      },
    }),
  )
}

export async function cancelWorkOrder(workOrderNo: string, reason: string, allowAbandonWip = false) {
  return withIdempotencyKey(`work-order:${workOrderNo}:cancel`, (idempotencyKey) =>
    apiRequest<WorkOrder>(`/work-orders/${workOrderNo}/cancel`, {
      method: 'POST',
      headers: {
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify({ reason, allow_abandon_wip: allowAbandonWip }),
    }),
  )
}

export async function scheduleWorkOrder(workOrderNo: string, payload: WorkOrderSchedulePayload) {
  return withIdempotencyKey(`work-order:${workOrderNo}:schedule`, (idempotencyKey) =>
    apiRequest<WorkOrder>(`/work-orders/${workOrderNo}/schedule`, {
      method: 'POST',
      headers: {
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify(payload),
    }),
  )
}

export async function receiveWorkOrder(workOrderNo: string, payload: ProductionReceiptCreatePayload) {
  return withIdempotencyKey(`work-order:${workOrderNo}:receipt`, (idempotencyKey) =>
    apiRequest<WorkOrderReceiptResponse>(`/work-orders/${workOrderNo}/receipt`, {
      method: 'POST',
      headers: {
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify(payload),
    }),
  )
}

export async function getWorkOrderTraceability(workOrderNo: string) {
  return apiRequest<WorkOrderTraceability>(`/work-orders/${workOrderNo}/traceability`)
}
