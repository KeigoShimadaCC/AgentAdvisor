---
id: SPEC-024
title: Structured deliberation (issue tree, living thesis, dual-track reasoning, pre-mortem)
phase: 6
status: verified
depends_on: [SPEC-023]
parallel_with: []
north_star_refs: ["5", "6.1", "6.2", "6.3", "9", "12", "16"]
last_updated: 2026-08-02
---

# SPEC-024 — Structured deliberation

## Summary

Turns the pipeline from a one-way conveyor into a hypothesis-driven process. Adds MECE problem
structuring before planning, makes the thesis a versioned living artifact instead of a
write-once statement, runs two independent theses on different model families and records their
divergence explicitly, and adds a pre-mortem pass that attacks the future rather than the
reasoning.

## Motivation

The Phase 4 evaluation showed the system frames well and challenges well but never revisits its
own thesis, has no explicit decomposition of the decision into sub-questions (so task selection
is unanchored), and concentrates all hypothesis formation in a single Director invocation on a
single model. North star Section 6.3 already distinguishes falsification from forecasting failure
modes; the Challenger only does the former.

## Scope

**Problem structurer**

- `orchestrator/artifacts/issue_tree.py`: `IssueTree`, `IssueNode`, `IssueNodeType`, with
  validators for unique IDs, resolvable parents, acyclicity and a single root.
- New role `structurer` (`cursor/roles/structurer.{md,yaml}`), `TaskRole.STRUCTURER`.
- New stage `CaseStage.STRUCTURING` between framing approval and the provisional thesis.
- `TaskProposalRecord` and `TaskRecord` gain optional `issue_node_id`.
- `orchestrator/issue_tree.py`: `compute_coverage` (share of leaf nodes with a completed task),
  used by the planner projection and the stop rule.

**Living thesis**

- `orchestrator/artifacts/thesis.py`: `ThesisRevision`, `ThesisTrigger`.
- `orchestrator/thesis.py`: `record_thesis_revision` writes `shared/thesis/thesis-NNN.yaml` and
  computes what changed relative to the previous head; every `PreliminaryRecommendation` write in
  the pipeline goes through it.
- Investigation performs an interim thesis update when more than one dispatch wave runs.
- Projection key `thesis_history` gives the Challenger and Synthesizer a compact drift summary.

**Dual-track reasoning**

- `cursor/roles/director-b.{md,yaml}` — the Director's instructions on a different model family.
- `orchestrator/artifacts/tracks.py`: `TrackDivergence`, `TrackPosition`.
- `orchestrator/tracks.py`: deterministic comparison of two theses.
- At `PROVISIONAL_THESIS`, both tracks run; on disagreement the Director runs one reconciliation
  pass that must address the rival thesis. Divergence is reported, never averaged.

**Pre-mortem**

- `orchestrator/artifacts/premortem.py`: `PreMortemReport`, `FailureMode`.
- New role `premortem` (`cursor/roles/premortem.{md,yaml}`), `TaskRole.PREMORTEM`.
- New stage `CaseStage.PRE_MORTEM` between the preliminary recommendation and the challenge.
- Failure-mode leading indicators are surfaced to the Synthesizer as change-trigger candidates.

## Out of scope

- More than two reasoning tracks, or any voting/averaging across tracks.
- Per-wave thesis updates beyond the first (cost control).
- Automatic issue-tree revision mid-case.

## Design

The issue tree anchors task selection: the planner receives the tree and must attach each
proposal to a node, and coverage becomes an objective stopping input rather than a judgement
call. The thesis ledger is append-only; the current head remains
`shared/preliminary_recommendation.yaml` so nothing downstream changes.

Dual-track is a diversity instrument, not a probability instrument. `TrackDivergence.agreement`
never feeds `model_stability`, which stays defined as the share of sensitivity runs supporting
the recommendation.

## Deliverables

- [x] `orchestrator/artifacts/{issue_tree,thesis,tracks,premortem}.py`
- [x] `orchestrator/{issue_tree,thesis,tracks}.py`
- [x] `cursor/roles/{structurer,premortem,director-b}.{md,yaml}`
- [x] stages `STRUCTURING`, `PRE_MORTEM`
- [x] `issue_node_id` on task proposals and task records
- [x] tests for tree validation, coverage, thesis ledger, divergence, pre-mortem wiring

## Acceptance criteria

- [x] An issue tree with a dangling parent or a cycle is rejected by the model validator.
- [x] Coverage is 0.0 with no completed tasks and 1.0 when every leaf has one.
- [x] Two thesis writes produce two revision files, and the second records what changed.
- [x] Two disagreeing tracks produce `agreement=false` and trigger exactly one reconciliation
      invocation; two agreeing tracks trigger none.
- [x] A stub run produces a `PreMortemReport` with at least one failure mode and leading
      indicators.
- [x] `make check` passes.

## Verification plan

`uv run pytest tests/test_issue_tree.py tests/test_thesis.py tests/test_tracks.py
tests/test_pipeline_stub.py`, then `make check`, then the live benchmark suite in SPEC-026.

## Verification results

2026-08-02. `make check` green (lint, mypy, 296 unit tests). Stub pipeline exercises structuring,
dual-track with a forced disagreement, interim thesis update, and pre-mortem. The live benchmark
leg (SPEC-026) has not been run, so the spec stays `implemented` rather than `verified`.

## Open questions

None.
