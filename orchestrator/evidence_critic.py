"""Deterministic quality assessment of a case's evidence corpus.

Source authority is computed from the fields the researcher already had to fill in,
never asserted by an agent, so a weak corpus cannot be described as a strong one.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from orchestrator.artifacts import (
    SOURCE_TIER_BY_TYPE,
    SOURCE_TIER_WEIGHT,
    EvidenceAuthorityScore,
    EvidenceCritique,
    EvidenceFlag,
    EvidenceRecord,
    IndependenceCluster,
    Level,
    SourceTier,
)
from orchestrator.case_store import Case

# A source loses its recency credit linearly over this window.
RECENCY_HORIZON_DAYS = 730
STALE_AFTER_DAYS = 365
CLUSTER_CONCENTRATION_THRESHOLD = 0.4
WEAK_AUTHORITY_THRESHOLD = 0.45
MIN_INDEPENDENT_GROUPS = 3
MIN_PRIMARY_SHARE = 0.25

_LEVEL_VALUE: dict[Level, float] = {Level.HIGH: 1.0, Level.MEDIUM: 0.6, Level.LOW: 0.2}


def _recency_credit(age_days: int) -> float:
    if age_days <= 0:
        return 1.0
    if age_days >= RECENCY_HORIZON_DAYS:
        return 0.0
    return 1.0 - (age_days / RECENCY_HORIZON_DAYS)


def authority_score(record: EvidenceRecord, *, as_of: date) -> tuple[float, int, SourceTier]:
    tier = SOURCE_TIER_BY_TYPE.get(record.source_type, SourceTier.WEAK)
    age_days = max(0, (as_of - record.publication_date).days)
    score = (
        SOURCE_TIER_WEIGHT[tier] * 0.5
        + _LEVEL_VALUE[record.reliability] * 0.2
        + _LEVEL_VALUE[record.directness] * 0.2
        + _recency_credit(age_days) * 0.1
    )
    return round(min(1.0, max(0.0, score)), 4), age_days, tier


def _flags(
    record: EvidenceRecord,
    *,
    tier: SourceTier,
    age_days: int,
    cluster_share: float,
) -> list[EvidenceFlag]:
    flags: list[EvidenceFlag] = []
    if tier is SourceTier.WEAK:
        flags.append(EvidenceFlag.WEAK_SOURCE_TIER)
    if age_days > STALE_AFTER_DAYS:
        flags.append(EvidenceFlag.STALE)
    if record.directness is Level.LOW:
        flags.append(EvidenceFlag.LOW_DIRECTNESS)
    if record.reliability is Level.LOW:
        flags.append(EvidenceFlag.LOW_RELIABILITY)
    if not record.limitations:
        flags.append(EvidenceFlag.MISSING_LIMITATIONS)
    if cluster_share > CLUSTER_CONCENTRATION_THRESHOLD:
        flags.append(EvidenceFlag.SINGLE_SOURCE_CLUSTER)
    return flags


def critique_evidence(records: list[EvidenceRecord], *, as_of: date) -> EvidenceCritique:
    total = len(records)
    if total == 0:
        return EvidenceCritique(
            evidence_count=0,
            scored=[],
            clusters=[],
            corpus_authority_mean=0.0,
            primary_source_share=0.0,
            max_cluster_share=0.0,
            independent_group_count=0,
            weakest_evidence_ids=[],
            gaps=["No evidence was gathered; every claim rests on unsupported reasoning."],
        )

    by_group: dict[str, list[str]] = defaultdict(list)
    for record in records:
        by_group[record.independence_group].append(record.evidence_id)

    cluster_share_by_group = {
        group: len(evidence_ids) / total for group, evidence_ids in by_group.items()
    }

    scored: list[EvidenceAuthorityScore] = []
    primary_count = 0
    for record in records:
        score, age_days, tier = authority_score(record, as_of=as_of)
        if tier is SourceTier.PRIMARY:
            primary_count += 1
        scored.append(
            EvidenceAuthorityScore(
                evidence_id=record.evidence_id,
                source_tier=tier,
                authority_score=score,
                age_days=age_days,
                independence_group=record.independence_group,
                flags=_flags(
                    record,
                    tier=tier,
                    age_days=age_days,
                    cluster_share=cluster_share_by_group[record.independence_group],
                ),
            )
        )

    clusters = [
        IndependenceCluster(
            independence_group=group,
            evidence_ids=sorted(evidence_ids),
            share_of_corpus=round(cluster_share_by_group[group], 4),
        )
        for group, evidence_ids in sorted(by_group.items())
    ]

    corpus_mean = round(sum(item.authority_score for item in scored) / total, 4)
    primary_share = round(primary_count / total, 4)
    max_cluster_share = round(max(cluster_share_by_group.values()), 4)
    weakest = [
        item.evidence_id
        for item in sorted(scored, key=lambda item: (item.authority_score, item.evidence_id))
        if item.authority_score < WEAK_AUTHORITY_THRESHOLD
    ]

    gaps: list[str] = []
    if primary_share < MIN_PRIMARY_SHARE:
        gaps.append(
            f"Only {primary_share:.0%} of evidence is primary (filings or official statistics); "
            "conclusions rest mostly on secondary reporting."
        )
    if len(by_group) < MIN_INDEPENDENT_GROUPS:
        gaps.append(
            f"Evidence spans only {len(by_group)} independence group(s); "
            "repeated coverage of one origin is not corroboration."
        )
    if max_cluster_share > CLUSTER_CONCENTRATION_THRESHOLD:
        dominant = max(cluster_share_by_group.items(), key=lambda item: item[1])
        gaps.append(f"Independence group '{dominant[0]}' supplies {dominant[1]:.0%} of the corpus.")
    if weakest:
        gaps.append(
            f"{len(weakest)} record(s) score below {WEAK_AUTHORITY_THRESHOLD} on source authority."
        )

    return EvidenceCritique(
        evidence_count=total,
        scored=scored,
        clusters=clusters,
        corpus_authority_mean=corpus_mean,
        primary_source_share=primary_share,
        max_cluster_share=max_cluster_share,
        independent_group_count=len(by_group),
        weakest_evidence_ids=weakest,
        gaps=gaps,
    )


def critique_case_evidence(case: Case, *, as_of: date) -> EvidenceCritique:
    critique = critique_evidence(case.list_artifacts(EvidenceRecord), as_of=as_of)
    case.write_artifact(critique)
    return critique
