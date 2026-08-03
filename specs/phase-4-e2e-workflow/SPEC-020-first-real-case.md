---
id: SPEC-020
title: First real decision case
phase: 4
status: verified
depends_on: [SPEC-019]
parallel_with: []
north_star_refs: ["17", "13", "18"]
last_updated: 2026-08-03
---

# SPEC-020 — First real decision case

## Summary

Run one genuine investment-style decision end to end with production role-model assignments and the default budget, measure everything, and write the findings report. This is a validation run, not new functionality.

## Motivation

North star 13 (compare decision quality with resource consumption), 17 (investment vertical first), and open questions 3/5/6/7 need first empirical data.

## Scope

- Select a real, personally relevant investment-style decision with the user at approval time (fallback: a public-company invest/stage/decline decision). **Chosen 2026-08-02: a career or compensation decision.** It is investment-style in the sense that matters here, a capital-allocation choice under uncertainty with an irreversible component, and benchmark scenario 04 already shows the pipeline handles the shape.
- Run via `advisor new` with default budget and the production role configs (Director opus-5 family, Challenger gpt-5.6 family, workers Cursor-pool, per the 2026-07-30 research).
- Capture: total/per-role invocations and tokens, wall clock, retry-ladder frequency, budget headroom, auditor findings usefulness, repair-cycle behavior, subjective output quality against the Section 3 promise (all twelve elements present and meaningful).
- Findings report `report-and-findings/<date>-first-real-case.md` (metrics tables + qualitative assessment + defect list); ROADMAP Phase 4 findings updated; new emergent-work candidates filed.
- Small fixes discovered during the run: config/prompt (role md) tuning allowed within this spec; code changes beyond ~20 lines require a new spec or an existing spec reopened.

## Out of scope

Benchmark comparison (SPEC-021/022), model reallocation beyond single-role prompt/config tuning, publishing case content (case data stays local; the findings report must contain no sensitive personal detail).

## Design

The case runs untouched first (no mid-run tuning) to get honest baseline metrics; a second tuned run is optional if the first reveals blocking prompt defects. Metrics extracted from audit.jsonl by a small script (`scripts/case_metrics.py`, part of this spec) rather than by hand.

## Deliverables

- [x] Completed real case under `cases/` (local only, gitignored) — `case-014-career-startup-pivot`, reached `done`
- [x] `scripts/case_metrics.py` — written early (2026-08-02) so the Phase 6 benchmark runs could be measured with the same instrument; 8 unit tests over a synthetic audit log
- [x] `report-and-findings/2026-08-03-first-real-case.md`
- [x] ROADMAP Phase 4 findings + emergent-work updates

## Acceptance criteria

- [x] Case reaches DONE (or a disclosed budget stop) without manual state surgery.
- [x] final_recommendation.md contains all twelve Section 3 elements with resolvable citations *(review gate flagged uncited claims — disclosed via the "done ≠ review-passed" path, not silently accepted; see defect 3 in the findings report)*.
- [x] Audit log alone suffices to reconstruct: every invocation's role, model, tokens, duration; every transition (the findings tables were produced entirely by `case_metrics.py` from `audit.jsonl`).
- [x] Findings report includes the full metrics table and answers: usage per decision, retry rate, weakest role, whether repair changed the recommendation.
- [x] `make check` green (no code regressions).

## Verification plan

```
advisor new "<chosen real decision>" && advisor status <id> ... advisor report <id>
uv run python scripts/case_metrics.py cases/<id> 
# review findings report together with the user
```

## Verification results

Verified 2026-08-03 via `case-014-career-startup-pivot` on the Droid CLI backend. Full report:
`report-and-findings/2026-08-03-first-real-case.md`.

- **Completed end to end, reached `done` with no manual state surgery.** Ran the full Section 8
  workflow: intake → framing (approved) → provisional thesis → planning → investigation (9 tasks,
  0 task failures) → assumptions → preliminary recommendation → pre-mortem → challenge → 2 repair
  cycles → synthesis → review → final approval → done.
- **Usage:** 1,576,002 tokens, 191 min wall clock, 45 invocations (32 ok, 71% first-pass, 12
  retries). 19 evidence, 4 assumptions, 7 objections.
- **All twelve Section 3 elements present** with distinct uncertainty measures (rec confidence
  55%, evidence confidence 45%, model stability 100%, outcome probabilities 65%/35%) and
  resolvable citations. The calibration review failed both attempts (uncited claims + undisclosed
  open objection); the recommendation was surfaced under the disclosed "done ≠ review-passed" path.
- **Answers:** repair did not change the preferred alternative (4 thesis revisions, 0 flips);
  weakest role analytically is the synthesizer (failed review twice); the structurer's low rate is
  an artifact of the backend crash below, not analytical quality.
- **Metrics reproduced from `audit.jsonl` alone** by `scripts/case_metrics.py`, confirming the
  audit log suffices to reconstruct the run. `make check` green (716 unit tests).

Two defects were found and fixed within this spec's engineering allowance: the spurious droid
`agent_error` post-completion crash (`5a3531a`, which caused 9 of 13 failures and cost the dual
track) and heavy-role timeouts at the ceiling (`ff91968`). One higher-value defect is filed as
emergent work: the synthesis stage received truncated inputs (missing the preliminary
recommendation, objection resolutions, and pre-mortem indicators), which is the direct cause of
the review failures and needs a projection/context-budget spec.

## Open questions

- ~~The concrete decision prompt: chosen with the user at approval time.~~ Resolved: a
  career-vs-startup capital-allocation decision (benchmark scenario 04 shape).
