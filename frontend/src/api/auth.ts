import { apiRequest } from './client'
import type { CurrentUser, LoginResponse } from '../types/auth'

export function login(username: string, password: string) {
  return apiRequest<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export function getCurrentUser() {
  return apiRequest<CurrentUser>('/auth/me')
}
