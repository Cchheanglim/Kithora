import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    // The API runs separately (uvicorn on :8000); proxying keeps it same-origin so the login cookie works.
    proxy: {
      '/v1': { target: 'http://127.0.0.1:8000', ws: true },
    },
  },
});
