import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// Standalone ML demo. Proxies /api to the existing FastAPI backend on :8000,
// so it uses the REAL ML endpoints. Runs on port 5200 to avoid clashing with
// the team's dealer_dashboard (5173).
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  server: {
    port: 5200,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
});
