import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { getCurrentUser, login as loginApi, logout as logoutApi } from '../api/auth'
import type { CurrentUser } from '../types/auth'

const LEGACY_TOKEN_STORAGE_KEY = 'easy_mes_access_token'
const USER_STORAGE_KEY = 'easy_mes_current_user'

function loadStoredUser() {
  const raw = window.localStorage.getItem(USER_STORAGE_KEY)
  if (!raw) {
    return null
  }
  try {
    return JSON.parse(raw) as CurrentUser
  } catch {
    window.localStorage.removeItem(USER_STORAGE_KEY)
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<CurrentUser | null>(loadStoredUser())
  const ready = ref(false)

  const isAuthenticated = computed(() => Boolean(user.value))

  async function login(tenantId: string, username: string, password: string) {
    const response = await loginApi(tenantId, username, password)
    user.value = response.user
    window.localStorage.removeItem(LEGACY_TOKEN_STORAGE_KEY)
    window.localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(response.user))
    ready.value = true
  }

  function clearSession() {
    user.value = null
    window.localStorage.removeItem(LEGACY_TOKEN_STORAGE_KEY)
    window.localStorage.removeItem(USER_STORAGE_KEY)
    ready.value = true
  }

  async function restore() {
    try {
      user.value = await getCurrentUser()
      window.localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user.value))
    } catch {
      clearSession()
    } finally {
      ready.value = true
    }
  }

  async function logout() {
    try {
      if (user.value) {
        await logoutApi()
      }
    } finally {
      clearSession()
    }
  }

  return {
    user,
    ready,
    isAuthenticated,
    clearSession,
    login,
    logout,
    restore,
  }
})
