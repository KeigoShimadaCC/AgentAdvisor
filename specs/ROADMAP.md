# Roadmap and spec status board

Single source of truth for phases, specs, statuses, and dependencies. Update this file whenever a spec changes state.

## Phases (proposed, to be confirmed as specs are written)

Phases are sequential; specs inside a phase may run in parallel where declared.

| Phase | Name | Purpose | Depends on |
|---|---|---|---|
| 0 | Foundations | Repo tooling, artifact schemas, case directory conventions, ID scheme | — |
| 1 | Orchestrator core | State machine, routing, budgets, schema validation, audit log, checkpointing | 0 |
| 2 | Cursor runtime | `AgentBackend` boundary, Cursor CLI adapter, role definitions (`cursor/roles/`), skills (`cursor/skills/`), workspace isolation | 0 (partially parallel with 1) |
| 3 | Decision workflow | End-to-end stages: intake, framing, planning, research, analysis, challenge, repair, synthesis, review | 1, 2 |
| 4 | Evaluation | Benchmark cases, single-agent baseline comparison, usage measurement | 3 |

## Spec status board

| Spec | Title | Phase | Status | Depends on | Parallel with |
|---|---|---|---|---|---|
| — | — | — | — | — | — |

Statuses: `draft` → `approved` → `in_progress` → `implemented` → `verified` (see `README.md`).
