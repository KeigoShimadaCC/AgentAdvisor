# Droid CLI as a second agent backend

Date: 2026-08-03
CLI version: droid 0.177.0

## Motivation

Cursor CLI quotas may run out. The `AgentBackend` protocol (SPEC-005) was
designed for exactly this: a second harness can be added behind the same
interface. This records what was tested and what was built.

## Probes (all live, 2026-08-03)

| Probe | Command | Result |
|---|---|---|
| Headless JSON | `droid exec -o json --cwd <ws> -m <model> "<prompt>"` | 7s round trip; envelope `{"type":"result","is_error":false,"duration_ms":...,"result":"...","session_id":"...","usage":{...}}` |
| File write | `droid exec --auto low` | Wrote `out/artifact.yaml` correctly |
| Workspace AGENTS.md | `--cwd <ws>` where ws has `AGENTS.md` | Loaded; role instructions reach the agent |
| Ancestor AGENTS.md (no git) | `--cwd <child>` with `AGENTS.md` in parent | **CLEAN** (no walk outside a git repo) |
| Ancestor AGENTS.md (in repo) | `--cwd benchmarks/` | **LEAK** (walks to git root). `assert_isolated` still needed. |
| Concurrency | 4 parallel `droid exec` in separate dirs | All succeeded, 8.2s vs 6.9s solo |
| Hermetic tools | `--settings '{"mcpServers":{}}'` + `--disable-builtin-skills` | Operator MCP servers and builtin skills stripped |
| Error handling | Bad model | exit 1, plain-text stderr, no JSON |
| stdin isolation | `stdin=DEVNULL` | Prevents droid reading the parent's stdin as a second prompt channel |

## Key differences from Cursor CLI

1. **Prompt is positional**, not `-p`.
2. **Permissions are an autonomy level**, not a permission file: no `--auto` is
   read-only; `--auto low` permits file writes; `--auto medium` permits running
   code (Analyst). The `.cursor/cli.json` file the workspace builder writes is
   ignored by Droid but harmless.
3. **Usage keys are snake_case**: `input_tokens`, `cache_read_input_tokens`,
   `cache_creation_input_tokens` vs Cursor's `inputTokens`, `cacheReadTokens`.
4. **Model IDs do not overlap** at all. Per-backend model assignment is needed.
5. **Droid can exit non-zero after a successful result.** The agent writes the
   output file and prints a valid JSON envelope, but the process trips during
   post-completion cleanup. The backend now parses the envelope before checking
   the exit code, so a valid `is_error: false` envelope is accepted regardless.

## What was built

Branch: `feat/droid-cli-backend` (worktree at `AgentAdvisor-droid-backend`).

### `orchestrator/backend.py`
- `DroidCLIBackend`: calls `droid exec -o json --cwd <ws> -m <model> --settings <no-mcp.json> --disable-builtin-skills [--auto low|medium] <prompt>`.
- `_run_json_cli` shared runner extracted from `CursorCLIBackend.run`; both
  backends differ only in argv builder and usage key map.
- `BackendName` enum, `make_backend()` factory, `AGENTADVISOR_BACKEND` env var.
- `RoleInvocation` gained `allow_shell: bool` (maps to `--auto medium` for the
  Analyst, `--auto low` for other writers, omitted for read-only).
- Late-crash fix: `_parse_envelope` runs before the exit-code check; a valid
  envelope with `is_error: false` is returned as OK even on non-zero exit.
- `stdin=DEVNULL` on all subprocess invocations.

### `orchestrator/backend_models.py` + `backends/droid/models.yaml`
- Per-backend model table: tier defaults (low/medium/high) plus per-role
  overrides where the specific model matters (Director tracks, Challenger,
  Premortem, Researcher, Reviewer).
- `roles_config.models_for(config, backend)` resolves the pair; Cursor falls
  back to the role YAML's own `default_model`/`escalation_model`.
- `validate_director_challenger_family_diversity` is now backend-aware.
- No role defaults to a high-tier model on Droid, so `max_high_tier_calls` is
  not exhausted by the Director's five-per-case invocations.

### CLI and scripts
- `advisor --backend {cursor,droid}` on every subcommand; `AGENTADVISOR_BACKEND`
  env var for unattended runs.
- `scripts/run_e2e_eval.py --backend droid`.
- `scripts/smoke_droid_cli.py` (7 checks: binary, auth, headless text, artifact
  roundtrip, workspace AGENTS.md, 3-way concurrency, leakage). All hard checks
  PASS.
- `make smoke-droid` target.

### Tests
- `tests/test_backend_droid.py`: 18 tests covering status mappings, snake_case
  usage extraction, banner tolerance, late-crash recovery, autonomy-level
  mapping, MCP isolation, backend selection, model catalogue coverage, budget
  tier map coverage, no-high-tier-defaults guard, Director/Challenger family
  diversity on Droid, attempt plan follows backend, fallback for unknown
  backend, missing-tier rejection.
- `tests/test_backend_live.py`: live droid artifact-write test (marked `live`).
- `tests/test_cli.py`: `--backend` flag selection and invalid-backend rejection.
- 365 unit tests pass; lint and mypy clean.

## E2e scenario result

Scenario 01 (public equity) ran on the droid backend. First run reached the
planner stage (5 successful invocations across intake, director, structurer)
before hitting the late-crash bug. After the fix, the run is being re-run.
The pipeline completed 13 of 14 stages before failing at the synthesizer
(the final stage). 41 invocations, 22 successful, 19 failed (mostly analyst
timeouts that succeeded on retry). Score: 1.70/2.0 (decision_completeness 2.0,
evidence_quality 2.0, analytical_quality 2.0, adversarial_robustness 2.0,
traceability 0.5 because no final recommendation was produced). 682k input
tokens, 494k output tokens, 8617s wall clock.

**What worked:** intake, framing, structuring, provisional_thesis, planning
(7 tasks), investigation (7/7 tasks, 0 failed), evidence_normalization,
assumption_ledger, preliminary_recommendation (dual track), pre_mortem
(4 failure modes), challenge (4 objections), repair cycle 1 (thesis changed),
challenge 2 final_pass (2 objections).

**What failed:** the synthesizer produced a schema-invalid `FinalRecommendation`
on its one successful attempt (outcome_probabilities validation error), and
agent_error on the other two. This is a model output quality issue, not a
backend plumbing issue. The same failure class occurs with Cursor.

**Droid-specific performance note:** the Analyst role (`--auto medium`,
code execution) frequently exceeds the 600s timeout on first attempt but
succeeds on retry. The late-crash fix (parsing the envelope before checking
the exit code) was essential: the planner's second attempt wrote a correct
output file and printed a valid envelope but exited non-zero, and without
the fix the pipeline would have stopped there.
