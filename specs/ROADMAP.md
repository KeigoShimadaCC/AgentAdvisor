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
| — | 0.1 Python tooling | no spec yet |
| — | 0.2 Harness smoke test | no spec yet |
| — | 0.3 Artifact schemas v1 | no spec yet |
| — | 0.4 Case store and audit log | no spec yet |

**Findings**

- (pre-phase, 2026-07-30) Cursor CLI validated as the Phase 1 harness: headless `-p` works; JSON envelope carries usage, session_id, duration; 3-way concurrency across model families succeeded; ~12–24k input-token overhead per invocation even for trivial tasks; no schema-constrained generation, so the file-write-then-validate pattern is mandatory. Details: `../report-and-findings/2026-07-30-cursor-cli-research.md`

## Phase 1 — Agent backend [not_started]

**Specs**

| Spec | Task | Status |
|---|---|---|
| — | 1.1 AgentBackend + CursorCLIBackend | no spec yet |
| — | 1.2 Role invocation kit | no spec yet |

**Findings**

- —

## Phase 2 — Orchestrator core [not_started]

**Specs**

| Spec | Task | Status |
|---|---|---|
| — | 2.1 Case state machine | no spec yet |
| — | 2.2 Budget controller and stop rules | no spec yet |
| — | 2.3 Task graph engine | no spec yet |

**Findings**

- —

## Phase 3 — Roles [not_started]

**Specs**

| Spec | Task | Status |
|---|---|---|
| — | 3.1 Intake and framing | no spec yet |
| — | 3.2 Planner | no spec yet |
| — | 3.3 Researcher + evidence normalization | no spec yet |
| — | 3.4 Analyst | no spec yet |
| — | 3.5 Director thesis | no spec yet |
| — | 3.6 Challenger | no spec yet |
| — | 3.7 Auditor | no spec yet |
| — | 3.8 Synthesis and review | no spec yet |

**Findings**

- —

## Phase 4 — End-to-end workflow and CLI [not_started]

**Specs**

| Spec | Task | Status |
|---|---|---|
| — | 4.1 Stage wiring | no spec yet |
| — | 4.2 User CLI | no spec yet |
| — | 4.3 First real case | no spec yet |

**Findings**

- —

## Phase 5 — Evaluation and hardening [not_started]

**Specs**

| Spec | Task | Status |
|---|---|---|
| — | 5.1 Benchmarks and baseline | no spec yet |
| — | 5.2 Comparative evaluation | no spec yet |

**Findings**

- —

---

## Emergent work

Work discovered mid-project lands here first as a candidate. With user approval it is promoted to a spec inside an existing phase, or to a new phase appended to the phase table. The static plan is never edited to absorb it.

**Candidates (identified during pre-phase research, not yet scheduled)**

- Concurrency behavior at more than 3 parallel CLI invocations (current cap: 3)
- `--resume <session_id>` repair-cycle experiment: resuming the Director versus fresh invocation with projected context (north star Section 21, question 1/7 adjacent)
- Per-role permission and sandbox profiles (`.cursor/cli.json`, `.cursor/sandbox.json`)
- MCP-based research tooling for the Researcher role (search providers, citation extraction)
- Root `AGENTS.md` leakage mitigation, if the Phase 0.2 smoke test detects leakage into runtime agent workspaces

**Promoted**

- —
