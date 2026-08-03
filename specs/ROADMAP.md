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
| 4 | End-to-end workflow and CLI | in_progress | 2, 3 |
| 5 | Evaluation and hardening | in_progress | 4 |
| 6 | Think-tank architecture | done | 4 |
| 7 | Product surface | in_progress | 4, 6 |

**Current position (2026-08-03).** Phase 6 is done: all four specs (023-026) verified, the before/after comparison report is at `report-and-findings/2026-08-03-phase-6-before-after.md`. Average score improved 1.89 to 1.96, evidence quality 1.53 to 1.80, assumptions 0 to 7.8/case, invocation success 52% to 92%, token cost down 40%. Phase 4 still needs SPEC-020 (a real, non-benchmark decision run through the CLI). Carried-over engineering tasks completed: citation checking consolidated into `citations.py`, coercion-layer property test covering every artifact model, coercion-layer accounting instrumentation with audit-log extraction. Phase 7 backend specs (027-033) implemented: case control service, revision loops, budget truth, safe resume, CaseView projection, and web app shell (FastAPI + SSE + React SPA scaffold). `make check` is green: lint, mypy, 674 unit tests, plus 17 live tests that are deselected by default. `make frontend-check` passes (tsc + type generation clean).

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
- ~~(2026-07-31) Final-recommendation citation checking is currently in `orchestrator/render.py` and the synthesis test file; it should be consolidated with `orchestrator/citations.py` (owned by SPEC-014) in Phase 4.~~ **Consolidated 2026-08-03** in `557569b`: `collect_final_recommendation_citation_ids` and `validate_final_recommendation_citations` moved to `citations.py`, with a cross-field validation hook registered for `FinalRecommendation` so citations are validated on write, not just on render.
- (2026-07-31) Full suite: 176 unit tests + 13 live tests green.

## Phase 4 — End-to-end workflow and CLI [in_progress]

**Specs**

| Spec | Task | Status |
|---|---|---|
| SPEC-018 | Stage wiring (end-to-end pipeline) | verified |
| SPEC-019 | User CLI | verified |
| SPEC-020 | First real decision case | approved |

**Findings**

