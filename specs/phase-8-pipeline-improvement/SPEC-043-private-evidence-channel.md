---
id: SPEC-043
title: Private evidence channel (text first cut)
phase: 8
status: draft
depends_on: []
parallel_with: [SPEC-038, SPEC-039, SPEC-041, SPEC-042]
north_star_refs: ["5.7", "7", "8", "10"]
last_updated: 2026-08-04
---

# SPEC-043 — Private evidence channel (text first cut)

## Summary

Lets the decision's own documents into the case. A user drops markdown or plain-text files into
`cases/<case-id>/inputs/`; a deterministic ingestion step turns them into evidence records with
`source_type: user_document`, correct provenance semantics, and isolation from the review roles.
Deliberately scoped to text formats so it adds no dependencies and proves the seam before the
binary-format work is specced.

## Motivation

North star Section 8, Stage 1 lists "available internal information" among the things intake must
extract. Nothing in the system implements it. The entire input surface is one prompt string plus at
most five clarification answers constrained to eight enum fields, so the system researches the
public web *around* a decision while remaining blind to the decision's own documents — the offer
letter, the term sheet, the vendor quote, the current spend.

This is the largest single divergence from professional practice, where an engagement's input is
dominated by client-internal material, and it is the change that most improves every downstream
stage at once: the analyst finally models real numbers instead of public proxies.

## Scope

- `orchestrator/artifacts/common.py` — `SourceType.USER_DOCUMENT`.
- `orchestrator/artifacts/intake.py` — `IntakeField.INTERNAL_INFORMATION`, and a relaxation of
  `validate_clarifications_target_unknown_fields` so a clarification may request a document.
- `orchestrator/ingest.py` — read `cases/<case-id>/inputs/*.{md,txt}`, split into excerpt-sized
  chunks, mint `E-` ids through the existing `unpack` path, write to the evidence ledger.
- `orchestrator/evidence_critic.py` — a `user_document` branch: `directness` high, authority tier
  `unverifiable`, and exclusion from independent-corroboration counting.
- `orchestrator/memory.py` — exclude `user_document` records from domain-keyed source reputation.
- `orchestrator/normalize.py` — `independence_group` of `user_document:<filename>`, so two excerpts
  from one document are never treated as two independent sources.
- `orchestrator/projection.py` — include key `private_evidence`, wired into researcher, analyst,
  director, director-b, structurer, premortem and assumption_analyst — and **not** into reviewer,
  reviewer-b or auditor.
- `orchestrator/workspace.py` — assert private evidence never reaches an excluded role's workspace.
- `orchestrator/gates.py` — `evidence.sole_private_support` when a material claim's only support is
  a user document.
- `cursor/roles/intake.md`, `researcher.md`, `analyst.md` — how to request and treat private evidence.
- `orchestrator/cli.py` — `advisor new --input <path>` copying files into the case before the run.
- `README.md` — document the `inputs/` convention.

## Out of scope

- **PDF, xlsx and docx parsing.** These require new dependencies, which `AGENTS.md` says need user
  sign-off, and the parsing quality question deserves its own spec once the seam is proven.
- An HTTP upload endpoint in `service/app.py`. v1 is filesystem-only.
- Encryption at rest, redaction, or PII detection.
- Sending private evidence to any backend other than the one already configured for the case.

## Design

**Provenance route: synthesized `file://` URLs.** `EvidenceRecord` requires `source_url`,
`publisher` and `publication_date`, and those fields are load-bearing in `normalize.py`,
`citations.py`, `evidence_critic.py`, `gates.py` and `memory.py`. Two alternatives were considered
and rejected: making them optional weakens validation for *all* evidence and breaks domain-keyed
source reputation; a separate `PrivateEvidenceRecord` model would have to be unioned at seventeen
consumer modules. Instead ingestion synthesizes `source_url: file://inputs/<filename>`,
`publisher: user-supplied`, and `publication_date` from the file mtime unless the user states one.
The model is untouched; the two modules that would be misled — `evidence_critic.py` and
`memory.py` — special-case `SourceType.USER_DOCUMENT` explicitly.

This is a deliberate trade: it keeps the change additive at the cost of two special cases, which are
tested and named rather than implicit.

**Chunking.** A document is split on markdown headings, falling back to paragraph groups, capped so
that a single record's `excerpt` stays within the projection character budget. Each chunk records
its source filename and heading path, so a citation points at a location a human can find.

**Isolation is the security-relevant part.** Private documents must reach the roles that reason
about the decision and must not reach the roles that check the reasoning — both because a reviewer
anchored on private material is not independent, and because narrowing the blast radius of personal
data is worth doing by construction. `assert_isolated` gains a check that no excluded role's
workspace contains a `private_evidence` projection.

**A decision the user should make explicitly:** private documents will be written into agent
workspaces and sent to a third-party CLI backend (Cursor or Droid). This spec does not change that
posture for public evidence, but it materially changes what is at stake. Flagged here rather than
buried.

## Deliverables

- [ ] `SourceType.USER_DOCUMENT` and `IntakeField.INTERNAL_INFORMATION`
- [ ] `orchestrator/ingest.py` with chunking and id minting
- [ ] `evidence_critic.py` and `memory.py` special cases
- [ ] `private_evidence` projection key with role allow-list
- [ ] `workspace.py` isolation assertion
- [ ] `evidence.sole_private_support` gate check
- [ ] `advisor new --input` and README documentation
- [ ] `tests/test_ingest.py` and an isolation test
- [ ] Regenerated `schemas/` and `frontend/src/generated/`

## Acceptance criteria

- [ ] `make check` and `make frontend-check` are green.
- [ ] A markdown file in `inputs/` produces evidence records with `source_type: user_document`,
      `file://` URLs, and an `independence_group` shared across all chunks of that file.
- [ ] Two chunks from one document do not count as two independent sources, asserted against the
      independence-clustering output.
- [ ] The evidence critique scores a user document as `unverifiable` authority and does not count it
      toward corroboration.
- [ ] `memory.py` records no source reputation entry for a `file://` URL.
- [ ] A test asserts the reviewer, reviewer-b and auditor workspaces contain no private evidence,
      and the analyst and director workspaces do.
- [ ] A material claim supported only by a user document produces exactly one
      `evidence.sole_private_support` finding.
- [ ] A case with an empty `inputs/` directory behaves identically to the pre-change pipeline.
- [ ] `advisor new --input <file>` copies the file and the run cites it.

## Verification plan

`make check`, `uv run pytest tests/test_ingest.py -v`, a stub pipeline run with a seeded `inputs/`
directory, an isolation check via the existing `assert_isolated` harness, and one live
`--budget-profile small` case using a synthetic offer letter, inspecting whether the analyst's model
actually uses the private figures.

## Verification results

Not yet executed.

## Open questions

- Should ingestion run before framing (so the framing director sees the documents) or after? Proposal:
  before, since a term sheet frequently changes what the decision even is.
- Does the user accept private documents being sent to the configured third-party CLI backend? This
  must be answered before the spec moves to `approved`.
