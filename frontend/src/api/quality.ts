import { apiRequest } from './client'
import { withIdempotencyKey } from './idempotency'
import type { DefectReason, Page } from '../types/masterData'
import type { InspectType, QualityRecord, QualityRecordCreatePayload } from '../types/quality'

const endpointByType: Record<InspectType, string> = {
  first_article: '/quality/first-article',
  patrol: '/quality/patrol',
  final: '/quality/final',
}

export async function createQualityRecord(inspectType: InspectType, payload: QualityRecordCreatePayload) {
  return withIdempotencyKey(`quality:${inspectType}:create`, (idempotencyKey) =>
    apiRequest<QualityRecord>(endpointByType[inspectType], {
      method: 'POST',
      headers: {
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify(payload),
    }),
  )
}

export async function listQualityRecords(params: { work_order_no?: string; limit?: number; offset?: number } = {}) {
  return apiRequest<Page<QualityRecord>>('/quality/records', { query: { ...params } })
}

export async function listQualityDefectReasons() {
  return apiRequest<DefectReason[]>('/quality/defect-reasons')
}
