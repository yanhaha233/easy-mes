import type { EntityRead, UUID } from './masterData'

export type InspectType = 'first_article' | 'patrol' | 'final'
export type InspectResult = 'pass' | 'fail' | 'concession'

export interface QualityRecordCreatePayload {
  work_order_no: string
  sample_qty: string
  pass_qty: string
  fail_qty: string
  result: InspectResult
  inspector_code: string | null
  disposition: string | null
  remark: string | null
}

export interface QualityRecord extends EntityRead {
  work_order_id: UUID
  operation_id: UUID | null
  work_order_no: string
  operation_seq: number | null
  operation_code: string | null
  operation_name: string | null
  inspector_code: string
  inspector_name: string
  inspect_type: InspectType
  sample_qty: string
  pass_qty: string
  fail_qty: string
  result: InspectResult
  disposition: string | null
  inspected_at: string
  remark: string | null
}
