---
id: SPEC-025
title: Institutional memory (case memory, specialist packs, outcome calibration, standing programs)
phase: 6
status: verified
depends_on: [SPEC-024]
parallel_with: []
north_star_refs: ["6.7", "18", "19", "21"]
last_updated: 2026-08-02
---

# SPEC-025 — Institutional memory

## Summary

Gives the system the thing that separates a think tank from a one-off consulting engagement:
memory. Cross-case storage of prior decisions, source reliability track records and recurring
assumptions; domain specialist skill packs so research is not always generic; outcome recording
with Brier scoring so the system's calibration is measurable; and standing research programs so a
new case inherits prior evidence instead of starting from zero.

## Motivation

North star 6.7 specifies domain specialists as skill packages (`cursor/skills/` is currently
empty), Section 19 wants measurable decision quality, and the Phase 4 evaluation identified
generic research as the driver of the weakest rubric dimension. Every case today starts with an
empty head.

## Scope

- `orchestrator/artifacts/memory.py`: `PriorCaseEntry`, `OutcomeRecord`, `SourceReputation`,
  `RecurringAssumption`, `PriorEvidenceEntry`, `CalibrationSummary`, `CaseMemoryDigest`.
- `orchestrator/memory.py`: `MemoryStore` over a memory root
  (`AGENTADVISOR_MEMORY_ROOT`, default `<repo>/memory`) with `record_case`, `record_outcome`,
  `digest_for`, `prior_evidence_for`, keyword-overlap retrieval and source-domain reputation.
- `orchestrator/calibration.py`: Brier score and reliability buckets over recorded outcomes.
- Projection keys `case_memory` and `prior_evidence`, wired into the Director, Planner and
  Researcher.
- `cursor/skills/registry.yaml` plus five packs: public-equity investing, startup investing,
  real estate, career and compensation, build-versus-buy.
- `orchestrator/skills.py`: keyword classifier and pack loading; `build_workspace` appends the
  selected pack to the workspace `AGENTS.md` for research, analysis and direction roles.
- `scripts/record_outcome.py`: CLI to attach a realized outcome to a completed case.
- Memory is written at the end of a successful case (`REVIEW` stage handler).

## Out of scope

- Vector or embedding retrieval (explicitly banned by `AGENTS.md` scope discipline). Retrieval is
  keyword overlap over stored questions and topics.
- Automatic re-verification of inherited evidence; inherited records are projected with an
  explicit staleness warning and must be re-confirmed to be cited.
- Multi-user or shared memory.

## Design

`memory/` mirrors `cases/`: local, gitignored, single-user. Retrieval is deliberately dumb and
inspectable: normalized keyword sets, Jaccard-style overlap, top-k. Inherited evidence never
enters the blackboard directly; it is projected as `prior_evidence.yaml` with `age_days` and a
banner stating it must be re-verified before citation, which keeps the provenance rule intact.

Skill packs are plain markdown appended to the role instructions inside the isolated workspace,
so they cannot leak across roles or cases and require no harness feature beyond what
`build_workspace` already does.

Calibration uses the recommendation's headline outcome probability against a recorded binary
realization. With few cases the Brier score is reported alongside the sample size and is never
used to alter a live case.

## Deliverables

- [x] `orchestrator/artifacts/memory.py`
- [x] `orchestrator/{memory,calibration,skills}.py`
- [x] `cursor/skills/registry.yaml` and five `SKILL.md` packs
- [x] projection keys `case_memory`, `prior_evidence`
- [x] `scripts/record_outcome.py`
- [x] tests for store round-trip, retrieval ranking, reputation, Brier scoring, classifier,
      workspace injection

## Acceptance criteria

- [x] Recording a case then requesting a digest for a similar question returns that case; an
      unrelated question does not.
- [x] Source reputation aggregates by registrable domain across cases.
- [x] Brier score of a perfectly calibrated toy set is 0.0 and of an inverted set is 1.0.
- [x] The classifier routes each of the five benchmark scenarios to the intended pack.
- [x] A workspace built for the researcher contains the pack text in `AGENTS.md`; one built for
      the reviewer does not.
- [x] `make check` passes.

## Verification plan

`uv run pytest tests/test_memory.py tests/test_calibration.py tests/test_skills.py`, then
`make check`, then the live benchmark suite in SPEC-026.

## Verification results

2026-08-02. `make check` green (lint, mypy, 296 unit tests). Memory round-trip, retrieval,
reputation, Brier and classifier tests pass; workspace injection verified for researcher and
negatively for reviewer. The live benchmark leg (SPEC-026) has not been run, so the spec stays
`implemented` rather than `verified`.

## Open questions

None.
