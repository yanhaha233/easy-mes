import { apiRequest } from './client'
import { withIdempotencyKey } from './idempotency'
import type { Page } from '../types/masterData'
import type {
  OperationBackfillPayload,
  OperationBackfillRequestRead,
  OperationBackfillReviewPayload,
  OperationClockResponse,
  OperationRead,
} from '../types/operation'

export async function getOperationByQr(code: string) {
  return apiRequest<OperationRead>('/operations/by-qr', { query: { code } })
}

export async function listOperationWorkbench(statuses = 'paused,in_progress,ready') {
  return apiRequest<OperationRead[]>('/operations/workbench', { query: { statuses, limit: 50 } })
}

export async function startOperation(operationId: string) {
  return withIdempotencyKey(`operation:${operationId}:start`, (idempotencyKey) =>
    apiRequest<OperationRead>(`/operations/${operationId}/start`, {
      method: 'POST',
      headers: {
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify({}),
    }),
  )
}

export async function pauseOperation(operationId: string, reason = '现场暂停') {
  return withIdempotencyKey(`operation:${operationId}:pause`, (idempotencyKey) =>
    apiRequest<OperationRead>(`/operations/${operationId}/pause`, {
      method: 'POST',
      headers: {
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify({ reason }),
    }),
  )
}

export async function resumeOperation(operationId: string, reason = '恢复生产') {
  return withIdempotencyKey(`operation:${operationId}:resume`, (idempotencyKey) =>
    apiRequest<OperationRead>(`/operations/${operationId}/resume`, {
      method: 'POST',
      headers: {
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify({ reason }),
    }),
  )
}

export interface ClockPayload {
  good_qty: string
  bad_qty: string
  defects: Array<{ reason_code: string; qty: string }>
  actual_materials: Array<{ material_code: string; qty: string; lot_no?: string | null }>
  operator_code?: string
  remark: string | null
}

export async function clockOperation(operationId: string, payload: ClockPayload) {
  return withIdempotencyKey(`operation:${operationId}:clock`, (idempotencyKey) =>
    apiRequest<OperationClockResponse>(`/operations/${operationId}/clock`, {
      method: 'POST',
      headers: {
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify(payload),
    }),
  )
}

export async function createBackfillRequest(operationId: string, payload: OperationBackfillPayload) {
  return withIdempotencyKey(`operation:${operationId}:backfill-request`, (idempotencyKey) =>
    apiRequest<OperationBackfillRequestRead>(`/operations/${operationId}/backfill-requests`, {
      method: 'POST',
      headers: {
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify(payload),
    }),
  )
}

export async function listBackfillRequests(params: { status?: string; limit?: number; offset?: number } = {}) {
  return apiRequest<Page<OperationBackfillRequestRead>>('/operation-backfill-requests', {
    query: { ...params },
  })
}

export async function approveBackfillRequest(requestId: string, payload: OperationBackfillReviewPayload) {
  return withIdempotencyKey(`backfill-request:${requestId}:approve`, (idempotencyKey) =>
    apiRequest<OperationBackfillRequestRead>(`/operation-backfill-requests/${requestId}/approve`, {
      method: 'POST',
      headers: {
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify(payload),
    }),
  )
}

export async function rejectBackfillRequest(requestId: string, payload: OperationBackfillReviewPayload) {
  return withIdempotencyKey(`backfill-request:${requestId}:reject`, (idempotencyKey) =>
    apiRequest<OperationBackfillRequestRead>(`/operation-backfill-requests/${requestId}/reject`, {
      method: 'POST',
      headers: {
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify(payload),
    }),
  )
}
