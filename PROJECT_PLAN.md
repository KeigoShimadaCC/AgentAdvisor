# Project Plan — Decision Intelligence Platform

**Status:** Static reference document. This file describes the goal, definition of done, and phase structure as designed at project start. It is not updated with progress. Live status, per-phase findings, and emergent work belong in `specs/ROADMAP.md`. Product intent is defined by `decision_intelligence_north_star.md`; if this plan and the north star conflict, the north star wins.

**Last updated:** 2026-07-30 (intentionally frozen after approval)

---

## 1. Goal

Build the smallest working system that takes a real, imperfectly defined decision prompt (first vertical: investment-style decisions) and runs the full multi-role workflow on Cursor CLI: intake, framing, planning, parallel evidence and analysis, provisional thesis, adversarial challenge, bounded repair, stop decision, synthesis, and calibration/citation review, producing a recommendation package that is measurably better than a single strong-agent baseline (north star Section 18) and fully auditable from its artifacts.

Single user, single machine, deterministic Python orchestrator, Cursor CLI as the first `AgentBackend`.

---

## 2. Definition of done

The MVP is done when every unchecked box below is either checked or explicitly waived by the user.

### A. Functional completeness

- [ ] One command starts a new case from a decision prompt and runs Stages 1–10 (north star Section 8) with human approval gates at framing and final delivery.
- [ ] A case can be checkpointed, resumed, and inspected mid-run.
- [ ] Repair cycles are capped at two; stop rules fire correctly; stopping due to budget or evidence gaps is disclosed in the final output.

### B. Output quality

- [ ] The final package contains all twelve elements promised in north star Section 3, in the Section 16 format.
- [ ] The alternative set includes at least one credible option the user did not supply (when applicable).
- [ ] Every material factual claim cites evidence records with provenance and `independence_group`.
- [ ] Outcome probability, evidence confidence, recommendation confidence, and model stability are reported as distinct measures.
- [ ] Quantitative results are reproducible: `analysis/` contains runnable code whose outputs match the reported numbers.

### C. Guardrails and engineering quality

- [ ] Every agent output is schema-validated before entering shared state; invalid output never contaminates state (tested).
- [ ] Per-case budgets (invocations, concurrency, repair cycles, high-tier calls, wall clock) are enforced by the orchestrator (tested).
- [ ] Workspace isolation is verified: no cross-agent file access, no repo-root `AGENTS.md` leakage into runtime agents.
- [ ] The audit log reconstructs the run: role, model, CLI version, tokens, duration, artifacts read/written, state transitions.
- [ ] Lint, typecheck, unit tests, and the harness smoke test are green.

### D. Usability

- [ ] Documented run instructions; a new case requires configuration and a prompt, never code edits.
- [ ] A status command shows current stage, task states, and budget consumption.
- [ ] The final recommendation is a readable Markdown document; underlying artifacts are browsable from it.

### E. Evaluation

- [ ] At least three benchmark cases run end to end within budget.
- [ ] A single-agent baseline comparison is documented using the Section 18 rubric.
- [ ] Included-usage consumption per case is measured and recorded.

### Explicitly not required for done

Web UI, decision domains beyond the investment vertical, claims of calibrated probabilities, autonomous execution of external actions, multi-user or remote operation.

---

## 3. Phase map

Each phase is a group of session-sized tasks. One task = one spec (see `specs/README.md`): written, approved, implemented, verified, in that order. A task is deliberately small enough for a coding agent to implement, test, and confirm working in one focused session.

| Phase | Name | Depends on | Parallelism |
|---|---|---|---|
| 0 | Foundations | — | 0.1 ∥ 0.2; then 0.3 → 0.4 |
| 1 | Agent backend | 0 | parallel with Phase 2 |
| 2 | Orchestrator core | 0 | parallel with Phase 1 |
| 3 | Roles | 1 (and 0.3 schemas) | role specs mutually parallel |
| 4 | End-to-end workflow and CLI | 2, 3 | mostly sequential |
| 5 | Evaluation and hardening | 4 | 5.1 before 5.2 |

```
Phase 0 Foundations
   ├──────────────► Phase 1 Agent backend ──► Phase 3 Roles ─┐
   └──────────────► Phase 2 Orchestrator core ───────────────┼─► Phase 4 E2E + CLI ─► Phase 5 Evaluation
                                                             ┘
```

---

## 4. Phase details

### Phase 0 — Foundations

**Goal:** A tooled repository where schemas, case storage, and the harness are proven before any workflow logic exists.

**Prerequisites:** none.

| Task | Content | Exit criterion |
|---|---|---|
| 0.1 Python tooling | pyproject, dependency management, ruff, mypy, pytest, one `make check`-style entry point | Quality gates run green on a seed module |
| 0.2 Harness smoke test | Scripted version of the validated CLI tests: auth, headless text, artifact round trip, JSON envelope parse, 3-way concurrency, root-AGENTS.md leakage check; machine-readable results | Passes locally; rerunnable after every CLI update |
| 0.3 Artifact schemas v1 | Typed models + JSON Schema export for decision spec, evidence, assumption, objection, task, recommendation, audit event; `E-/A-/T-/O-` ID scheme; fixtures | Round-trip serialization and validation tests green |
| 0.4 Case store and audit log | Create/load `cases/<case-id>/` layout, atomic artifact writes, ID allocation, append-only audit log capturing CLI version and usage metadata | Unit tests green |

### Phase 1 — Agent backend

**Goal:** One reliable primitive: "invoke a role on a model, in an isolated workspace, get back a schema-valid artifact or a classified failure."

**Prerequisites:** Phase 0.

