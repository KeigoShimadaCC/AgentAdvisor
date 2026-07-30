---
id: SPEC-002
title: Cursor CLI harness smoke test
phase: 0
status: verified
depends_on: []
parallel_with: [SPEC-001]
north_star_refs: ["11", "21"]
last_updated: 2026-07-31
---

# SPEC-002 — Cursor CLI harness smoke test

## Summary

Codify the manual harness tests of 2026-07-30 (`report-and-findings/2026-07-30-cursor-cli-research.md`) into one rerunnable script, so any Cursor CLI update can be revalidated with a single command.

## Motivation

The CLI is beta, auto-updates by default, and its flags churn. North star Section 11 requires the backend boundary to rest on verified behavior; Section 21 lists concurrency as an open question. The smoke test is the standing answer.

## Scope

Script `scripts/smoke_cursor_cli.py` (stdlib only, runnable before SPEC-001 tooling exists) with checks:

1. **binary**: `cursor-agent` on PATH; capture `--version` string.
2. **auth**: `cursor-agent status` reports logged in.
3. **headless-text**: `-p --trust --model composer-2.5 --output-format text` echo test returns the exact requested token.
4. **artifact-roundtrip**: agent reads a `task.json`, writes `answer.json`; validate JSON parses and required keys exist; `--output-format json` envelope contains `is_error=false`, `session_id`, `usage.inputTokens`.
5. **concurrency-3**: three parallel invocations (composer-2.5, gpt-5.2, cursor-grok-4.5-low) in separate temp dirs; all succeed.
6. **agents-md-leakage**: outside the repo, build `parent/AGENTS.md` containing a sentinel token and `parent/child/` workspace; invoke agent with cwd `parent/child` asking whether its instructions contain the sentinel; record LEAK/CLEAN (informative check: result recorded, does not fail the run; a LEAK finding goes to ROADMAP emergent work).

All work in temp dirs; every invocation wrapped in a hard timeout (120s); results written as JSON (`--out <path>`, default under `/tmp`) including cli_version, per-check pass/fail, durations, token usage.

## Out of scope

Testing every model; permission/sandbox profiles; MCP; `--resume` behavior (emergent-work candidates).

## Design

Pure stdlib (`subprocess`, `json`, `tempfile`, `concurrent.futures`, `argparse`). Exit code 0 only if all hard checks pass (leakage check is soft). `Makefile` gets a `smoke` target once SPEC-001 lands (`python3 scripts/smoke_cursor_cli.py`). Approximately 6 cheap-model invocations per run; expected cost negligible.

## Deliverables

- [x] `scripts/smoke_cursor_cli.py`
- [x] `smoke` target in `Makefile` (owned by SPEC-001, which holds the Makefile)

## Acceptance criteria

- [x] `python3 scripts/smoke_cursor_cli.py --out /tmp/smoke.json` exits 0 on the current machine.
- [x] `/tmp/smoke.json` contains `cli_version`, all six check results, and token usage per invocation.
- [x] Leakage check result (LEAK or CLEAN) is recorded in the ROADMAP Phase 0 findings after first run.

## Verification plan

```
python3 scripts/smoke_cursor_cli.py --out /tmp/smoke.json && python3 -m json.tool /tmp/smoke.json
```

Then record findings (cli_version, leakage result) in `specs/ROADMAP.md` Phase 0.

## Verification results

**2026-07-31 — PASS (all five hard checks), leakage check returned LEAK.** CLI version `2026.07.23-e383d2b`.

| Check | Kind | Result | Duration |
|---|---|---|---|
| binary | hard | pass | 0.27s |
| auth | hard | pass | 2.16s |
| headless-text | hard | pass | 15.15s |
| artifact-roundtrip | hard | pass (is_error=false, session_id present, usage.inputTokens=12424) | 17.29s |
| concurrency-3 | hard | pass (composer-2.5, gpt-5.2, cursor-grok-4.5-low all succeeded) | 28.44s |
| agents-md-leakage | soft | **LEAK** | 17.41s |

Total usage for one run: 89,485 input / 1,293 output / 138,643 cache-read tokens. Exit code 0; report at `/tmp/smoke.json`.

The LEAK verdict triggered a dedicated follow-up investigation: `report-and-findings/2026-07-31-agents-md-leakage.md`. `cursor-agent` walks the workspace's directory ancestry upward and loads every `AGENTS.md` it finds; a local `AGENTS.md` is additive rather than suppressive, and neither a nested `.git` boundary nor an explicit `--workspace` flag stops it. Consequence: runtime agent workspaces must not live inside this repository. This is now a design constraint on SPEC-004 and SPEC-006.

Lint note: the script is included in `make lint` (`ruff check`/`format` over `orchestrator tests scripts`) despite being stdlib-only, so it cannot rot.

## Open questions

- None blocking. Leakage semantics may vary by CLI version; the check records rather than asserts, and the standing mitigation (out-of-repo workspaces) does not depend on the verdict.
