import { apiRequest } from './client'
import type { DefectReport, OeeReport, OutputReport } from '../types/report'

export interface DefectReportParams {
  date_from?: string
  date_to?: string
}

export async function getDefectReport(params: DefectReportParams = {}) {
  return apiRequest<DefectReport>('/reports/defects', { query: { ...params } })
}

export interface OutputReportParams {
  date?: string
}

export async function getOutputReport(params: OutputReportParams = {}) {
  return apiRequest<OutputReport>('/reports/output', { query: { ...params } })
}

export interface OeeReportParams {
  date?: string
  planned_minutes?: number
}

export async function getOeeReport(params: OeeReportParams = {}) {
  return apiRequest<OeeReport>('/reports/oee', { query: { ...params } })
}
