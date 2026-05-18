import { apiRequest } from './client'
import type { Page } from '../types/masterData'
import type {
  ProductionReceiptCreatePayload,
  WorkOrder,
  WorkOrderCreatePayload,
  WorkOrderListItem,
  WorkOrderReceiptResponse,
  WorkOrderTraceability,
} from '../types/workOrder'

export interface WorkOrderListParams {
  keyword?: string
  status?: string
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
  return apiRequest<WorkOrder>('/work-orders', {
    method: 'POST',
    headers: {
      'Idempotency-Key': crypto.randomUUID(),
    },
    body: JSON.stringify(payload),
  })
}

export async function confirmWorkOrder(workOrderNo: string) {
  return apiRequest<WorkOrder>(`/work-orders/${workOrderNo}/confirm`, { method: 'POST' })
}

export async function cancelWorkOrder(workOrderNo: string, reason: string) {
  return apiRequest<WorkOrder>(`/work-orders/${workOrderNo}/cancel`, {
    method: 'POST',
    headers: {
      'Idempotency-Key': crypto.randomUUID(),
    },
    body: JSON.stringify({ reason }),
  })
}

export async function scheduleWorkOrder(workOrderNo: string) {
  return apiRequest<WorkOrder>(`/work-orders/${workOrderNo}/schedule`, { method: 'POST' })
}

export async function receiveWorkOrder(workOrderNo: string, payload: ProductionReceiptCreatePayload) {
  return apiRequest<WorkOrderReceiptResponse>(`/work-orders/${workOrderNo}/receipt`, {
    method: 'POST',
    headers: {
      'Idempotency-Key': crypto.randomUUID(),
    },
    body: JSON.stringify(payload),
  })
}

export async function getWorkOrderTraceability(workOrderNo: string) {
  return apiRequest<WorkOrderTraceability>(`/work-orders/${workOrderNo}/traceability`)
}
