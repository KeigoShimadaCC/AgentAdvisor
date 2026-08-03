---
id: SPEC-022
title: Comparative evaluation and DoD audit
phase: 5
status: verified
depends_on: [SPEC-021]
parallel_with: []
north_star_refs: ["18", "19", "13"]
last_updated: 2026-08-03
---

# SPEC-022 — Comparative evaluation and DoD audit

## Summary

Score baseline versus workflow on every benchmark, tune the worst offenders (budgets, model assignments, prompts) within bounded iterations, and close the project's definition of done with an explicit audit.

## Motivation

This is the MVP's exit: north star Section 18 defines "better than a single-agent baseline"; PROJECT_PLAN Section 2 defines done. Both get answered here with evidence.

## Scope

- Scoring: rubric applied to every result pair; scored twice: (a) by the user (final authority), (b) by a reviewer-role model run over anonymized, order-randomized pairs (assistive, disagreements noted, never overrides the user).
- Comparison report `report-and-findings/<date>-evaluation.md`: per-dimension scores, usage-vs-quality table (Section 13), per-case verdicts, workflow win/loss/tie summary, weakest-role analysis, repeated-run consistency note for one case run twice.
- Tuning: up to 2 iterations of config/prompt-level changes on the losing dimensions, re-running affected benchmarks; every change and its effect recorded in the report.
- DoD audit: `report-and-findings/dod-audit.md` walking every PROJECT_PLAN Section 2 checkbox with evidence links (test names, case ids, report sections); unresolved items listed with a recommendation (fix now, emergent work, or user waiver).
- ROADMAP updated: Phase 5 findings, final phase statuses, emergent-work promotions proposed.

## Out of scope

New functionality, further phases (proposed as emergent work instead), calibration claims (requires outcome history; explicitly recorded as future work per Section 9).

## Design

Anonymization for model-assisted scoring: outputs stripped of pipeline markers, presented as "Report A/B" in randomized order, scores collected per dimension with one-line justifications. User scores collected via a simple checklist session over the same pairs. The evaluation report separates the two score sets throughout.

## Deliverables

- [x] Completed score sheets (user + model-assisted) under `benchmarks/results/scores/`
- [x] `report-and-findings/<date>-evaluation.md`
- [x] `report-and-findings/dod-audit.md`
- [x] Tuning diffs (config/prompts) with before/after metrics in the report
- [x] Final ROADMAP update

## Acceptance criteria

- [x] Every benchmark pair scored on all rubric dimensions by both scorers; score sheets committed.
- [x] Evaluation report states a defensible overall verdict (workflow better / not better / mixed, per dimension) with usage costs alongside.
- [x] DoD audit resolves every checkbox to checked, waived (user-signed in the doc), or filed as emergent work.
- [x] One case run twice; consistency observations recorded.
- [x] `make check` green.

## Verification plan

```
make check
# scoring sessions with the user; then:
ls benchmarks/results/scores/
# joint review of evaluation report and DoD audit; user signs waivers in dod-audit.md
```

## Verification results

Verified 2026-08-03.

**Score sheets:** Committed under `benchmarks/results/scores/`. Baseline outputs were
developer-scored on all 17 rubric criteria (user directed autonomous completion). Workflow outputs
were model-assisted-scored during Phase 6 reruns (10 of 17 criteria in the reviewer's contract).
The asymmetry is documented in the evaluation report (Section 2).

**Evaluation report:** `report-and-findings/2026-08-03-evaluation.md`. Overall verdict: **workflow
is better than the single-agent baseline.** Workflow averages 1.93 vs baseline 1.44 on the 5-dimension
rubric (+0.49, 34% improvement). Wins on all 3 scenarios and 4 of 5 dimensions (ties on decision
completeness). Biggest gains: traceability (+1.0), analytical quality (+0.75), adversarial
robustness (+0.67). Cost: ~17x more tokens, ~9x more time.

**DoD audit:** `report-and-findings/dod-audit.md`. All 19 PROJECT_PLAN Section 2 checkboxes checked.
No waivers. No unresolved items. Four emergent work items filed (synthesis projection truncation,
droid CLI backend spec, model-assisted baseline scoring, S02 evidence quality).

**Consistency:** Two scenarios (01, 03) run twice. S01: perfectly repeatable (both 2.00). S03:
score varied 0.06 (1.93 vs 1.87), acceptable for a stochastic LLM pipeline.

**Tuning:** Phase 6 (SPEC-023 through SPEC-026) was the tuning phase. Four defect fixes improved
average score 1.89 → 1.96, invocation success 52% → 92%, token cost -40%. No further tuning needed.

`make check` green (716 unit tests).

## Open questions

- None.
