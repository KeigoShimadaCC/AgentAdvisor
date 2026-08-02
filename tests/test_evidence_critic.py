from __future__ import annotations

from datetime import date

from orchestrator.artifacts import EvidenceFlag, EvidenceRecord, Level, SourceTier, SourceType
from orchestrator.evidence_critic import authority_score, critique_evidence

AS_OF = date(2026, 8, 1)


def _record(
    evidence_id: str,
    *,
    source_type: SourceType = SourceType.REGULATORY_FILING,
    reliability: Level = Level.HIGH,
    directness: Level = Level.HIGH,
    published: date = date(2026, 7, 1),
    group: str = "sec-filings",
    limitations: list[str] | None = None,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        claim=f"Claim for {evidence_id}",
        source_title="Filing",
        publisher="Publisher",
        source_url=f"https://example.com/{evidence_id}",
        source_type=source_type,
        publication_date=published,
        retrieval_date=AS_OF,
        excerpt="Excerpt text",
        reliability=reliability,
        directness=directness,
        independence_group=group,
        limitations=limitations if limitations is not None else ["Scope limited"],
        retrieved_by="researcher",
    )


def test_primary_recent_source_outscores_weak_stale_source() -> None:
    strong, _, strong_tier = authority_score(_record("E-001"), as_of=AS_OF)
    weak, _, weak_tier = authority_score(
        _record(
            "E-002",
            source_type=SourceType.OTHER,
            reliability=Level.LOW,
            directness=Level.LOW,
            published=date(2022, 1, 1),
        ),
        as_of=AS_OF,
    )
    assert strong_tier is SourceTier.PRIMARY
    assert weak_tier is SourceTier.WEAK
    assert strong > weak
    assert 0.0 <= weak <= strong <= 1.0


def test_authority_score_is_bounded_and_monotone_in_reliability() -> None:
    high, _, _ = authority_score(_record("E-001", reliability=Level.HIGH), as_of=AS_OF)
    medium, _, _ = authority_score(_record("E-002", reliability=Level.MEDIUM), as_of=AS_OF)
    low, _, _ = authority_score(_record("E-003", reliability=Level.LOW), as_of=AS_OF)
    assert high > medium > low


def test_repeated_coverage_of_one_origin_is_one_cluster_not_corroboration() -> None:
    records = [_record(f"E-00{index}", group="press-release-a") for index in range(1, 5)]
    critique = critique_evidence(records, as_of=AS_OF)

    assert critique.independent_group_count == 1
    assert critique.max_cluster_share == 1.0
    assert len(critique.clusters) == 1
    assert critique.clusters[0].evidence_ids == ["E-001", "E-002", "E-003", "E-004"]
    assert any("independence group" in gap for gap in critique.gaps)
    assert all(EvidenceFlag.SINGLE_SOURCE_CLUSTER in scored.flags for scored in critique.scored)


def test_diverse_primary_corpus_reports_no_concentration_gap() -> None:
    records = [
        _record("E-001", group="sec-filings"),
        _record("E-002", group="fed-statistics", source_type=SourceType.OFFICIAL_STATISTIC),
        _record("E-003", group="academic", source_type=SourceType.ORIGINAL_RESEARCH),
    ]
    critique = critique_evidence(records, as_of=AS_OF)

    assert critique.independent_group_count == 3
    assert critique.max_cluster_share < 0.4
    assert not any("supplies" in gap for gap in critique.gaps)


def test_empty_corpus_is_reported_as_a_gap_not_silently_scored_zero() -> None:
    critique = critique_evidence([], as_of=AS_OF)

    assert critique.evidence_count == 0
    assert critique.corpus_authority_mean == 0.0
    assert critique.gaps
    assert "No evidence" in critique.gaps[0]


def test_missing_limitations_and_staleness_are_flagged() -> None:
    critique = critique_evidence(
        [_record("E-001", published=date(2023, 1, 1), limitations=[])], as_of=AS_OF
    )
    flags = critique.scored[0].flags
    assert EvidenceFlag.STALE in flags
    assert EvidenceFlag.MISSING_LIMITATIONS in flags


def test_secondary_only_corpus_reports_low_primary_share() -> None:
    records = [
        _record(f"E-00{index}", source_type=SourceType.REPUTABLE_SECONDARY, group=f"g{index}")
        for index in range(1, 5)
    ]
    critique = critique_evidence(records, as_of=AS_OF)

    assert critique.primary_source_share == 0.0
    assert any("primary" in gap for gap in critique.gaps)