- (2026-07-31) Pipeline implemented: `orchestrator/stages.py` (11 stage handlers) + `orchestrator/pipeline.py` (entry point with auto-approval, budget, citation hooks). 179 unit tests pass. Full details in `../report-and-findings/2026-07-31-e2e-evaluation.md`.
- (2026-07-31) Live e2e run (scenario 01): pipeline reached synthesis with 25 evidence records, 4 objections, 8 tasks, score 1.23/2.0. Synthesis failed with 172 FinalRecommendation validation errors (nested objects where strings expected). Fix applied: added valid YAML example to synthesizer.md. Awaiting live re-test after usage limit resets.
- (2026-07-31) Analytical quality gap: analyst produced 0 analysis results. Root cause not yet investigated. This is the most important issue to fix before the next live run.
- (2026-07-31) Cursor Pro usage limit hit after ~30 invocations. Resets 2026-08-30. Director/Synthesizer switched from `claude-opus-5-thinking-high` to `gpt-5.2`; Reviewer switched to `composer-2.5` for family diversity. All 5 scenarios in the second run failed at framing due to the overall usage limit.
- (2026-07-31) Citation hooks fixed: skip validation when blackboard is empty (provisional thesis stage). Task graph budget kind fixed to `agent_invocations`. Synthesizer timeout increased to 600s.
- (2026-08-02) **All 5 e2e scenarios completed successfully.** Average score 1.89/2.0 (94.4%). Four rounds of fixes applied: (1) analyst task dispatch mapping, (2) synthesis coercion + missing field defaults, (3) enum coercion for challenger, (4) model_stability consistency + dangling citation ID tolerance. 181 unit tests pass. Full details in `../report-and-findings/2026-08-02-e2e-final-evaluation.md`.
- (2026-08-02) Key results: Decision completeness 2.00/2.0, Adversarial robustness 2.00/2.0, Traceability 2.00/2.0 across all scenarios. S04 achieved perfect 2.00/2.0. Weakest dimension: Evidence quality (1.53 avg, source authority scoring gap). No assumption records produced in any scenario (planner does not commission assumption-gathering tasks). 52% invocation success rate (99/207 failed). Coercion layer is critical for pipeline completion.
- (2026-08-02) **Phase 4 is not closeable yet: SPEC-019 is marked `in_progress` but none of its three deliverables exist** (`orchestrator/cli.py`, the `advisor` entry point, `tests/test_cli.py`). The status was advanced during the SPEC-018 commit rather than by CLI work. Until then, cases are driven through `orchestrator/pipeline.py` and `scripts/run_e2e_eval.py`, which means DoD D ("a new decision needs a prompt and configuration only") is unproven. The root `README.md` is a SPEC-019 deliverable and is deliberately not written before it. **Resolved the same day** by implementing SPEC-019.
- (2026-08-02) **SPEC-019 implemented.** `advisor new | status | approve | resume | report | list`, exit codes 0/2/3, `--json` for tooling, `--budget-profile`, auditable `FramingApproval` artifacts for both gates, and `AGENTADVISOR_CASES_ROOT` so cases can live outside the repo. 17 CLI tests; suite now 313. `--depth` was specced but dropped: nothing downstream reads `DecisionSpec.depth`, so the flag would have been decoration. Phase 4's remaining item is SPEC-020.
- (2026-08-02) `scripts/case_metrics.py` (a SPEC-020 deliverable) written early and run against the Phase 6 scenario 01 log. First output already answers north star 13 for one case: 4.0M tokens and 85 minutes for 56 attempts at a 46% success rate, with analyst (21 attempts, 33% ok) and researcher (13 attempts, 23% ok) consuming 73% of all tokens. Building it is also what exposed the budget-counter persistence bug, since the case reported no consumption at all.
- (2026-08-03) **Carried-over engineering tasks completed.** (a) Final-recommendation citation checking consolidated from `render.py` into `citations.py` with a cross-field validation hook (`557569b`). (b) Coercion-layer property test covering every artifact model's every field (`128231f`, 178 tests). (c) Coercion-layer accounting instrumentation: `CoercionReport` records what the coercion layer changed, logged to audit trail, extracted by `case_metrics.py` (`5af2fce`). Also fixed a `_base_type` bug where `dict[str, int]` was misidentified as `str`. Suite now 522 unit tests.

## Phase 5 — Evaluation and hardening [not_started]

**Specs**

| Spec | Task | Status |
|---|---|---|
| SPEC-021 | Benchmark cases and single-agent baseline | in_progress |
| SPEC-022 | Comparative evaluation and DoD audit | draft |

**Findings**

- (2026-08-03) SPEC-021 scripts and tests implemented without live CLI: `scripts/run_baseline.py` (single-shot Cursor CLI invocation with Section 16 output template), `scripts/run_benchmarks.py` (workflow runner reusing `run_scenario` with pre-seeded approvals, copies final package to `benchmarks/results/<case>/workflow/`). `tests/test_benchmark_configs.py` extended with budget profile validation, framing approval decision check, Section 18 dimension coverage, and script existence checks. 5 new tests, suite now 527. Live baseline+workflow runs still needed to produce `summary.json` results.

## Phase 6 — Think-tank architecture [done]

Promoted 2026-08-02 from an architecture review of the Phase 4 results. The review identified six
structural weaknesses: the flow is a waterfall rather than a hypothesis loop, there is no MECE
problem decomposition, assumptions are orphaned, the Auditor has neither a schedule nor
enforcement power, the Reviewer is a rubber stamp, and a single Director is a single point of
epistemic failure. Phase 6 addresses all six and adds the cross-case memory that distinguishes a
think tank from a one-off engagement.

**Specs**

