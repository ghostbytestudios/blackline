import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Local-only dev server. The /api proxy forwards to the FastAPI backend so the
// browser never makes a cross-origin call (no CORS surface in the browser).
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: false,
      },
    },
  },
});
