import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API runs on :8000; proxy /api during dev so cookies are first-party.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
