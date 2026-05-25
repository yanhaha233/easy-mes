<template>
  <div class="app-shell">
    <header v-if="!isLoginRoute" class="app-header">
      <RouterLink class="brand" :to="homeTo">
        <span class="brand__mark">EM</span>
        <span>
          <strong>Easy MES</strong>
          <small>{{ userLabel }}</small>
        </span>
      </RouterLink>

      <nav class="top-nav" aria-label="主导航">
        <RouterLink v-for="item in visibleNavItems" :key="item.to" :to="item.to">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <button class="user-chip" type="button" @click="logout">
        <el-icon><SwitchButton /></el-icon>
        <span>退出</span>
      </button>
    </header>

    <RouterView />

    <nav v-if="!isLoginRoute" class="bottom-nav" aria-label="移动端主导航">
      <RouterLink v-for="item in visibleNavItems" :key="item.to" :to="item.to">
        <el-icon><component :is="item.icon" /></el-icon>
        <span>{{ item.label }}</span>
      </RouterLink>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { DataBoard, Files, Stopwatch, SwitchButton, Tickets, Warning } from '@element-plus/icons-vue'

import { AUTH_EXPIRED_EVENT } from './api/client'
import { useAuthStore } from './stores/auth'
import type { UserRole } from './types/auth'

type NavItem = {
  to: string
  label: string
  icon: unknown
  roles?: UserRole[]
}

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const roleLabels: Record<UserRole, string> = {
  planner: '计划员',
  operator: '操作员',
  inspector: '质检员',
  admin: '管理员',
}

const navItems: NavItem[] = [
  { to: '/', label: '总览', icon: DataBoard },
  { to: '/work-orders', label: '工单', icon: Tickets, roles: ['planner', 'admin'] },
  { to: '/shop-floor', label: '报工', icon: Stopwatch, roles: ['operator', 'admin'] },
  { to: '/quality', label: '质量', icon: Warning, roles: ['inspector', 'admin'] },
  { to: '/master-data', label: '档案', icon: Files, roles: ['planner', 'admin'] },
]

const isLoginRoute = computed(() => route.name === 'login')
const homeTo = computed(() => {
  const role = authStore.user?.role
  if (role === 'operator') {
    return '/shop-floor'
  }
  if (role === 'inspector') {
    return '/quality'
  }
  return '/'
})
const visibleNavItems = computed(() => {
  const role = authStore.user?.role
  return navItems.filter((item) => {
    if (item.to === '/') {
      return role === 'planner' || role === 'admin'
    }
    return !item.roles?.length || (role && item.roles.includes(role))
  })
})
const userLabel = computed(() => {
  const user = authStore.user
  if (!user) {
    return '未登录'
  }
  return `${user.display_name} / ${roleLabels[user.role]}`
})

async function logout() {
  await authStore.logout()
  await router.replace('/login')
}

function handleAuthExpired() {
  authStore.clearSession()
  if (route.name !== 'login') {
    router.replace({ name: 'login', query: { redirect: route.fullPath } })
  }
}

onMounted(() => {
  window.addEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired)
})

onUnmounted(() => {
  window.removeEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired)
})
</script>
