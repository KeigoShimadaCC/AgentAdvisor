---
id: SPEC-051
title: Presence and engagement — notifications, the away digest, reactions, calibration
phase: 9
status: draft
depends_on: [SPEC-046, SPEC-047, SPEC-048]
parallel_with: [SPEC-052]
north_star_refs: ["13", "15"]
last_updated: 2026-08-05
---

# SPEC-051 — Presence and engagement: notifications, the away digest, reactions, calibration

## Summary

Everything about the user when they are not reading the screen. Runs reach 191 minutes and the
product's honest advice is "you can leave the page" — after which nothing tells anyone to come back:
no tab title, no notification, no digest on return, despite every event carrying a line cursor and
the stream accepting `since=`. This spec completes the Notification API that SPEC-035 scoped and
never built, adds a return digest, gives the user something to do while a case runs, and finally
puts the Brier calibration machinery on a screen.

## Motivation

North star Section 15 places the user outside the loop for the long middle of the engagement and
asks the platform to flag material uncertainties "only when necessary" — which presumes a channel
for flagging that does not exist. Section 13 (cost and resource principles) motivates surfacing
live spend: a run can cost 1.58M tokens and the counters in `EffortView` are visible only inside the
Method room. The calibration screen answers the review's sharpest finding: `calibration.py` is
written, tested, honest about small samples, and has never been shown to anyone.

## Scope

- `frontend/src/presence/title.ts` — document title as a progress channel: phase and position while
  running, a distinct form at a gate, restored on unmount.
- `frontend/src/presence/notify.ts` — the Notification API as SPEC-035 specified it: permission
  requested when the first case starts running, two classes (needs-you at either gate, ready at
  delivery) plus failure, deep-linking to the relevant surface, and an in-app banner fallback when
  permission is denied. Honours the watch-or-notify preference SPEC-050 captures.
- `frontend/src/presence/AwayDigest.tsx` — on return, a summary of the gap between the persisted
  cursor from SPEC-047 and the current head: evidence gathered, thesis changes, objections raised,
  gates failed and repaired, loops entered. Computed client-side from events already received.
  Suppressed entirely when nothing happened.
- Live spend in SPEC-048's chrome: invocations, tokens and wall clock against their caps from
  `EffortView`.
- `frontend/src/engagement/reactions.ts` + controls — mark an assumption "this looks wrong" or an
  objection "this one matters" as it appears; stored per case in `localStorage`; used to pre-fill
  the delivery revision note so three passive hours accumulate into a position.
- `frontend/src/screens/Calibration/Calibration.tsx` — a screen over SPEC-046's
  `GET /api/calibration`: sample size, Brier score, mean forecast versus mean realised, and the
  interpretation string rendered verbatim. An outcome prompt for decided cases, posting to the
  existing `POST /api/cases/{id}/outcome`.

## Out of scope

- **The standing note channel.** Phase 8 SPEC-043 builds a better version — a private evidence
  channel taking files from `cases/<case-id>/inputs/` and open intake questions, producing real
  evidence records with `source_type: user_document`. Phase 9 renders that in SPEC-049 and SPEC-053
  rather than adding a parallel note artifact. This spec adds **no** artifact type.
- **Building the outcome loop.** Phase 8 SPEC-042 closes it into the Brier machinery. This spec
  renders the result and drives the prompt; SPEC-053 owns the monitoring plan and the due-checks
  surface that SPEC-042's `advisor watch` exposes only on the CLI.
- Showing the issue tree *at* the scope gate. The tree is produced by `structuring`/`planning`,
  which run after `awaiting_framing_approval`; moving it earlier reorders stages and the phase
  constraint forbids it. Deferred with its reason recorded.

## Design

The digest is computed rather than stored because the data is already in the client: SPEC-047
persists a cursor and the stream replays from it, so "what happened while I was away" is a fold over
the same events the narrator consumes, using the same reducer. That keeps one source of truth for
what an event means and makes the digest a unit-testable function of a cursor range.

Reactions are deliberately client-side and terminal at the delivery gate. The alternative — writing
them into the case as they occur — would give the user a mid-run write path into a case the
single-writer discipline reserves for the worker, and phase 8 SPEC-043 already provides the
sanctioned route for user input. Pre-filling the revision note routes the same intent through the
approval mechanism that already exists.

The calibration screen renders the interpretation string verbatim rather than reformatting it,
because the honesty is in the wording: under five outcomes the module says "this is noise, not a
calibration estimate," and a UI that turned that into a confident dial would undo the property the
module was written to protect.

## Deliverables

- [ ] `frontend/src/presence/title.ts`, `notify.ts` (permission, two classes, fallback banner)
- [ ] `frontend/src/presence/AwayDigest.tsx` + its reducer-based gap computation
- [ ] Live spend in the case chrome
- [ ] `frontend/src/engagement/reactions.ts` + assumption/objection controls + revision pre-fill
- [ ] `frontend/src/screens/Calibration/Calibration.tsx` + outcome prompt
- [ ] Tests: `digest.test.ts`, `notify.test.ts`, `reactions.test.tsx`, `Calibration.test.tsx`

## Acceptance criteria

- [ ] The document title reflects phase while running and a distinct gate state on arrival, and is
      restored when the case surface unmounts.
- [ ] No notification is issued without granted permission; with permission denied the in-app
      fallback banner appears; with the watch preference selected, gate notifications are suppressed.
- [ ] The away digest computed over a cursor-gap fixture matches expected counts for evidence,
      thesis changes, objections, gates and loops; with an empty gap it is not rendered at all.
- [ ] Live spend in the chrome matches `EffortView` for invocations, tokens and wall clock, and
      shows each against its cap.
- [ ] Reactions survive a reload, are scoped per case, and appear in the delivery revision note
      pre-fill; they write nothing into the case directory.
- [ ] With fewer than five recorded outcomes the calibration screen renders the module's
      interpretation verbatim and shows no headline score as though it were meaningful; the case
      view never reads calibration.
- [ ] Axe, visual-regression and terminology-guard passes for all new surfaces;
      `make frontend-check`, `make e2e-frontend` and `make check` green;
      `tests/test_pipeline_invariants.py` passes.

## Verification plan

```
cd frontend && npm test -- presence engagement Calibration
make frontend-check && make frontend-build
E2E_MODE=replay npx playwright test --config=e2e/playwright.config.ts   # digest over a cursor gap
E2E_MODE=fixture npx playwright test --config=e2e/playwright.config.ts
make e2e-frontend
uv run pytest tests/test_pipeline_invariants.py -q
make check
```

## Verification results

Not yet executed.

## Open questions

- Notification permission timing. SPEC-035 specified "first run start"; the UX review argued the
  same moment for the same reason. Confirm no earlier prompt is wanted, since an unexplained
  permission dialog on first load is the most common way this feature is refused permanently.
