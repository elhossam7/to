import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/events": "http://127.0.0.1:8000",
      "/profiles": "http://127.0.0.1:8000",
      "/status": "http://127.0.0.1:8000",
      "/ingest": "http://127.0.0.1:8000"
    }
  }
});
