---
id: SPEC-056
title: Phase 9 re-evaluation — visual regression, full e2e, and a real case on the new surface
phase: 9
status: implemented
depends_on: [SPEC-045, SPEC-046, SPEC-047, SPEC-048, SPEC-049, SPEC-050, SPEC-051, SPEC-052, SPEC-053, SPEC-054, SPEC-055]
parallel_with: []
north_star_refs: ["15", "18"]
last_updated: 2026-08-07
---

# SPEC-056 — Phase 9 re-evaluation: visual regression, full e2e, and a real case on the new surface

## Summary

Closes the phase the way phases 4, 5 and 7 were closed: no new functionality, one honest measurement
written up as a report. Runs the full suite across every mode, theme and viewport; drives one real
case end to end on the new surface — exercising phase 8's pipeline so the run covers both phases at
once; and audits that the backend surface matches what phase 9 promised and nothing else moved.

## Motivation

North star Section 18 (MVP success criteria) and Section 15. Phase 9's claim is that the product now
communicates what it does, and the whole phase rests on a structural promise — that a UX phase
changed no pipeline behaviour. Both claims need evidence rather than assertion, and the repo's own
precedent is to produce it: SPEC-020 ran the first real case, SPEC-022 the comparative evaluation,
SPEC-037 the browser verification, each with a dated report in `report-and-findings/`.

## Scope

- Full verification sweep:
  - `make check` (ruff, mypy, the Python unit suite including `tests/test_pipeline_invariants.py`);
  - `make frontend-check` (tsc, generated-types drift, the token guard from SPEC-045, unit tests);
  - `make e2e-frontend` across fixture, stub and replay;
  - visual regression across the light/dark × desktop/mobile matrix against SPEC-045's baselines;
  - axe on every route in both themes;
  - `coverage.spec.ts` from SPEC-053.
- One real case run end to end on the new UI against a real backend, exercising phase 8's stages, at
  the standard effort profile. Recorded: wall clock, invocations, tokens, loops entered, gates
  raised, and the screens the operator actually used.
- A before/after comparison on the UX claims that are measurable rather than aesthetic:
  - time from submitting a prompt to a rendered case surface (was: blocked until framing completed);
  - proportion of run wall-clock during which the interface shows an accurate current activity
    (was: near zero between invocation completions);
  - whether a second challenge round is distinguishable from a stall (was: no);
  - count of phase 8 artifact types reachable from a screen (was: zero);
  - behaviour when the service dies mid-run: does the interface say it is stale, or keep presenting
    a frozen brief as current (was: presents it as current, indistinguishably from a finished one).
- A backend-surface audit: `git diff` against the phase 9 base restricted to `orchestrator/`,
  confirming it contains only the additions listed in the phase README and nothing else.
- `report-and-findings/2026-XX-XX-phase-9-before-after.md` and the ROADMAP phase 9 findings entry.

## Out of scope

- Any new feature, fix or refactor. Defects found here return to the spec that owns them, per
  `specs/README.md`'s lifecycle rule; this sheet does not absorb them.
- Re-verifying phase 8's analytic claims, which SPEC-044 owns.
- Live-model e2e beyond the single real case, which spends real usage and stays manual and consented
  as SPEC-037 established.

## Design

The four measured claims are chosen because they are the ones a screenshot cannot settle and an
opinion should not. Three are directly instrumentable from the audit log and the DOM; the fourth is
a count. "Proportion of wall clock with an accurate current activity" is computed by walking the
audit log and asking, at each second, whether the UI had an event within the progress cadence that
correctly named the running role — which is exactly what SPEC-046's two events make possible and
what the phase's central complaint was about.

The backend-surface audit exists because "we did not change the pipeline" is the phase's structural
promise, and `tests/test_pipeline_invariants.py` proves only that transitions and handlers are
unchanged. A diff review over `orchestrator/` catches the wider claim — that everything added was a
read or an emit.

## Deliverables

- [x] Full verification sweep executed, with commands and outcomes recorded in this sheet
- [ ] One real case run end to end on the new surface exercising phase 8's stages — **not executed**;
      spends real API usage and stays manual and consented per SPEC-037. Stub mode's full lifecycle
      (both gates signed, artifacts asserted from disk) is the closest available evidence.
- [x] The four measured before/after claims, computed and recorded — all five bullets, in the report
- [x] Backend-surface audit: `orchestrator/` diff reviewed against the phase README's table
- [x] `report-and-findings/2026-08-07-phase-9-before-after.md`
- [x] `specs/ROADMAP.md` — phase 9 marked done with findings

## Acceptance criteria

