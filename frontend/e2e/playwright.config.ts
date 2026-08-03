import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ── Mode selection ───────────────────────────────────────────────────────────
//
// The suite supports three deterministic backing modes, selected by the
// ``E2E_MODE`` env var.  Each mode starts a different ``advisor ui``
// configuration:
//
//   fixture (default) — committed dummy case data, read-only journeys
//   stub              — real orchestrator on StubBackend, full lifecycle
//   replay            — recorded audit timing, progress-experience assertions
//
// ``make e2e-frontend`` runs all three sequentially.

const E2E_MODE = process.env.E2E_MODE ?? "fixture";

const FRONTEND_PORT = 5173;
const BACKEND_PORT = 8765;

// Resolve repo and frontend dirs relative to this config file
// (frontend/e2e/playwright.config.ts → frontend/ → repo root).
const frontendDir = path.resolve(__dirname, "..");
const repoRoot = path.resolve(frontendDir, "..");

// ── Backend command per mode ─────────────────────────────────────────────────

let backendCommand: string;
let backendEnv: Record<string, string> = {};

if (E2E_MODE === "replay") {
  backendCommand =
    "uv run advisor ui --replay tests/fixtures/cases/case-001-fixture-001 --speed 1000";
} else if (E2E_MODE === "stub") {
  // Stub mode needs a fresh temp cases directory so each run starts clean.
  const stubCasesRoot = path.join(frontendDir, "e2e", ".tmp", "cases-stub");
  backendCommand = `rm -rf ${stubCasesRoot} && mkdir -p ${stubCasesRoot} && uv run advisor ui --cases-root ${stubCasesRoot}`;
  backendEnv = { AGENTADVISOR_BACKEND: "stub" };
} else {
  // fixture (default)
  backendCommand = "uv run advisor ui --cases-root tests/fixtures/cases";
}

export default defineConfig({
  testDir: ".",
  timeout: 60_000,
  expect: { timeout: 10_000 },

  // Determinism: single worker, no parallelism.
  fullyParallel: false,
  workers: 1,

  // retries: 0 for fixture/stub (determinism is the point).
  // Replay gets 1 retry for timing flake; webkit always gets 1.
  retries: E2E_MODE === "replay" ? 1 : 0,

  reporter: [
    ["html", { open: "never", outputFolder: "artifacts/report" }],
    ["list"],
  ],
  outputDir: "artifacts/test-results",

  use: {
    baseURL: `http://127.0.0.1:${FRONTEND_PORT}`,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "webkit",
      use: { ...devices["Desktop Safari"] },
      retries: 1, // reading-experience parity, allow one retry
    },
  ],

  // Two servers: the FastAPI backend (advisor ui) and the Vite dev server
  // (which proxies /api to the backend per vite.config.ts).
  webServer: [
    {
      command: backendCommand,
      cwd: repoRoot,
      port: BACKEND_PORT,
      timeout: 30_000,
      reuseExistingServer: !process.env.CI,
      env: {
        ...process.env,
        AGENTADVISOR_TEST_HOOKS: "1",
        ...backendEnv,
      } as Record<string, string>,
    },
    {
      command: "npm run dev",
      cwd: frontendDir,
      port: FRONTEND_PORT,
      timeout: 30_000,
      reuseExistingServer: !process.env.CI,
      env: { ...process.env } as Record<string, string>,
    },
  ],
});
