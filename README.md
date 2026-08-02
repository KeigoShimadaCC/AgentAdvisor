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
- [Cursor CLI](https://cursor.com/cli) (`cursor-agent`) authenticated and on `PATH`

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
pre-mortem, adversarial challenge, repair, synthesis and review. Expect roughly an hour
and a few hundred thousand tokens for a standard case.

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

Useful flags:

- `--budget-profile small` caps a run harder than the default (15 invocations instead
  of 40). Use it for cheap experiments.
- `--edit <file.yaml>` on `approve` records framing corrections instead of a plain
  approval, so the change is auditable rather than silent.
- `--answers <file.yaml>` answers the clarification questions intake raised, as a
  mapping of `question_id` to answer.
- `--cases-root <dir>` or `AGENTADVISOR_CASES_ROOT` puts case data somewhere else.

Exit codes: `0` success, `2` your mistake (unknown case, wrong stage), `3` the pipeline
failed (the cause is printed).

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
memory/        # cross-case memory: prior cases, source reputation, calibration (gitignored)
orchestrator/  # the deterministic Python orchestrator
cursor/roles/  # agent role definitions consumed by cursor-agent at runtime
cursor/skills/ # domain specialist packs, selected per case by keyword
specs/         # spec sheets; ROADMAP.md is the live status board
benchmarks/    # benchmark decision cases used for evaluation
schemas/       # exported JSON Schemas for every artifact type
```

## Development

```bash
make check   # ruff, ruff format, mypy, pytest
make test    # unit tests only
make schemas # regenerate schemas/ from the pydantic models
```

Live tests that call real models are marked `live` and deselected by default:

```bash
uv run pytest -m live
```
