"""Cross-case institutional memory.

A think tank differs from a one-off engagement by remembering. This store keeps
completed decisions, the reliability track record of sources, recurring assumptions
and reusable evidence, so a new case does not start with an empty head.

Retrieval is deliberately dumb and inspectable: normalized keyword overlap, no
embeddings (banned by the project's scope discipline). Nothing retrieved from memory
is citable; it is prior context that must be re-established inside the live case.
"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml  # type: ignore[import-untyped]

from orchestrator.artifacts import (
    AssumptionRecord,
    CalibrationSummary,
    CaseMemoryDigest,
    DecisionSpec,
    EvidenceRecord,
    FinalRecommendation,
    IntakeRecord,
    Level,
    OutcomeRecord,
    PriorCaseEntry,
    PriorEvidenceDigest,
    PriorEvidenceEntry,
    RecurringAssumption,
    SourceReputation,
)
from orchestrator.artifacts.yaml_io import dump_model_to_yaml_text
from orchestrator.calibration import summarize_calibration
from orchestrator.case_store import Case, atomic_write_text
from orchestrator.evidence_critic import authority_score

MAX_PRIOR_CASES = 3
MAX_SOURCE_REPUTATIONS = 8
MAX_RECURRING_ASSUMPTIONS = 5
MAX_PRIOR_EVIDENCE = 6
MIN_KEYWORD_OVERLAP = 0.12
MIN_SHARED_KEYWORDS = 2
"""Two unrelated decisions routinely share one ordinary word ("buy", "sell"). One
shared token is coincidence, not relevance, so a match needs at least two."""

USAGE_NOTE = (
    "Prior-case context only. Nothing in this digest may be cited as evidence in the current "
    "case; treat it as institutional recall that must be re-established from live sources."
)
STALENESS_WARNING = (
    "These records were gathered for earlier decisions and are stale by construction. They may "
    "not be cited. Re-verify any that still matter and register them as fresh evidence."
)

_WORD_RE = re.compile(r"[a-z][a-z0-9-]{2,}")
_STOPWORDS = frozenset(
    {
        "should",
        "would",
        "could",
        "the",
        "and",
        "for",
        "with",
        "into",
        "from",
        "that",
        "this",
        "have",
        "has",
        "are",
        "was",
        "were",
        "you",
        "your",
        "our",
        "about",
        "over",
        "than",
        "then",
        "what",
        "when",
        "which",
        "want",
        "make",
        "now",
        "vs",
        "versus",
        "or",
    }
)


def keywords(text: str, *, limit: int = 24) -> list[str]:
    seen: dict[str, None] = {}
    for token in _WORD_RE.findall(text.lower()):
        if token in _STOPWORDS:
            continue
        seen.setdefault(token, None)
        if len(seen) >= limit:
            break
    return list(seen)


def overlap(left: list[str], right: list[str]) -> float:
    left_set, right_set = set(left), set(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def is_related(query: list[str], candidate: list[str]) -> bool:
    shared = set(query) & set(candidate)
    return len(shared) >= MIN_SHARED_KEYWORDS and overlap(query, candidate) >= MIN_KEYWORD_OVERLAP


def registrable_domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if not host:
        return "unknown"
    host = host.split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host or "unknown"


def memory_root() -> Path:
    configured = os.getenv("AGENTADVISOR_MEMORY_ROOT")
    root = (
        Path(configured).expanduser()
        if configured
        else Path(__file__).resolve().parents[1] / "memory"
    )
    root.mkdir(parents=True, exist_ok=True)
    return root


@dataclass(frozen=True, slots=True)
class _Files:
    cases: Path
    evidence: Path

    @staticmethod
    def under(root: Path) -> _Files:
        return _Files(cases=root / "cases.yaml", evidence=root / "evidence.yaml")


def _load_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, list):
        return []
    return [item for item in loaded if isinstance(item, dict)]


def _dump_models(path: Path, models: list[Any]) -> None:
    payload = [model.model_dump(mode="json") for model in models]
    atomic_write_text(path, yaml.safe_dump(payload, sort_keys=True, allow_unicode=True))


class MemoryStore:
    """File-backed cross-case memory. Single user, single process."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or memory_root()
        self._root.mkdir(parents=True, exist_ok=True)
        self._files = _Files.under(self._root)

    @property
    def root(self) -> Path:
        return self._root

    # ── reads ────────────────────────────────────────────────────────────

    def prior_cases(self) -> list[PriorCaseEntry]:
        return [PriorCaseEntry.model_validate(item) for item in _load_list(self._files.cases)]

    def prior_evidence(self) -> list[PriorEvidenceEntry]:
        return [
            PriorEvidenceEntry.model_validate(item) for item in _load_list(self._files.evidence)
        ]

    # ── writes ───────────────────────────────────────────────────────────

    def record_case(self, case: Case, *, domains: list[str] | None = None) -> PriorCaseEntry:
        """Snapshot a completed case into memory. Overwrites any earlier snapshot."""
        recommendation = case.read_artifact(FinalRecommendation)
        question = self._decision_question(case)
        headline_name, headline_probability = self._headline_outcome(recommendation)

        entry = PriorCaseEntry(
            case_id=case.root.name,
            decision_question=question,
            keywords=keywords(question),
            domains=sorted(domains or []),
            recommended_action=recommendation.recommended_action,
            alternatives_considered=[
                item.alternative for item in recommendation.alternatives_considered
            ],
            recommendation_confidence=recommendation.recommendation_confidence.value,
            evidence_confidence=recommendation.evidence_confidence.value,
            headline_outcome_name=headline_name,
            headline_outcome_probability=headline_probability,
            completed_at=datetime.now(UTC),
            outcome=self._existing_outcome(case.root.name),
        )

        entries = [item for item in self.prior_cases() if item.case_id != entry.case_id]
        entries.append(entry)
        entries.sort(key=lambda item: item.completed_at)
        _dump_models(self._files.cases, entries)

        self._record_evidence(case, domains=domains or [])
        return entry

    def record_outcome(self, case_id: str, outcome: OutcomeRecord) -> PriorCaseEntry:
        entries = self.prior_cases()
        matched = next((item for item in entries if item.case_id == case_id), None)
        if matched is None:
            raise KeyError(f"No prior case recorded for '{case_id}'.")
        updated = matched.model_copy(update={"outcome": outcome})
        entries = [updated if item.case_id == case_id else item for item in entries]
        _dump_models(self._files.cases, entries)
        return updated

    # ── digests ──────────────────────────────────────────────────────────

    def digest_for(self, question: str, *, exclude_case_id: str | None = None) -> CaseMemoryDigest:
        query = keywords(question)
        candidates = [
            entry
            for entry in self.prior_cases()
            if entry.case_id != exclude_case_id and is_related(query, entry.keywords)
        ]
        candidates.sort(key=lambda entry: overlap(query, entry.keywords), reverse=True)
        selected = candidates[:MAX_PRIOR_CASES]

        return CaseMemoryDigest(
            generated_at=datetime.now(UTC),
            prior_cases=selected,
            source_reputations=self.source_reputations()[:MAX_SOURCE_REPUTATIONS],
            recurring_assumptions=self.recurring_assumptions()[:MAX_RECURRING_ASSUMPTIONS],
            calibration=self.calibration(),
            usage_note=USAGE_NOTE,
        )

    def prior_evidence_for(
        self, question: str, *, exclude_case_id: str | None = None
    ) -> PriorEvidenceDigest:
        query = keywords(question)
        scored = [
            (overlap(query, entry.topics), entry)
            for entry in self.prior_evidence()
            if entry.from_case_id != exclude_case_id and is_related(query, entry.topics)
        ]
        selected = [entry for _, entry in sorted(scored, key=lambda pair: pair[0], reverse=True)][
            :MAX_PRIOR_EVIDENCE
        ]
        return PriorEvidenceDigest(
            generated_at=datetime.now(UTC),
            entries=selected,
            staleness_warning=STALENESS_WARNING,
        )

    def source_reputations(self) -> list[SourceReputation]:
        by_domain: dict[str, list[PriorEvidenceEntry]] = defaultdict(list)
        for entry in self.prior_evidence():
            by_domain[registrable_domain(entry.source_url)].append(entry)

        reputations = [
            SourceReputation(
                domain=domain,
                times_cited=len(entries),
                times_contradicted=0,
                mean_authority=round(
                    sum(entry.authority_score for entry in entries) / len(entries), 4
                ),
                source_types=sorted({entry.source_type for entry in entries}),
                case_ids=sorted({entry.from_case_id for entry in entries}),
            )
            for domain, entries in by_domain.items()
        ]
        reputations.sort(key=lambda item: (-item.times_cited, item.domain))
        return reputations

    def recurring_assumptions(self) -> list[RecurringAssumption]:
        path = self._root / "assumptions.yaml"
        records = _load_list(path)
        parsed = [RecurringAssumption.model_validate(item) for item in records]
        parsed.sort(key=lambda item: (-item.occurrences, item.normalized_claim))
        return parsed

    def calibration(self) -> CalibrationSummary:
        return summarize_calibration(
            [entry.outcome for entry in self.prior_cases() if entry.outcome is not None]
        )

    # ── internals ────────────────────────────────────────────────────────

    def _existing_outcome(self, case_id: str) -> OutcomeRecord | None:
        return next(
            (entry.outcome for entry in self.prior_cases() if entry.case_id == case_id), None
        )

    def _decision_question(self, case: Case) -> str:
        specs = case.list_artifacts(DecisionSpec)
        if specs:
            return specs[0].question
        intakes = case.list_artifacts(IntakeRecord)
        if intakes:
            return intakes[0].decision_question or intakes[0].raw_prompt
        return case.root.name

    @staticmethod
    def _headline_outcome(
        recommendation: FinalRecommendation,
    ) -> tuple[str | None, float | None]:
        for name, estimate in recommendation.outcome_probabilities.items():
            if estimate.point is not None:
                return name, estimate.point
            if estimate.interval_low is not None and estimate.interval_high is not None:
                return name, (estimate.interval_low + estimate.interval_high) / 2
        return None, None

    def _record_evidence(self, case: Case, *, domains: list[str]) -> None:
        today = date.today()
        question = self._decision_question(case)
        topic_seed = keywords(question, limit=8)

        existing = [
            entry for entry in self.prior_evidence() if entry.from_case_id != case.root.name
        ]
        for record in case.list_artifacts(EvidenceRecord):
            score, _, _ = authority_score(record, as_of=today)
            existing.append(
                PriorEvidenceEntry(
                    claim=record.claim,
                    source_title=record.source_title,
                    publisher=record.publisher,
                    source_url=record.source_url,
                    source_type=record.source_type,
                    publication_date=record.publication_date,
                    topics=sorted(set(topic_seed) | set(keywords(record.claim, limit=8))),
                    from_case_id=case.root.name,
                    authority_score=score,
                )
            )
        _dump_models(self._files.evidence, existing)
        self._record_assumptions(case, domains=domains)

    def _record_assumptions(self, case: Case, *, domains: list[str]) -> None:
        del domains
        path = self._root / "assumptions.yaml"
        existing = {
            item.normalized_claim: item
            for item in (RecurringAssumption.model_validate(entry) for entry in _load_list(path))
        }
        for record in case.list_artifacts(AssumptionRecord):
            key = " ".join(keywords(record.claim, limit=10))
            if not key:
                continue
            previous = existing.get(key)
            if previous is None:
                existing[key] = RecurringAssumption(
                    normalized_claim=key,
                    example_claim=record.claim,
                    occurrences=1,
                    max_materiality=record.materiality,
                    case_ids=[case.root.name],
                )
                continue
            if case.root.name in previous.case_ids:
                continue
            existing[key] = previous.model_copy(
                update={
                    "occurrences": previous.occurrences + 1,
                    "max_materiality": _stronger(previous.max_materiality, record.materiality),
                    "case_ids": sorted({*previous.case_ids, case.root.name}),
                }
            )
        _dump_models(path, sorted(existing.values(), key=lambda item: item.normalized_claim))


_LEVEL_RANK: dict[Level, int] = {Level.LOW: 0, Level.MEDIUM: 1, Level.HIGH: 2}


def _stronger(left: Level, right: Level) -> Level:
    return left if _LEVEL_RANK[left] >= _LEVEL_RANK[right] else right


def write_digests(
    case: Case,
    *,
    question: str,
    store: MemoryStore | None = None,
    domains: list[str] | None = None,
) -> tuple[CaseMemoryDigest, PriorEvidenceDigest]:
    """Materialize both memory digests onto the case so they can be projected."""
    memory = store or MemoryStore()
    digest = memory.digest_for(question, exclude_case_id=case.root.name)
    if domains:
        digest = digest.model_copy(
            update={
                "prior_cases": [
                    entry
                    for entry in digest.prior_cases
                    if not entry.domains or set(entry.domains) & set(domains)
                ]
                or digest.prior_cases
            }
        )
    evidence_digest = memory.prior_evidence_for(question, exclude_case_id=case.root.name)
    case.write_artifact(digest)
    case.write_artifact(evidence_digest)
    return digest, evidence_digest


def dump_digest_yaml(digest: CaseMemoryDigest) -> str:
    return dump_model_to_yaml_text(digest)
