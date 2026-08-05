# Decision Intelligence Platform

A personal multi-agent system that turns an imperfectly defined decision ("Should I buy
Nvidia or a semiconductor ETF?") into a recommendation with explicit uncertainty and an
inspectable chain from objectives to conclusion.

It behaves like a small consulting team: it frames the question, decomposes it, gathers
evidence, models the numbers, argues against itself, and only then recommends. It is not
a search assistant and not a multi-agent chat room.

Read [`decision_intelligence_north_star.md`](decision_intelligence_north_star.md) for the
product and architecture direction, and [`AGENTS.md`](AGENTS.md) if you are writing code
here.

## What you get

Every case produces a `final_recommendation.md` backed by typed artifacts on disk: the
evidence records with sources and limitations, the assumptions the reasoning rests on,
the objections raised against it, the quantitative scenarios, and an audit log of every
agent invocation. A finished case is auditable from its files alone.

Four kinds of uncertainty are tracked separately and never collapsed into one number:
outcome probability, evidence confidence, recommendation confidence, and model stability.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- An agent CLI backend, authenticated and on `PATH` — either the
  [Cursor CLI](https://cursor.com/cli) (`cursor-agent`, the default) or the Factory
  [Droid CLI](https://factory.ai) (`droid`, select with `--backend droid` or
  `AGENTADVISOR_BACKEND=droid`)
- Node.js and npm, only if you use the web UI (`advisor ui`)

## Install

```bash
uv sync --group dev
```

That puts the `advisor` command in `.venv/bin`. Either activate the environment or
prefix commands with `uv run`.

## Quickstart

Start a case. The system runs intake and framing, then stops and asks you to confirm
that it understood the decision:

```bash
uv run advisor new "I have \$50,000 and want semiconductor exposure. Should I buy Nvidia now, buy a semiconductor ETF, or wait for the next earnings report?" --slug semis
```

```
Created case-001-semis at /path/to/cases/case-001-semis
Case case-001-semis is waiting for framing approval.
  Review: /path/to/cases/case-001-semis
  Then:   advisor approve case-001-semis
```

Read the framing it produced in `cases/case-001-semis/shared/decision_spec.yaml`, then
approve it:

```bash
uv run advisor approve case-001-semis
```

The pipeline now runs unattended for a while: structuring, provisional thesis, planning,
investigation, evidence critique, assumption ledger, preliminary recommendation,
pre-mortem, adversarial challenge, repair, synthesis and review. Expect a few hours and
one to two million tokens for a standard case (the first verified real case took
1.58M tokens and 191 minutes over 45 invocations on the droid backend).

Check on it at any time:

```bash
uv run advisor status case-001-semis
```

```
Case:    case-001-semis
Stage:   investigation
Updated: 2026-08-02T11:04:18+00:00
Tasks:   completed 6, active 2, planned 2
Records: 15 evidence, 0 objections
Budget:
  agent_invocations    18 / 40
  high_tier_calls      0 / 6
  research_tasks       8 / 15
  repair_cycles        0 / 2
```

When it finishes it stops once more, at the final approval gate. Approve it and read the
report:

```bash
uv run advisor approve case-001-semis
uv run advisor report case-001-semis
```

## Commands

| Command | What it does |
|---|---|
| `advisor new "<prompt>" [--slug s]` | Create a case and run it to the first gate |
| `advisor status <case-id> [--json]` | Stage, task counts, budget consumption, pending gate |
| `advisor approve <case-id>` | Clear the gate the case is waiting on and continue |
| `advisor resume <case-id>` | Continue a case interrupted mid-stage |
| `advisor report <case-id>` | Print the final recommendation |
| `advisor list [--json]` | Every case with its stage |
| `advisor watch [<case-id>] [--due]` | Monitoring checks that have come due |
| `advisor check <case-id> <M-nnn> --observed "..." [--breached]` | Record an observation |
| `advisor ui [--port p]` | Serve the local web UI (see below) |

Useful flags:

- `--backend {cursor,droid}` on `new` picks the agent CLI that roles run on
  (default: `AGENTADVISOR_BACKEND`, else `cursor`).
- `--budget-profile small` caps a run harder than the default (15 invocations instead
  of 40). Use it for cheap experiments.
- `--edit <file.yaml>` on `approve` records framing corrections instead of a plain
  approval, so the change is auditable rather than silent.
- `--answers <file.yaml>` answers the clarification questions intake raised, as a
  mapping of `question_id` to answer.
- `--input <file>` on `new` (repeatable) hands the case a document about the decision
  itself — an offer letter, a term sheet, a vendor quote. See below.
- `--cases-root <dir>` or `AGENTADVISOR_CASES_ROOT` puts case data somewhere else.

Exit codes: `0` success, `2` your mistake (unknown case, wrong stage), `3` the pipeline
failed (the cause is printed).

## Web UI

The same cases can be driven from a local web app: each case is a living advisory
brief with two signed checkpoint sheets (scope and delivery), five inspection rooms
(sources, assumptions, options, challenges, method), and the four uncertainty measures
in four distinct encodings.

```bash
uv run advisor ui            # FastAPI service + SSE on :8765
cd frontend && npm install && npm run dev   # SPA on http://localhost:5173
```

See [`frontend/README.md`](frontend/README.md) for the dev setup, replay mode (re-watch
a recorded case at scaled speed, zero tokens), and the Playwright e2e suite.

## Your own documents

Public research alone cannot see the decision's own paperwork, and the numbers that
usually decide a personal case live there. Drop markdown or plain-text files into
`cases/<case-id>/inputs/`, or pass them at creation:

```bash
uv run advisor new "Should I accept this offer?" --input ~/offer.md --slug offer
```

They are read at intake and become evidence records like any other, with three
differences: their `source_type` is `user_document`, every excerpt from one file shares
one independence group (so two quotes from your offer letter are never corroboration),
and they are scored `unverifiable` rather than placed on the public-source authority
ladder. A conclusion resting only on them is flagged in the report.

Private evidence reaches the roles that reason about the decision and is withheld from
the ones that check the reasoning — a reviewer anchored on your own material is not
independent. It also stays inside its own case and never enters cross-case memory.

**Supplied documents are sent to whichever agent CLI backend the case runs on.** Text
formats only for now; other files are reported and skipped rather than silently ignored.

## After delivery

A finished case leaves a monitoring plan: the pre-mortem's leading indicators and the
recommendation's change triggers, each with an observable, a breach threshold and a check
cadence, paired with the pre-mortem's preventive actions as a register of prepared
responses. It lives in `memory/monitoring/` and outlives the case.

```bash
uv run advisor watch --due
uv run advisor check case-001-semis M-001 --observed "Q3 growth 3.1%, Q4 4.2%" --breached
```

A breach prints the responses linked to that indicator and recommends opening a **new**
case. Delivered cases stay terminal: a decision made under different conditions is a
different decision, and reopening one would corrupt the audit chain the product rests on.

## Recording what actually happened

The only honest check on the system's probabilities is whether they came true. When you
learn the outcome of a past decision, record it:

```bash
uv run python scripts/record_outcome.py --list
uv run python scripts/record_outcome.py \
  --case-id case-001-semis \
  --summary "Bought the ETF; up 11% at the 12-month mark." \
  --followed --realized
```

Recorded outcomes feed a Brier score that later cases see, so the system knows whether
it has been running optimistic or pessimistic.

## Where things live

```
cases/         # case blackboards: artifacts, state, audit log (gitignored)
memory/        # cross-case memory: prior cases, reputation, calibration, monitoring (gitignored)
orchestrator/  # the deterministic Python orchestrator (incl. service/ for the web API)
frontend/      # the web UI: React SPA, generated types, Playwright e2e suite
backends/      # per-backend model configuration (e.g. backends/droid/models.yaml)
cursor/roles/  # agent role definitions consumed by the agent CLI at runtime
cursor/skills/ # domain specialist packs, selected per case by keyword
specs/         # spec sheets; ROADMAP.md is the live status board
benchmarks/    # benchmark decision cases used for evaluation
schemas/       # exported JSON Schemas for every artifact type
scripts/       # smoke tests, benchmark runners, outcome recording, case metrics
tests/         # unit tests and committed fixture cases
```

## Development

```bash
make check          # ruff, ruff format, mypy, pytest
make test           # unit tests only
make schemas        # regenerate schemas/ from the pydantic models
make frontend-check # tsc, generated-type drift check, frontend unit tests
make e2e-frontend   # Playwright e2e suite (fixture, stub, replay modes)
```

Live tests that call real models are marked `live` (plus `live_slow` for long runs) and
deselected by default:

```bash
uv run pytest -m "live or live_slow"
```
