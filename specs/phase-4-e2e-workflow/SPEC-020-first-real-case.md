---
id: SPEC-020
title: First real decision case
phase: 4
status: draft
depends_on: [SPEC-019]
parallel_with: []
north_star_refs: ["17", "13", "18"]
last_updated: 2026-07-30
---

# SPEC-020 — First real decision case

## Summary

Run one genuine investment-style decision end to end with production role-model assignments and the default budget, measure everything, and write the findings report. This is a validation run, not new functionality.

## Motivation

North star 13 (compare decision quality with resource consumption), 17 (investment vertical first), and open questions 3/5/6/7 need first empirical data.

## Scope

- Select a real, personally relevant investment-style decision with the user at approval time (fallback: a public-company invest/stage/decline decision).
- Run via `advisor new` with default budget and the production role configs (Director opus-5 family, Challenger gpt-5.6 family, workers Cursor-pool, per the 2026-07-30 research).
- Capture: total/per-role invocations and tokens, wall clock, retry-ladder frequency, budget headroom, auditor findings usefulness, repair-cycle behavior, subjective output quality against the Section 3 promise (all twelve elements present and meaningful).
- Findings report `report-and-findings/<date>-first-real-case.md` (metrics tables + qualitative assessment + defect list); ROADMAP Phase 4 findings updated; new emergent-work candidates filed.
- Small fixes discovered during the run: config/prompt (role md) tuning allowed within this spec; code changes beyond ~20 lines require a new spec or an existing spec reopened.

## Out of scope

Benchmark comparison (SPEC-021/022), model reallocation beyond single-role prompt/config tuning, publishing case content (case data stays local; the findings report must contain no sensitive personal detail).

## Design

The case runs untouched first (no mid-run tuning) to get honest baseline metrics; a second tuned run is optional if the first reveals blocking prompt defects. Metrics extracted from audit.jsonl by a small script (`scripts/case_metrics.py`, part of this spec) rather than by hand.

## Deliverables

- [ ] Completed real case under `cases/` (local only, gitignored)
- [ ] `scripts/case_metrics.py`
- [ ] `report-and-findings/<date>-first-real-case.md`
- [ ] ROADMAP Phase 4 findings + emergent-work updates

## Acceptance criteria

- [ ] Case reaches DONE (or a disclosed budget stop) without manual state surgery.
- [ ] final_recommendation.md contains all twelve Section 3 elements with resolvable citations.
- [ ] Audit log alone suffices to reconstruct: every invocation's role, model, tokens, duration; every transition (spot-check by replaying metrics script).
- [ ] Findings report includes the full metrics table and answers: usage per decision, retry rate, weakest role, whether repair changed the recommendation.
- [ ] `make check` green (no code regressions).

## Verification plan

```
advisor new "<chosen real decision>" && advisor status <id> ... advisor report <id>
uv run python scripts/case_metrics.py cases/<id> 
# review findings report together with the user
```

## Verification results

—

## Open questions

- The concrete decision prompt: chosen with the user at approval time.
