from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from orchestrator.artifacts import EvidenceBatch, EvidenceRecord

_TRACKING_QUERY_KEYS = frozenset(
    {
        "fbclid",
        "gclid",
        "igshid",
        "mc_cid",
        "mc_eid",
        "mkt_tok",
        "ref",
        "source",
    }
)
_TRACKING_QUERY_PREFIXES = ("utm_",)
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "was",
        "were",
        "with",
    }
)
_POSITIVE_TOKENS = frozenset({"above", "at_least", "grew", "higher", "increased", "rise", "up"})
_NEGATIVE_TOKENS = frozenset(
    {"below", "decline", "decreased", "down", "fell", "fewer", "lower", "no", "not"}
)
_WIRE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\breuters\b", re.IGNORECASE), "reuters"),
    (re.compile(r"\bassociated\s+press\b|\bap\s+news\b", re.IGNORECASE), "associated-press"),
    (re.compile(r"\bbloomberg\b", re.IGNORECASE), "bloomberg"),
)
_UK_SECOND_LEVEL = frozenset({"ac", "co", "gov", "org"})
_JP_SECOND_LEVEL = frozenset({"ac", "co", "ed", "go", "lg", "ne", "or"})


@dataclass(frozen=True, slots=True)
class QuarantinedEvidence:
    ordinal: int
    reasons: tuple[str, ...]
    raw_record: dict[str, Any]


@dataclass(frozen=True, slots=True)
class NormalizedEvidenceBatch:
    accepted: tuple[EvidenceRecord, ...]
    quarantined: tuple[QuarantinedEvidence, ...]
    contradiction_links: tuple[tuple[str, str], ...]
    stale_evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Candidate:
    ordinal: int
    record: EvidenceRecord
    raw_record: dict[str, Any]
    canonical_url: str
    origin: str
    claim_signature: str


def canonicalize_url(source_url: str) -> str:
    parsed = urlsplit(source_url.strip())
    scheme = parsed.scheme.lower() if parsed.scheme else "https"
    hostname = (parsed.hostname or "").lower()
    port = parsed.port
    if port is None or (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        netloc = hostname
    else:
        netloc = f"{hostname}:{port}"
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_QUERY_KEYS
        and not any(key.lower().startswith(prefix) for prefix in _TRACKING_QUERY_PREFIXES)
    ]
    filtered_query.sort()
    query = urlencode(filtered_query, doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))


