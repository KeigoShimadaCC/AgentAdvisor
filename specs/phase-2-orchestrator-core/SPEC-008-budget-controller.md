---
id: SPEC-008
title: Budget controller and stop rules
phase: 2
status: verified
depends_on: [SPEC-007]
parallel_with: [SPEC-009]
north_star_refs: ["13", "8"]
last_updated: 2026-07-31
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

- [x] `orchestrator/budget.py`
- [x] `BudgetConfig` defaults documented in `schemas/` export (via SPEC-003 mechanism)
- [x] `tests/test_budget.py`

## Acceptance criteria

- [x] Exceeding any cap makes `try_consume` return false; 100 threaded consumers never overshoot a cap.
- [x] High-tier calls counted only for models mapped to the high tier.
- [x] StopEvaluator: table-driven tests cover all Stage 9 stop reasons and the continue case.
- [x] Budget-exhaustion stop emits a `DisclosureRecord` with the exhausted dimensions.
- [x] `make check` green.

## Verification plan

```
make check
uv run pytest tests/test_budget.py -q
```

## Verification results

**2026-07-31 — PASS.** `orchestrator/budget.py` and `tests/test_budget.py` (17 tests) are complete with `BudgetConfig` defaults aligned to north star Section 13: 40 agent invocations, 3 concurrent workers, 2 repair cycles, 15 research tasks, 6 high-tier calls, and 7200 seconds wall clock. `try_consume` is implemented as lock-guarded check-and-increment that returns `False` on refusal, and a 100-thread test verifies the counter reaches the cap exactly without overshoot.

Stop-rule semantics are implemented as a pure evaluator with injected clock and full table-driven coverage of all six Stage 9 stop reasons plus continue, so deadline behavior is tested deterministically without sleep-based flake. High-tier accounting increments only for models mapped to the high tier through an injected tier map, and budget or deadline exhaustion emits a `DisclosureRecord` that names exhausted dimensions so Synthesizer output explicitly discloses a budget-driven stop.

One specification amendment has been incorporated and validated: because Stage 9 distinguishes deadline from depth limit, `StopEvaluatorInputs` now includes an explicit `depth_limit_reached` flag in addition to deadline state. This keeps the stop reason precise instead of collapsing two different termination causes.

## Open questions

- None.
