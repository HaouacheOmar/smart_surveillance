import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev proxy mirrors nginx.conf so cookies stay same-origin.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": { target: "ws://localhost:8000", ws: true },
      "/stream": { target: "http://localhost:8001", rewrite: (p) => p.replace(/^\/stream/, "/streams") },
    },
  },
});
