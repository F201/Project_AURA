import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  envDir: '../', // Load .env from project root
  server: {
    port: 5173,
    open: true,
  },
  optimizeDeps: {
    // Pre-bundle pixi-live2d-display so Vite converts its CJS deps (url, eventemitter3) to ESM
    include: ['pixi-live2d-display', 'pixi-live2d-display/cubism4', 'pixi.js'],
  },
  assetsInclude: ['**/*.wasm', '**/*.moc3'],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test-setup.js',
  },
})
