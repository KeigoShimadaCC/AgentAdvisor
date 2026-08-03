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

// Use the venv Python directly (uv run may not be in PATH in subprocess).
const pyBin = path.join(repoRoot, ".venv", "bin", "python");
const advisorUi = `${pyBin} -m orchestrator.cli ui`;

// ── Backend command per mode ─────────────────────────────────────────────────

let backendCommand: string;
let backendEnv: Record<string, string> = {};

if (E2E_MODE === "replay") {
  // --cases-root must point at the fixture directory so the service can find
  // the replay case (config.cases_root is used by _load_or_404; without this
  // it defaults to <repo>/cases and the fixture is not found).
  backendCommand =
    `${advisorUi} --cases-root tests/fixtures/cases --replay tests/fixtures/cases/case-001-fixture-001 --speed 1000`;
} else if (E2E_MODE === "stub") {
  // Stub mode needs a fresh temp cases directory so each run starts clean.
  const stubCasesRoot = path.join(frontendDir, "e2e", ".tmp", "cases-stub");
  // Bypass the CLI's main() which calls make_backend() and rejects
  // AGENTADVISOR_BACKEND=stub (only "cursor"/"droid" are valid BackendName
  // values).  The stub env var is still inherited by worker subprocesses
  // via os.environ.copy() in control._spawn_worker, and the worker's
  // _build_backend handles "stub" correctly.  We start uvicorn directly
  // with the app factory so make_backend is never called in this process.
  backendCommand = `rm -rf ${stubCasesRoot} && mkdir -p ${stubCasesRoot} && ${pyBin} -c "import pathlib, uvicorn; from orchestrator.service.app import create_app; app = create_app(cases_root=pathlib.Path('${stubCasesRoot}')); uvicorn.run(app, host='127.0.0.1', port=${BACKEND_PORT}, log_level='info')"`;
  backendEnv = { AGENTADVISOR_BACKEND: "stub" };
} else {
  // fixture (default)
  backendCommand = `${advisorUi} --cases-root tests/fixtures/cases`;
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
      command: `${frontendDir}/node_modules/.bin/vite --host 127.0.0.1 --port ${FRONTEND_PORT} --strictPort`,
      cwd: frontendDir,
      port: FRONTEND_PORT,
      timeout: 30_000,
      reuseExistingServer: !process.env.CI,
      env: { ...process.env } as Record<string, string>,
    },
  ],
});
