---
id: SPEC-019
title: User CLI
phase: 4
status: draft
depends_on: [SPEC-018]
parallel_with: []
north_star_refs: ["15"]
last_updated: 2026-07-30
---

# SPEC-019 — User CLI

## Summary

The user-facing command surface: start a case, see progress, answer approval gates, resume, and read the report. A new decision must require a prompt and configuration only, never code edits (DoD D).

## Motivation

North star Section 15: commissioning a consulting engagement, not operating an agent framework; meaningful progress over raw transcripts.

## Scope

`orchestrator/cli.py`, exposed as `advisor` via `pyproject.toml` script entry (stdlib argparse):

- `advisor new "<decision prompt>" [--slug s] [--budget-profile default|small] [--depth standard|quick]` → creates case, runs to the first halt (usually AWAITING_FRAMING_APPROVAL), prints case id and what is awaited.
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

## Deliverables

- [ ] `orchestrator/cli.py` + `advisor` entry point
- [ ] `README.md` quickstart section
- [ ] `tests/test_cli.py` (subprocess invocations against a stubbed pipeline; approval round trip; exit codes)

## Acceptance criteria

- [ ] Full lifecycle via CLI with StubBackend: new → status → approve → status → approve → report, asserting printed stage/budget info matches case state at each step.
- [ ] `approve` at a non-approval stage exits 2 with a clear message.
- [ ] `status --json` parses and contains stage, budgets, pending approval fields.
- [ ] README example commands work verbatim on the toy case.
- [ ] `make check` green.

## Verification plan

```
make check
uv run pytest tests/test_cli.py -q
# manual: follow README quickstart on the toy case end to end
```

## Verification results

—

## Open questions

- None.
