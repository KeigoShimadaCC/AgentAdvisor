---
id: SPEC-003
title: Artifact schemas v1
phase: 0
status: draft
depends_on: [SPEC-001]
parallel_with: []
north_star_refs: ["7", "7.1", "10"]
last_updated: 2026-07-30
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
- `PreliminaryRecommendation` and `FinalRecommendation` (Section 16 structure, distinct uncertainty measures per Section 9)
- `AuditEvent` (ts, actor, event_type, payload, model, cli_version, usage, duration_ms)
- `ProbabilityEstimate` sub-model used wherever a probability appears: point value or interval, method (`reference_class` | `scenario_model` | `structured_subjective`), reference class, base rate, and documented adjustments each citing evidence IDs (the Section 9 base-rate-first audit trail)
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

- [ ] `orchestrator/artifacts/` package (one module per artifact family)
- [ ] `schemas/*.schema.json` (generated, committed)
- [ ] `tests/test_artifacts.py`, `tests/fixtures/artifacts/`

## Acceptance criteria

- [ ] Every model round-trips YAML → model → YAML byte-identically for all valid fixtures.
- [ ] Every invalid fixture raises a validation error naming the offending field.
- [ ] `make schemas` is idempotent; the sync test fails if `schemas/` drifts from the models.
- [ ] `make check` green.

## Verification plan

```
make check
make schemas && git diff --exit-code schemas/
uv run pytest tests/test_artifacts.py -q
```

## Verification results

—

## Open questions

- Reliability/directness as enum (high/medium/low) or 0–1 float: propose enum for v1 (avoids false precision per north star 5.5); confirm at approval.
