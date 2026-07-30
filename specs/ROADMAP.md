# Roadmap — live status board

**Dynamic document.** Updated whenever a spec or phase changes state, and whenever new work is discovered. The static plan (goal, definition of done, full phase descriptions, dependencies) lives in `../PROJECT_PLAN.md` and is not repeated here.

Phase statuses: `not_started` | `in_progress` | `blocked` | `done`
Spec statuses: `draft` → `approved` → `in_progress` → `implemented` → `verified` (see `README.md`)

## Phase status

| Phase | Name | Status | Depends on |
|---|---|---|---|
| 0 | Foundations | done | — |
| 1 | Agent backend | in_progress | 0 (parallel with 2) |
| 2 | Orchestrator core | not_started | 0 (parallel with 1) |
| 3 | Roles | not_started | 1, 0.3 (role specs mutually parallel) |
| 4 | End-to-end workflow and CLI | not_started | 2, 3 |
| 5 | Evaluation and hardening | not_started | 4 |

---

## Phase 0 — Foundations [done]

**Specs**

| Spec | Task | Status |
|---|---|---|
| SPEC-001 | Python project tooling | verified |
| SPEC-002 | Cursor CLI harness smoke test | verified |
| SPEC-003 | Artifact schemas v1 | verified |
| SPEC-004 | Case store and audit log | verified |

**Findings**

- (pre-phase, 2026-07-30) Cursor CLI validated as the Phase 1 harness: headless `-p` works; JSON envelope carries usage, session_id, duration; 3-way concurrency across model families succeeded; ~12–24k input-token overhead per invocation even for trivial tasks; no schema-constrained generation, so the file-write-then-validate pattern is mandatory. Details: `../report-and-findings/2026-07-30-cursor-cli-research.md`
- (pre-phase, 2026-07-30) Spec review against the north star and PROJECT_PLAN closed five gaps before implementation: missing PROVISIONAL_THESIS stage (SPEC-007/018), unwired final-falsification/repair routing (SPEC-007/018), uncomputed model stability (now `orchestrator/stability.py` in SPEC-013), missing `ProbabilityEstimate` basis structure (SPEC-003), and unrestricted runtime write access (per-workspace `.cursor/cli.json` in SPEC-006). Shared files were re-partitioned (per-role `cursor/roles/<role>.yaml`, `orchestrator/artifacts/` package, invocation-kit variants owned by SPEC-006) so Phase 3 specs remain parallel-safe.
- **(2026-07-31) `AGENTS.md` leaks into agent workspaces, so runtime workspaces cannot live in this repo.** The SPEC-002 smoke test's leakage probe returned LEAK, and a follow-up experiment (`../report-and-findings/2026-07-31-agents-md-leakage.md`) established the rule: `cursor-agent` walks the workspace's directory ancestry upward and loads every `AGENTS.md` it finds; a local workspace `AGENTS.md` is additive rather than suppressive; a nested `.git` boundary does not stop the walk; `--workspace` does not either; and no documented flag, env var, or config key disables the behavior. A workspace outside the repo tree is clean. **Decision:** `cases/` holds durable data only (artifacts, state, audit log, archived workspace copies) and nothing executes there; live workspaces are built under `AGENTADVISOR_RUNTIME_ROOT` (default `~/.local/share/agentadvisor/workspaces`) and archived back into `cases/<id>/agents/<role>--<task-id>/` afterwards. SPEC-004 gained `runtime_root()` and `archive_agent_workspace()`; SPEC-006 gained `orchestrator/isolation.py::assert_isolated`, which fails an invocation if any ancestor `AGENTS.md` exists.
- (2026-07-31) Review of the first SPEC-003 implementation caught the four uncertainty measures being flattened toward `Level` enums. North star Section 9 states three of them numerically, so `model_stability` became a computed `ModelStability` record (share must equal `runs_supporting / runs_total`, so it cannot be model-asserted) and the two confidences became `ConfidenceAssessment` (value plus required basis). `Level` is retained only for subjective per-item judgements. `ProbabilityEstimate` was also over-constrained and would have forced fabricated reference classes; base-rate fields are now conditionally required.
- (2026-07-31) One measured Cursor CLI smoke run costs roughly 89k input / 1.3k output / 139k cache-read tokens across 6 invocations, which sets a floor for per-case budget expectations.

## Phase 1 — Agent backend [not_started]

**Specs**

| Spec | Task | Status |
|---|---|---|
| SPEC-005 | AgentBackend interface and CursorCLIBackend | draft |
| SPEC-006 | Role invocation kit | draft |

**Findings**

- —

## Phase 2 — Orchestrator core [not_started]

**Specs**

| Spec | Task | Status |
|---|---|---|
| SPEC-007 | Case state machine | draft |
| SPEC-008 | Budget controller and stop rules | draft |
| SPEC-009 | Task graph engine | draft |

**Findings**

- —

## Phase 3 — Roles [not_started]

**Specs**

| Spec | Task | Status |
|---|---|---|
| SPEC-010 | Intake and framing roles | draft |
| SPEC-011 | Planner role | draft |
| SPEC-012 | Researcher role and evidence normalization | draft |
| SPEC-013 | Quantitative Analyst role | draft |
| SPEC-014 | Director thesis and preliminary recommendation | draft |
| SPEC-015 | Challenger role | draft |
| SPEC-016 | Process Auditor role | draft |
| SPEC-017 | Synthesizer and calibration/citation reviewer | draft |

**Findings**

- —

## Phase 4 — End-to-end workflow and CLI [not_started]

**Specs**

| Spec | Task | Status |
|---|---|---|
| SPEC-018 | Stage wiring (end-to-end pipeline) | draft |
| SPEC-019 | User CLI | draft |
| SPEC-020 | First real decision case | draft |

**Findings**

- —

## Phase 5 — Evaluation and hardening [not_started]

**Specs**

| Spec | Task | Status |
|---|---|---|
| SPEC-021 | Benchmark cases and single-agent baseline | draft |
| SPEC-022 | Comparative evaluation and DoD audit | draft |

**Findings**

- —

---

## Emergent work

Work discovered mid-project lands here first as a candidate. With user approval it is promoted to a spec inside an existing phase, or to a new phase appended to the phase table. The static plan is never edited to absorb it.

**Candidates (identified during pre-phase research, not yet scheduled)**

- Concurrency behavior at more than 3 parallel CLI invocations (current cap: 3)
- `--resume <session_id>` repair-cycle experiment: resuming the Director versus fresh invocation with projected context (north star Section 21, question 1/7 adjacent)
- Sandbox policies and hard network enforcement (`.cursor/sandbox.json`), including no-network guarantees for Analyst scripts (SPEC-013); per-workspace `.cursor/cli.json` write/shell profiles were promoted into SPEC-006
- MCP-based research tooling for the Researcher role (search providers, citation extraction) (SPEC-012)
- Root `AGENTS.md` leakage mitigation, if the SPEC-002 smoke test detects leakage into runtime agent workspaces
- Live citation re-verification by the reviewer (north star open question 8; out of scope in SPEC-017)
- Repeated-run consistency measurement across benchmarks (out of scope in SPEC-021)
- Domain Specialist skill packs under `cursor/skills/` (north star 6.7); the MVP relies on the generic Researcher and Analyst
- Per-task marginal-value gate (north star Section 13 rule); MVP substitutes priority ordering, task caps, and Auditor relevance flags (accepted simplification)
- Evaluation of workflow variations (north star Section 19 item 3); SPEC-021 runs baseline + full workflow only

**Promoted**

- Per-workspace permission profiles (`.cursor/cli.json`) → SPEC-006 (2026-07-30, spec review)
