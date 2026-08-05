---
id: SPEC-056
title: Phase 9 re-evaluation — visual regression, full e2e, and a real case on the new surface
phase: 9
status: draft
depends_on: [SPEC-045, SPEC-046, SPEC-047, SPEC-048, SPEC-049, SPEC-050, SPEC-051, SPEC-052, SPEC-053, SPEC-054, SPEC-055]
parallel_with: []
north_star_refs: ["15", "18"]
last_updated: 2026-08-05
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

- [ ] Full verification sweep executed, with commands and outcomes recorded in this sheet
- [ ] One real case run end to end on the new surface exercising phase 8's stages
- [ ] The four measured before/after claims, computed and recorded
- [ ] Backend-surface audit: `orchestrator/` diff reviewed against the phase README's table
- [ ] `report-and-findings/2026-XX-XX-phase-9-before-after.md`
- [ ] `specs/ROADMAP.md` — phase 9 marked done with findings

## Acceptance criteria

- [ ] `make check`, `make frontend-check` and `make e2e-frontend` all green from a clean checkout,
      with the e2e suite within SPEC-037's 10-minute budget on the reference machine.
- [ ] Visual regression passes across light/dark × desktop/mobile with no unreviewed baseline
      changes; axe reports zero serious/critical on every route in both themes.
- [ ] `coverage.spec.ts` passes: every phase 8 artifact type is reachable from a screen.
- [ ] The full e2e matrix stays inside SPEC-037's 10-minute budget and the visual suite passes twice
      consecutively with no pixel diff, per SPEC-055's budgets.
- [ ] The real case completes on the new surface with both checkpoints signed through the UI, and
      its artifacts validate — asserted from disk, not from the screen.
- [ ] All four measured claims are recorded with their method, including any that did not improve.
- [ ] The `orchestrator/` diff contains only the additions listed in the phase README's backend table;
      `tests/test_pipeline_invariants.py` passes.
- [ ] The report exists and the ROADMAP carries the phase 9 findings entry.

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

Not yet executed.

## Open questions

- The phase 9 base commit for the backend-surface audit must be pinned when the phase starts, not
  at verification time, or the diff will include phase 8's merge.
