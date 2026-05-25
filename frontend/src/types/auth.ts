export type UserRole = 'planner' | 'operator' | 'inspector' | 'admin'

export interface CurrentUser {
  id: string
  tenant_id: string
  username: string
  display_name: string
  role: UserRole
  worker_id: string | null
  worker_code: string | null
  worker_name: string | null
}

export interface LoginResponse {
  access_token: string
  token_type: 'bearer'
  expires_at: string
  user: CurrentUser
}
