import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Proxy keeps browser Origin as http://localhost:5173 (backend CORS allowlist).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        ws: true,
      },
    },
  },
});
