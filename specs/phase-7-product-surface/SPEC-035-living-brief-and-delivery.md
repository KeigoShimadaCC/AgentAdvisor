---
id: SPEC-035
title: Living brief, progress experience, and delivery checkpoint UI
phase: 7
status: verified
depends_on: [SPEC-029, SPEC-030, SPEC-031, SPEC-034, SPEC-036]
parallel_with: []
north_star_refs: ["9", "15", "16"]
last_updated: 2026-08-03
---

# SPEC-035 — Living brief, progress experience, and delivery checkpoint UI

## Summary

The case's center of gravity, per discovery report §13.3 and §13.9: the brief that assembles
itself from real artifacts during the run (skeleton sections, settle-in on arrival, margin
narration from the event stream, Method strip with phases and honest time ranges, leave-safely
affordance and the two notification classes), and the delivery checkpoint — the answer card
carrying the four uncertainty measures in four distinct encodings, the integrity slip, the
tripwires, the full §16-ordered brief, and the accept / send-back-once signature. Also the
disclosed early-stop, failed-run, and interrupted-run renderings of the same route.

## Motivation

North star Section 15 step 5 ("meaningful progress rather than raw chain-of-thought") and
Section 16 (the report format); Section 9's four-measure discipline made visual. The honesty
machinery this screen renders — `review_accepted`, disclosure records, effort counters,
not-assessed sentinels — is exactly what SPEC-029/030/031 made real.

## Scope

- `frontend/src/screens/Brief/` — one state-aware route rendering all case states:
  - skeleton with honest placeholders per pending section (section list and order from
    `CaseView.brief`);
  - live assembly: sections move `pending → partial → final` on SSE, with a 200–300 ms settle
    animation (disabled under `prefers-reduced-motion`), scroll position preserved
    (new-content pills, never scroll-jacking);
  - margin narration: non-`technical` lexicon events as timestamped cards, expandable to the
    artifacts they cite; retries and coercion events never appear here;
  - working-view card: thesis revisions as discrete change cards ("the working view changed —
    see why" with changed-because links), carrying the engine's NON-FINAL stamp; **no live
    numeric estimate anywhere mid-run**;
  - Method strip: six phases with states, elapsed time, coarse expected ranges (from recorded
    per-phase medians in a static table), "nothing needs you / needs you" line, leave-safely
    explainer;
  - sealed answer card during synthesis/review ("drafting and independently checking…").
- `frontend/src/screens/Delivery/` — the delivery sheet:
  - answer card: recommended action + timing; the four measures as the four house widgets —
    probability phrase+[range] band with countable-dots popover; 5-step labeled confidence bands
    with basis text; source-strength grade with mix bar; k-of-n stability dots — with the
    `NotAssessed` variants rendering the not-assessed state (never a number); ≤4 key reasons
    with citation chips; tripwires ("this advice expires if…");
  - integrity slip, non-collapsible below one line: review verdict from `review_accepted` +
    defects, open high-materiality objections, disclosure record ("stopped early — not
    investigated: …"), not-assessed inventory;
  - the full brief below in canonical section order with provenance stripes (six labels), every
    claim's citation chips opening the thread panel (claim → evidence records with grades →
    excerpt terminus — inspector internals are SPEC-036's component, consumed here);
  - signature: Accept (writes `FinalApproval`), Send back with a note (SPEC-028; disabled with
    the reason once spent); signed record rendered at `/decisions/{id}/delivery`;
  - export: download the deterministic Markdown; print stylesheet for PDF.
- Notifications: Notification API with permission prompt at first run start; two classes —
  *needs-you* (gate reached, interrupted) and *ready* (delivery) — deep-linking to the sheet;
  in-app fallback banner when permission is denied.
- Failure-path renderings on the brief route: `failed` (cause + retry-phase CTA), disclosed
  early stop (accept-as-is vs extend framing), interrupted (resume CTA via SPEC-030 path).

## Out of scope

- Rooms' internals and the inspector implementation (SPEC-036; this spec consumes the thread
  panel as a component).
- Margin Q&A on the brief (V2 per the report).
- Outcome-recording UI (V2; the API endpoint exists).
- Any streaming-granularity work beyond the audit event cadence.

## Design

The brief renders exclusively from `CaseView` + SSE — it never fetches raw artifacts, so its
honesty is exactly the projection's honesty. The four widgets are one shared component library
(`frontend/src/uncertainty/`) with a single fixed probability vocabulary table; no other
component may render a probability, confidence, or stability value — the collapse defect is
prevented by module boundary, not convention. ETAs come from a static measured-medians table
shipped with the app (updated by hand from evaluation data), displayed only as ranges.

## Deliverables

- [x] `frontend/src/screens/Brief/` (all states incl. failure paths)
- [x] `frontend/src/screens/Delivery/` + signed-record view
- [x] `frontend/src/uncertainty/` widget library (the four encodings + not-assessed states)
- [x] notification wiring + in-app fallback
- [x] export (Markdown download, print stylesheet)
- [x] component tests: widget rendering incl. sentinel variants, narration filtering, scroll
      preservation logic, signature gating

## Acceptance criteria

- [x] Under replay of the reference fixture, brief sections appear in artifact order — a section
      never renders `final` before its artifact's event — and the margin shows only
      non-technical narration (assert absence of retry/coercion strings).
- [x] The fixture's stability sentinel renders as "not assessed" in the answer card; the string
      "0.0%" appears nowhere; the confidence widgets show their basis text.
- [x] The integrity slip on the fixture (failing review) leads with the reviewer's verdict and
      lists the undisclosed-objection defects; it renders before the full brief in DOM order.
- [x] Accepting on a stub case writes `outputs/final_approval.yaml` and flips the UI to the
      signed state without reload; send-back is possible exactly once, then disabled with the
      reason shown.
- [x] With `prefers-reduced-motion`, no settle animation plays (computed-style assertion);
      scroll position is preserved when a section is inserted above the viewport (unit-tested
      logic).
- [x] Both screens pass axe with no serious/critical violations; the four widgets expose the
      specified text equivalents to assistive tech.
- [x] `make frontend-check` and `make check` pass.

## Verification plan

```
cd frontend && npm test -- --run
uv run advisor ui --replay tests/fixtures/cases/case-fixture-001 --speed 60   # manual: assembly, narration, sealed card
make frontend-check && make check
```

## Verification results

- 2026-08-03 documentation sync from current evidence and Phase 7 findings in
  `specs/ROADMAP.md`: SPEC-035 is included in the verified closure of the browser product surface.
- Frontend validation is green: `make frontend-check` (`tsc --noEmit`, generated-types drift
  check clean, 71 frontend unit tests in 13 files) and `make check` (ruff + mypy + 716 Python
  unit tests).
- Browser verification ran under SPEC-037 using fixture/stub/replay modes; 35 chromium Playwright
  tests passed (fixture 24, stub 5, replay 6), including delivery/brief rendering and integrity
  presentation checks called out in the Phase 7 findings.
- ROADMAP Phase 7 Findings records that delivery checkpoint behavior includes the four
  never-collapsed uncertainty encodings and that the SPEC-037 real-browser sweeps closed defects
  that unit tests alone could not surface.

## Open questions

- Whether the working-view card shows the provisional preferred option mid-run or only its
  existence (report §21 Q3) — default to showing option + NON-FINAL stamp; flag for usability
  testing.
