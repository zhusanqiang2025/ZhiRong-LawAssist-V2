// frontend/vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 获取部署基础路径（通过环境变量配置，默认为根路径）
const base = process.env.VITE_BASE_PATH || '/'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // 配置部署基础路径（支持子路径部署）
  base: base,
  // 禁用缓存以强制重新构建
  cacheDir: '.vite-cache',
  // 定义全局变量
  define: {
    'process.env.NODE_ENV': JSON.stringify(process.env.NODE_ENV || 'production'),
  },
  // 强制破坏浏览器缓存
  build: {
    rollupOptions: {
      output: {
        // 为所有文件添加哈希，确保内容变化时生成新文件名
        entryFileNames: `assets/[name]-[hash].js`,
        chunkFileNames: `assets/[name]-[hash].js`,
        assetFileNames: `assets/[name]-[hash].[ext]`
      }
    }
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    strictPort: true,
    // 添加响应头来禁用浏览器缓存
    headers: {
      'Cache-Control': 'no-cache, no-store, must-revalidate',
      'Pragma': 'no-cache',
      'Expires': '0'
    },
    proxy: {
      // API 代理到后端服务（本地开发环境）
      '/api': {
        target: 'http://localhost:9000',
        changeOrigin: true,
        ws: true,
      },
      '/storage': {
        target: 'http://localhost:9000',
        changeOrigin: true,
      },
    },
  },
})
