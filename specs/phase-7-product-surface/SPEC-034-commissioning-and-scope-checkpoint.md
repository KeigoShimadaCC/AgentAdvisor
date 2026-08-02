---
id: SPEC-034
title: Commissioning flow and scope checkpoint UI
phase: 7
status: draft
depends_on: [SPEC-028, SPEC-033]
parallel_with: [SPEC-036]
north_star_refs: ["8", "14", "15"]
last_updated: 2026-08-02
---

# SPEC-034 — Commissioning flow and scope checkpoint UI

## Summary

The product's opening act, per discovery report §13.1–13.2: the new-decision entry (one large
prompt, effort choice, example chips, the method promise line), the interview cards that finally
deliver the intake role's clarification questions to a human, and the scope checkpoint sheet —
restatement, options with origin marks, strikeable investigation outline, per-item ground-rule
confirmations, effort disclosure, and a signature block that becomes a permanent part of the
case record. No schema vocabulary, no YAML, no auto-proceed.

## Motivation

North star Section 15 steps 1–4 verbatim; Section 14 makes approval a real consent act. Every
run to date auto-approved this gate; the clarification questions have never been asked
(discovery report §4.6). This screen is where the product's trust sequence starts ("it
understood me / it asks smart questions").

## Scope

- `frontend/src/screens/NewDecision/` — entry screen per §13.1: prompt input, effort selector
  (Quick look / Standard / Deep dive, labeled with honest time ranges; maps to SPEC-029
  profiles), example chips from the five benchmark domains, the one-line method promise
  including the not-licensed-advice disclaimer; POST create → inline restatement beat.
- `frontend/src/screens/NewDecision/InterviewCards.tsx` — one card per `ClarificationQuestion`:
  plain-language question, translated materiality reason, quick-answer chips + free text, and
  "Skip — assume something reasonable" which visibly labels the resulting declared assumption.
- `frontend/src/screens/ScopeCheckpoint/` — the sheet per §13.2:
  - decision restatement (editable prose → `edits.question`),
  - options list with origin marks (yours / added-by-analysis), remove/annotate/add
    (→ `edits.alternatives`),
  - investigation outline from the issue tree...* (see design note), strikeable
    (→ `edits.excluded_questions`), each with its resolution criteria behind ⓘ,
  - ground rules as individually confirmable items (deadline, risk tolerance, reversibility;
    assumed-because-skipped values marked and editable),
  - effort & limits disclosure, what-it-can't-do block,
  - signature block: "Sign & begin" (primary), "Save and decide later" (parks), plus the
    revision path — submitting edits routes through SPEC-028's `request_framing_revision` and
    re-presents the revised sheet.
  - The signed record (who, when, what changed, `summary_hash` of the rendered sheet content)
    posts to the scope checkpoint endpoint and later renders read-only at `/decisions/{id}/scope`.
- Parked/needs-you rendering in library cards and brief header funneling into the sheet
  (report §13.4), including the do-nothing consequence line.
- Copy sourced exclusively from the terminology lexicon (report §14): a `frontend/src/copy/`
  module consuming shared term tables; zero raw stage/role/enum strings.
- Keyboard-complete and screen-reader-labeled per report §16 (this spec's screens only).

\* The outline shown at the sheet is the *planned* decomposition. Because structuring runs after
the gate, v1 shows the framing spec's objectives/alternatives plus "what I'll investigate" as
the broadened question list from the decision spec; once STRUCTURING completes, the Plan room
(SPEC-036) shows the real tree. The sheet's copy must not promise node-level fidelity it doesn't
have. (Recorded as the one deliberate divergence from the report's wireframe, which showed the
full tree at the gate.)

## Out of scope

- The living brief and delivery sheet (SPEC-035); rooms (SPEC-036).
- Notifications (SPEC-035).
- Mobile-specific optimizations beyond responsive reflow of these screens.
- Any framing content generation change (engine side is SPEC-028).

## Design

The sheet is a full-focus route, not a modal; the case parks indefinitely (no timers, no
default-checked confirmations). All user input serializes into the existing `FramingApproval`
payload shapes: prose edits into `edits`, answers into `clarification_answers`, per-item
confirmations into the checkpoint POST's `confirmations` list (persisted by the service into the
approval artifact's payload so the consent moment is reconstructable). Skipped questions become
visibly-declared assumptions in copy — the engine already attributes defaults as its own; the UI
mirrors that honestly.

## Deliverables

- [ ] `frontend/src/screens/NewDecision/` (entry + interview cards)
- [ ] `frontend/src/screens/ScopeCheckpoint/` (sheet, signed-record view, parked states)
- [ ] `frontend/src/copy/` terminology tables wired to both screens
- [ ] component tests (Vitest + Testing Library) for card logic, confirmation gating, payload
      assembly; API-integration tests against the stub-backed service

## Acceptance criteria

- [ ] From a clean service (stub backend), a decision created in the browser reaches the scope
      sheet showing the restatement and the real `IntakeRecord` clarification questions with
      materiality reasons; a skipped question renders the declared-assumption label.
- [ ] "Sign & begin" is disabled until every ground-rule item is individually confirmed; signing
      writes `shared/framing_approval.yaml` whose payload contains the confirmations and
      `summary_hash`, and the UI transitions to the running state via SSE without reload.
- [ ] Striking a question and signing routes through the framing-revision path: the sheet
      re-presents with a revised spec (stub), and `framing_revisions == 1` on disk.
- [ ] No string from `CaseStage`, `TaskRole`, or artifact schema field names appears in the
      rendered DOM of either screen (automated assertion over a served page).
- [ ] Both screens pass an axe scan with no serious/critical violations and are fully operable
      keyboard-only (component test walks the sign path by keyboard).
- [ ] `make frontend-check` and `make check` pass.

## Verification plan

```
cd frontend && npm test -- --run
uv run pytest tests/test_service_api.py -q          # checkpoint payload round-trip
make frontend-check && make check
```

## Verification results

—

## Open questions

- None (the gate-time outline fidelity divergence is recorded in Scope).
