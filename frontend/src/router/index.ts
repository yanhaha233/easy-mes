import { createRouter, createWebHistory } from 'vue-router'

import DashboardView from '../views/DashboardView.vue'
import LoginView from '../views/LoginView.vue'
import MasterDataView from '../views/MasterDataView.vue'
import QualityView from '../views/QualityView.vue'
import ShopFloorView from '../views/ShopFloorView.vue'
import WorkOrdersView from '../views/WorkOrdersView.vue'
import { useAuthStore } from '../stores/auth'
import type { UserRole } from '../types/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
    },
    {
      path: '/',
      name: 'dashboard',
      component: DashboardView,
    },
    {
      path: '/master-data',
      name: 'master-data',
      component: MasterDataView,
      meta: { roles: ['planner', 'admin'] },
    },
    {
      path: '/work-orders',
      name: 'work-orders',
      component: WorkOrdersView,
      meta: { roles: ['planner', 'admin'] },
    },
    {
      path: '/shop-floor',
      name: 'shop-floor',
      component: ShopFloorView,
      meta: { roles: ['operator', 'admin'] },
    },
    {
      path: '/quality',
      name: 'quality',
      component: QualityView,
      meta: { roles: ['inspector', 'admin'] },
    },
  ],
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore()
  if (!authStore.ready) {
    await authStore.restore()
  }
  if (to.name === 'login') {
    return authStore.isAuthenticated ? { name: 'dashboard' } : true
  }
  if (!authStore.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  const roles = to.meta.roles as UserRole[] | undefined
  if (roles?.length && authStore.user && !roles.includes(authStore.user.role)) {
    return { name: 'dashboard' }
  }
  return true
})

export default router
