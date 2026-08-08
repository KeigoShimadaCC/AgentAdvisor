import { test as baseTest, expect, type Page } from "@playwright/test";

// ── Mode guard ───────────────────────────────────────────────────────────────

export const E2E_MODE = process.env.E2E_MODE ?? "fixture";

/**
 * Conditionally skip a ``describe`` block when the suite is not running in the
 * requested mode.  Uses Playwright's ``test.describe.skip`` so skipped blocks
 * are fully typed and reported as skipped in the test output.
 *
 * Usage::
 *
 *   modeDescribe("fixture", "library tests", () => {
 *     test("shows cases", async ({ page }) => { ... });
 *   });
 */
export function modeDescribe(mode: string, title: string, body: () => void): void {
  if (E2E_MODE === mode) {
    baseTest.describe(title, body);
  } else {
    baseTest.describe.skip(title, body);
  }
}

// ── Terminology guard ────────────────────────────────────────────────────────

/**
 * Raw enum strings and schema field names that must never appear in the
 * rendered DOM.  The terminology lexicon (``copy/terms.ts``) is the sole
 * source of user-facing labels; these internal identifiers leak if a screen
 * forgets to translate them.
 */
const FORBIDDEN_TERMS: string[] = [
  // CaseStage enum values
  "awaiting_framing_approval",
  "awaiting_final_approval",
  "provisional_thesis",
  "assumption_ledger",
  "pre_mortem",
  "stop_decision",
  "evidence_critique",
  "preliminary_recommendation",
  // TaskRole enum values (beyond what might legitimately appear in copy)
  "assumption_analyst",
  "director_b",
  // Raw schema field names that should be translated.  NOTE: simple English
  // words that are also field names ("reliability", "directness",
  // "materiality", "provenance") are intentionally excluded because the app
  // uses them as legitimate human labels (e.g. "High reliability", "High
  // materiality", "Provenance chain").  Only compound snake_case identifiers
  // that would only leak if a screen forgot to translate are forbidden.
  "risk_tolerance",
  "reversibility",
  "decision_question",
  "alternatives_mentioned",
  "independence_group",
  "cluster_share",
  "authority_score",
  "source_tier",
  "resolution_status",
  "objection_id",
  "evidence_id",
  "assumption_id",
  // StopReason enum values. These reached users verbatim on the Delivery sheet
  // and the early-stop path — "Stop reasons: no_critical_evidence_gaps_remain,
  // recommendation_stable_across_plausible_sensitivity_ranges" — for the whole
  // of phase 9, because this list named stage and role enums but not these
  // (found in SPEC-056, fixed in its follow-up).
  "no_critical_evidence_gaps_remain",
  "recommendation_stable_across_plausible_sensitivity_ranges",
  "no_unresolved_objection_likely_to_change_decision",
  "expected_value_of_more_research_low",
  "investigation_budget_exhausted",
  "user_deadline_or_depth_limit_reached",
  // BudgetDimension enum values, which leaked from the same two lines.
  "agent_invocations",
  "concurrent_workers",
  "repair_cycles",
  "research_tasks",
  "high_tier_calls",
  "wall_clock_s",
];

/**
 * Sweep the visible DOM for forbidden terminology.  Call after navigating to
 * any screen.  Fails if any forbidden term appears in the page's visible text
 * content.
 */
export async function assertNoForbiddenTerms(page: Page): Promise<void> {
  // Settle before reading (SPEC-056 follow-up). The projection is refetched
  // shortly after the first paint, and the disclosure block — the one that was
  // leaking raw `StopReason` values — arrives with it. Reading `innerText` as
  // soon as the shell is up sampled the page *before* the offending text
  // existed, so the guard reported clean on a screen that was leaking. Longer
  // than SPEC-047's 250ms refetch debounce, for the same reason the visual
  // suite waits longer than it.
  await page.waitForTimeout(1_200);
  // Filenames are not terminology. The Method room lists the case's own records
  // by their real names — `evidence_critique.yaml` — and an auditor matching a
  // row against what is on disk needs exactly that string. Renaming it to
  // "Critiquing the evidence.yaml" would point at a file that does not exist.
  // Stripping them keeps the guard about *prose* and lets it stay strict there.
  const bodyText = (await page.locator("body").innerText()).replace(
    /\b[a-z0-9_]+\.(ya?ml|json|md|jsonl)\b/g,
    "",
  );
  const found: string[] = [];
  for (const term of FORBIDDEN_TERMS) {
    if (bodyText.includes(term)) {
      found.push(term);
    }
  }
  expect(
    found,
    `Forbidden internal terminology found in DOM: ${found.join(", ")}`,
  ).toEqual([]);
}

// ── API helpers (for stub-mode lifecycle tests) ──────────────────────────────

const API_BASE = "/api";

export async function apiPost<T = unknown>(
  page: Page,
  path: string,
  body?: unknown,
): Promise<{ status: number; data: T }> {
  const resp = await page.request.post(`${API_BASE}${path}`, {
    data: body ?? {},
    headers: { "Content-Type": "application/json" },
  });
  const data = (await resp.json().catch(() => null)) as T;
  return { status: resp.status(), data };
}

export async function apiGet<T = unknown>(
  page: Page,
  path: string,
): Promise<{ status: number; data: T }> {
  const resp = await page.request.get(`${API_BASE}${path}`);
  const data = (await resp.json().catch(() => null)) as T;
  return { status: resp.status(), data };
}

/** Poll the case view endpoint until the stage matches, or timeout. */
export async function waitForStage(
  page: Page,
  caseId: string,
  stage: string,
  timeoutMs = 30_000,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const { data } = await apiGet<{ stage: string }>(
      page,
      `/cases/${caseId}/view`,
    );
    if (data?.stage === stage) return;
    await page.waitForTimeout(500);
  }
  throw new Error(`Case ${caseId} did not reach stage "${stage}" within ${timeoutMs}ms`);
}

// ── Fixture case IDs ─────────────────────────────────────────────────────────

export const FIXTURE_COMPLETED = "case-001-fixture-001";
export const FIXTURE_PARKED = "case-002-fixture-002-parked";
