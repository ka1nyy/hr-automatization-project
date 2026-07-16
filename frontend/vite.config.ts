import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        // Docker Compose publishes the combined app container's FastAPI
        // process on this dedicated host port for Vite hot-reload sessions.
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  },
  test: { environment: 'jsdom', globals: true, testTimeout: 15_000 }
});
