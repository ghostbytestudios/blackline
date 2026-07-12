import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

// E2E smoke stack: a real backend on 8799 with a throwaway vault directory
// (fast Argon2 so vault creation doesn't dominate the run) and vite on 5299.
// Locally the backend runs from its venv; in CI the deps are installed globally.
const backendDir = resolve(import.meta.dirname, "../backend");
const venvPython = resolve(
  backendDir,
  process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python",
);
const python = existsSync(venvPython) ? venvPython : "python";
const dataDir = resolve(import.meta.dirname, ".e2e-data");

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  fullyParallel: false,
  workers: 1, // the tests share one backend vault
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: "http://127.0.0.1:5299",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: `"${python}" -m uvicorn app.main:app --host 127.0.0.1 --port 8799`,
      cwd: backendDir,
      url: "http://127.0.0.1:8799/health",
      reuseExistingServer: false,
      timeout: 60_000,
      env: {
        BLACKLINE_DATA_DIR: dataDir,
        BLACKLINE_ARGON2_TIME_COST: "1",
        BLACKLINE_ARGON2_MEMORY_KIB: "8192",
        BLACKLINE_ARGON2_PARALLELISM: "1",
      },
    },
    {
      command: "npx vite --port 5299 --strictPort",
      cwd: import.meta.dirname,
      url: "http://127.0.0.1:5299",
      reuseExistingServer: false,
      timeout: 60_000,
      env: {
        BLACKLINE_API_TARGET: "http://127.0.0.1:8799",
        VITE_SKIP_TUTORIAL: "1",
      },
    },
  ],
});