def normalize_evidence_batch(
    raw_records: list[dict[str, Any]] | EvidenceBatch,
    *,
    question: str | None = None,
    stale_after_days: int,
) -> NormalizedEvidenceBatch:
    if stale_after_days <= 0:
        raise ValueError("stale_after_days must be positive.")

    if isinstance(raw_records, EvidenceBatch):
        if question is not None and question != raw_records.question:
            raise ValueError(
                "question must match EvidenceBatch.question when batch input is provided."
            )
        question = raw_records.question
        if raw_records.no_evidence_found and not raw_records.records:
            return NormalizedEvidenceBatch(
                accepted=tuple(),
                quarantined=tuple(),
                contradiction_links=tuple(),
                stale_evidence_ids=tuple(),
            )
        record_payloads = [
            record.model_dump(mode="json", exclude={"schema_version"})
            for record in raw_records.records
        ]
    else:
        if question is None or not question.strip():
            raise ValueError("question is required when raw record input is provided.")
        record_payloads = raw_records

    assert question is not None
    parsed_candidates: list[_Candidate] = []
    quarantined: list[QuarantinedEvidence] = []
    question_slug = _slug(question) or "question"

    for ordinal, raw_record in enumerate(record_payloads):
        try:
            record = EvidenceRecord.model_validate(raw_record)
        except ValidationError as exc:
            quarantined.append(
                QuarantinedEvidence(
                    ordinal=ordinal,
                    reasons=(f"schema_validation_error: {exc.errors()[0]['msg']}",),
                    raw_record=raw_record,
                )
            )
            continue

        canonical_url = canonicalize_url(record.source_url)
        parsed_candidates.append(
            _Candidate(
                ordinal=ordinal,
                record=record,
                raw_record=raw_record,
                canonical_url=canonical_url,
                origin=_origin_key(canonical_url),
                claim_signature=_claim_signature(record.claim),
            )
        )

    if not parsed_candidates:
        return NormalizedEvidenceBatch(
            accepted=tuple(),
            quarantined=tuple(sorted(quarantined, key=lambda item: item.ordinal)),
            contradiction_links=tuple(),
            stale_evidence_ids=tuple(),
        )

    deduped: list[_Candidate] = []
    by_url: dict[str, _Candidate] = {}
    by_near: dict[tuple[str, str, str], _Candidate] = {}
    for candidate in parsed_candidates:
        near_key = (
            candidate.origin,
            candidate.claim_signature,
            candidate.record.publication_date.isoformat(),
        )
        duplicate_of: str | None = None
        if candidate.canonical_url in by_url:
            duplicate_of = by_url[candidate.canonical_url].record.evidence_id
        elif near_key in by_near:
            duplicate_of = by_near[near_key].record.evidence_id

        if duplicate_of is not None:
            quarantined.append(
                QuarantinedEvidence(
                    ordinal=candidate.ordinal,
                    reasons=(f"duplicate_of:{duplicate_of}",),
                    raw_record=candidate.raw_record,
                )
            )
            continue

        by_url[candidate.canonical_url] = candidate
        by_near[near_key] = candidate
        deduped.append(candidate)

    as_of = max(candidate.record.retrieval_date for candidate in deduped)
    grouped = _assign_conservative_independence_groups(deduped, question_slug=question_slug)
    with_staleness: list[EvidenceRecord] = []
    stale_ids: set[str] = set()
    for record in grouped:
        age_days = (as_of - record.publication_date).days
        if age_days > stale_after_days:
            stale_ids.add(record.evidence_id)
            stale_note = (
                "Stale for this question: publication date is "
                f"{age_days} days older than threshold {stale_after_days} days."
            )
            record = record.model_copy(
                update={"limitations": _append_unique(record.limitations, stale_note)}
            )
        with_staleness.append(record)

    contradiction_links = _find_contradictions(with_staleness)
    contradicted_by: dict[str, list[str]] = {}
    for left_id, right_id in contradiction_links:
        contradicted_by.setdefault(left_id, []).append(right_id)
        contradicted_by.setdefault(right_id, []).append(left_id)

    final_accepted: list[EvidenceRecord] = []
    for record in with_staleness:
        peers = sorted(set(contradicted_by.get(record.evidence_id, [])))
        if peers:
            link_note = "Contradiction linked with: " + ", ".join(peers) + "."
            record = record.model_copy(
                update={"limitations": _append_unique(record.limitations, link_note)}
            )
        try:
            validated = EvidenceRecord.model_validate(record.model_dump(mode="json"))
        except ValidationError as exc:
            quarantined.append(
                QuarantinedEvidence(
                    ordinal=_ordinal_for_record(deduped, record.evidence_id),
                    reasons=(f"post_normalization_schema_error: {exc.errors()[0]['msg']}",),
                    raw_record=record.model_dump(mode="json"),
                )
            )
            continue
        final_accepted.append(validated)

    final_accepted.sort(key=lambda record: record.evidence_id)
    quarantined.sort(key=lambda item: item.ordinal)
    return NormalizedEvidenceBatch(
        accepted=tuple(final_accepted),
        quarantined=tuple(quarantined),
        contradiction_links=tuple(sorted(contradiction_links)),
        stale_evidence_ids=tuple(sorted(stale_ids)),
    )


def dump_normalized_batch(batch: NormalizedEvidenceBatch) -> str:
    payload = {
        "accepted": [record.model_dump(mode="json") for record in batch.accepted],
        "contradiction_links": [list(pair) for pair in batch.contradiction_links],
        "quarantined": [
            {
                "ordinal": item.ordinal,
                "reasons": list(item.reasons),
                "raw_record": item.raw_record,
            }
            for item in batch.quarantined
        ],
        "stale_evidence_ids": list(batch.stale_evidence_ids),
    }
    dumped = cast(str, yaml.safe_dump(payload, sort_keys=True, allow_unicode=True))
    if not dumped.endswith("\n"):
        dumped = f"{dumped}\n"
    return dumped


def write_quarantine_file(
    workspace: Path,
    quarantined: tuple[QuarantinedEvidence, ...] | list[QuarantinedEvidence],
    *,
    relative_path: str = "outputs/evidence_quarantine.yaml",
) -> Path | None:
    if not quarantined:
        return None
    path = workspace / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "quarantined": [
            {
                "ordinal": item.ordinal,
                "reasons": list(item.reasons),
                "raw_record": item.raw_record,
            }
            for item in quarantined
        ]
    }
    dumped = cast(str, yaml.safe_dump(payload, sort_keys=True, allow_unicode=True))
    if not dumped.endswith("\n"):
        dumped = f"{dumped}\n"
    path.write_text(dumped, encoding="utf-8")
    return path


