---
id: SPEC-022
title: Comparative evaluation and DoD audit
phase: 5
status: draft
depends_on: [SPEC-021]
parallel_with: []
north_star_refs: ["18", "19", "13"]
last_updated: 2026-07-30
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

- [ ] Completed score sheets (user + model-assisted) under `benchmarks/results/scores/`
- [ ] `report-and-findings/<date>-evaluation.md`
- [ ] `report-and-findings/dod-audit.md`
- [ ] Tuning diffs (config/prompts) with before/after metrics in the report
- [ ] Final ROADMAP update

## Acceptance criteria

- [ ] Every benchmark pair scored on all rubric dimensions by both scorers; score sheets committed.
- [ ] Evaluation report states a defensible overall verdict (workflow better / not better / mixed, per dimension) with usage costs alongside.
- [ ] DoD audit resolves every checkbox to checked, waived (user-signed in the doc), or filed as emergent work.
- [ ] One case run twice; consistency observations recorded.
- [ ] `make check` green.

## Verification plan

```
make check
# scoring sessions with the user; then:
ls benchmarks/results/scores/
# joint review of evaluation report and DoD audit; user signs waivers in dod-audit.md
```

## Verification results

—

## Open questions

- None.
