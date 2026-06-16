import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import basicSsl from '@vitejs/plugin-basic-ssl';

// HTTPS is required for OIDC PKCE (window.crypto.subtle).
// Enable by default in dev; set VITE_DEV_HTTPS=false to opt out.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const enableHttps = false;

  return {
    plugins: [
      react(),
      ...(enableHttps ? [basicSsl()] : []),
    ],
    server: {
      host: true,
      port: 5173,
      strictPort: true,
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:1337',
          changeOrigin: true,
          secure: false,
        },
        '/uploads': {
          target: 'http://127.0.0.1:1337',
          changeOrigin: true,
          secure: false,
        },
      },
    },
  };
});
