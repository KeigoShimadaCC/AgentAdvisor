---
id: SPEC-008
title: Budget controller and stop rules
phase: 2
status: draft
depends_on: [SPEC-007]
parallel_with: [SPEC-009]
north_star_refs: ["13", "8"]
last_updated: 2026-07-30
---

# SPEC-008 — Budget controller and stop rules

## Summary

Hard per-case caps and the deterministic stop decision, including the disclosure record when stopping for budget rather than evidence completeness.

## Motivation

North star 13 (budgets are mandatory, enforced by code, not agent self-restraint) and Stage 9 (stop rules; budget stops must be disclosed in the final output).

## Scope

`orchestrator/budget.py`:

- `BudgetConfig` model (defaults from north star 13): max_agent_invocations 40, max_concurrent_workers 3, max_repair_cycles 2, max_research_tasks 15, max_high_tier_calls 6, max_wall_clock_s 7200. Loaded per case, overridable at case creation.
- `BudgetLedger`: counters persisted in case state; `try_consume(kind, model) -> bool` (thread-safe); high-tier detection from a configured model-tier map in the per-role configs (`cursor/roles/<role>.yaml`).
- `StopEvaluator.evaluate(inputs) -> StopDecision`: pure function over typed inputs (open critical evidence gaps, unresolved material objections, recommendation-stability flag, remaining budget, deadline) returning `continue` or `stop` with machine-readable reasons (Stage 9 list). The stability flag is computed deterministically by SPEC-013's stability function from Analyst sensitivity results, never model-asserted.
- `DisclosureRecord` artifact: emitted whenever stop reason includes budget/deadline exhaustion; consumed by the Synthesizer stage so the limitation appears in the final output.

## Out of scope

Estimating probability-of-changing-the-decision (Planner's job; arrives as an input field), monetary cost tracking (usage tokens are recorded by SPEC-006 audits; interpretation is Phase 4/5 work).

## Design

Ledger consumption is check-and-increment under a lock; refusal returns false and the caller (state machine / task dispatcher) reacts, keeping policy out of the ledger. Wall clock via injected clock for testability. StopEvaluator has no I/O and no model calls; every returned reason maps 1:1 to a Stage 9 bullet.

## Deliverables

- [ ] `orchestrator/budget.py`
- [ ] `BudgetConfig` defaults documented in `schemas/` export (via SPEC-003 mechanism)
- [ ] `tests/test_budget.py`

## Acceptance criteria

- [ ] Exceeding any cap makes `try_consume` return false; 100 threaded consumers never overshoot a cap.
- [ ] High-tier calls counted only for models mapped to the high tier.
- [ ] StopEvaluator: table-driven tests cover all Stage 9 stop reasons and the continue case.
- [ ] Budget-exhaustion stop emits a `DisclosureRecord` with the exhausted dimensions.
- [ ] `make check` green.

## Verification plan

```
make check
uv run pytest tests/test_budget.py -q
```

## Verification results

—

## Open questions

- None.
