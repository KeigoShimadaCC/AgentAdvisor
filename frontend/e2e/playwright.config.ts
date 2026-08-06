import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ── Mode selection ───────────────────────────────────────────────────────────
//
// The suite supports four backing modes, selected by the ``E2E_MODE`` env var.
// Each mode starts a different ``advisor ui`` configuration:
//
//   fixture (default) — committed dummy case data, read-only journeys
//   stub              — real orchestrator on StubBackend, full lifecycle
//   replay            — recorded audit timing, progress-experience assertions
//   live              — real agent backend, opt-in smoke (SPEC-037; requires
//                       E2E_LIVE=1 and AGENTADVISOR_E2E_BUDGET_ACK=1, and only
//                       ever runs live.spec.ts)
//
// ``make e2e-frontend`` runs the three deterministic modes sequentially;
// ``make e2e-frontend-live`` runs the live smoke.

const E2E_MODE = process.env.E2E_MODE ?? "fixture";

// Dedicated e2e ports, deliberately NOT the dev defaults (5173/8765): a
// leftover dev server, replay server, or another session's stack must never
// be able to stand in for the suite's own servers.
const FRONTEND_PORT = 5273;
const BACKEND_PORT = 8865;

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
    `${advisorUi} --port ${BACKEND_PORT} --cases-root tests/fixtures/cases --replay tests/fixtures/cases/case-001-fixture-001 --speed 1000`;
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
} else if (E2E_MODE === "live") {
  // Live mode: the real backend with a temp cases root that survives the run
  // for inspection. Never points at cases/ and never at the committed fixtures.
  const liveCasesRoot = path.join(frontendDir, "e2e", ".tmp", "cases-live");
  backendCommand = `mkdir -p ${liveCasesRoot} && ${advisorUi} --port ${BACKEND_PORT} --cases-root ${liveCasesRoot}`;
} else {
  // fixture (default)
  backendCommand = `${advisorUi} --port ${BACKEND_PORT} --cases-root tests/fixtures/cases`;
}

// ── Projects ─────────────────────────────────────────────────────────────────

const chromiumProject = {
  // PW_CHROME overrides the browser binary. Playwright resolves a build
  // keyed to the pinned @playwright/test version, so an environment that
  // ships a different chromium (a container image, a distro package)
  // cannot launch the suite at all. Unset, this is exactly the default
  // resolution — the escape hatch costs nothing and is the difference
  // between the suite running somewhere and not running there.
  name: "chromium",
  use: {
    ...devices["Desktop Chrome"],
    launchOptions: { executablePath: process.env.PW_CHROME || undefined },
  },
};

const webkitProject = {
  name: "webkit",
  use: { ...devices["Desktop Safari"] },
  retries: 1, // reading-experience parity, allow one retry
};

// SPEC-037's mobile project: the 390x844 viewport over the fixture journeys
// and the checkpoint flows only — the stub lifecycle and the replay timing
// assertions are desktop concerns, and the rooms were not designed for this
// width yet (that is SPEC-052's scope), so the grep keeps the project to the
// flows a decision owner would actually start from a phone.
const mobileProject = {
  name: "mobile",
  use: {
    ...devices["Desktop Chrome"],
    viewport: { width: 390, height: 844 },
    launchOptions: { executablePath: process.env.PW_CHROME || undefined },
  },
  grep: /case library|scope checkpoint/,
};

const projects =
  E2E_MODE === "live"
    ? [chromiumProject] // a live smoke needs exactly one browser
    : E2E_MODE === "fixture"
      ? [chromiumProject, webkitProject, mobileProject]
      : [chromiumProject, webkitProject];

export default defineConfig({
  testDir: ".",
  // Live mode runs only its own spec; the deterministic modes collect
  // everything (live.spec.ts included — it reports itself skipped, which is
  // what SPEC-037 asks the default suite to show).
  testMatch: E2E_MODE === "live" ? "live.spec.ts" : undefined,
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

  projects,

  // Two servers: the FastAPI backend (advisor ui) and the Vite dev server
  // (which proxies /api to the backend per vite.config.ts).
  webServer: [
    {
      command: backendCommand,
      cwd: repoRoot,
      port: BACKEND_PORT,
      timeout: 30_000,
      // Never reuse: a stale server (e.g. a leaked replay backend, which
      // lists only its replay case) silently poisons the whole run. Failing
      // loudly on an occupied port is the honest behavior.
      reuseExistingServer: false,
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
      reuseExistingServer: false,
      env: {
        ...process.env,
        // Point vite.config.ts's /api proxy at the suite's own backend.
        AGENTADVISOR_API_PORT: String(BACKEND_PORT),
      } as Record<string, string>,
    },
  ],
});
