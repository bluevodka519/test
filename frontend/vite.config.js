import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// /api is proxied to the FastAPI backend, so no CORS setup is needed
// and no courier credentials ever reach the browser.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
