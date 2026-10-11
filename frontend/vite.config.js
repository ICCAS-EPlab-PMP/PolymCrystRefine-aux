import { defineConfig, loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';
import path from 'path';
import pkg from './package.json';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const backendPort = env.VITE_BACKEND_PORT || '18730';

  return {
    plugins: [vue()],
    // Single version source for the plain-browser fallback: the running
    // Electron app reports its version via IPC (app.getVersion, i.e.
    // PRE/package.json); in a browser there is no IPC, so components fall
    // back to this build-time constant taken from frontend/package.json.
    define: {
      __APP_VERSION__: JSON.stringify(pkg.version),
    },
    // Use relative paths so Electron can load via file:// protocol
    base: './',
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src')
      }
    },
    build: {
      outDir: 'dist',
      emptyOutDir: true
    },
    server: {
      port: 5173,
      strictPort: false,
      proxy: {
        '/api': {
          target: `http://localhost:${backendPort}`,
          changeOrigin: true
        }
      }
    }
  };
});
