import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    // Plugin oficial para compilar componentes React con Vite.
    react(),
    // Configura la app como PWA instalable y actualizable.
    VitePWA({
      registerType: 'autoUpdate',
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,ico}'],
        maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
      },
      manifest: {
        // Metadatos que ve el navegador cuando instala la aplicacion.
        name: 'Chillamicito Stock',
        short_name: 'Chillamicito',
        description: 'Gestión de stock para Restaurante Chillamicito',
        theme_color: '#1f6f5b',
        background_color: '#f7faf8',
        display: 'standalone',
        start_url: '/',
        icons: [
          // Iconos usados por la PWA en escritorio o movil.
          {
            src: '/pwa-192.svg',
            sizes: '192x192',
            type: 'image/svg+xml'
          },
          {
            src: '/pwa-512.svg',
            sizes: '512x512',
            type: 'image/svg+xml'
          }
        ]
      }
    })
  ]
});
