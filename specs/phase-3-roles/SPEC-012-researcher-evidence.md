---
id: SPEC-012
title: Researcher role and evidence normalization
phase: 3
status: draft
depends_on: [SPEC-006]
parallel_with: [SPEC-010, SPEC-011, SPEC-013, SPEC-014, SPEC-015, SPEC-016, SPEC-017]
north_star_refs: ["6.5", "10", "8"]
last_updated: 2026-07-30
---

# SPEC-012 — Researcher role and evidence normalization

## Summary

Temporary researcher workers that return structured evidence records with full provenance, plus the deterministic normalization pass that deduplicates sources, assigns independence groups, and flags contradictions before anything reaches the Director.

## Motivation

North star Section 10: provenance is part of the product; ten articles from one press release are one source. Stage 5: normalization is partly deterministic, never left to agent discretion.

## Scope

- `cursor/roles/researcher.md`: answer exactly the assigned question; prefer primary sources (Section 10 source order); emit `EvidenceRecord`s (≤8 per task) with every provenance field, explicit limitations, and contradicting evidence recorded rather than discarded; prose essays prohibited; "no reliable evidence found" is a valid, schema-conformant outcome.
- Web access: researcher relies on Cursor's built-in web search tooling; each record must carry source_url and retrieval date.
- `orchestrator/normalize.py` (pure, no model calls): URL canonicalization + near-duplicate collapse; independence-group assignment (same publisher/domain or same canonical origin → same group; syndication heuristics documented in code); staleness flags (publication_date older than a per-question threshold); contradiction pairing (opposing claims on the same assumption linked); schema re-validation gate into `shared/evidence/`.
- `cursor/roles/researcher.yaml` (Cursor-pool model per the research report; projection: decision spec excerpt + assigned task + related existing evidence IDs only).
- Fixtures: raw researcher outputs including duplicates, syndicated copies, a contradiction, and a stale source.

## Out of scope

MCP-based search tooling (ROADMAP emergent candidate), citation verification against live sources (SPEC-017 reviewer scope), assumption updates (Director, SPEC-014).

## Design

Normalization runs on every researcher batch before blackboard write; rejected records are quarantined in the agent workspace with reasons, never silently dropped. Independence grouping is intentionally conservative: uncertain independence collapses into the same group (understates, never overstates, source diversity).

## Deliverables

- [ ] `cursor/roles/researcher.md`
- [ ] `orchestrator/normalize.py`
- [ ] `cursor/roles/researcher.yaml`
- [ ] `tests/test_normalize.py` (pure fixtures), `tests/test_role_researcher.py`; live mini-run test

## Acceptance criteria

- [ ] Normalization fixtures: duplicates collapse, syndicated copies share an independence_group, contradiction pair linked, stale source flagged; all deterministic (same input → byte-identical output).
- [ ] Fixture replay of researcher output validates or quarantines every record; nothing enters the ledger unvalidated.
- [ ] Live mini-run on a narrow factual question returns ≥1 schema-valid EvidenceRecord with url, dates, excerpt, independence_group in ≤2 attempts.
- [ ] `make check` green.

## Verification plan

```
make check
uv run pytest tests/test_normalize.py tests/test_role_researcher.py -q
uv run pytest -m live -k researcher -q
```

## Verification results

—

## Open questions

- Live-test question choice should be cheap and stable (e.g., a public statistic); finalize at approval.
