import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: './',                 // relative paths for Electron file:// protocol
  server: {
    port: 5174,               // different from dashboard (5173) so both can run together
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  optimizeDeps: {
    include: ['pixi-live2d-display/cubism4'],
  },
  assetsInclude: ['**/*.wasm', '**/*.moc3'],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test-setup.ts',
  },
})
