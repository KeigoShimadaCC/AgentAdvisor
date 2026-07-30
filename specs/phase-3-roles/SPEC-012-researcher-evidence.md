---
id: SPEC-012
title: Researcher role and evidence normalization
phase: 3
status: verified
depends_on: [SPEC-006]
parallel_with: [SPEC-010, SPEC-011, SPEC-013, SPEC-014, SPEC-015, SPEC-016, SPEC-017]
north_star_refs: ["6.5", "10", "8"]
last_updated: 2026-07-31
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

- [x] `cursor/roles/researcher.md`
- [x] `orchestrator/normalize.py`
- [x] `cursor/roles/researcher.yaml`
- [x] `tests/test_normalize.py` (pure fixtures), `tests/test_role_researcher.py`; live mini-run test

## Acceptance criteria

- [x] Normalization fixtures: duplicates collapse, syndicated copies share an independence_group, contradiction pair linked, stale source flagged; all deterministic (same input → byte-identical output).
- [x] Fixture replay of researcher output validates or quarantines every record; nothing enters the ledger unvalidated.
- [x] Live mini-run on a narrow factual question returns ≥1 schema-valid EvidenceRecord with url, dates, excerpt, independence_group in ≤2 attempts.
- [x] `make check` green.

## Verification plan

```
make check
uv run pytest tests/test_normalize.py tests/test_role_researcher.py -q
uv run pytest -m live -k researcher -q
```

## Verification results

**2026-07-31 — PASS.** The researcher now emits an `EvidenceBatch` (cap 8, with `no_evidence_found` as an explicit first-class outcome) rather than a single `EvidenceRecord`, matching the spec's "up to 8 records" and "no reliable evidence found is valid" requirements. `orchestrator/normalize.py` accepts `EvidenceBatch` and preserves all guarantees: URL canonicalization, near-duplicate collapse, conservative independence grouping (syndication heuristics documented in code), staleness flagging, contradiction pairing, schema re-validation gate, quarantine of rejected records with reasons. Determinism verified by running the fixture twice and comparing byte-for-byte. The live mini-run asked for the 2020 Japan census population and returned 1 schema-valid `EvidenceRecord` citing `https://www.stat.go.jp/english/data/kokusei/2020/summary/pdf/01.pdf` in ≤2 attempts. An empty `no_evidence_found=True` batch normalizes to zero records without raising, and a 9-record batch is rejected by the cap validator.

**Amendment 2026-07-31:** `cursor/roles/researcher.yaml` `output_artifact_type` changed from `evidence_record` to `evidence_batch`. `EvidenceBatch` model added to `orchestrator/artifacts/evidence.py` with `task_id`, `question`, `records`, `no_evidence_found`, `search_notes`. Batches are transport envelopes: `orchestrator/unpack.py::unpack_evidence_batch` assigns canonical `E-` IDs via `case.next_id` and writes individual records to the blackboard (see SPEC-006 amendment).

## Open questions

- ~~Live-test question choice~~ **Resolved 2026-07-31.** The live mini-run asks for the population of Japan recorded by the 2020 national census: a fixed historical statistic with an official primary source, so the answer cannot drift between runs and the assertion stays structural (schema validity, url, dates, excerpt, independence group) rather than depending on a moving value.
