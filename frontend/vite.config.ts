import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // AG Grid Community is ~1 MB minified; fine for a single-page demo.
  build: { chunkSizeWarningLimit: 2000 },
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
