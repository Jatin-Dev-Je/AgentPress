import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const target = env.VITE_BACKEND_URL || 'http://localhost:8000';

  return {
    plugins: [react()],
    server: {
      port: 5173,
      open: false,
      proxy: {
        '/agents': { target, changeOrigin: true },
        '/plugins': { target, changeOrigin: true },
        '/audit': { target, changeOrigin: true },
        '/health': { target, changeOrigin: true },
        '/version': { target, changeOrigin: true },
      },
    },
    build: {
      outDir: 'dist',
    },
  };
});
