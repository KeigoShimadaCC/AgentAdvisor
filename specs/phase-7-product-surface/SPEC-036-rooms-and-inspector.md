---
id: SPEC-036
title: Rooms and record inspector
phase: 7
status: draft
depends_on: [SPEC-032, SPEC-033]
parallel_with: [SPEC-034]
north_star_refs: ["3", "10", "15"]
last_updated: 2026-08-02
---

# SPEC-036 — Rooms and record inspector

## Summary

The inspection layer behind the brief, per discovery report §13.5–13.8 and §12: five rooms —
Sources, Assumptions, Options, Challenges, Plan — plus the Method room and the record inspector
slide-over with the chain view ("pull the thread") that terminates at a highlighted source
excerpt, and the "show the machinery" raw layer. This is the product's differentiator made
navigable: the inspectable chain from any claim to its provenance.

## Motivation

North star Section 3: the differentiator is the inspectable chain; Section 10: citations sit
next to claims with provenance and independence; Section 15: the interface distinguishes sourced
fact, interpretation, user input, assumption, calculation, recommendation. All the data exists
(SPEC-032 projects it); this spec gives it its rooms.

## Scope

- `frontend/src/screens/rooms/Sources/` (§13.5): corpus header (authority mean in words,
  source-mix bar, origins count with the >40% concentration warning), filterable cards
  (question, grade, stance, flags), two-part grade chips (tier × reliability/directness),
  limitations always visible pre-expansion, cluster view (origin bubbles by share-of-corpus),
  per-question honest-empties rendering `no_evidence_found` + search notes, weakest-evidence
  callout, compact table view.
- `frontend/src/screens/rooms/Assumptions/` (§13.6): load-bearing callout (top materiality ×
  low confidence), ledger with type/status/materiality facets, for/against split bars that never
  net out, per-assumption probability as phrase+[range], skipped-question origin labels,
  unsupported-high-materiality warning surfaced from gates.
- `frontend/src/screens/rooms/Options/` (§13.7): ranked list with origin marks and per-rank
  rationale, recommended row anchored, EV bars + sensitivity/break-even summaries only where
  `AnalysisResult` exists ("modeled" badge linking the reproducible script path), eliminated-
  options coda, equal-rank grouping for duplicate ranks.
- `frontend/src/screens/rooms/Challenges/` (§13.8): fixed framing header; objections
  status-first (open always on top, never hidden) with target deep-links, reversal-evidence
  lines, commissioned-repair links; pre-mortem block in past tense with probability×severity
  chips and leading indicators cross-linked to tripwires; second-opinion panel — two position
  cards, agreement badge or side-by-side disagreement with the divergence summary, the
  never-averaged footer, and the stated-absence state when track B did not run.
- `frontend/src/screens/rooms/Plan/`: question outline (accessible indented tree with
  disclosure), per-node resolution criteria, coverage fractions ("7 of 11 questions"), struck/
  out-of-scope items, links from nodes to their tasks/evidence.
- `frontend/src/screens/rooms/Method/`: phase timeline from audit events, gate reports
  translated (check-id → plain sentence, target-id links), invocation table (role, model,
  attempts, status, tokens, duration), effort meters vs caps (SPEC-029 data), signed checkpoint
  records, thesis timeline (revision cards with paired confidence dots), raw file browser
  (SPEC-033 passthrough, YAML syntax-highlighted, schema name shown).
- `frontend/src/inspector/` — the shared record inspector slide-over for any
  `E-/A-/O-/T-/Q-/VC-` id at `/decisions/{id}/r/{artifact-id}`: typed header, full record in
  product language, chain view (what cites it / what it cites, claim → excerpt terminus),
  "show the machinery" toggle → raw YAML + relevant audit slice (via `id_mapping` join).
  Consumed by SPEC-035's thread panel.
- Room tab states: new-content markers driven by SSE; stage-aware empty states with the §12.3
  three-truths vocabulary (not yet / nothing found / cut at limit).

## Out of scope

- Any spatial/canvas rendering of the question map (outline only, per report).
- Editing or annotating records (annotations are V2).
- Cross-case views (memory surfacing beyond the digest cards' banners).
- The brief and checkpoint sheets themselves (SPEC-034/035).

## Design

Every room is a projection consumer; a source card is one shared component wherever it appears
(brief citation popover, Sources room, chain view) so grades and limitations are learned once.
The inspector is route-addressable (deep links, notification targets) and strictly one-way
deepening with breadcrumbs back to the brief. Method is the designated home for everything the
lexicon marks `technical` — the single placement rule that keeps progress from becoming logs.

## Deliverables

- [ ] five rooms + Method room
- [ ] shared inspector + chain view + raw layer
- [ ] shared source-card / assumption-card / objection-card components
- [ ] room empty/new-content states
- [ ] component tests per room over the fixture projections

## Acceptance criteria

- [ ] Sources on the reference fixture: corpus header values match `evidence_critique.yaml`
      exactly; a known incentive-flagged record (medium reliability) shows its limitation line
      unexpanded; the cluster view groups the known same-origin records; a `no_evidence_found`
      question renders its search notes.
- [ ] Challenges: all open objections render above resolved ones; the divergence fixture renders
      two positions side-by-side with the word "disagree" and no averaged number; the track-B-
      absent fixture renders the stated-absence line.
- [ ] Options: the eliminated option renders its verified elimination reason; duplicate ranks
      group as equal.
- [ ] Inspector for a known evidence id shows claim, excerpt, grades, limitations verbatim;
      machinery toggle shows the raw YAML and the audit slice containing its unpack event.
- [ ] Plan coverage fraction equals the projection's `covered/leaf` counts; tree operable
      keyboard-only.
- [ ] Every room reachable and operable keyboard-only; axe scan clean (no serious/critical) on
      all six rooms; no raw enum/schema strings in any room DOM.
- [ ] `make frontend-check` and `make check` pass.

## Verification plan

```
cd frontend && npm test -- --run
make frontend-check && make check
# manual: fixture walkthrough of each room + inspector deep links
```

## Verification results

—

## Open questions

- None.
