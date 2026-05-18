import { apiRequest } from './client'
import type { OperationClockResponse, OperationRead } from '../types/operation'

export async function getOperationByQr(code: string) {
  return apiRequest<OperationRead>('/operations/by-qr', { query: { code } })
}

export async function startOperation(operationId: string) {
  return apiRequest<OperationRead>(`/operations/${operationId}/start`, {
    method: 'POST',
    headers: {
      'Idempotency-Key': crypto.randomUUID(),
    },
    body: JSON.stringify({ operator_code: 'default_operator' }),
  })
}

export async function pauseOperation(operationId: string, reason = '现场暂停') {
  return apiRequest<OperationRead>(`/operations/${operationId}/pause`, {
    method: 'POST',
    headers: {
      'Idempotency-Key': crypto.randomUUID(),
    },
    body: JSON.stringify({ operator_code: 'default_operator', reason }),
  })
}

export async function resumeOperation(operationId: string, reason = '恢复生产') {
  return apiRequest<OperationRead>(`/operations/${operationId}/resume`, {
    method: 'POST',
    headers: {
      'Idempotency-Key': crypto.randomUUID(),
    },
    body: JSON.stringify({ operator_code: 'default_operator', reason }),
  })
}

export interface ClockPayload {
  good_qty: string
  bad_qty: string
  defects: Array<{ reason_code: string; qty: string }>
  actual_materials: Array<{ material_code: string; qty: string; lot_no?: string | null }>
  operator_code: string
  remark: string | null
}

export async function clockOperation(operationId: string, payload: ClockPayload) {
  return apiRequest<OperationClockResponse>(`/operations/${operationId}/clock`, {
    method: 'POST',
    headers: {
      'Idempotency-Key': crypto.randomUUID(),
    },
    body: JSON.stringify(payload),
  })
}
