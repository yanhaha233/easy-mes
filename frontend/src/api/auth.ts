import { apiRequest } from './client'
import type { CurrentUser, LoginResponse } from '../types/auth'

export const DEFAULT_TENANT_ID = '00000000-0000-0000-0000-000000000001'

export function login(tenantId: string, username: string, password: string) {
  return apiRequest<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ tenant_id: tenantId, username, password }),
  })
}

export function getCurrentUser() {
  return apiRequest<CurrentUser>('/auth/me')
}

export function logout() {
  return apiRequest<void>('/auth/logout', {
    method: 'POST',
  })
}
