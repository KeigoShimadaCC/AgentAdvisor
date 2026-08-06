# Spec sweep — 2026-08-06

A full pass over all 56 spec sheets in `specs/`, checking each sheet's deliverables, acceptance
criteria and verification claims against the actual codebase, and fixing what did not hold up.
Initiated as an autonomous sweep ("check each spec sheet, fix the gaps, don't stop until all
specs are done"), so it also establishes the toolchain baselines a fresh machine needs to repeat
every check.

## Baselines

Established before touching anything, and re-verified after every fix:

| Check | Before | After |
|---|---|---|
| `make check` (ruff, mypy, pytest) | 919 passed, 18 live deselected | **928 passed, 19 deselected** |
| `make frontend-check` (tsc, drift, vitest) | 105 passed | **109 passed** |
| `npm run e2e:typecheck` | clean | clean |
| `make e2e-frontend` (fixture + stub + replay) | **broken target** (see SPEC-037 below) | **green: 53 + 10 + 12 passed** across chromium, webkit and the new mobile project |

The test-count deltas are the sweep's own additions: +9 rubric tests (SPEC-026), +4 Options-room
tests (SPEC-040), +1 deselected live test (SPEC-018's `live_slow` case).

## Gaps found and fixed (code)

Eight places where a sheet claimed something the codebase did not have. Each fix is recorded in
the sheet itself with a dated amendment.

1. **SPEC-008 — `BudgetConfig` was never exported as a schema.** Added to `MODEL_EXPORTS` in
   `orchestrator/artifacts/schema_export.py`; `make schemas` + `make frontend-types` generated
   `schemas/budget_config.schema.json` and `frontend/src/generated/budget_config.ts` (64 schemas
   now processed). The drift gate (`npm run check:clean`) passes.
2. **SPEC-018 — the live toy-case e2e test did not exist.** Created
   `tests/test_pipeline_live.py`: a `live_slow` purchase-timing case on the small budget (≤15
   invocations), cheap-model pins per backend with the Director/Challenger family split
   preserved, asserting DONE, audit usage metadata, a valid `FinalRecommendation` and the
   rendered report. Collects and deselects cleanly; running it needs an authenticated CLI.
3. **SPEC-026 — the rubric extension was only half delivered.** `_phase6_metrics` collected the
   numbers but `benchmarks/rubric.yaml` had no Phase 6 criteria, despite the phase-6 report
   claiming "the rubric was extended". Added six `phase: 6` dimensions (12 criteria) to the
   rubric and a `_score_phase6` scorer to `scripts/run_e2e_eval.py`, wired exactly like
   SPEC-044's Phase 8 extension (legacy average untouched). 35 rubric tests pass. Erratum added
   to `report-and-findings/2026-08-03-phase-6-before-after.md`.
4. **SPEC-037 — three scope items absent.** Created `frontend/e2e/live.spec.ts` (the
   consent-gated live smoke: preflights agent-CLI auth, commissions on the small profile,
   renders the real scope sheet, signs, observes `structuring` completing via the audit log,
   pauses, asserts disk artifacts; 20-minute wall; temp cases root), added the `mobile`
   Playwright project (390×844, library + scope-checkpoint flows), added `make
   e2e-frontend-live`, and documented live mode in `frontend/README.md`. Verified: the live
   spec reports skipped without consent and the suite passes, in both fixture and live config.
5. **SPEC-037 — `make e2e-frontend` never worked as written.** Each recipe line runs in its own
   shell, so the `npx playwright` lines executed from the repo root and failed with
   "e2e/playwright.config.ts does not exist". The 2026-08-03 verification had run the modes
   from `frontend/` by hand. Fixed the recipe; the full target is now green end to end for the
   first time (fixture 53 passed/25 skipped, stub 10, replay 12 — chromium, webkit and mobile).
6. **SPEC-040 — the Options-room ACH panel was never built.** The projection
   (`ach_scored`, `ach_uninformative_evidence_ids`, per-option disconfirmation standings) and
   the generated TS types carried the data with no consumer. `OptionsRoom.tsx` now renders a
   "Competing hypotheses" exhibit (standings least-disconfirmed first, records-against as
   `CitationLink`s, the zero-diagnosticity list named) plus a "least disconfirmed" badge on the
   rank-1 option. Four new tests over a new `makeOptionsACHFixture`; 11/11 pass.
7. **SPEC-042 — no `monitor` entry in `backends/droid/models.yaml`.** The role sat on the
   tier-low default (haiku) for a structured-output task — the failure mode the `ach` override
   exists for. Added the override (claude-sonnet-5 / gpt-5.4) with the reasoning recorded.
   Verified by resolving the pair and running the droid/lexicon/monitoring tests (47 passed).
8. **Phase 9 — the effort-history read had no owner.** SPEC-050's measured effort estimates
   need a history endpoint; its open question recommended `GET /api/effort-history`, but
   SPEC-046 (the sheet that gathers phase 9's backend changes) did not own it. Added to
   SPEC-046's scope, deliverables and acceptance criteria; SPEC-050's open question resolved.

## Spec-text corrections (drift between sheet and code)

Recorded in place with dated amendments; no code change needed.

- **SPEC-010** — clarification cap said 5; SPEC-043 raised it to 8. Sheet now says 8.
- **SPEC-021** — "final package in every results folder" contradicted the sheet's own
  committed-layout rule; criterion amended to match (summary.json committed; run-time copies
  stay local).
- **SPEC-023** — three inaccuracies: the Auditor is invoked at CHALLENGE (not
  post-investigation); `AuditStopInput` has no orchestrator consumer (enforcement is via the
  deterministic gates); the verification plan cited a nonexistent
  `tests/test_assumption_ledger.py`.
- **SPEC-035** — two checked deliverables (Notification API wiring, export/print stylesheet) do
  not exist. Unchecked, with the deferral to SPEC-051/052 recorded. The spec stays `verified`:
  no acceptance criterion covers them, and phase 9's drafts own the work.
- **SPEC-037** — the "axe passes in both themes" criterion and the "dark and light themes"
  scope bullet were unsatisfiable (one theme exists; the second is SPEC-045's). Amended; the
  axe half passes on the single theme.
- **SPEC-042** — the scope named lexicon events `indicator_check_recorded` /
  `indicator_breached`, which were never emitted events; corrected to the real three
  (`monitoring_plan_written`, `monitoring_plan_not_concretized`, `monitoring_plan_skipped`) and
  recorded that `tests/test_lexicon.py` is the test satisfying the unknown-event-fallback
  criterion.
- **Phase 9 README + sheets** — the README said "four waves" while listing six; claimed every
  intra-wave pair was `parallel_with` while 048 depends on 047; said "051 renders SPEC-042's
  outputs" while 051's own sheet assigns that surface to 053 (and SPEC-042 shipped its own
  Delivery block); claimed "not one of SPEC-038–044 mentions the frontend/CaseView/UI", which
  was false (038/040 projected, 042 built an endpoint and a screen); and misstated the sheets'
  measured sizes. All corrected in place; the `parallel_with` graph was symmetrised (049 now
  lists 054, 052 lists 055 — both relationships were already declared one-way). SPEC-053's
  summary carries the same correction.

## Deliberately not done

- **SPEC-035's two missing features** (notifications, export). They are assigned to draft
  SPEC-051/052; implementing a draft spec's scope before approval would violate the lifecycle
  in `specs/README.md`. The sheets now say so.
- **SPEC-044's live benchmark sweep** and **executing the new live tests** (SPEC-018's
  `test_pipeline_live.py`, SPEC-037's `live.spec.ts`). All three need an authenticated agent
  CLI and real token spend (SPEC-044: ~7M tokens). The infrastructure is now in place and
  self-skipping; the runs remain for an environment with credentials.
- **Phase 9 implementation.** All twelve sheets are drafts; the sweep corrected their internal
  consistency only.

## State of the board

Phases 0–7 remain done and re-verified. Phase 8 remains `in_progress` on SPEC-044 alone (the
live sweep). Phase 9 remains all-draft, now internally consistent. Every one of the 56 sheets
was checked; 15 changed (ten in phases 0–8, five in phase 9, plus the phase-9 README), and the
other 41 verified as accurate as written.
