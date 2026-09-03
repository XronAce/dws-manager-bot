import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// GitHub Pages serves a project site under /<repo>/, so assets must be
// requested from that prefix rather than the domain root.
export default defineConfig({
  plugins: [react()],
  base: process.env.VITE_BASE ?? '/dws-manager-bot/',
  build: { outDir: 'dist', sourcemap: false },
})
