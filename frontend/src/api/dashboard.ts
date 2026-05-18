import { apiRequest } from './client'

export interface WorkOrderDashboard {
  total: number
  draft: number
  pending: number
  scheduled: number
  in_progress: number
  completed: number
  ready_operations: number
  in_progress_operations: number
  actual_good_qty: string
  actual_bad_qty: string
}

export async function getWorkOrderDashboard() {
  return apiRequest<WorkOrderDashboard>('/dashboard/work-orders')
}
