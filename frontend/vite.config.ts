import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      manifest: {
        name: "Zeal Enterprises",
        short_name: "Zeal",
        description: "Zeal Enterprises business management",
        theme_color: "#0B0B0B",
        background_color: "#FFFFFF",
        display: "standalone",
        start_url: "/",
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        // never cache API responses: stock and money must always be live
        navigateFallbackDenylist: [/^\/api/, /^\/admin/],
      },
    }),
  ],
  server: {
    port: 5173,
    // Same-origin in dev, so session cookies and CSRF just work.
    proxy: { "/api": "http://127.0.0.1:8000", "/media": "http://127.0.0.1:8000", "/admin": "http://127.0.0.1:8000", "/static": "http://127.0.0.1:8000" },
  },
});
