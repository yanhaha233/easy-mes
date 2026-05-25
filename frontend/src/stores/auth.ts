import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { getCurrentUser, login as loginApi, logout as logoutApi } from '../api/auth'
import { AUTH_TOKEN_STORAGE_KEY } from '../api/client'
import type { CurrentUser } from '../types/auth'

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
  const token = ref(window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY))
  const user = ref<CurrentUser | null>(loadStoredUser())
  const ready = ref(false)

  const isAuthenticated = computed(() => Boolean(token.value && user.value))

  async function login(username: string, password: string) {
    const response = await loginApi(username, password)
    token.value = response.access_token
    user.value = response.user
    window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, response.access_token)
    window.localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(response.user))
    ready.value = true
  }

  function clearSession() {
    token.value = null
    user.value = null
    window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY)
    window.localStorage.removeItem(USER_STORAGE_KEY)
    ready.value = true
  }

  async function restore() {
    if (!token.value) {
      ready.value = true
      return
    }
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
      if (token.value) {
        await logoutApi()
      }
    } finally {
      clearSession()
    }
  }

  return {
    token,
    user,
    ready,
    isAuthenticated,
    clearSession,
    login,
    logout,
    restore,
  }
})
