---
id: SPEC-033
title: Local web app shell — advisor ui service, SSE events, SPA scaffold, replay mode
phase: 7
status: implemented
depends_on: [SPEC-027, SPEC-032]
parallel_with: []
north_star_refs: ["15"]
last_updated: 2026-08-02
---

# SPEC-033 — Local web app shell: advisor ui service, SSE events, SPA scaffold, replay mode

## Summary

The product's runtime: a localhost FastAPI service started by `advisor ui`, exposing the REST
surface over SPEC-027's control layer and SPEC-032's projection, a server-sent-events stream fed
by tailing `audit.jsonl` through a presentation lexicon, and the Vite/React/TypeScript SPA
scaffold it serves. Includes **replay mode** — re-emitting a recorded case's audit events on
scaled timing — which is how the progress experience is developed and tested without spending a
single model token.

## Motivation

North star Section 15: the user commissions an engagement and sees "meaningful progress rather
than raw chain-of-thought." The engine's only live signal is the per-event-flushed audit log
(discovery report §4.4, §17.4); this spec turns that into the UI's nervous system. Local-first
form factor per report §17.1.

## Scope

- `orchestrator/service/app.py` — FastAPI application, bound to `127.0.0.1` only:
  - `GET  /api/cases` → `CaseSummary[]`
  - `GET  /api/cases/{id}/view` → `CaseView`
  - `GET  /api/cases/{id}/events?since=<line>` → SSE (translated event + raw payload + line
    cursor; 15 s heartbeat)
  - `GET  /api/cases/{id}/artifacts/{artifact_id}` → raw artifact as JSON + schema name
  - `GET  /api/cases/{id}/files/{path}` → read-only text passthrough (Method room), temp files
    filtered
  - `POST /api/cases` `{prompt, effort, slug?}` → `control.new_case`
  - `POST /api/cases/{id}/checkpoints/scope` `{decision, edits?, clarification_answers?,
    confirmations, summary_hash}` → `control.approve_framing` / SPEC-028 revision functions
  - `POST /api/cases/{id}/checkpoints/delivery` `{decision, note?}` → `control.approve_final` /
    `request_final_revision`
  - `POST /api/cases/{id}/pause | /resume`
  - `POST /api/cases/{id}/outcome` `{summary, followed, realized}` → the SPEC-025 outcome path
  - error model: `{error, detail, case_stage}` with correct 409 (`WrongStage`/`CaseLocked`) /
    404 / 422 mapping
- `orchestrator/service/events.py` — audit tailer (line-number cursor, survives rotation-free
  append-only file), `watchdog` watcher for task-record status flips debounced into
  `view_dirty` hints, reconnect-safe `since` replay.
- `orchestrator/service/lexicon.py` + `orchestrator/service/lexicon_data.yaml` — the
  presentation lexicon v1: one narration template per known audit `event_type` (~25) with
  slot-filling from payloads, a `technical: true` flag for Method-only events
  (`role_invocation_attempt` retries, coercion notices), and passthrough-as-technical for
  unknown types. This YAML is the single source for UI terminology of events.
- `advisor` console entry point in `pyproject.toml` → `orchestrator/cli.py` implementing only
  `advisor ui [--port] [--replay <case-dir> [--speed N]] [--cases-root PATH]`; other subcommands
  print "not yet implemented — see SPEC-019". (SPEC-019 later fills them over the same control
  layer.)
- Replay mode: serves a fixture case read-only and re-emits its audit lines on recorded
  inter-event timing × speed factor; checkpoint POSTs are disabled with a clear 409.
- `frontend/` scaffold — Vite + React + TypeScript, npm; routes per report §12.4 (library,
  decision space with room tabs, `/r/{artifact-id}` inspector); typed API client over the
  generated types; SSE client with cursor resume; two placeholder screens proving the loop
  (library list; raw CaseView inspector). Design-system tokens and real screens are
  SPEC-034–036.
- Build wiring: service serves `frontend/dist` when present; `make frontend-build`,
  `make frontend-check` (eslint + tsc), dev-mode Vite proxy documented in `frontend/README.md`.
- New dependencies (flagged for approval with this spec, per AGENTS.md): Python `fastapi`,
  `uvicorn`, `watchdog`; Node toolchain (`vite`, `react`, `typescript`, `eslint`) confined to
  `frontend/`.

## Out of scope

- The designed screens (SPEC-034 commissioning/scope, SPEC-035 brief/delivery, SPEC-036 rooms).
- Desktop notifications (SPEC-035 owns the Notification API usage).
- Any non-localhost binding, auth, TLS, or multi-user concerns.
- WebSockets (SSE is deliberate — unidirectional suffices; approvals are POSTs).

## Design

The service is a *reader* of case files and a *client* of `control.py` — it never mutates case
state directly, preserving the single-writer discipline (SPEC-027's lock). SSE cursors are audit
line numbers, so "what happened while I was away" and reconnects are the same code path, and the
audit log remains the only chronology. The lexicon lives as data (YAML), not code, because
SPEC-034–037 and the terminology system iterate on copy without touching Python. Replay is the
same event pipeline with a synthetic clock — one pipeline, three drivers (live tail, cold
catch-up, replay).

## Deliverables

- [ ] `orchestrator/service/app.py`, `events.py`, `lexicon.py`, `lexicon_data.yaml`
- [ ] `orchestrator/cli.py` (`advisor ui`) + `pyproject.toml` script entry + new deps
- [ ] `frontend/` scaffold (routes, typed client, SSE client, two proof screens, lint/tsc config)
- [ ] `make frontend-build`, `make frontend-check`; `frontend/README.md`
- [ ] `tests/test_service_api.py`, `tests/test_events.py` (httpx/ASGI, no browser)

## Acceptance criteria

- [ ] `advisor ui --cases-root tests/fixtures/cases` serves the library; `/api/cases/{fixture}/
      view` returns the SPEC-032 projection; unknown case → 404 with the error model.
- [ ] SSE with `since=0` on the fixture replays every audit event in order with monotonically
      increasing cursors; appending a line to the fixture copy's `audit.jsonl` mid-stream
      delivers the translated event within 1 s (test-driven with a temp copy).
- [ ] Every `event_type` present in the fixture's audit log has a lexicon entry that fills
      without error; an injected unknown type arrives flagged `technical`, with no raw-JSON
      narration string.
- [ ] Full stub lifecycle through HTTP only: `POST /api/cases` → poll/SSE to scope checkpoint →
      `POST checkpoints/scope` (approve) → SSE shows post-gate stages → `POST
      checkpoints/delivery` → case `done`; `framing_approval.yaml` and `final_approval.yaml`
      exist on disk.
- [ ] Checkpoint POST at the wrong stage returns 409 naming the actual stage; replay mode
      returns 409 for all POSTs.
- [ ] `--replay` emits the fixture's first events at recorded relative timing scaled by
      `--speed` (timing asserted with tolerance).
- [ ] `make frontend-check` and `make check` pass.

## Verification plan

```
uv run pytest tests/test_service_api.py tests/test_events.py -q
make frontend-check && make frontend-build
uv run advisor ui --replay tests/fixtures/cases/case-fixture-001 --speed 60   # manual smoke
make check
```

## Verification results

—

## Open questions

- New runtime dependencies (`fastapi`, `uvicorn`, `watchdog`, Node toolchain) require explicit
  user approval with this spec, per AGENTS.md's dependency rule.
