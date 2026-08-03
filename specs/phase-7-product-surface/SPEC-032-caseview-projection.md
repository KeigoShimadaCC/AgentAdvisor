---
id: SPEC-032
title: CaseView projection, committed fixture case, and generated frontend types
phase: 7
status: verified
depends_on: [SPEC-023, SPEC-024, SPEC-025, SPEC-030, SPEC-031]
parallel_with: []
north_star_refs: ["9", "15", "17"]
last_updated: 2026-08-03
---

# SPEC-032 — CaseView projection, committed fixture case, and generated frontend types

## Summary

The frontend's read model: one versioned Pydantic document, `CaseView`, assembled server-side
from a case directory — phases, brief sections with per-section status, the four uncertainty
measures as tagged unions that structurally distinguish *assessed* from *not assessed*, room
data, integrity, history, and audit-derived effort. Plus the two assets everything downstream
builds on: a committed, sanitized full-case fixture (today `cases/` is gitignored and empty in a
fresh checkout), and TypeScript types generated from the exported JSON Schemas so frontend types
can never drift from the artifacts.

## Motivation

The discovery report (§17.3) isolates the UI from orchestrator internals behind a projection:
stage enums, file layout, and coercion quirks must not leak into client code, and sentinel
detection must happen once, server-side (north star Section 9 — a placeholder presented as a
measurement is the collapse defect). PROJECT_PLAN's schema-drift risk is answered by generating
types from the existing `schema_export` pipeline.

## Scope

- `orchestrator/service/` package (new), `orchestrator/service/caseview.py`:
  - `build_case_view(case) -> CaseView`.
  - Phase mapping: the 19 `CaseStage` values → 6 presentation phases + `needs_you`
    (`scope_checkpoint | delivery_checkpoint | interrupted | none`) + terminal flags.
  - `BriefSection[]` in renderer order; each `{key, status: pending|partial|final|not_assessed,
    blocks[]}` where blocks carry the renderer's six provenance labels and citation ids.
  - `Measure` tagged unions: `AssessedConfidence{value, basis} | NotAssessed{reason}`,
    `AssessedStability{runs_supporting, runs_total, share} | NotAssessed{reason}`, probability
    entries preserving point-XOR-interval and the adjustment trail. Sentinel predicates imported
    from `orchestrator/artifacts/sentinels.py` (SPEC-031).
  - Rooms: sources (records joined with critique scores, tiers, flags, cluster shares),
    assumptions (with for/against id lists resolved to titles), options
    (ranked `AlternativeAssessment` + analysis EV table when present), challenges (objections
    status-sorted, premortem, track divergence verbatim-structured), plan (issue tree outline +
    coverage fractions).
  - Integrity: gate summaries (translated check ids per SPEC-033's lexicon keys),
    `review_accepted` (SPEC-030), review defects/verdicts, disclosure record.
  - History: thesis revisions, framing/final approval records.
  - Effort: counters derived from `audit.jsonl` (invocation counts, token sums, per-stage
    durations) plus SPEC-029's persisted counters and caps.
- `orchestrator/artifacts/schema_export.py`: export `CaseView` and nested models
  (`schemas/case_view.schema.json` etc.) via the existing `MODEL_EXPORTS` mechanism.
- **Fixture case** `tests/fixtures/cases/case-001-fixture-001/` — a trimmed, sanitized copy of the
  completed reference case (full directory shape: `state.yaml`, `audit.jsonl`, `shared/**`,
  `analysis/**`, `outputs/**`; agent workspace archives reduced to one exemplar). It must
  include the interesting truths: a failing review with `review_accepted: false`, the stability
  sentinel, open objections, a thesis flip, and a `no_evidence_found` honest-empty. A second
  minimal fixture `case-002-fixture-002-parked/` parked at `awaiting_framing_approval` with
  clarification questions.
- Type generation: `frontend/package.json` script `generate:types` (json-schema-to-typescript)
  emitting `frontend/src/generated/*.ts` from `schemas/*.schema.json`; `make frontend-types`
  target; generated files committed; CI-style check that regeneration is clean.
- `tests/test_caseview.py` — projector against both fixtures.

## Out of scope

- HTTP serving of the view (SPEC-033).
- Any write path; `CaseView` is strictly derived.
- Narration text itself (the event lexicon is SPEC-033; this spec only stabilizes ids/keys).
- Cross-case aggregation (memory digests pass through as-is with their banners).

## Design

`CaseView` is versioned (`view_version: 1`) and additive-only within a version. It is computed on
demand from disk (no cache invalidation problem at single-user scale; the projector is pure and
fast — the audit scan dominates and is bounded by file size). Everything presentation-shaped but
engine-owned (renderer section order, provenance labels, sentinel predicates) is imported from
the engine so export and UI cannot diverge. The fixture is the contract's test bed and doubles
as SPEC-033 replay input and SPEC-037 dummy data — one asset, three consumers.

## Deliverables

- [x] `orchestrator/service/caseview.py` + models
- [x] schema export entries + regenerated `schemas/`
- [x] `tests/fixtures/cases/case-001-fixture-001/`, `case-002-fixture-002-parked/`
- [x] `frontend/src/generated/` types + `make frontend-types`
- [x] `tests/test_caseview.py`

## Acceptance criteria

- [x] `build_case_view(case-001-fixture-001)` returns a validating `CaseView` where: model stability
      is the `NotAssessed` variant (reason names the single-run sentinel); integrity carries
      `review_accepted == false` with the review defects; challenges list every open objection
      first; effort invocation count equals the hand-counted `role_invocation_attempt` lines.
- [x] `build_case_view(case-002-fixture-002-parked)` yields `needs_you == scope_checkpoint` and the
      clarification questions with their materiality reasons.
- [x] Probability entries never carry both a point and an interval (property test over fixtures).
- [x] `make schemas` then `make frontend-types` is idempotent (`git diff --exit-code` on
      `schemas/` and `frontend/src/generated/`).
- [x] `npx tsc --noEmit` passes over the generated types.
- [x] `make check` passes.

## Verification plan

```
uv run pytest tests/test_caseview.py -q
make schemas && make frontend-types && git diff --exit-code schemas/ frontend/src/generated/
cd frontend && npx tsc --noEmit
make check
```

## Verification results

**2026-08-03 — verification plan executed.** `make check` green: ruff, ruff format, mypy on 65 source files, 639 unit tests (17 live deselected).

Spec's own plan run in full — 21 tests: `tests/test_caseview.py`: all pass. `make schemas && make frontend-types` regenerated 60 schemas with 0 changed and left `schemas/` and `frontend/src/generated/` byte-identical; `npx tsc --noEmit` exited 0.

## Open questions

- None.
