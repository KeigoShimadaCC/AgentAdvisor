---
id: SPEC-018
title: Stage wiring (end-to-end pipeline)
phase: 4
status: draft
depends_on: [SPEC-007, SPEC-008, SPEC-009, SPEC-010, SPEC-011, SPEC-012, SPEC-013, SPEC-014, SPEC-015, SPEC-016, SPEC-017]
parallel_with: []
north_star_refs: ["8", "14", "15"]
last_updated: 2026-07-30
---

# SPEC-018 — Stage wiring (end-to-end pipeline)

## Summary

Connect everything: real stage handlers for the SPEC-007 state machine that drive roles, task graph, budgets, auditor checkpoints, approval gates, the bounded repair loop, and the stop decision, proven end to end on a toy decision case with cheap models.

## Motivation

North star Section 8 defines the workflow; Sections 14/15 define where the human approves. This spec turns eleven verified components into one pipeline.

## Scope

`orchestrator/stages.py` handlers, one per stage:

- INTAKE → intake role; FRAMING → director-framing; halt at AWAITING_FRAMING_APPROVAL until a `FramingApproval` artifact exists (written via CLI in SPEC-019; tests write it directly).
- PROVISIONAL_THESIS → director (provisional-thesis mode) immediately after framing approval (north star Stage 3).
- PLANNING → planner + acceptance filter + task-graph population; auditor checkpoint.
- INVESTIGATION → task-graph dispatch (researchers/analyst) with budget gating and normalization; auditor checkpoint per wave.
- PRELIMINARY_RECOMMENDATION → director (preliminary mode).
- CHALLENGE → challenger; auditor checkpoint (objection triage inputs).
- STOP_DECISION → StopEvaluator over auditor stop-inputs, objections, stability (SPEC-013 function), budget; routes to REPAIR (≤2: planner repair mode + targeted dispatch + director update, then CHALLENGE in final-falsification mode before the next stop decision) or SYNTHESIS.
- SYNTHESIS → synthesizer; REVIEW → reviewer gate (one synthesis retry on fail); render; halt at AWAITING_FINAL_APPROVAL; DONE.
- Auditor findings reactions (deterministic): duplicate task → cancel; off-topic task → cancel + audit; mandate violation → re-run producer through retry ladder.
- Toy case fixture: two-alternative purchase-timing decision, tiny budget (≤15 invocations), all roles pinned to cheap models via test role-config overrides.

## Out of scope

CLI commands (SPEC-019), real-scale case (SPEC-020), any new role behavior.

## Design

Handlers contain orchestration only; every substantive judgment stays inside role invocations. Two E2E tests: (1) full StubBackend run with scripted artifacts asserting the exact stage sequence, artifact set, audit-log completeness, and repair-loop bound; (2) `@pytest.mark.live_slow` toy-case run on cheap models asserting completion within budget and a rendered final_recommendation.md.

## Deliverables

- [ ] `orchestrator/stages.py` (+ pipeline entry `orchestrator/pipeline.py`)
- [ ] Toy case fixture + cheap-model roles override
- [ ] `tests/test_pipeline_stub.py`, `tests/test_pipeline_live.py` (`live_slow` marker)

## Acceptance criteria

- [ ] Stub E2E: stage sequence matches the Section 8 order including PROVISIONAL_THESIS, both approval gates halt and resume, each repair cycle routes REPAIR → CHALLENGE (final falsification) → STOP_DECISION with at most 2 cycles, every invocation and transition present in audit.jsonl.
- [ ] Budget exhaustion path (stub): tiny budget forces a stop with DisclosureRecord surfaced in the rendered output.
- [ ] Live toy case: completes ≤15 invocations, produces valid FinalRecommendation + final_recommendation.md, total usage recorded in audit log.
- [ ] Case resume works mid-INVESTIGATION on the stub run (kill and continue).
- [ ] `make check` green.

## Verification plan

```
make check
uv run pytest tests/test_pipeline_stub.py -q
uv run pytest -m live_slow tests/test_pipeline_live.py -q   # ~10-15 cheap invocations
```

## Verification results

—

## Open questions

- None.
