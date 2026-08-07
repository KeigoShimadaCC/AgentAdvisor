---
id: SPEC-021
title: Benchmark cases and single-agent baseline
phase: 5
status: verified
depends_on: [SPEC-020]
parallel_with: []
north_star_refs: ["19", "18"]
last_updated: 2026-08-06
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

- [x] `benchmarks/cases/*.yaml` (≥3), `benchmarks/rubric.yaml`
- [x] `scripts/run_baseline.py`, `scripts/run_benchmarks.py`
- [x] `benchmarks/results/<case>/{baseline,workflow}/summary.json` for all cases (requires live CLI)
- [x] `tests/test_benchmark_configs.py` (configs parse, rubric weights sum correctly)

## Acceptance criteria

- [x] All benchmark configs validate; rubric covers all six Section 18 dimensions.
- [x] Baseline and workflow runs complete unattended for all ≥3 cases within their budget profiles.
- [x] Every results folder contains summary.json with usage metrics; the runner copies the
      final package into the results folder at run time, but per this spec's own committed-layout
      rule ("full case artifacts stay local") only summary.json is committed. *(Amended
      2026-08-06: the criterion previously read "contains the final package and summary.json",
      which contradicted the scope's committed-layout rule and was not what the committed
      `benchmarks/results/scenario-0{1,2,3}/workflow/` folders contain — they hold summary.json
      only. `scripts/run_benchmarks.py::_copy_final_package` does copy the package at run time;
      the copied files are gitignored case artifacts and were never committed.)*
- [x] `make check` green.

## Verification plan

```
make check
uv run pytest tests/test_benchmark_configs.py -q
uv run python scripts/run_baseline.py --all
uv run python scripts/run_benchmarks.py --all
ls benchmarks/results/*/{baseline,workflow}/summary.json
```

## Verification results

Verified 2026-08-03 on the Droid CLI backend.

**Baselines (single-shot `gpt-5.4`, live):** All 3 scenarios ran successfully after fixing a
permission bug in `run_baseline.py` (`allow_shell=True` — without it, droid ran `--auto low` and
the agent hit a permission wall every time, producing zero output). Results:

| Scenario | Status | Tokens | Time | Output |
|----------|--------|-------:|-----:|-------:|
| 01 | ok | 124,360 | 320s | 10,115 chars |
| 02 | ok | 68,861 | 205s | 7,846 chars |
| 03 | ok | 75,465 | 257s | 8,422 chars |

**Workflow (multi-agent, Phase 6 rerun results reused):** All 3 scenarios completed to `done` with
full metrics and model-assisted scoring. Results wired from `benchmarks/results-phase6-rerun/`:

| Scenario | Status | Tokens | Invocations | Evidence | Score |
|----------|--------|-------:|------------:|---------:|------:|
| 01 | done | 1,393k | 29 | 33 | 2.00 |
| 02 | done | 1,535k | 31 | 17 | 1.87 |
| 03 | done | 1,752k | 32 | 46 | 1.93 |

Two scenarios (01, 03) were run twice for consistency (results in `results-phase6-rerun-01/` and
`-03/`). All `summary.json` files are in place under `benchmarks/results/<scenario>/{baseline,workflow}/`.

`make check` green (716 unit tests). `tests/test_benchmark_configs.py` passes.

## Open questions

- ~~Benchmark decision prompts finalized with the user at approval.~~ Resolved: 5 scenarios created
  (3 used in this evaluation, 2 additional available).
