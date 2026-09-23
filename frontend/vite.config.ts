import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

import { APP_VERSION, APP_VERSION_LABEL } from "./src/version";

export default defineConfig({
  plugins: [
    react(),
    {
      name: "eldledger-version-json",
      generateBundle() {
        this.emitFile({
          type: "asset",
          fileName: "version.json",
          source: `${JSON.stringify({ version: APP_VERSION, label: APP_VERSION_LABEL })}\n`,
        });
      },
    },
  ],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        // Windows resolves localhost to ::1 first; that hits a stale WSL relay, not uvicorn.
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
