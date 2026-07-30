---
id: SPEC-021
title: Benchmark cases and single-agent baseline
phase: 5
status: draft
depends_on: [SPEC-020]
parallel_with: []
north_star_refs: ["19", "18"]
last_updated: 2026-07-30
---

# SPEC-021 — Benchmark cases and single-agent baseline

## Summary

A small benchmark suite and the single strong-agent baseline runner, so the multi-agent workflow's value can be measured rather than assumed.

## Motivation

North star Section 19: every benchmark runs through a single-agent baseline and the structured workflow; the MVP claim (Section 18) is comparative.

## Scope

- `benchmarks/cases/`: ≥3 investment-style decision prompts with different characters (e.g. public-equity entry, staged startup investment, build-vs-buy with capital commitment), each a YAML file: prompt, fixed FramingApproval answers (so runs are unattended), budget profile, notes on what a good answer must address.
- `benchmarks/rubric.yaml`: Section 18 dimensions (decision completeness, evidence quality, analytical quality, adversarial robustness, relevance/efficiency, traceability) decomposed into 0–2 scored criteria each, with scoring instructions.
- Baseline runner `scripts/run_baseline.py`: one single-shot `cursor-agent` invocation (strongest Director-tier model, web access, same prompt + Section 16 output template) writing to `benchmarks/results/<case>/baseline/`.
- Workflow runner `scripts/run_benchmarks.py`: executes each benchmark through `advisor` unattended (pre-seeded approvals), copies final package + metrics to `benchmarks/results/<case>/workflow/`.
- Results layout committed: prompts, rubric, and per-run summary.json (metrics); full case artifacts stay local.

## Out of scope

Scoring and comparison (SPEC-022), repeated-run consistency measurement (emergent candidate if variance appears), non-investment domains.

## Design

Unattended operation is the main new mechanics: `advisor` gains nothing; runners pre-write approval artifacts between pipeline halts by polling status. Baseline gets the same output template so format differences do not contaminate quality comparison (only substance differs).

## Deliverables

- [ ] `benchmarks/cases/*.yaml` (≥3), `benchmarks/rubric.yaml`
- [ ] `scripts/run_baseline.py`, `scripts/run_benchmarks.py`
- [ ] `benchmarks/results/<case>/{baseline,workflow}/summary.json` for all cases
- [ ] `tests/test_benchmark_configs.py` (configs parse, rubric weights sum correctly)

## Acceptance criteria

- [ ] All benchmark configs validate; rubric covers all six Section 18 dimensions.
- [ ] Baseline and workflow runs complete unattended for all ≥3 cases within their budget profiles.
- [ ] Every results folder contains the final package and summary.json with usage metrics.
- [ ] `make check` green.

## Verification plan

```
make check
uv run pytest tests/test_benchmark_configs.py -q
uv run python scripts/run_baseline.py --all
uv run python scripts/run_benchmarks.py --all
ls benchmarks/results/*/{baseline,workflow}/summary.json
```

## Verification results

—

## Open questions

- Benchmark decision prompts finalized with the user at approval.