| Task | Content | Exit criterion |
|---|---|---|
| 1.1 `AgentBackend` + `CursorCLIBackend` | Subprocess invocation with hard timeout, `--output-format json` envelope parsing, error taxonomy (timeout, nonzero exit, unparseable, is_error), usage capture | Unit tests against a fake binary; one live invocation test |
| 1.2 Role invocation kit | Workspace builder (role md projected as the workspace `AGENTS.md`), context packet assembler (blackboard projection), output collection, schema validation, retry-then-escalate ladder | Live single-role run produces a validated artifact; leakage check passes |

### Phase 2 — Orchestrator core

**Goal:** The deterministic spine: state machine, budgets, and task graph, fully testable without any model calls.

**Prerequisites:** Phase 0. Runs parallel with Phase 1 (shares only schemas); all tests use a stub backend.

| Task | Content | Exit criterion |
|---|---|---|
| 2.1 Case state machine | Stage states and transitions, checkpoint/resume, deterministic routing | Simulated full workflow with stub agents passes tests |
| 2.2 Budget controller and stop rules | Caps (invocations, concurrency, repair cycles, high-tier calls, wall clock), stop-decision logic, escalation policy | Unit tests covering exhaustion and disclosure paths |
| 2.3 Task graph engine | Task records, dependencies, parallel dispatch, result reconciliation into shared state | Unit tests with concurrent stub workers |

### Phase 3 — Roles

**Goal:** Each role exists as a versioned definition (role md + context projection config + bound output schema) proven with a golden-fixture test and one live mini-run on a cheap model.

**Prerequisites:** Phase 1 (invocation kit), Phase 0.3 (schemas). Role specs are mutually parallel.

| Task | Role(s) | Notes |
|---|---|---|
| 3.1 Intake and framing | Intake extractor, Director-framing | Decision spec generation, broadened alternatives, approval-gate artifact |
| 3.2 Planner | Planner | Task proposals with materiality, information gain, cost fields |
| 3.3 Researcher | Researcher + deterministic evidence normalization | Provenance, independence groups, dedup |
| 3.4 Analyst | Quantitative Analyst | Scenario and sensitivity model; reproducible code under `analysis/` |
| 3.5 Director thesis | Director | Provisional thesis and preliminary recommendation |
| 3.6 Challenger | Challenger | Different model family from Director; bounded objection count |
| 3.7 Auditor | Process Auditor | Relevance, drift, duplication, schema conformance; read-only mode if viable |
| 3.8 Synthesis and review | Synthesizer, Calibration/Citation reviewer | Final report renderer included |

**Exit criterion per task:** schema-valid artifact from a golden fixture and from one live cheap-model run.

### Phase 4 — End-to-end workflow and CLI

**Goal:** The whole pipeline runs as one product.

**Prerequisites:** Phases 2 and 3.

| Task | Content | Exit criterion |
|---|---|---|
| 4.1 Stage wiring | Full Stages 1–10 with approval gates, repair loop (max 2), stop decision, budget-stop disclosure | Toy decision case end to end on cheap models |
| 4.2 User CLI | `new`, `status`, `resume`, `report` commands | DoD items A and D demonstrable |
| 4.3 First real case | Full investment-style decision run; usage measured | Findings report in `report-and-findings/` |

### Phase 5 — Evaluation and hardening

**Goal:** Prove (or disprove) that the workflow beats a single-agent baseline, and close the DoD.

**Prerequisites:** Phase 4.

| Task | Content | Exit criterion |
|---|---|---|
| 5.1 Benchmarks and baseline | ≥3 benchmark cases, single-agent baseline runner, Section 18 rubric | Both pipelines run on all benchmarks |
| 5.2 Comparative evaluation | Scored comparison, budget/model tuning, DoD audit | Findings report; DoD checklist resolved |

---

## 5. Working method

- Spec-driven: every task above becomes one spec in `specs/phase-<n>-*/` following `specs/TEMPLATE.md` and the lifecycle in `specs/README.md`.
- `specs/ROADMAP.md` is the only live status document: phase states, spec states, per-phase findings, and emergent work discovered mid-project.
- Work discovered along the way is recorded in ROADMAP's emergent-work section first, then promoted to a spec (and, if large, a new phase) with user approval. This plan is not edited to absorb it.

## 6. Standing risks and assumptions

| Risk | Mitigation |
|---|---|
| Cursor CLI is beta, auto-updates, flags churn | Record CLI version per case; rerun smoke test (0.2) after updates |
| ~12–24k input-token overhead per invocation | Minimize invocation count; cheap Cursor-pool models for volume roles; measure in 4.3 |
| Concurrency beyond n=3 unproven | Cap concurrency at 3 until tested; candidate emergent work |
| Model catalogue name churn | Role→model mapping lives in config, never in code |
| Included-usage exhaustion | Budget controller (2.2); Cursor-pool models for workers |
| Schema evolution mid-project | Versioned schemas from 0.3; fixtures regenerated per version |

## 7. Document map

| Document | Nature | Role |
|---|---|---|
| `decision_intelligence_north_star.md` | static | Why and what: product intent, architecture principles |
| `PROJECT_PLAN.md` (this file) | static | How and when: goal, definition of done, phase structure |
| `specs/ROADMAP.md` | dynamic | Live status, per-phase findings, emergent work |
| `specs/phase-*/SPEC-*.md` | per-task | Contracts: scope, design, acceptance criteria, verification |
| `report-and-findings/*.md` | append-only | Evidence: research, measurements, experiment writeups |
| `AGENTS.md` | maintained | Mechanics and rules for the development agent |
