<template>
  <main class="login-page">
    <section class="login-panel">
      <div class="login-brand">
        <span class="brand__mark">EM</span>
        <div>
          <h1>Easy MES</h1>
          <p>选择演示账号进入对应工作台</p>
        </div>
      </div>

      <el-form class="login-form" label-position="top" @submit.prevent="submit">
        <el-form-item label="账号">
          <el-input v-model="form.username" autocomplete="username" size="large" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" autocomplete="current-password" show-password size="large" type="password" />
        </el-form-item>
        <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
        <el-button class="login-submit" type="primary" size="large" :loading="loading" @click="submit">
          登录
        </el-button>
      </el-form>

      <div class="demo-users">
        <button v-for="account in demoAccounts" :key="account.username" type="button" @click="fillDemo(account)">
          <strong>{{ account.label }}</strong>
          <span>{{ account.username }} / {{ account.password }}</span>
        </button>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiError } from '../api/client'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const loading = ref(false)
const error = ref('')
const form = reactive({
  username: 'planner',
  password: 'planner123',
})

const demoAccounts = [
  { label: '计划员', username: 'planner', password: 'planner123' },
  { label: '操作员', username: 'operator', password: 'operator123' },
  { label: '质检员', username: 'inspector', password: 'inspector123' },
  { label: '管理员', username: 'admin', password: 'admin123' },
]

function fillDemo(account: { username: string; password: string }) {
  form.username = account.username
  form.password = account.password
}

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await authStore.login(form.username, form.password)
    await router.replace((route.query.redirect as string) || '/')
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : '登录失败'
  } finally {
    loading.value = false
  }
}
</script>
