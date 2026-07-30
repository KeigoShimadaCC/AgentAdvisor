# Roadmap — live status board

**Dynamic document.** Updated whenever a spec or phase changes state, and whenever new work is discovered. The static plan (goal, definition of done, full phase descriptions, dependencies) lives in `../PROJECT_PLAN.md` and is not repeated here.

Phase statuses: `not_started` | `in_progress` | `blocked` | `done`
Spec statuses: `draft` → `approved` → `in_progress` → `implemented` → `verified` (see `README.md`)

## Phase status

| Phase | Name | Status | Depends on |
|---|---|---|---|
| 0 | Foundations | not_started | — |
| 1 | Agent backend | not_started | 0 (parallel with 2) |
| 2 | Orchestrator core | not_started | 0 (parallel with 1) |
| 3 | Roles | not_started | 1, 0.3 (role specs mutually parallel) |
| 4 | End-to-end workflow and CLI | not_started | 2, 3 |
| 5 | Evaluation and hardening | not_started | 4 |

---

## Phase 0 — Foundations [not_started]

**Specs**

| Spec | Task | Status |
|---|---|---|
| SPEC-001 | Python project tooling | draft |
| SPEC-002 | Cursor CLI harness smoke test | draft |
| SPEC-003 | Artifact schemas v1 | draft |
| SPEC-004 | Case store and audit log | draft |

**Findings**

- (pre-phase, 2026-07-30) Cursor CLI validated as the Phase 1 harness: headless `-p` works; JSON envelope carries usage, session_id, duration; 3-way concurrency across model families succeeded; ~12–24k input-token overhead per invocation even for trivial tasks; no schema-constrained generation, so the file-write-then-validate pattern is mandatory. Details: `../report-and-findings/2026-07-30-cursor-cli-research.md`

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
- Per-role permission and sandbox profiles (`.cursor/cli.json`, `.cursor/sandbox.json`), including hard no-network enforcement for Analyst scripts (SPEC-013)
- MCP-based research tooling for the Researcher role (search providers, citation extraction) (SPEC-012)
- Root `AGENTS.md` leakage mitigation, if the SPEC-002 smoke test detects leakage into runtime agent workspaces
- Live citation re-verification by the reviewer (north star open question 8; out of scope in SPEC-017)
- Repeated-run consistency measurement across benchmarks (out of scope in SPEC-021)

**Promoted**

- —