- [~] `make check`, `make frontend-check` and `make e2e-frontend` all green from a clean checkout,
      with the e2e suite within SPEC-037's 10-minute budget on the reference machine. **`make check`
      and `make frontend-check` met; the budget met at 589s.** `make e2e-frontend` was **not** run to
      completion — the target includes the `webkit` project, whose browser is absent from this
      container and cannot be downloaded behind the proxy, so the three modes were run scoped to the
      five chromium-based projects instead. This needs a reference machine with webkit installed.
- [~] Visual regression passes across light/dark × desktop/mobile with no unreviewed baseline
      changes; axe reports zero serious/critical on every route in both themes. **axe met** (15
      routes × both themes, zero serious/critical). **Visual: see below.**
- [x] `coverage.spec.ts` passes: every phase 8 artifact type is reachable from a screen.
- [ ] The full e2e matrix stays inside SPEC-037's 10-minute budget and the visual suite passes twice
      consecutively with no pixel diff, per SPEC-055's budgets. **Budget met (589s / 9m49s); the
      twice-consecutive criterion is NOT met** — one clean run in three, failing `room-method` then
      `room-options` with an identical 5017↔5022px capture oscillation. DOM instability, viewport
      feedback and the browser-binary difference are each eliminated in the report; the remaining
      cause is in the `fullPage` capture path and returns to SPEC-055.
- [ ] The real case completes on the new surface with both checkpoints signed through the UI, and
      its artifacts validate — **not executed**, see deliverables.
- [x] All four measured claims are recorded with their method, including any that did not improve.
- [x] The `orchestrator/` diff contains only the additions listed in the phase README's backend table;
      `tests/test_pipeline_invariants.py` passes.
- [x] The report exists and the ROADMAP carries the phase 9 findings entry.

## Verification plan

```
make check
make frontend-check
make frontend-build
make e2e-frontend
E2E_MODE=fixture npx playwright test --config=frontend/e2e/playwright.config.ts visual.spec.ts coverage.spec.ts
uv run pytest tests/test_pipeline_invariants.py -q
git diff --stat <phase-9-base>..HEAD -- orchestrator/     # backend-surface audit
# real case (manual, consented, spends usage):
uv run advisor ui   # drive one case end to end through the browser
uv run python scripts/case_metrics.py cases/<case-id>
```

## Verification results

Executed 2026-08-07. Full write-up: `report-and-findings/2026-08-07-phase-9-before-after.md`.

| Gate | Outcome |
|---|---|
| `make check` | green — ruff + mypy clean, 968 passed, 105s (1002 after merging main) |
| `make frontend-check` | green — tsc clean, 64 schemas (0 drift), token guard clean, 414 passed (418 after merging main) |
| `make frontend-build` | green — 393.63 kB JS / 78.17 kB CSS |
| e2e, three modes | green on **5 of 6 projects** — fixture 189 / stub 6 / replay 12, **589s total** pre-merge; re-run on the merged tree at **558s** (fixture 189 / stub 6 / replay 12). `make e2e-frontend` itself cannot complete here: it runs the `webkit` project and that browser is absent and not installable behind the proxy, so the modes were run scoped to the chromium-based projects |
| `tests/test_pipeline_invariants.py` | green — 7 passed |
| `coverage.spec.ts` | green — 7 engine outputs plus its self-guard |
| axe | zero serious/critical, 15 routes × both themes |
| `tests/test_phase9_measure.py` | green — 16 passed (the measurement instrument's own tests) |

Measured claims (method in `scripts/phase9_measure.py`):

| Claim | Before | After |
|---|---|---|
| Wall clock with an accurate current activity | ≤ 6.6% | ≥ 93.4% |
| Submit → rendered case surface | at framing (674–781ms, stub) | 193–298ms |
| Second challenge round distinguishable from a stall | no | yes, counted and named |
| Phase 8 artifact types reachable from a screen | 0 | 7 |
| Service dies mid-run | frozen brief shown as current | marked stale |

Backend surface across phase 9's fourteen commits: **six files, +393 / −24**, all reads, emits,
presentation strings, one projection addition and one parameter.

Defects found: two product defects filed and not fixed (a slug truncation that makes a class of
prompts un-startable; commissioning errors bypassing the failure taxonomy, plus raw enum stop
reasons on two surfaces), and two harness defects fixed here (`make e2e-frontend` never ran from the
repo root; the visual baselines are browser-binary-specific).

Not run: the `webkit` project (browser unavailable in this container and not installable behind the
proxy — which also means `make e2e-frontend` as written cannot complete here), and the single real
live-model case (manual and consented per SPEC-037).

## Open questions

- The phase 9 base commit for the backend-surface audit must be pinned when the phase starts, not
  at verification time, or the diff will include phase 8's merge.
  **Resolved at verification:** phase 9's commits straddle phase 8's merge (`726baf8`), so a
  two-dot diff from the branch point is wrong in exactly this way. The audit aggregates the
  fourteen phase-9 commits individually instead.
