import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Local-only dev server. The /api proxy forwards to the FastAPI backend so the
// browser never makes a cross-origin call (no CORS surface in the browser).
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true, // lets Testing Library auto-clean the DOM between tests
    include: ["src/**/*.test.{ts,tsx}"],
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        // Override for test/demo stacks running the API on another port.
        target: process.env.BLACKLINE_API_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: false,
      },
    },
  },
});
