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

// PW_CHROME (from Phase 8) points at a specific Chrome binary when the
// environment's pre-installed browser does not match the pinned Playwright
// version. Hoisted so every Chrome-based project in the SPEC-045 matrix picks
// it up, not just the first one.
//
// It must point at the **headless shell** (`chrome-headless-shell` /
// `headless_shell`), not at the full `chrome` binary. SPEC-045's baselines were
// captured with the shell, and the two synthesise bold type differently: the
// full binary renders every bold heading a fraction differently and the page
// ends up ~5px taller, which fails 27 baselines at once on the case surface.
// The trap is that the obvious response is to re-baseline, which would silently
// throw the visual gate away (found in SPEC-056).
const chromeBinary = process.env.PW_CHROME
  ? { launchOptions: { executablePath: process.env.PW_CHROME } }
  : {};

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
  // SPEC-053: monitoring plans and the calibration record live under the memory
  // root, outside the case directory, so a fixture case cannot carry them.
  // Pointing the memory root at a committed fixture is what makes the
  // monitoring surfaces reachable in e2e rather than component tests only.
  backendEnv = { AGENTADVISOR_MEMORY_ROOT: path.join(repoRoot, "tests", "fixtures", "memory") };
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
  use: { ...devices["Desktop Chrome"], colorScheme: "light" as const, ...chromeBinary },
  // The reduced-motion check asserts the preference is *applied*, so it is
  // only meaningful in the project that applies it.
  grepInvert: /reduced motion/,
};

const chromiumDarkProject = {
  name: "chromium-dark",
  use: { ...devices["Desktop Chrome"], colorScheme: "dark" as const, ...chromeBinary },
  grep: /visual baselines|token contrast|accessibility \(axe\)/,
};

// SPEC-052: the most likely moment to check a three-hour run is on a phone,
// and until this phase no project had ever exercised one.
const mobileProject = {
  name: "mobile",
  use: { ...devices["Pixel 7"], colorScheme: "light" as const, ...chromeBinary },
  grep: /visual baselines|small viewports/,
};

// Axe only. The small-viewport sweep is layout, and layout does not differ by
// theme — running it twice cost two minutes and bought nothing.
const mobileDarkProject = {
  name: "mobile-dark",
  use: { ...devices["Pixel 7"], colorScheme: "dark" as const, ...chromeBinary },
  grep: /accessibility \(axe\)/,
};

const reducedMotionProject = {
  name: "reduced-motion",
  // Both styles.css and Brief.tsx branch on this and nothing tested it.
  use: {
    ...devices["Desktop Chrome"],
    ...chromeBinary,
    contextOptions: { reducedMotion: "reduce" as const },
  },
  grep: /reduced motion/,
};

const webkitProject = {
  name: "webkit",
  use: { ...devices["Desktop Safari"], colorScheme: "light" as const },
  retries: 1, // reading-experience parity, allow one retry
  // Screenshots are engine-specific; webkit would need its own baselines
  // for no additional signal about the design system.
  grepInvert: /visual baselines|token contrast|density guard/,
};

const ALL_PROJECTS = [
  chromiumProject,
  chromiumDarkProject,
  mobileProject,
  mobileDarkProject,
  reducedMotionProject,
  webkitProject,
];

// The deterministic modes carry the whole SPEC-045 matrix and let
// ``modeDescribe`` do the skipping; a live smoke spends real usage, so it runs
// on exactly one browser (SPEC-037).
const projects = E2E_MODE === "live" ? [chromiumProject] : ALL_PROJECTS;

export default defineConfig({
  testDir: ".",
  // Live mode runs only its own spec; the deterministic modes collect
  // everything (live.spec.ts included — it reports itself skipped, which is
  // what SPEC-037 asks the default suite to show).
  testMatch: E2E_MODE === "live" ? "live.spec.ts" : undefined,
  timeout: 60_000,
  expect: {
    timeout: 10_000,
    // Screenshot determinism.  A flaky visual gate is worse than no visual
    // gate: it gets muted rather than fixed, and then the harness has cost
    // time and bought nothing.  Animations are frozen and a small per-pixel
    // tolerance absorbs font antialiasing without hiding a layout change.
    toHaveScreenshot: {
      animations: "disabled",
      caret: "hide",
      scale: "css",
      maxDiffPixelRatio: 0.01,
    },
  },

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

  // SPEC-045: the verification matrix.
  //
  // Theme and viewport are projects rather than per-test loops so a run can be
  // scoped to one dimension.  That scoping is load-bearing: the full
  // cross-product multiplied against every route would blow SPEC-037's
  // ten-minute budget, so the visual and axe sweeps run on the two theme
  // projects and mobile covers layout only (see SPEC-055's budgets).
  //
  // `colorScheme` sets the OS preference and `data-theme` is stamped by the
  // app's own control; both are exercised because an explicit choice has to
  // beat the media query in both directions.
  // Each project runs only the sweeps that dimension can actually falsify.
  // The full cross-product (5 projects x 3 modes x every spec) would be four
  // to six times SPEC-037's ten-minute budget, and a suite that slow gets
  // skipped rather than fixed. Scoping is therefore part of the design, not an
  // optimisation: dark repeats the presentation sweeps, mobile repeats layout
  // only, reduced-motion runs one targeted check, and webkit stays on the
  // functional journeys it has always covered.
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
