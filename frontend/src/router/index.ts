import { createRouter, createWebHistory } from 'vue-router'

import DashboardView from '../views/DashboardView.vue'
import MasterDataView from '../views/MasterDataView.vue'
import QualityView from '../views/QualityView.vue'
import ShopFloorView from '../views/ShopFloorView.vue'
import WorkOrdersView from '../views/WorkOrdersView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: DashboardView,
    },
    {
      path: '/master-data',
      name: 'master-data',
      component: MasterDataView,
    },
    {
      path: '/work-orders',
      name: 'work-orders',
      component: WorkOrdersView,
    },
    {
      path: '/shop-floor',
      name: 'shop-floor',
      component: ShopFloorView,
    },
    {
      path: '/quality',
      name: 'quality',
      component: QualityView,
    },
  ],
})

export default router
