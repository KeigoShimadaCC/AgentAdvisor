"""Private evidence ingestion (SPEC-043).

North star Section 8, Stage 1 lists "available internal information" among the things
intake must extract. Nothing implemented it: the entire input surface was one prompt
string plus a handful of enum-constrained clarifications, so the system researched the
public web *around* a decision while remaining blind to the decision's own documents.

**The provenance decision.** ``EvidenceRecord`` requires ``source_url``, ``publisher`` and
``publication_date``, and those fields are load-bearing in ``normalize.py``,
``citations.py``, ``evidence_critic.py``, ``gates.py`` and ``memory.py``. Two alternatives
were rejected: making them optional weakens validation for *all* evidence, and a separate
``PrivateEvidenceRecord`` would have to be unioned at seventeen consumer modules.

Instead ingestion synthesizes a ``file://`` or ``user://`` reference and the model is left
untouched. The two modules that would be misled by a fake URL — the evidence critic's
authority ladder and the cross-case source reputation — special-case
``SourceType.USER_DOCUMENT`` explicitly. That is a deliberate trade: two named and tested
special cases instead of either weakened validation everywhere or a union type.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime

from orchestrator.artifacts import (
    EvidenceRecord,
    Level,
    SourceType,
)
from orchestrator.case_store import Case

__all__ = [
    "INGEST_DIR",
    "SUPPORTED_SUFFIXES",
    "DocumentChunk",
    "chunk_markdown",
    "ingest_case_inputs",
    "record_from_fact_answer",
]

#: Where the decision owner drops their material.
INGEST_DIR = "inputs"

#: Text formats only. PDF, xlsx and docx need dependencies, which AGENTS.md says require
#: user sign-off, and the parsing-quality question deserves its own spec once this seam
#: is proven.
SUPPORTED_SUFFIXES = frozenset({".md", ".markdown", ".txt"})

#: Excerpts must stay inside the projection character budget; a 40-page document that
#: arrives as one record would crowd out everything else the reading role needs.
MAX_EXCERPT_CHARS = 1200

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    """One excerpt-sized piece of a supplied document."""

    heading_path: str
    text: str


def chunk_markdown(content: str, *, max_chars: int = MAX_EXCERPT_CHARS) -> list[DocumentChunk]:
    """Split on markdown headings, falling back to paragraph groups.

    Each chunk records the heading path it came from, so a citation points at a location
    a human can actually find in the original file.
    """
    lines = content.splitlines()
    sections: list[tuple[str, list[str]]] = []
    stack: list[str] = []
    current: list[str] = []
    current_path = ""

    for line in lines:
        match = _HEADING_RE.match(line)
        if match is None:
            current.append(line)
            continue
        if current and any(item.strip() for item in current):
            sections.append((current_path, current))
        depth = len(match.group(1))
        title = match.group(2).strip()
        stack = stack[: depth - 1]
        stack.append(title)
        current_path = " > ".join(stack)
        current = []
    if current and any(item.strip() for item in current):
        sections.append((current_path, current))

    if not sections and content.strip():
        sections = [("", lines)]

    chunks: list[DocumentChunk] = []
    for heading_path, body in sections:
        paragraphs = [p.strip() for p in "\n".join(body).split("\n\n") if p.strip()]
        buffer = ""
        for paragraph in paragraphs:
            candidate = f"{buffer}\n\n{paragraph}" if buffer else paragraph
            if len(candidate) > max_chars and buffer:
                chunks.append(DocumentChunk(heading_path=heading_path, text=buffer))
                buffer = paragraph
            else:
                buffer = candidate
        while len(buffer) > max_chars:
            chunks.append(DocumentChunk(heading_path=heading_path, text=buffer[:max_chars]))
            buffer = buffer[max_chars:].lstrip()
        if buffer:
            chunks.append(DocumentChunk(heading_path=heading_path, text=buffer))
    return chunks


def _document_record(
    *,
    evidence_id: str,
    filename: str,
    chunk: DocumentChunk,
    modified: date,
    retrieved_on: date,
) -> EvidenceRecord:
    location = f"{filename}#{chunk.heading_path}" if chunk.heading_path else filename
    claim_source = chunk.heading_path or chunk.text.strip().splitlines()[0][:120]
    return EvidenceRecord(
        evidence_id=evidence_id,
        claim=f"From the supplied document {location}: {claim_source}".strip(),
        source_title=location,
        publisher="user-supplied",
        source_url=f"file://{INGEST_DIR}/{filename}",
        source_type=SourceType.USER_DOCUMENT,
        publication_date=modified,
        retrieval_date=retrieved_on,
        excerpt=chunk.text[:MAX_EXCERPT_CHARS],
        reliability=Level.MEDIUM,
        directness=Level.HIGH,
        # One document is one source however many excerpts it yields, so two chunks of
        # the same file can never read as corroboration.
        independence_group=f"user_document:{filename}",
        limitations=[
            "Supplied by the decision owner; no external source confirms it.",
            "Not independent of any other excerpt from the same document.",
        ],
        retrieved_by="intake-ingest",
    )


def record_from_fact_answer(
    *,
    evidence_id: str,
    question_id: str,
    question: str,
    answer: str,
    retrieved_on: date | None = None,
) -> EvidenceRecord:
    """Turn an answered ``fact`` clarification into user-supplied evidence.

    Recorded as evidence rather than promoted to fact: a remembered number is exactly as
    unverifiable as a supplied document, and the reader must be able to see which claims
    rest on it.
    """
    today = retrieved_on or datetime.now(UTC).date()
    return EvidenceRecord(
        evidence_id=evidence_id,
        claim=f"{question} — {answer}",
        source_title=f"Intake answer to {question_id}",
        publisher="user-supplied",
        source_url=f"user://intake/{question_id}",
        source_type=SourceType.USER_DOCUMENT,
        publication_date=today,
        retrieval_date=today,
        excerpt=answer[:MAX_EXCERPT_CHARS],
        reliability=Level.MEDIUM,
        directness=Level.HIGH,
        independence_group=f"user_answer:{question_id}",
        limitations=[
            "Stated by the decision owner at intake; no external source confirms it.",
        ],
        retrieved_by="intake-ingest",
    )


def ingest_case_inputs(case: Case, *, retrieved_on: date | None = None) -> list[EvidenceRecord]:
    """Read ``cases/<id>/inputs/`` and write one evidence record per chunk.

    Returns the records written, empty when the directory is absent or holds nothing
    supported — in which case the case behaves exactly as it did before this existed.
    Unsupported files are skipped silently here and reported by the caller, so a stray
    PDF does not fail a run.
    """
    inputs_dir = case.root / INGEST_DIR
    if not inputs_dir.is_dir():
        return []

    today = retrieved_on or datetime.now(UTC).date()
    written: list[EvidenceRecord] = []

    for path in sorted(inputs_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).date()
        for chunk in chunk_markdown(content):
            record = _document_record(
                evidence_id=case.next_id("E-"),
                filename=path.name,
                chunk=chunk,
                modified=modified,
                retrieved_on=today,
            )
            case.write_artifact(record)
            written.append(record)
    return written


def unsupported_input_files(case: Case) -> list[str]:
    """Files in ``inputs/`` this cut cannot read, for an honest disclosure to the user."""
    inputs_dir = case.root / INGEST_DIR
    if not inputs_dir.is_dir():
        return []
    return sorted(
        path.name
        for path in inputs_dir.iterdir()
        if path.is_file() and path.suffix.lower() not in SUPPORTED_SUFFIXES
    )
