import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5180,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8010',
        changeOrigin: true,
      },
    },
  },
})
