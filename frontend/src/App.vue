<template>
  <div class="app-shell">
    <header class="app-header">
      <RouterLink class="brand" to="/">
        <span class="brand__mark">EM</span>
        <span>
          <strong>Easy MES</strong>
          <small>默认计划员 / 操作员</small>
        </span>
      </RouterLink>

      <nav class="top-nav" aria-label="主导航">
        <RouterLink v-for="item in navItems" :key="item.to" :to="item.to">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>
    </header>

    <RouterView />

    <nav class="bottom-nav" aria-label="移动端主导航">
      <RouterLink v-for="item in navItems" :key="item.to" :to="item.to">
        <el-icon><component :is="item.icon" /></el-icon>
        <span>{{ item.label }}</span>
      </RouterLink>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { DataBoard, Files, Stopwatch, Tickets, Warning } from '@element-plus/icons-vue'

const navItems = [
  { to: '/', label: '总览', icon: DataBoard },
  { to: '/work-orders', label: '工单', icon: Tickets },
  { to: '/shop-floor', label: '报工', icon: Stopwatch },
  { to: '/quality', label: '质量', icon: Warning },
  { to: '/master-data', label: '档案', icon: Files },
]
</script>
