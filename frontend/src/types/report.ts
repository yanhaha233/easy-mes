export interface DefectSummaryItem {
  reason_code: string
  reason_name: string
  category: string | null
  bad_qty: string
  clock_count: number
}

export interface DefectRecordItem {
  work_order_no: string | null
  operation_seq: number | null
  operation_name: string | null
  work_center_code: string | null
  work_center_name: string | null
  operator_code: string | null
  operator_name: string | null
  ended_at: string
  reason_code: string
  reason_name: string
  qty: string
  remark: string | null
}

export interface DefectReport {
  date_from: string | null
  date_to: string | null
  total_bad_qty: string
  total_clock_records: number
  items: DefectSummaryItem[]
  recent_records: DefectRecordItem[]
}

export interface OutputWorkCenterItem {
  work_center_code: string
  work_center_name: string
  good_qty: string
  bad_qty: string
  total_qty: string
  clock_count: number
}

export interface OutputMaterialItem {
  material_code: string
  material_name: string
  material_unit: string
  good_qty: string
  bad_qty: string
  total_qty: string
  work_order_count: number
}

export interface OutputRecordItem {
  work_order_no: string | null
  material_code: string | null
  material_name: string | null
  material_unit: string | null
  operation_seq: number | null
  operation_name: string | null
  work_center_code: string | null
  work_center_name: string | null
  operator_code: string | null
  operator_name: string | null
  ended_at: string
  good_qty: string
  bad_qty: string
  total_qty: string
  remark: string | null
}

export interface OutputReport {
  report_date: string
  total_good_qty: string
  total_bad_qty: string
  total_output_qty: string
  clock_count: number
  work_order_count: number
  by_work_center: OutputWorkCenterItem[]
  by_material: OutputMaterialItem[]
  recent_records: OutputRecordItem[]
}

export interface OeeWorkCenterItem {
  work_center_code: string
  work_center_name: string
  work_center_type: string | null
  planned_run_minutes: string
  actual_run_minutes: string
  oee: string
  good_qty: string
  bad_qty: string
  total_qty: string
  clock_count: number
}

export interface OeeReport {
  report_date: string
  planned_minutes_per_work_center: number
  total_actual_minutes: string
  average_oee: string
  items: OeeWorkCenterItem[]
}
