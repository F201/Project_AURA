import { resolve } from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  base: './',
  publicDir: false,
  build: {
    outDir: '../mobile/build/assets/avatar',
    emptyOutDir: true,
    rollupOptions: { input: resolve(import.meta.dirname, 'mobile-avatar.html') },
  },
})
