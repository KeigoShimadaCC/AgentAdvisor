# Roadmap — live status board

**Dynamic document.** Updated whenever a spec or phase changes state, and whenever new work is discovered. The static plan (goal, definition of done, full phase descriptions, dependencies) lives in `../PROJECT_PLAN.md` and is not repeated here.

Phase statuses: `not_started` | `in_progress` | `blocked` | `done`
Spec statuses: `draft` → `approved` → `in_progress` → `implemented` → `verified` (see `README.md`)

## Phase status

| Phase | Name | Status | Depends on |
|---|---|---|---|
| 0 | Foundations | done | — |
| 1 | Agent backend | done | 0 (parallel with 2) |
| 2 | Orchestrator core | done | 0 (parallel with 1) |
| 3 | Roles | done | 1, 0.3 (role specs mutually parallel) |
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

## Phase 1 — Agent backend [done]

**Specs**

| Spec | Task | Status |
|---|---|---|
| SPEC-005 | AgentBackend interface and CursorCLIBackend | verified |
| SPEC-006 | Role invocation kit | verified |

**Findings**

- (2026-07-31) A hung agent is now structurally incapable of wedging the orchestrator: the backend runs the CLI in its own session and kills the whole process group on timeout, verified by a test that asserts a grandchild process spawned by a fake binary is gone afterwards. Raw output is truncated at 8k chars so a runaway agent cannot flood the audit log.
- (2026-07-31) Failed invocations are archived, not discarded. Successful attempts land at `agents/<role>--<task-id>/` and failures at `--attempt-<n>`, so the reason an escalation happened stays reconstructable from the case alone.
- (2026-07-31) Role-model assignment now lives in `cursor/roles/<role>.yaml` with Director on `claude-opus-5-thinking-high` and Challenger on `gpt-5.6-sol-high`, keeping the two on different model families as the north star requires.

## Phase 2 — Orchestrator core [done]

**Specs**

| Spec | Task | Status |
|---|---|---|
| SPEC-007 | Case state machine | verified |
| SPEC-008 | Budget controller and stop rules | verified |
| SPEC-009 | Task graph engine | verified |

**Findings**

- (2026-07-31) Routing initially conflated three roles: the REVIEW stage was pointed at the Auditor, INTAKE at the Director, and STOP_DECISION was given an agent role even though it is a deterministic evaluator. `TaskRole` gained `intake` and `reviewer`, and STOP_DECISION now carries no roles at all. Worth remembering for Phase 3: a stage having no agent is a legitimate and important case.
- (2026-07-31) The Stage 4 priority formula could not actually be computed, because `TaskRecord` had no cost field and `priority_score` was silently standing in for the whole expression. Explicit `estimated_cost` and `probability_of_changing_conclusion` fields were added, and a test now proves a cheap low-materiality task can outrank an expensive high-materiality one.
- **(2026-07-31) The marginal-value rule is now enforced rather than deferred.** North star Section 13 assigns enforcement to the orchestrator, and it had been recorded as an accepted MVP simplification. Once the cost field existed the gate was trivial, so it is implemented as a pre-dispatch check that leaves refused tasks `planned` and audits the computed numbers. This closes the emergent-work candidate rather than carrying it.
- (2026-07-31) A failing task used to be recorded as `blocked`, which made it indistinguishable from a task blocked by someone else's failure. `TaskStatus.FAILED` was added so the audit trail can tell the difference.

## Phase 3 — Roles [done]

**Specs**

| Spec | Task | Status |
|---|---|---|
| SPEC-010 | Intake and framing roles | verified |
| SPEC-011 | Planner role | verified |
| SPEC-012 | Researcher role and evidence normalization | verified |
| SPEC-013 | Quantitative Analyst role | verified |
| SPEC-014 | Director thesis and preliminary recommendation | verified |
| SPEC-015 | Challenger role | verified |
| SPEC-016 | Process Auditor role | verified |
| SPEC-017 | Synthesizer and calibration/citation reviewer | verified |

**Findings**

- (2026-07-31) The invocation kit needed three amendments discovered during parallel role implementation: `variant` parameter for named role configs (SPEC-010 framing), `mode` field in `task.yaml` for task-mode branching (Director/Planner/Challenger/Auditor), and projection routing through canonical `case_store` paths instead of ad-hoc `outputs/` guesses. Unknown projection keys now raise `ProjectionError` rather than silently returning empty context. SPEC-006 was amended to record these.
- (2026-07-31) Two batch artifact models were added because the specs require multiple records per invocation but the kit produces one artifact: `EvidenceBatch` (Researcher, cap 8, `no_evidence_found` as first-class outcome) and `ObjectionBatch` (Challenger, caps 5/2 by mode, `no_objections_justification` for empty). `orchestrator/unpack.py` unpacks batches into individual blackboard records with orchestrator-allocated canonical IDs; agent-supplied IDs are never trusted for persistence. `case.write_artifact` on a batch raises a targeted error.
- (2026-07-31) `ObjectionRecord` was extended with `reversal_evidence`, `target_section`, `referenced_evidence_ids`, and `referenced_assumption_ids` as first-class fields. A compatibility pre-validator that silently coerced legacy fields was removed because it violated the "validate before accepting" rule. Nine stale fixtures were migrated.
- (2026-07-31) Three live tests initially skipped instead of failing (analyst, synthesizer, reviewer), and the director live test used a fabricated `composer-2.5` config instead of the real `claude-opus-5-thinking-high`. All four were fixed: skips removed, director monkeypatch removed, role mds enriched with explicit schema-valid YAML templates and field-type constraints, timeouts raised to 300s for the analyst and synthesizer. All 13 live tests now pass with real configurations.
- (2026-07-31) The Auditor live run confirmed that fenced-YAML-in-stdout under plan mode is not fully reliable: the model did not fence the YAML block, and success depended on `_extract_yaml_block`'s fallback. The fallback is sufficient; the write-enabled path remains available if needed.
- (2026-07-31) Final-recommendation citation checking is currently in `orchestrator/render.py` and the synthesis test file; it should be consolidated with `orchestrator/citations.py` (owned by SPEC-014) in Phase 4.
- (2026-07-31) Full suite: 176 unit tests + 13 live tests green.

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
- ~~Per-task marginal-value gate (north star Section 13 rule)~~ **Promoted and implemented 2026-07-31 in SPEC-009**, since adding `estimated_cost` to `TaskRecord` made the real rule cheaper than the planned workaround.
- Evaluation of workflow variations (north star Section 19 item 3); SPEC-021 runs baseline + full workflow only

**Promoted**

- Per-workspace permission profiles (`.cursor/cli.json`) → SPEC-006 (2026-07-30, spec review); implemented and verified 2026-07-31
- Out-of-repo runtime workspaces + `assert_isolated` guard → SPEC-004/SPEC-006 (2026-07-31, forced by the leakage finding); implemented and verified
- Per-task marginal-value gate → SPEC-009 (2026-07-31); implemented and verified
