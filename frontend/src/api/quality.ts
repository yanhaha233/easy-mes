import { apiRequest } from './client'
import type { Page } from '../types/masterData'
import type { InspectType, QualityRecord, QualityRecordCreatePayload } from '../types/quality'

const endpointByType: Record<InspectType, string> = {
  first_article: '/quality/first-article',
  patrol: '/quality/patrol',
  final: '/quality/final',
}

export async function createQualityRecord(inspectType: InspectType, payload: QualityRecordCreatePayload) {
  return apiRequest<QualityRecord>(endpointByType[inspectType], {
    method: 'POST',
    headers: {
      'Idempotency-Key': crypto.randomUUID(),
    },
    body: JSON.stringify(payload),
  })
}

export async function listQualityRecords(params: { work_order_no?: string; limit?: number; offset?: number } = {}) {
  return apiRequest<Page<QualityRecord>>('/quality/records', { query: { ...params } })
}
