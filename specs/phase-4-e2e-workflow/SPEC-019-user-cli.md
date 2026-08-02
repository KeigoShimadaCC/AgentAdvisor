---
id: SPEC-019
title: User CLI
phase: 4
status: verified
depends_on: [SPEC-018]
parallel_with: []
north_star_refs: ["15"]
last_updated: 2026-08-02
---

# SPEC-019 — User CLI

## Summary

The user-facing command surface: start a case, see progress, answer approval gates, resume, and read the report. A new decision must require a prompt and configuration only, never code edits (DoD D).

## Motivation

North star Section 15: commissioning a consulting engagement, not operating an agent framework; meaningful progress over raw transcripts.

## Scope

`orchestrator/cli.py`, exposed as `advisor` via `pyproject.toml` script entry (stdlib argparse):

- `advisor new "<decision prompt>" [--slug s] [--budget-profile default|small]` → creates case, runs to the first halt (usually AWAITING_FRAMING_APPROVAL), prints case id and what is awaited.
- `advisor status <case-id>` → stage, task-graph counts by status, budget consumption vs caps, pending approvals; `--json` for machine output.
- `advisor approve <case-id> [--edit <file.yaml>]` → records FramingApproval (or final approval), optionally with user edits/answers; resumes the pipeline.
- `advisor resume <case-id>` → continues after interruption.
- `advisor report <case-id>` → prints the final_recommendation.md path and its content.
- `advisor list` → cases with stage and updated time.
- README run instructions (installation, one worked example) — authorized documentation deliverable of this spec.

## Out of scope

Web UI, TUI dashboards, artifact browsing beyond printing paths, multi-user concerns.

## Design

CLI is a thin adapter over case store + pipeline: parse → call → print. All output plain text (tables via string formatting); `--json` variants for status/list to keep future tooling possible. Exit codes: 0 ok, 2 user error (bad id, wrong stage for approve), 3 pipeline failure (case in FAILED with cause printed).

**Approval mechanism.** `advisor approve <case-id>` writes a `FramingApproval` artifact to the case (at `shared/framing_approval.yaml`) with the user's decision (approve | edit | answers), then sets `CaseState.framing_approved = True` (or `final_approved = True` at the final gate) and saves state, then resumes the pipeline. The state flag is what the state machine's approval-gate check reads; the artifact is the auditable record of what the user decided.

**Resume input.** A resumed case recovers its prompt from `IntakeRecord.raw_prompt`, which is the only place the user's words survive verbatim. A case therefore cannot be resumed before intake has produced one; `resume` says so rather than silently running with an empty prompt.

**Amendments made during implementation (2026-08-02).**

1. `--depth` was dropped. `Depth` has values `light|standard|deep`, not the `standard|quick` this spec named, and more importantly nothing downstream branches on it: the Director writes `DecisionSpec.depth` and no code reads it. A flag that plumbs a value nothing consumes is decoration, so effort control is `--budget-profile` alone until a stage actually varies with depth.
2. `AGENTADVISOR_CASES_ROOT` was added, and `case_store.default_cases_root()` made public, so cases can live outside the repo the same way `runtime_root()` and `memory_root()` already allow. The CLI is where a hardcoded `./cases` first becomes user-visible.
3. `tests/test_cli.py` drives `main(argv, backend=...)` in-process rather than through subprocesses, because injecting a `StubBackend` across a process boundary would require an env-var backend switch in production code. One subprocess test covers the entry point itself.

## Deliverables

- [x] `orchestrator/cli.py` + `advisor` entry point
- [x] `README.md` quickstart section
- [x] `tests/test_cli.py` (approval round trip; exit codes; entry-point subprocess check)

## Acceptance criteria

- [x] Full lifecycle via CLI with StubBackend: new → status → approve → status → approve → report, asserting printed stage/budget info matches case state at each step.
- [x] `approve` at a non-approval stage exits 2 with a clear message.
- [x] `status --json` parses and contains stage, budgets, pending approval fields.
- [x] README example commands work verbatim on the toy case.
- [x] `make check` green.

## Verification plan

```
make check
uv run pytest tests/test_cli.py -q
# manual: follow README quickstart on the toy case end to end
```

## Verification results

**2026-08-02.** `make check` green: ruff, ruff format, mypy on 58 source files, 313 unit tests (17 live deselected). `tests/test_cli.py` is 17 tests covering the full lifecycle against `PipelineStubBackend`, both approval paths, framing edits, and every exit-2 case (wrong stage, unknown id, malformed id, no report yet, resume before intake, `--edit` at the final gate).

The lifecycle test asserts state-machine agreement rather than string matching alone: after `new` the case is at `AWAITING_FRAMING_APPROVAL`, after the first `approve` at `AWAITING_FINAL_APPROVAL`, after the second at `DONE`, each read back through `load_case_state`.

Not yet done: the manual README walkthrough against live models. That is SPEC-020's first real case, which uses these commands end to end.

## Open questions

- None.
