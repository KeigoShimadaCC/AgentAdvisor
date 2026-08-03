import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The e2e suite runs its backend on a dedicated port and points the proxy at
// it via AGENTADVISOR_API_PORT; plain `npm run dev` keeps the advisor ui
// default (8765).
const apiPort = process.env.AGENTADVISOR_API_PORT ?? "8765";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": `http://127.0.0.1:${apiPort}`,
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
