export type UserRole = 'planner' | 'operator' | 'inspector' | 'admin'

export interface CurrentUser {
  id: string
  tenant_id: string
  username: string
  display_name: string
  role: UserRole
}

export interface LoginResponse {
  access_token: string
  token_type: 'bearer'
  expires_at: string
  user: CurrentUser
}