def _assign_conservative_independence_groups(
    candidates: list[_Candidate], *, question_slug: str
) -> list[EvidenceRecord]:
    signature_to_group: dict[str, str] = {}
    grouped: list[EvidenceRecord] = []
    for candidate in candidates:
        record = candidate.record
        signatures = _independence_signatures(candidate)
        shared_groups = sorted(
            {
                signature_to_group[signature]
                for signature in signatures
                if signature in signature_to_group
            }
        )
        if shared_groups:
            group = shared_groups[0]
        else:
            wire_key = _wire_service_key(record)
            publisher_key = _slug(record.publisher)
            if wire_key:
                group = f"{question_slug}-wire-{wire_key}"
            elif publisher_key:
                group = f"{question_slug}-publisher-{publisher_key}"
            elif candidate.origin != "unknown-origin":
                group = f"{question_slug}-origin-{candidate.origin}"
            else:
                group = f"{question_slug}-uncertain-source-cluster"
        for signature in signatures:
            signature_to_group.setdefault(signature, group)
        grouped.append(record.model_copy(update={"independence_group": group}))
    return grouped


def _independence_signatures(candidate: _Candidate) -> set[str]:
    signatures: set[str] = set()
    publisher_slug = _slug(candidate.record.publisher)
    if publisher_slug:
        signatures.add(f"publisher:{publisher_slug}")
    if candidate.origin != "unknown-origin":
        signatures.add(f"origin:{candidate.origin}")
    else:
        signatures.add("origin:unknown")
    wire_key = _wire_service_key(candidate.record)
    if wire_key is not None:
        signatures.add(f"wire:{wire_key}")
    if not signatures:
        signatures.add("uncertain")
    return signatures


def _wire_service_key(record: EvidenceRecord) -> str | None:
    haystack = " ".join(
        [record.publisher, record.source_title, record.excerpt, record.source_url]
    ).lower()
    for pattern, label in _WIRE_PATTERNS:
        if pattern.search(haystack):
            return label
    return None


def _origin_key(canonical_url: str) -> str:
    hostname = (urlsplit(canonical_url).hostname or "").lower()
    if not hostname:
        return "unknown-origin"
    return _registrable_domain(hostname)


def _registrable_domain(hostname: str) -> str:
    labels = [label for label in hostname.split(".") if label]
    if len(labels) <= 2:
        return hostname
    if labels[-1] == "uk" and labels[-2] in _UK_SECOND_LEVEL and len(labels) >= 3:
        return ".".join(labels[-3:])
    if labels[-1] == "jp" and labels[-2] in _JP_SECOND_LEVEL and len(labels) >= 3:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _claim_signature(claim: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", claim.lower()).strip()
    return normalized


def _find_contradictions(records: list[EvidenceRecord]) -> list[tuple[str, str]]:
    links: set[tuple[str, str]] = set()
    for left_index, left in enumerate(records):
        for right in records[left_index + 1 :]:
            if _topic_key(left.claim) != _topic_key(right.claim):
                continue
            if not _claims_contradict(left.claim, right.claim):
                continue
            first, second = sorted((left.evidence_id, right.evidence_id))
            links.add((first, second))
    return sorted(links)


def _topic_key(claim: str) -> str:
    collapsed = re.sub(r"[^a-z0-9]+", " ", claim.lower()).strip()
    tokens = [token for token in collapsed.split() if token and token not in _STOPWORDS]
    filtered = [token for token in tokens if not token.isdigit() and token not in _POSITIVE_TOKENS]
    filtered = [token for token in filtered if token not in _NEGATIVE_TOKENS]
    if not filtered:
        return collapsed
    return " ".join(filtered)


def _claims_contradict(left_claim: str, right_claim: str) -> bool:
    left_number = _first_number(left_claim)
    right_number = _first_number(right_claim)
    if left_number is not None and right_number is not None and left_number != right_number:
        return True
    left_polarity = _polarity(left_claim)
    right_polarity = _polarity(right_claim)
    return left_polarity != 0 and right_polarity != 0 and left_polarity != right_polarity


def _first_number(text: str) -> float | None:
    matches = re.findall(r"(\d[\d,]*(?:\.\d+)?)", text)
    if not matches:
        return None
    values = [float(token.replace(",", "")) for token in matches]
    return max(values)


def _polarity(text: str) -> int:
    tokens = re.sub(r"[^a-z0-9]+", " ", text.lower()).split()
    positive_hits = sum(1 for token in tokens if token in _POSITIVE_TOKENS)
    negative_hits = sum(1 for token in tokens if token in _NEGATIVE_TOKENS)
    if positive_hits > negative_hits:
        return 1
    if negative_hits > positive_hits:
        return -1
    return 0


def _append_unique(items: list[str], item: str) -> list[str]:
    if item in items:
        return list(items)
    return [*items, item]


def _slug(value: str) -> str:
    lowered = value.lower()
    collapsed = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return collapsed[:48]


def _ordinal_for_record(candidates: list[_Candidate], evidence_id: str) -> int:
    for candidate in candidates:
        if candidate.record.evidence_id == evidence_id:
            return candidate.ordinal
    return -1
