---
id: SPEC-013
title: Quantitative Analyst role
phase: 3
status: draft
depends_on: [SPEC-006]
parallel_with: [SPEC-010, SPEC-011, SPEC-012, SPEC-014, SPEC-015, SPEC-016, SPEC-017]
north_star_refs: ["6.6", "5.5", "8"]
last_updated: 2026-07-30
---

# SPEC-013 — Quantitative Analyst role

## Summary

The Analyst writes and executes real analysis code (scenario model, expected values, sensitivity, break-even) inside the case's `analysis/` directory; the orchestrator re-executes the code to prove the reported numbers are reproducible.

## Motivation

North star 6.6 and the Section 8 decision model: no unsupported arithmetic in prose; DoD B requires reported numbers to match re-executed code.

## Scope

- `cursor/roles/analyst.md`: build the scenario set (bull/base/bear/failure plus decision-specific factors), state every assumption as an `AssumptionRecord` reference or new proposal, write a standalone Python script `analysis/<task-id>/model.py` (stdlib + numpy if present) that prints a deterministic `results.yaml` (scenarios with probability ranges, per-alternative expected values, sensitivity table, break-even thresholds), seed-fixed where stochastic; ranges over false precision (Section 5.5/9); scenario probabilities expressed as `ProbabilityEstimate`s built base-rate-first (reference class, then documented adjustments citing evidence IDs).
- `AnalysisResult` artifact model binding `results.yaml` + declared assumptions + script path.
- Stability function `orchestrator/stability.py`: pure computation of model stability (share of sensitivity runs in which a given preferred alternative remains best) from an `AnalysisResult`; consumed by the stop decision (SPEC-008) and the final package (SPEC-017).
- Reproducibility gate in `orchestrator/reproduce.py`: re-run `model.py` in a fresh subprocess (timeout, cwd = analysis dir), diff regenerated `results.yaml` against the committed one (exact for fixed-seed, tolerance 1e-9 for floats).
- Analyst workspace exception: projection mounts `analysis/<task-id>/` as writable working area in addition to `outputs/`.
- `cursor/roles/analyst.yaml` (coding-strong model: gpt-5.3-codex per research report; Shell-enabled permission profile; projection: decision spec, relevant evidence, assumption registry slice).

## Out of scope

Financial-domain model templates (emergent work if the generic scenario model proves insufficient), charting, notebook support.

## Design

The reproducibility gate is the acceptance boundary: an analysis whose rerun diverges is treated as invalid output and enters the SPEC-006 retry ladder with the diff as feedback. Scripts must not access the network (instruction + audit of the run duration/output; hard sandboxing tracked as emergent work).

## Deliverables

- [ ] `cursor/roles/analyst.md`
- [ ] `AnalysisResult` model + schema export
- [ ] `orchestrator/reproduce.py`
- [ ] `orchestrator/stability.py`
- [ ] `cursor/roles/analyst.yaml`
- [ ] `tests/test_reproduce.py` (fixture script: pass, diverge, timeout), `tests/test_stability.py`, `tests/test_role_analyst.py`; live mini-run test

## Acceptance criteria

- [ ] Reproduce gate: fixture pass/diverge/timeout behave as specified; diverging analysis is rejected with a diff.
- [ ] Fixture replay produces a schema-valid AnalysisResult whose EVs match the fixture script rerun.
- [ ] Live mini-run on a toy two-alternative decision yields a valid, reproducible AnalysisResult in ≤2 attempts.
- [ ] Every number in `results.yaml` originates from the script (spot-checked by the fixture design: script output is the artifact).
- [ ] `make check` green.

## Verification plan

```
make check
uv run pytest tests/test_reproduce.py tests/test_role_analyst.py -q
uv run pytest -m live -k analyst -q
```

## Verification results

—

## Open questions

- numpy as a standing dependency or stdlib-only for v1: propose stdlib-only until a case needs Monte Carlo; confirm at approval.
