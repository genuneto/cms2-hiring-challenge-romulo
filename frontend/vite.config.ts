import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In dev the browser talks to Vite, and Vite forwards /api to OUR backend. The upstream is never reachable from here.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
