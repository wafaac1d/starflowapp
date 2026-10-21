import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  use: { baseURL: "http://127.0.0.1:4173" },
  webServer: {
    command: "uv run python scripts/e2e_serve.py",
    cwd: "..",
    url: "http://127.0.0.1:4173/liveness",
    timeout: 180_000,
    reuseExistingServer: false,
  },
});
