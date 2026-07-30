---
id: SPEC-003
title: Artifact schemas v1
phase: 0
status: verified
depends_on: [SPEC-001]
parallel_with: []
north_star_refs: ["7", "7.1", "9", "10"]
last_updated: 2026-07-31
---

# SPEC-003 — Artifact schemas v1

## Summary

Typed models for every blackboard artifact, with YAML persistence and exported JSON Schemas. These are the contracts all agents and orchestrator code speak.

## Motivation

North star 5.2/7: agents communicate through typed artifacts, and traceability depends on stable IDs linking evidence, assumptions, tasks, and objections.

## Scope

Pydantic v2 models in the `orchestrator/artifacts/` package, one module per artifact family, so later specs add files instead of editing a shared module:

- `DecisionSpec` (question, owner, deadline, alternatives, objectives, constraints, risk_tolerance, reversibility, depth)
- `EvidenceRecord` (claim, source fields, publication/retrieval dates, excerpt, reliability, directness, `independence_group`, limitations, retrieved_by)
- `AssumptionRecord` (claim, type, estimate, confidence, materiality, evidence_for/against, status)
- `ObjectionRecord` (target, claim, materiality, reasoning, resolution_status, commissioned_tasks)
- `TaskRecord` (role, question, why_it_matters, expected_information_gain, materiality, inputs, required_output, completion_criteria, status, priority fields)
- `PreliminaryRecommendation` and `FinalRecommendation` (Section 16 structure, distinct uncertainty measures per Section 9). The four measures use deliberately different types so they cannot be conflated: `outcome_probabilities` is a mapping to `ProbabilityEstimate`; `evidence_confidence` and `recommendation_confidence` are `ConfidenceAssessment` (0–1 value plus a required `basis` string, matching the Section 9 example numbers); `model_stability` is a `ModelStability` record (`share_of_sensitivity_runs_supporting_recommendation`, `runs_total`, `runs_supporting`) that only deterministic code may produce.
- `AuditEvent` (ts, actor, event_type, payload, model, cli_version, usage, duration_ms)
- `ProbabilityEstimate` sub-model used wherever a probability appears: point value or interval, method (`reference_class` | `scenario_model` | `structured_subjective`), reference class, base rate, and documented adjustments each citing evidence IDs (the Section 9 base-rate-first audit trail). `reference_class`/`base_rate` are required when `method == reference_class` and optional otherwise, so pre-calibration `structured_subjective` estimates are not forced to invent a prior. An empty `adjustments` list is legal and means the estimate equals the base rate.
- Shared enums (materiality, confidence, statuses) and validated ID types: `E-\d+`, `A-\d+`, `T-\d+`, `O-\d+`, `case-\d+[-a-z0-9-]*`

Plus:

- YAML load/dump helpers (`yaml.safe_load`, deterministic key order on dump)
- `make schemas`: exports JSON Schema for every model to `schemas/<name>.schema.json` (committed)
- Fixtures: `tests/fixtures/artifacts/` with valid and invalid examples per model

## Out of scope

Storage layout (SPEC-004), context projection (SPEC-006), schema migration tooling (regenerate fixtures on version bump instead).

## Design

Model modules only, no I/O logic beyond YAML helpers. Cross-references are ID strings, not object references, so artifacts stay independently serializable. `schema_version: int = 1` field on every model. A sync test re-exports schemas to a temp dir and diffs against `schemas/` so committed schemas can never drift.

## Deliverables

- [x] `orchestrator/artifacts/` package (one module per artifact family)
- [x] `schemas/*.schema.json` (generated, committed)
- [x] `tests/test_artifacts.py`, `tests/fixtures/artifacts/`

## Acceptance criteria

- [x] Every model round-trips YAML → model → YAML byte-identically for all valid fixtures.
- [x] Every invalid fixture raises a validation error naming the offending field.
- [x] `make schemas` is idempotent; the sync test fails if `schemas/` drifts from the models.
- [x] `make check` green.

## Verification plan

```
make check
make schemas && git diff --exit-code schemas/
uv run pytest tests/test_artifacts.py -q
```

## Verification results

**2026-07-31 — PASS.** 16 modules under `orchestrator/artifacts/`, 16 exported schemas, 23 tests in `tests/test_artifacts.py`.

- `make check` → exit 0 (ruff clean, mypy "no issues found in 16 source files", pytest `31 passed, 1 deselected` across the whole suite).
- `make schemas && git diff --exit-code schemas/` → exit 0, export is idempotent.
- Drift detection was verified adversarially, not just assumed: tampering with `schemas/evidence_record.schema.json` (changing its `title`) made `test_schema_sync` fail with a diff; restoring the file made it pass again.

Three defects were found by review against north star Section 9 after the first implementation pass and fixed before sign-off:

1. `model_stability` had been typed as a `Level` enum. It is a deterministically computed ratio, so it is now a `ModelStability` record (`share_of_sensitivity_runs_supporting_recommendation`, `runs_total`, `runs_supporting`) with a validator asserting the share equals `runs_supporting / runs_total` within 1e-6. An inconsistent stability record cannot be persisted, and a model cannot assert one that the sensitivity runs do not support.
2. `evidence_confidence` and `recommendation_confidence` had been `Level` enums. Section 9 states them numerically, so both are now `ConfidenceAssessment` (0–1 `value` plus a required `basis`). `Level` remains in use for `reliability`, `directness`, and `materiality`, which are subjective per-item judgements.
3. `ProbabilityEstimate` required `reference_class`, `base_rate`, and at least one adjustment on every estimate, which forced fabrication for pre-calibration estimates. Those fields are now conditionally required only when `method == reference_class`, and an empty `adjustments` list is valid and means the estimate equals the base rate.

## Open questions

- ~~Reliability/directness as enum (high/medium/low) or 0–1 float~~ **Resolved 2026-07-31: enum.** Reliability, directness, materiality, and per-item confidence are `Level` (high/medium/low), because they are subjective judgements and north star 5.5 forbids false precision. The recommendation-level measures are the deliberate exception: Section 9's reporting example states them numerically (`recommendation_confidence: 0.74`, `evidence_confidence: 0.61`, `share_of_sensitivity_runs_supporting_recommendation: 0.76`), so those are floats carrying an explicit basis, and model stability is computed rather than asserted.