| Spec | Task | Status |
|---|---|---|
| SPEC-023 | Epistemic hygiene layer | verified |
| SPEC-024 | Structured deliberation | verified |
| SPEC-025 | Institutional memory | verified |
| SPEC-026 | Think-tank re-evaluation | verified |

**Findings**

- (2026-08-02) Tiers 1–3 are implemented and green under `make check` (lint, mypy, 296 unit tests, 17 live tests deselected). New deterministic modules: `orchestrator/gates.py` (scheduled process gates that can cancel tasks), `evidence_critic.py` (primary-source and cluster-concentration scoring), `verification.py` (reviewer worksheet with a single synthesis retry edge), `issue_tree.py` (MECE structuring with cycle/dangling-parent rejection and leaf coverage), `thesis.py` (append-only revision ledger), `tracks.py` (dual-track directors plus reconciliation on disagreement), `memory.py` + `calibration.py` (cross-case store, source reputation by registrable domain, Brier scoring), `skills.py` (keyword-selected specialist packs injected into researcher workspaces only). Four new roles: `structurer`, `assumption_analyst`, `director-b`, `premortem`.
- (2026-08-02) Cross-case memory lives in a gitignored root `memory/` directory (`cases.yaml`, `evidence.yaml`, `assumptions.yaml`), not in `cases/`, because it outlives any single case. Outcomes are recorded with `scripts/record_outcome.py`, which is what makes the Brier calibration series accumulate.
- (2026-08-02) Track B's output contract initially described fields absent from the schema, which would have made every dual-track run fail validation. Fixed in `cursor/roles/director-b.md`; worth remembering that role md contracts drift from schemas silently because only runtime validation catches them.
- ~~**(2026-08-02) SPEC-023 to SPEC-025 stay `implemented`, not `verified`.**~~ **Verified 2026-08-03** after the SPEC-026 live comparison completed. All four Phase 6 specs are now `verified`.
- (2026-08-02) **Three defects found while running the SPEC-026 sweep, all fixed in `0d0be44`.** (a) `run_case` re-loaded state from disk while the `BudgetLedger` mutated a different object, so budget counters were never persisted: caps were per-process, not per-case, and a resumed case silently started spending again from zero. (b) `coerce_payload_for_model` skipped every `list[...] | None` field because `Optional` reaches the union branch of `get_origin` and the list predicates never unwrapped it; scenario 03 failed intake and scored 0.00 because of it. (c) A vague deadline ("this quarter") failed date validation outright; it now nulls, with the wording preserved in `raw_prompt` and `intake.md` instructing a clarification question instead of a guessed date. Scenarios 01 and 03 need re-running before the comparison is honest: 01 lost its dual track to the track B defect, 03 never started.
- ~~Scenarios 01 and 03 need re-running~~ **Re-runs completed 2026-08-03.** See the Phase 6 comparison finding below.
- (2026-08-02) **Role definitions were teaching schemas the orchestrator rejects.** The analyst's own worked example used `method: base_rate` (not a `ProbabilityMethod`) and an adjustment shape of `{delta, reason, evidence_id}` instead of `{description, delta, evidence_ids}`, which accounts for most of the 30 validation failures in scenario 01. The researcher contract listed field names without types, so `directness: direct` and a bare-string `limitations` looked reasonable. Both rewritten in `a2ef43d`, along with a static check (`tests/test_role_contracts.py`) that validates every worked example against the schema its role config declares; it caught a fourth instance immediately in `synthesizer.md`. Separately, whole researcher batches were being discarded for unquoted colons in source titles, so the shared invocation prompt now carries a YAML quoting rule (`22077f5`). Early signal from scenario 04, which picked the fixes up mid-run: invocation success rose from 46% (scenario 01) and 57% (scenario 02) to 78%.
- (2026-08-03) **Phase 6 comparison complete.** All five scenarios re-run with all fixes applied. Average score 1.89 to 1.96, evidence quality 1.53 to 1.80, assumptions 0 to 7.8/case, invocation success 52% to 92%, input tokens 11.9M to 7.1M (-40%), wall clock 285 min to 202 min (-29%). Scenario 02 evidence quality flat at 1.33 is the remaining gap. Full report: `../report-and-findings/2026-08-03-phase-6-before-after.md`. SPEC-023 through SPEC-026 all verified.

