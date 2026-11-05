import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, proxy /api to a control-plane API. In production Caddy does this.
// API_TARGET defaults to a local API; point it at the live site to develop against real data.
const target = process.env.API_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target, changeOrigin: true },
    },
  },
  build: { outDir: "dist", sourcemap: false, chunkSizeWarningLimit: 700 },
});
