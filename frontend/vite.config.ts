import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

/**
 * 开发期的三个约定：
 *
 * 1. **前端只调 `/api/v1`，永远不写死主机名。**
 *    开发时由这里的 proxy 转到本机后端；上线后前端和后端**同源**（nginx 一个域名
 *    既给静态文件又反代 `/api`），所以生产构建也用同一个相对路径。
 *    同源还有个附带好处：**根本不存在 CORS** —— 这本来就是\"服务端爬虫\"方案的动机之一。
 * 2. 后端默认在 `127.0.0.1:8000`（`uvicorn app.main:app`）。
 *    换端口不用改这个文件：`VITE_DEV_API_TARGET=http://127.0.0.1:9000 npm run dev`。
 * 3. 静态资源 `base` 留默认 `/`。若日后要挂到子路径再改这里（同时改 nginx）。
 */
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 4000,
    proxy: {
      '/api': {
        target: process.env.VITE_DEV_API_TARGET ?? 'http://127.0.0.1:4001',
        changeOrigin: true,
      },
    },
  },
  build: {
    // 移动端首屏要快：把体积大的库分开，方便后面按路由懒加载
    rollupOptions: {
      output: {
        manualChunks: {
          vue: ['vue', 'vue-router', 'pinia'],
          vant: ['vant'],
          hls: ['hls.js'],
        },
      },
    },
  },
})