## Phase 7 — Product surface [in_progress]

Promoted 2026-08-02 by user direction from the frontend discovery report at
`phase-7-product-surface/frontend-discovery-report.md`. The report answers north star open
question 21.12 (visual interface vs Markdown artifacts): the selected direction is a local-first
web app in which each case is a single "living brief" with two signed checkpoint sheets, five
inspection rooms, and four never-collapsed uncertainty encodings. The report also identified the
engine defects that would make an honest UI impossible today (approval edits consumed by nothing,
budget counters never persisted, unsafe resume, `done` ≠ review-passed, renderer citation spam);
SPEC-027 to SPEC-031 close those first, SPEC-032/033 build the read model and service shell,
SPEC-034 to SPEC-036 build the screens, and SPEC-037 verifies the whole product in a real
browser (deterministic fixture/stub/replay modes plus an opt-in live-backend smoke).

**Specs**

| Spec | Task | Status |
|---|---|---|
| SPEC-027 | Case control service and run supervisor | verified |
| SPEC-028 | Framing revision loop and final send-back | verified |
| SPEC-029 | Budget truth and disclosed stops | verified |
| SPEC-030 | Safe resume and delivery-integrity persistence | verified |
| SPEC-031 | Renderer and presentation-data fixes | verified |
| SPEC-032 | CaseView projection, fixture case, generated frontend types | verified |
| SPEC-033 | Local web app shell: advisor ui, SSE, SPA scaffold, replay | implemented |
| SPEC-034 | Commissioning flow and scope checkpoint UI | implemented |
| SPEC-035 | Living brief, progress experience, delivery checkpoint UI | draft |
| SPEC-036 | Rooms and record inspector | implemented |
| SPEC-037 | Frontend e2e suite in a real browser | draft |

**Findings**

- **(2026-08-03) SPEC-027 to SPEC-032 verified; 639 unit tests green.** Each spec's own
  verification plan was executed rather than inferred from a passing suite: 027 (30 tests plus a
  clean `make schemas`), 028 (64), 029 (33), 030 (27), 031 (31), 032 (21 plus regenerating 60
  schemas and `npx tsc --noEmit`). All six had sat at `implemented`/`in_progress` with the
  results section empty, and the phase table still read `not_started` while six of its specs were
  built — a status board that disagrees with itself is worse than none.
- **(2026-08-03) The sentinel module had re-created the defect it exists to prevent.**
  `artifacts/sentinels.py` hardcoded `"Not independently assessed"` and the qualitative-conversion
  prefix, duplicating strings `yaml_io.py` owns and writes. Rewording either filler would have
  silently stopped placeholder detection, and the renderer would present coercion defaults as
  measurements again — north star Section 9's collapse defect, reintroduced through string
  duplication. The markers are now derived from `_DEFAULT_FILLERS` and from a live
  `_confidence_from_word` conversion, and `tests/test_sentinels.py` drives the real coercion
  entry points so a reworded filler breaks a test instead of the product.
