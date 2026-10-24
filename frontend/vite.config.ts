import path from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const root = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  publicDir: path.resolve(root, "../static"),
  plugins: [react()],
  server: {
    fs: { allow: [path.resolve(root, "..")] },
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      "/liveness": "http://127.0.0.1:8000",
      "/readiness": "http://127.0.0.1:8000",
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test-setup.ts",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});
