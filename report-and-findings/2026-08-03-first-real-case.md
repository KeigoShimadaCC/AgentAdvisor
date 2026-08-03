# SPEC-020 — First real decision case (findings)

**Date:** 2026-08-03
**Case:** `case-014-career-startup-pivot` (local only, gitignored)
**Backend:** Droid CLI (`droid exec`), `AGENTADVISOR_BACKEND=droid`
**Budget profile:** small (`max_agent_invocations=15` per the ledger's invocation counter; wall-clock cap 3600s not enforced as a hard kill)

## Decision context

An investment-style, capital-allocation-under-uncertainty decision with an irreversible
component: whether to leave a stable senior engineering role for a founding-engineer seat at a
Series B AI-infrastructure startup, taking a cash pay cut in exchange for an equity grant. This is
the decision character SPEC-020 selected (career/compensation, benchmark scenario 04 shape). The
prompt and dollar figures are illustrative and local; nothing here is sensitive personal data.

## Outcome

The case ran the full Section 8 workflow end to end and reached `done` (via the final approval
gate) with **no manual state surgery**. The workflow produced a complete, well-structured
recommendation: negotiate cash compensation before joining, with a lower-commitment trial as the
fallback if renegotiation fails. The four uncertainty measures are reported as distinct quantities
(recommendation confidence 55%, evidence confidence 45%, model stability 100% (3/3), outcome
probabilities 65%/35%), and material claims carry resolvable `E-`/`A-` citations.

**Important caveat:** the calibration/citation **review failed on both attempts** (initial +
the one permitted synthesis retry). The recommendation was surfaced anyway under the documented
"done ≠ review-passed" path, with the failure disclosed. See defects below.

## Metrics

| Metric | Value |
|---|---|
| Wall clock | 191 min |
| Invocations | 45 attempts, 32 ok (71%), 12 retries |
| Tokens | 1,576,002 total (774,014 in / 801,988 out) |
| Records produced | 19 evidence, 4 assumptions, 7 objections |
| Repair cycles | 2 |
| Synthesis retries | 1 (max) |
| Review outcomes | fail, fail |
| Dual track | skipped |
| Thesis revisions | 4 (0 changed the preferred alternative) |
| Stop decisions | continue, continue, continue |

### Per-role usage

| Role | Att | OK | Rate | Tokens | Time | Model |
|---|---|---|---|---|---|---|
| researcher | 10 | 7 | 70% | 574,091 | 20.9m | gpt-5.4 (+1) |
| analyst | 7 | 6 | 86% | 340,273 | 69.2m | claude-sonnet-5 |
| director | 8 | 5 | 62% | 224,398 | 20.9m | gpt-5.4 (+1) |
| synthesizer | 4 | 2 | 50% | 125,721 | 26.2m | claude-sonnet-5 |
| structurer | 3 | 1 | 33% | 72,094 | 8.3m | claude-sonnet-5 (+1) |
| reviewer | 2 | 2 | 100% | 67,361 | 4.5m | gpt-5.4 |
| premortem | 1 | 1 | 100% | 50,514 | 1.8m | gpt-5.4 |
| planner | 4 | 3 | 75% | 48,370 | 7.7m | claude-haiku-4-5 |
| challenger | 3 | 3 | 100% | 47,310 | 9.1m | claude-sonnet-5 |
| assumption_analyst | 2 | 1 | 50% | 21,365 | 9.1m | claude-sonnet-5 |
| intake | 1 | 1 | 100% | 4,505 | 0.7m | claude-haiku-4-5 |

Failure causes: 9 `backend_failure`, 4 `validation_failure`.

## Questions the spec asks

- **Usage per decision:** ~1.58M tokens, 191 min wall clock, 45 invocations (33 counted against
  the invocation budget). The analyst dominates wall-clock time (69 min across 7 attempts) because
  it runs and reproduces saved analysis code; the researcher dominates tokens (574k) because
  evidence batches are large.
- **Retry rate:** 12 retries across 45 attempts; 71% of attempts succeeded first pass. The
  retries cluster in two roles hit by a backend-specific crash (see defect 1), not in analytical
  disagreement.
- **Weakest role:** by first-pass success, structurer (33%) and synthesizer (50%). The
  structurer's rate is an artifact of defect 1, not analytical quality (its recovered output was
  schema-valid). The synthesizer is the genuinely weak link here: it failed review twice.
- **Did repair change the recommendation?** No. Two repair cycles ran and the thesis was revised
  four times, but the preferred alternative never changed. Repair deepened evidence rather than
  flipping the conclusion.

## Qualitative assessment (Section 3 promise)

All twelve elements are present and meaningful: executive recommendation, decision confidence
(four distinct measures), alternatives considered (7, including options the user did not supply),
key reasons, scenario analysis, quantitative findings, strongest counterarguments, pre-mortem,
critical assumptions, change triggers, next actions, and evidence/citations with provenance
labels. The recommendation is decision-useful and honestly hedged: it caps its own confidence and
names its weakest evidence (self-reported compensation data). The case is auditable from its
artifacts alone.

## Defects found

1. **Spurious `agent_error` on the droid backend (9 of 13 failures).** `claude-sonnet-5` runs a
   role to completion, writes a schema-valid artifact, then trips on post-completion cleanup and
   returns `is_error=true`. The structurer wrote a valid 12KB issue tree twice and was rejected
   both times before an escalation model happened to succeed; the dual-track director was lost
   entirely this way (defect 2). **Fixed** in `5a3531a`: the orchestrator now accepts a file-write
   role's output when the required artifact is present and schema-valid, regardless of the CLI's
   error flag (validation is the real gate). This case ran on the pre-fix code, so its retry
   counts overstate what a current run would spend.

2. **Dual track skipped.** Track B (director-b) hit defect 1 twice and then a validation failure
   on its escalation model, so the orchestrator gracefully degraded to a single track. The
   epistemic-diversity check the dual track exists to provide did not happen. Defect 1's fix
   should recover most track-B attempts going forward.

3. **Synthesis inputs were truncated, and review failed twice.** The synthesizer's own output
   states that the case's preliminary recommendation, objection resolutions, and pre-mortem
   leading indicators "were truncated out of the inputs available to this synthesis." The reviewer
   then blocked on `verification.undisclosed_open_objection` and `verification.uncited_claim`,
   with all 8 verdicts unsupported after the retry. This is a projection/context-budget defect in
   the synthesis stage, not a synthesizer-model failure: it cannot cite or resolve inputs it never
   received. This is the highest-value defect to fix next and is filed as emergent work.

4. **Heavy-role timeouts sat at the ceiling on droid.** An earlier run saw an analyst task time
   out at exactly 600s. **Fixed** in `ff91968`: heavy-role timeouts scale 2x on the droid backend.

## Emergent work filed

- Synthesis-stage projection truncation (defect 3): the synthesizer must receive the preliminary
  recommendation, objection resolutions, and pre-mortem indicators, or the review gate will keep
  failing on inputs the synthesizer never saw. Needs a projection/context-budget spec.

## Verification

- Case reached `done` without manual state surgery — met.
- `final_recommendation.md` contains all twelve Section 3 elements — met; citations resolvable but
  the review gate flagged uncited claims (disclosed, not silently accepted).
- Audit log reconstructs role, model, tokens, duration, and every transition — met (this report's
  tables were produced entirely by `scripts/case_metrics.py` from `audit.jsonl`).
- `make check` green (716 unit tests) — met.