- **(2026-08-03) Phase 7 tier 1 was implemented twice, in parallel, and the duplicate was
  closed.** An independent branch built SPEC-027/028/031 while main built 027 to 032; the two
  converged on the same module layout, the same routing-owned revision caps, the same re-run task
  ids, and independently hit and fixed the same `archive_agent_workspace` collision with the same
  `--rerun-<n>` scheme. All 22 overlapping files conflicted as add/add, so the duplicate was
  closed rather than merged (PR #2). Worth remembering: parallel sessions need to claim specs
  before implementing, not after.
- (2026-08-02) Discovery findings that shaped the specs, verified against the implementation and
  the two real cases: approval is two booleans nothing external can set; `FramingApproval.edits`
  and `clarification_answers` are written but never consumed; `state.yaml` `budget_counters` is
  always `{}` (ledger aliasing), leaving `DisclosureRecord` unreachable; resume is non-idempotent
  (zombie `active` tasks, workspace-archive `FileExistsError` → case `FAILED`, duplicate ID
  minting on re-unpack); a case reaches `done` even when review fails after its single retry
  (case-001 shipped exactly so); the renderer appends the full citation list to every bullet
  (~40% of the reference report); coercion sentinels ("Not independently assessed",
  `runs_total==1`) render as measurements. The only live progress signal is per-event-flushed
  `audit.jsonl` (no `stage_started` event exists); StubBackend + archived real cases enable
  full frontend development and three of SPEC-037's four e2e modes at zero token cost.

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
- ~~(2026-08-02) A static check that every `cursor/roles/<role>.md` output contract matches the artifact schema the orchestrator validates it against.~~ **Promoted and implemented 2026-08-02** as `tests/test_role_contracts.py`, after the same defect class appeared a third and fourth time (analyst, synthesizer).
- ~~(2026-08-02) Coercion-layer accounting: the Phase 4 runs depended on coercion to complete, so how often it fires, and for which role and field, should be measured rather than assumed benign. Sharpened by the optional-list bug below: the layer was silently not firing on a whole category of fields and nothing noticed until a benchmark scenario died.~~ **Implemented 2026-08-03** in `5af2fce`: `CoercionReport` records every field change, logged to audit trail, extracted by `case_metrics.py` with per-role/per-field/per-type counts. Also fixed a `_base_type` bug where `dict[str, int]` was misidentified as `str`.
- ~~(2026-08-02) A property test over every artifact model asserting the coercion layer reaches every field, rather than testing hand-picked fields. The `list[...] | None` gap existed because coverage was chosen by example.~~ **Implemented 2026-08-03** in `128231f`: 178 parametrized tests walk every `ArtifactModel` subclass and every field, verifying coercion coverage. Found one known exception (`SensitivityRow.parameter_value: float | NonEmptyStr`).
- ~~(2026-08-02) Researcher and analyst produce most of the token spend at the worst success rates.~~ **Fixed the same day** in `a2ef43d`; see the Phase 6 findings.
- (2026-08-03) Droid CLI (`droid exec`) as a second agent backend behind the existing `AgentBackend` protocol. Implemented on `feat/droid-cli-backend`: `DroidCLIBackend`, per-backend model tables (`backends/<backend>/models.yaml`), `--backend {cursor,droid}` CLI flag, `AGENTADVISOR_BACKEND` env var, `scripts/smoke_droid_cli.py`, and 18 new unit tests. The workspace `AGENTS.md` delivery mechanism works unchanged. One Droid-specific fix: the backend now parses the JSON envelope before checking the exit code, because Droid can crash during post-completion cleanup after printing a valid result. Details: `../report-and-findings/2026-08-03-droid-cli-research.md`. **Not yet promoted to a spec** (implemented directly at user request); needs a SPEC for the Phase 1 backend table and a Phase 5 benchmark re-run under Droid before the two backends' scores are comparable.

**Promoted**

- Frontend product surface: discovery report + spec family SPEC-027…SPEC-037 → **Phase 7** (2026-08-02, user-directed)
- Per-workspace permission profiles (`.cursor/cli.json`) → SPEC-006 (2026-07-30, spec review); implemented and verified 2026-07-31
- Out-of-repo runtime workspaces + `assert_isolated` guard → SPEC-004/SPEC-006 (2026-07-31, forced by the leakage finding); implemented and verified
- Per-task marginal-value gate → SPEC-009 (2026-07-31); implemented and verified
- Static role-md ↔ schema contract check → `tests/test_role_contracts.py` (2026-08-02); folded into the Phase 6 work rather than given its own spec, because it is a test for an existing contract rather than new behaviour
