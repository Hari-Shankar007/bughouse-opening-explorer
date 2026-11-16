import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const api = process.env.CATALOG_API_URL || 'http://127.0.0.1:8001';

export default defineConfig({
  base: process.env.GITHUB_ACTIONS === 'true' ? '/bughouse-opening-explorer/' : '/',
  plugins: [react()],
  server: { proxy: {
    '/api/catalog': { target: api, changeOrigin: true, rewrite: path => path.replace(/^\/api\/catalog/, '/api') },
    '/api/opening': { target: api, changeOrigin: true, rewrite: path => path.replace(/^\/api\/opening/, '/api/opening') }
  } }
});
