import { apiRequest } from './client'
import type {
  Bom,
  DefectReason,
  Material,
  Page,
  Routing,
  SimpleEntity,
  Team,
  WorkCenter,
  Worker,
} from '../types/masterData'

export type SimpleResource = 'materials' | 'workCenters' | 'teams' | 'workers' | 'defectReasons'
export type MasterResource = SimpleResource | 'boms' | 'routings'

const resourcePaths: Record<MasterResource, string> = {
  materials: '/materials',
  workCenters: '/work-centers',
  teams: '/teams',
  workers: '/workers',
  defectReasons: '/defect-reasons',
  boms: '/boms',
  routings: '/routings',
}

export interface ListParams {
  keyword?: string
  is_active?: boolean | ''
  status?: string
  material_id?: string
  limit?: number
  offset?: number
}

type ResourceEntityMap = {
  materials: Material
  workCenters: WorkCenter
  teams: Team
  workers: Worker
  defectReasons: DefectReason
  boms: Bom
  routings: Routing
}

export async function listMaster<R extends MasterResource>(
  resource: R,
  params: ListParams = {},
): Promise<Page<ResourceEntityMap[R]>> {
  return apiRequest<Page<ResourceEntityMap[R]>>(resourcePaths[resource], { query: { ...params } })
}

export async function createMaster<R extends MasterResource>(
  resource: R,
  payload: Record<string, unknown>,
): Promise<ResourceEntityMap[R]> {
  return apiRequest<ResourceEntityMap[R]>(resourcePaths[resource], {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateMaster<R extends MasterResource>(
  resource: R,
  id: string,
  payload: Record<string, unknown>,
): Promise<ResourceEntityMap[R]> {
  return apiRequest<ResourceEntityMap[R]>(`${resourcePaths[resource]}/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function deleteMaster(resource: MasterResource, id: string): Promise<void> {
  await apiRequest<void>(`${resourcePaths[resource]}/${id}`, { method: 'DELETE' })
}

export type LookupData = {
  materials: Material[]
  workCenters: WorkCenter[]
  teams: Team[]
}

export async function loadLookups(): Promise<LookupData> {
  const [materials, workCenters, teams] = await Promise.all([
    listMaster('materials', { is_active: true, limit: 100, offset: 0 }),
    listMaster('workCenters', { is_active: true, limit: 100, offset: 0 }),
    listMaster('teams', { is_active: true, limit: 100, offset: 0 }),
  ])
  return {
    materials: materials.items,
    workCenters: workCenters.items,
    teams: teams.items,
  }
}

export type { Bom, DefectReason, Material, Routing, SimpleEntity, Team, WorkCenter, Worker }
