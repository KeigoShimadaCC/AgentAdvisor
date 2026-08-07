"""FastAPI service — the ``advisor ui`` REST surface (SPEC-033).

Bound to ``127.0.0.1`` only.  The service is a *reader* of case files and a
*client* of :mod:`orchestrator.control` — it never mutates case state
directly, preserving SPEC-027's single-writer discipline.

The app is constructed via :func:`create_app` so tests can inject a fixture
``cases_root`` without starting a server.  A module-level ``app`` is also
exposed for ASGI servers that import a global.
"""

from __future__ import annotations

import logging
import math
import os
import re
import threading
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from orchestrator.artifacts import (
    FinalApproval,
    FinalDecision,
    FramingApproval,
    FramingDecision,
    OutcomeRecord,
)
from orchestrator.case_store import Case, default_cases_root, load_case
from orchestrator.control import (
    RevisionCapReached,
    WrongStage,
    approve_final,
    approve_framing,
    new_case,
    pause,
    request_final_revision,
    request_framing_revision,
    resume,
    spawn_worker_background,
)
from orchestrator.memory import MemoryStore, memory_root
from orchestrator.monitoring import MonitoringStore, due_checks
from orchestrator.service.caseview import (
    _read_audit_events,
    build_case_view,
    needs_you_for_state,
)
from orchestrator.service.events import replay_stream, sse_event_stream
from orchestrator.state_machine import CaseStage, load_case_state
from orchestrator.supervisor import CaseLocked as _CaseLocked  # noqa: F401 (re-export)

__all__ = ["create_app", "app", "ServiceConfig", "CaseSummary"]

# Filenames / patterns that the read-only ``/files`` passthrough never serves.
_BLOCKED_FILENAMES: frozenset[str] = frozenset({".run.lock"})
_BLOCKED_SUFFIXES: tuple[str, ...] = (".tmp", ".lock")
_BLOCKED_PREFIXES: tuple[str, ...] = (".",)

# A safe relative path: no traversal, no absolute paths.
_SAFE_REL_RE = re.compile(r"^(?!.*\.\.).+$")


# Stages where the pipeline is actively running (not waiting for user input
# and not terminal).  If a case is in one of these stages when the server
# starts, the worker process was likely killed by a restart and the case
# is stranded.  Auto-resume recovers it.
_ACTIVE_STAGES: frozenset[CaseStage] = frozenset(
    {
        CaseStage.INTAKE,
        CaseStage.FRAMING,
        CaseStage.STRUCTURING,
        CaseStage.PROVISIONAL_THESIS,
        CaseStage.PLANNING,
        CaseStage.INVESTIGATION,
        CaseStage.EVIDENCE_CRITIQUE,
        CaseStage.ASSUMPTION_LEDGER,
        CaseStage.PRELIMINARY_RECOMMENDATION,
        CaseStage.PRE_MORTEM,
        CaseStage.CHALLENGE,
        CaseStage.REPAIR,
        CaseStage.STOP_DECISION,
        CaseStage.SYNTHESIS,
        CaseStage.REVIEW,
    }
)

_logger = logging.getLogger("orchestrator.service.auto_resume")


def _monitoring_as_of_from_env() -> date | None:
    """An explicit "today" for monitoring dueness, or ``None`` for the real clock.

    Set ``AGENTADVISOR_MONITORING_AS_OF`` to an ISO date to freeze it. This exists for
    fixtures: a committed monitoring plan has a fixed delivery date, so what it renders
    drifts as the calendar advances, and a visual baseline captured against it has a
    silent expiry. An unparseable value is ignored rather than raising — a malformed
    test hook must not take down a real service.
    """
    raw = os.getenv("AGENTADVISOR_MONITORING_AS_OF")
    if not raw:
        return None
    try:
        return date.fromisoformat(raw.strip())
    except ValueError:
        return None


def _is_resumable(case: Case) -> bool:
    """Whether a worker could recover this case's raw prompt to resume it.

    Mirrors ``worker._resolve_raw_prompt``: the prompt comes from
    ``control_meta.yaml`` or, failing that, an ``IntakeRecord``.  Legacy or
    corrupt cases with neither cannot be resumed — spawning a worker for them
    just crashes on every server startup — so auto-resume must skip them.
    """
    meta_path = case.root / "shared" / "control_meta.yaml"
    if meta_path.exists():
        try:
            data = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and str(data.get("raw_prompt", "") or "").strip():
                return True
        except (OSError, yaml.YAMLError):
            pass
    try:
        from orchestrator.artifacts import IntakeRecord

        records = case.list_artifacts(IntakeRecord)
        if records and records[0].raw_prompt:
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


def _find_stuck_cases(cases_root: Path) -> list[tuple[str, CaseStage]]:
    """Return ``(case_id, stage)`` for every case stranded in an active stage."""
    stuck: list[tuple[str, CaseStage]] = []
    if not cases_root.exists():
        return stuck
    for entry in sorted(cases_root.iterdir()):
        if not entry.is_dir() or not (entry / "state.yaml").exists():
            continue
        try:
            case = load_case(entry.name, cases_root=cases_root)
            state = load_case_state(case)
        except Exception:  # noqa: BLE001
            continue
        if state.stage not in _ACTIVE_STAGES:
            continue
        if not _is_resumable(case):
            _logger.info(
                "Skipping un-resumable stuck case %s (no raw_prompt or IntakeRecord)",
                entry.name,
            )
            continue
        stuck.append((entry.name, state.stage))
    return stuck


def _auto_resume_stuck_cases(cases_root: Path) -> None:
    """Scan for stranded cases and resume each in a background thread."""
    stuck = _find_stuck_cases(cases_root)
    if not stuck:
        return
    for case_id, stage in stuck:
        _logger.info("Auto-resuming stuck case %s (stage=%s)", case_id, stage.value)
        thread = threading.Thread(
            target=_resume_in_background,
            args=(case_id, cases_root),
            daemon=True,
            name=f"auto-resume-{case_id}",
        )
        thread.start()


def _resume_in_background(case_id: str, cases_root: Path) -> None:
    """Call control.resume in a background thread, logging errors."""
    try:
        resume(case_id, cases_root=cases_root)
    except Exception as exc:  # noqa: BLE001
        _logger.warning("Auto-resume failed for %s: %s", case_id, exc)


# ── Request/response models ──────────────────────────────────────────────────


class CaseSummary(BaseModel):
    """One row in the case library list.

    ``needs_you`` is served here rather than re-derived on the client: the
    projection already owns that rule (SPEC-032), and a second copy of it in
    the frontend is a copy that drifts (SPEC-046).
    """

    model_config = {"extra": "forbid"}

    case_id: str
    stage: str
    title: str
    updated: str
    needs_you: str = "none"


class NewCaseRequest(BaseModel):
    model_config = {"extra": "forbid"}

    prompt: str
    effort: str = "default"
    slug: str | None = None


class ScopeCheckpointRequest(BaseModel):
    model_config = {"extra": "forbid"}

    decision: str  # "approve" | "edit" | "answer_clarifications"
    edits: dict[str, Any] = Field(default_factory=dict)
    clarification_answers: dict[str, str] = Field(default_factory=dict)
    confirmations: list[str] = Field(default_factory=list)
    summary_hash: str | None = None
    approved_by: str = "user"


class DeliveryCheckpointRequest(BaseModel):
    model_config = {"extra": "forbid"}

    decision: str  # "accept" | "revise"
    note: str | None = None
    approved_by: str = "user"


class OutcomeRequest(BaseModel):
    model_config = {"extra": "forbid"}

    summary: str
    followed: bool
    realized: bool
    forecast_name: str | None = None
    forecast_probability: float | None = Field(default=None, ge=0.0, le=1.0)


class ErrorResponse(BaseModel):
    model_config = {"extra": "forbid"}

    error: str
    detail: str
    case_stage: str | None = None


# ── Service config ───────────────────────────────────────────────────────────


class ServiceConfig:
    """Runtime configuration for the service, held on ``app.state``."""

    def __init__(
        self,
        cases_root: Path | None = None,
        replay_dir: Path | None = None,
        speed: float = 60.0,
        monitoring_root: Path | None = None,
        monitoring_as_of: date | None = None,
    ) -> None:
        self.cases_root = cases_root or default_cases_root()
        self.replay_dir = replay_dir
        self.speed = speed
        # SPEC-042: monitoring plans live outside the case tree, under the memory root.
        # Injectable so tests never touch the real one.
        self.monitoring_root = monitoring_root
        # The date "is this check due?" is answered against. ``None`` means the real
        # clock, which is what any real deployment wants.
        #
        # A fixture cannot want that. Dueness is ``(today - delivered_at) >= cadence``,
        # so a plan with a fixed delivery date changes what it renders as the calendar
        # advances: the committed e2e fixture showed "1 check is due now" and would have
        # said "2 checks are due now" from 2026-08-23, breaking the delivery visual
        # baseline with no code change behind it (found in SPEC-056). Pinning the date
        # is what makes a dated fixture reproducible.
        self.monitoring_as_of = monitoring_as_of or _monitoring_as_of_from_env()


# ── Helpers ──────────────────────────────────────────────────────────────────


def _case_title(case: Case) -> str:
    """A short human label for a case, from its intake record or prompt."""
    try:
        from orchestrator.artifacts import IntakeRecord

        records = case.list_artifacts(IntakeRecord)
        if records:
            return records[0].decision_question or records[0].raw_prompt
    except Exception:  # noqa: BLE001 — corrupt intake must not break the list
        pass
    # Fallback to the control meta raw_prompt.
    meta = case.root / "shared" / "control_meta.yaml"
    if meta.exists():
        try:
            data = yaml.safe_load(meta.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("raw_prompt"), str):
                return str(data["raw_prompt"])
        except Exception:  # noqa: BLE001
            pass
    return case.root.name


def _case_stage_value(case_id: str, config: ServiceConfig) -> str | None:
    try:
        case = load_case(case_id, cases_root=config.cases_root)
        return load_case_state(case).stage.value
    except Exception:  # noqa: BLE001
        return None


def _error_response(
    error: str,
    detail: str,
    case_stage: str | None = None,
    status_code: int = 400,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(error=error, detail=detail, case_stage=case_stage).model_dump(),
    )


def _load_or_404(case_id: str, config: ServiceConfig) -> Case:
    try:
        return load_case(case_id, cases_root=config.cases_root)
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _control_error_to_response(
    exc: BaseException,
    case_id: str,
    config: ServiceConfig,
) -> JSONResponse:
    """Map a control-layer exception to the SPEC-033 error model."""
    stage = _case_stage_value(case_id, config)
    if isinstance(exc, _CaseLocked):
        return _error_response("case_locked", str(exc), stage, status_code=409)
    if isinstance(exc, WrongStage):
        return _error_response(
            "wrong_stage",
            str(exc),
            exc.actual_stage,
            status_code=409,
        )
    if isinstance(exc, (FileNotFoundError, NotADirectoryError)):
        return _error_response("not_found", str(exc), stage, status_code=404)
    if isinstance(exc, RevisionCapReached):
        return _error_response("revision_cap_reached", str(exc), stage, status_code=422)
    if isinstance(exc, ValueError):
        # approve_framing/approve_final raise plain ValueError on wrong stage.
        msg = str(exc)
        if "not '" in msg and "stage" in msg.lower():
            return _error_response("wrong_stage", msg, stage, status_code=409)
        return _error_response("validation_error", msg, stage, status_code=422)
    return _error_response("internal_error", str(exc), stage, status_code=500)


# ── App factory ──────────────────────────────────────────────────────────────


def create_app(
    cases_root: Path | None = None,
    *,
    replay_dir: Path | None = None,
    speed: float = 60.0,
    monitoring_root: Path | None = None,
) -> FastAPI:
    """Create a configured FastAPI application.

    Parameters
    ----------
    cases_root:
        Directory holding case directories.  Defaults to
        ``AGENTADVISOR_CASES_ROOT`` or ``<repo>/cases``.
    replay_dir:
        If set, the service runs in replay mode: only the given case is
        served read-only, and the SSE stream replays its audit events on
        scaled timing.  All POSTs return 409 in replay mode.
    speed:
        Replay speed factor (inter-event delay / speed).
    """
    config = ServiceConfig(
        cases_root=cases_root,
        replay_dir=replay_dir,
        speed=speed,
        monitoring_root=monitoring_root,
    )
    application = FastAPI(title="Advisor UI", version="1")
    application.state.config = config

    # Auto-resume any cases stranded in an active stage by a prior crash.
    @application.on_event("startup")
    async def _startup_auto_resume() -> None:
        if replay_dir is not None:
            return  # read-only replay mode
        _auto_resume_stuck_cases(config.cases_root)

    _register_routes(application, config)
    return application


def _percentile(values: list[float], fraction: float) -> float:
    """Nearest-rank percentile.

    Deliberately not an interpolating percentile: with the two or three runs a
    real history starts with, interpolation invents a number between two
    observations and presents it with the same authority as a measurement.
    Nearest-rank always returns a duration some case actually took.
    """
    if not values:
        raise ValueError("percentile of an empty sequence")
    ordered = sorted(values)
    rank = max(1, math.ceil(fraction * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def _case_wall_clock_s(case: Case) -> float | None:
    """Elapsed seconds for a case, from the first audit event to the last."""
    timestamps: list[datetime] = []
    for event in _read_audit_events(case):
        raw = event.get("ts")
        if isinstance(raw, str):
            try:
                timestamps.append(datetime.fromisoformat(raw.replace("Z", "+00:00")))
            except ValueError:
                continue
    if len(timestamps) < 2:
        return None
    return (max(timestamps) - min(timestamps)).total_seconds()


def _effort_history(config: ServiceConfig) -> dict[str, Any]:
    """Measured wall-clock durations per budget profile, from completed cases.

    Only ``done`` cases count.  A case that is still running or that failed
    partway through has a duration, but it is not a duration *of a completed
    case*, and quoting it would understate what finishing costs.
    """
    root = config.cases_root
    durations: dict[str, list[float]] = {}
    if root.exists():
        for entry in sorted(root.iterdir()):
            if not entry.is_dir() or not (entry / "state.yaml").exists():
                continue
            try:
                case = load_case(entry.name, cases_root=root)
                state = load_case_state(case)
                if state.stage is not CaseStage.DONE:
                    continue
                meta_path = case.root / "shared" / "control_meta.yaml"
                meta = (
                    yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
                    if meta_path.exists()
                    else {}
                )
                profile = str(meta.get("budget_profile") or "default")
                elapsed = _case_wall_clock_s(case)
            except Exception:  # noqa: BLE001 — one corrupt case must not hide the rest
                continue
            if elapsed is None or elapsed <= 0:
                continue
            durations.setdefault(profile, []).append(elapsed)

    profiles = {
        profile: {
            "samples": len(values),
            "p50_s": _percentile(values, 0.50),
            "p90_s": _percentile(values, 0.90),
        }
        for profile, values in sorted(durations.items())
    }
    return {"profiles": profiles}


def _register_routes(application: FastAPI, config: ServiceConfig) -> None:
    is_replay = config.replay_dir is not None

    # ── GET /api/cases ────────────────────────────────────────────────────
    @application.get("/api/cases", response_model=list[CaseSummary])
    async def list_cases() -> list[CaseSummary]:
        if is_replay:
            # In replay mode only the replay case is listed.
            replay_name = config.replay_dir.name if config.replay_dir else ""
            case = _load_or_404(replay_name, config)
            state = load_case_state(case)
            return [
                CaseSummary(
                    case_id=case.root.name,
                    stage=state.stage.value,
                    title=_case_title(case),
                    updated=state.updated_at.isoformat(),
                    needs_you=needs_you_for_state(state),
                )
            ]

        root = config.cases_root
        if not root.exists():
            return []
        summaries: list[CaseSummary] = []
        for entry in sorted(root.iterdir()):
            if not entry.is_dir() or not (entry / "state.yaml").exists():
                continue
            try:
                case = load_case(entry.name, cases_root=root)
                state = load_case_state(case)
            except Exception:  # noqa: BLE001 — corrupt case must not hide others
                continue
            summaries.append(
                CaseSummary(
                    case_id=entry.name,
                    stage=state.stage.value,
                    title=_case_title(case),
                    updated=state.updated_at.isoformat(),
                    needs_you=needs_you_for_state(state),
                )
            )
        return summaries

    # ── GET /api/cases/{case_id}/view ─────────────────────────────────────
    @application.get("/api/cases/{case_id}/view")
    async def get_case_view(case_id: str) -> JSONResponse:
        case = _load_or_404(case_id, config)
        view = build_case_view(case)
        return JSONResponse(content=view.model_dump(mode="json"))

    # ── GET /api/cases/{case_id}/events ───────────────────────────────────
    @application.get("/api/cases/{case_id}/events")
    async def get_events(case_id: str, request: Request, since: int = 0) -> StreamingResponse:
        case = _load_or_404(case_id, config)
        audit_path = case.root / "audit.jsonl"

        if is_replay:
            generator: AsyncIterator[str] = _replay_generator(audit_path, since, config.speed)
        else:
            generator = sse_event_stream(audit_path, since=since)

        return StreamingResponse(
            generator,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ── GET /api/cases/{case_id}/monitoring ───────────────────────────────
    @application.get("/api/cases/{case_id}/monitoring")
    async def get_monitoring(case_id: str) -> JSONResponse:
        """SPEC-042 — the delivered monitoring plan and which checks are due.

        Read-only, and it never touches the case directory: the plan lives outside the
        pipeline under the memory root, which is what lets a delivered case stay terminal.
        """
        _load_or_404(case_id, config)
        store = MonitoringStore(config.monitoring_root)
        plan = store.read_plan(case_id)
        if plan is None:
            return JSONResponse(content={"plan": None, "due": []})
        due = due_checks(plan, store.checks(case_id), as_of=config.monitoring_as_of)
        return JSONResponse(
            content={
                "plan": plan.model_dump(mode="json"),
                "due": [
                    {
                        "indicator_id": item.indicator.indicator_id,
                        "observable": item.indicator.observable,
                        "threshold": item.indicator.threshold,
                        "days_overdue": item.days_overdue,
                        "last_checked": (
                            item.last_checked.isoformat() if item.last_checked else None
                        ),
                    }
                    for item in due
                ],
            }
        )

    # ── GET /api/cases/{case_id}/artifacts/{artifact_id} ─────────────────
    @application.get("/api/cases/{case_id}/artifacts/{artifact_id:path}")
    async def get_artifact(case_id: str, artifact_id: str) -> JSONResponse:
        case = _load_or_404(case_id, config)
        target = _resolve_artifact_path(case.root, artifact_id)
        if target is None or not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail=f"Artifact not found: {artifact_id}")
        if _is_blocked(target):
            raise HTTPException(status_code=404, detail=f"Artifact not found: {artifact_id}")
        try:
            raw = target.read_text(encoding="utf-8")
        except OSError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        # Parse YAML → JSON for a stable wire format.
        schema_name = target.stem
        try:
            data = yaml.safe_load(raw)
        except yaml.YAMLError:
            data = raw
        return JSONResponse(
            content={"artifact_id": artifact_id, "schema": schema_name, "data": data}
        )

    # ── GET /api/cases/{case_id}/files/{file_path} ───────────────────────
    @application.get("/api/cases/{case_id}/files/{file_path:path}")
    async def get_file(case_id: str, file_path: str) -> PlainTextResponse:
        case = _load_or_404(case_id, config)
        target = _resolve_safe_path(case.root, file_path)
        if target is None or not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
        if _is_blocked(target):
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
        try:
            content = target.read_text(encoding="utf-8")
        except OSError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return PlainTextResponse(content, media_type="text/plain; charset=utf-8")

    # ── POST /api/cases ──────────────────────────────────────────────────
    #
    # The control-plane POSTs below are declared as *sync* ``def`` on purpose.
    # They call blocking control functions (``new_case``/``approve_framing``/
    # ``resume`` → ``_run_worker_to_halt`` → ``process.communicate()``) that
    # block until a worker subprocess reaches its next halt — seconds to many
    # minutes.  FastAPI runs sync path operations in a threadpool, so the
    # blocking call never occupies uvicorn's single asyncio event loop.  If any
    # of these were ``async def``, one in-flight control call would freeze every
    # other request (case list polls, SSE, views) for the whole worker run.
    # SPEC-046: 202, not 201, and the worker runs in the background.  Creating
    # a case used to run intake *and* framing to the first halt before
    # returning, so the client had no case id — and nothing to stream — for
    # minutes.  The case directory and its audit line are durable before this
    # responds, so the id it hands back is immediately resolvable.
    @application.post("/api/cases", status_code=202)
    def post_new_case(body: NewCaseRequest) -> JSONResponse:
        _reject_replay(is_replay)
        slug = body.slug or _slug_from_prompt(body.prompt)
        try:
            case_id = new_case(
                body.prompt,
                slug=slug,
                budget_profile=body.effort,
                cases_root=config.cases_root,
                worker_runner=spawn_worker_background,
            )
        except Exception as exc:  # noqa: BLE001
            raise _http_from_control(exc, "new", config) from exc
        return JSONResponse(
            status_code=202,
            content={"case_id": case_id, "stage": _case_stage_value(case_id, config)},
        )

    # ── POST /api/cases/{case_id}/checkpoints/scope ──────────────────────
    @application.post("/api/cases/{case_id}/checkpoints/scope")
    def post_scope_checkpoint(case_id: str, body: ScopeCheckpointRequest) -> JSONResponse:
        _reject_replay(is_replay)
        try:
            if body.decision == "approve":
                approval = FramingApproval(
                    decision=FramingDecision.APPROVE,
                    approved_by=body.approved_by,
                    approved_at=datetime.now(UTC),
                )
                approve_framing(
                    case_id,
                    approval,
                    cases_root=config.cases_root,
                    worker_runner=spawn_worker_background,
                )
            elif body.decision in ("edit", "answer_clarifications"):
                request_framing_revision(
                    case_id,
                    edits=body.edits,
                    clarification_answers=body.clarification_answers,
                    cases_root=config.cases_root,
                )
            else:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unknown scope decision: {body.decision}",
                )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise _http_from_control(exc, case_id, config) from exc
        stage = _case_stage_value(case_id, config)
        return JSONResponse(content={"case_id": case_id, "stage": stage})

    # ── POST /api/cases/{case_id}/checkpoints/delivery ───────────────────
    @application.post("/api/cases/{case_id}/checkpoints/delivery")
    def post_delivery_checkpoint(case_id: str, body: DeliveryCheckpointRequest) -> JSONResponse:
        _reject_replay(is_replay)
        try:
            if body.decision == "accept":
                approval = FinalApproval(
                    decision=FinalDecision.ACCEPT,
                    approved_by=body.approved_by,
                    approved_at=datetime.now(UTC),
                )
                approve_final(
                    case_id,
                    approval,
                    cases_root=config.cases_root,
                    worker_runner=spawn_worker_background,
                )
            elif body.decision == "revise":
                if not body.note:
                    raise HTTPException(
                        status_code=422,
                        detail="note is required for a delivery revision.",
                    )
                request_final_revision(
                    case_id,
                    note=body.note,
                    cases_root=config.cases_root,
                    worker_runner=spawn_worker_background,
                )
            else:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unknown delivery decision: {body.decision}",
                )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise _http_from_control(exc, case_id, config) from exc
        stage = _case_stage_value(case_id, config)
        return JSONResponse(content={"case_id": case_id, "stage": stage})

    # ── POST /api/cases/{case_id}/pause ──────────────────────────────────
    @application.post("/api/cases/{case_id}/pause")
    def post_pause(case_id: str) -> JSONResponse:
        _reject_replay(is_replay)
        try:
            pause(case_id, cases_root=config.cases_root)
        except Exception as exc:  # noqa: BLE001
            raise _http_from_control(exc, case_id, config) from exc
        return JSONResponse(content={"case_id": case_id, "paused": True})

    # ── POST /api/cases/{case_id}/resume ─────────────────────────────────
    @application.post("/api/cases/{case_id}/resume")
    def post_resume(case_id: str) -> JSONResponse:
        _reject_replay(is_replay)
        try:
            resume(case_id, cases_root=config.cases_root, worker_runner=spawn_worker_background)
        except Exception as exc:  # noqa: BLE001
            raise _http_from_control(exc, case_id, config) from exc
        stage = _case_stage_value(case_id, config)
        return JSONResponse(content={"case_id": case_id, "stage": stage})

    # ── GET /api/effort-history ──────────────────────────────────────────
    #
    # SPEC-050.  The effort chips promised "roughly 10-20 minutes" for a
    # standard case; the first verified real case took 191 minutes and 1.58M
    # tokens.  A product whose pitch is epistemic honesty cannot open with an
    # estimate off by an order of magnitude, and the fix is not a better guess —
    # it is to stop guessing.  This reports what runs actually took, per budget
    # profile, and says how many runs that is drawn from so the client can tell
    # a measurement from a rumour.
    #
    # A sibling read rather than part of ``/api/calibration``: calibration is
    # the system's forecasting track record, and mixing wall-clock timing into
    # it would make a single-purpose contract answer two questions.
    @application.get("/api/effort-history")
    async def get_effort_history() -> JSONResponse:
        return JSONResponse(content=_effort_history(config))

    # ── GET /api/calibration ─────────────────────────────────────────────
    #
    # SPEC-046.  ``MemoryStore.calibration()`` has existed since SPEC-025 and
    # nothing has ever served it, so no user has seen the system's own track
    # record.  Read-only and cross-case, so it takes no case id.
    @application.get("/api/calibration")
    async def get_calibration() -> JSONResponse:
        store = MemoryStore(root=memory_root())
        return JSONResponse(content=store.calibration().model_dump(mode="json"))

    # ── POST /api/cases/{case_id}/outcome ────────────────────────────────
    @application.post("/api/cases/{case_id}/outcome")
    def post_outcome(case_id: str, body: OutcomeRequest) -> JSONResponse:
        _reject_replay(is_replay)
        case = _load_or_404(case_id, config)
        state = load_case_state(case)
        if state.stage is not CaseStage.DONE:
            raise HTTPException(
                status_code=409,
                detail=f"Outcome can only be recorded for a done case (stage={state.stage.value}).",
            )
        store = MemoryStore(root=memory_root())
        try:
            prior_entry = next(
                (item for item in store.prior_cases() if item.case_id == case_id), None
            )
            if prior_entry is None:
                raise HTTPException(
                    status_code=409,
                    detail=f"Case {case_id} is not recorded in memory yet.",
                )
            forecast_name = body.forecast_name or prior_entry.headline_outcome_name
            forecast_probability = (
                body.forecast_probability
                if body.forecast_probability is not None
                else prior_entry.headline_outcome_probability
            )
            if forecast_name is None or forecast_probability is None:
                raise HTTPException(
                    status_code=422,
                    detail="No stored forecast; pass forecast_name and forecast_probability.",
                )
            store.record_outcome(
                case_id,
                OutcomeRecord(
                    recorded_at=datetime.now(UTC),
                    outcome_summary=body.summary,
                    recommendation_followed=body.followed,
                    forecast_outcome_name=forecast_name,
                    forecast_probability=forecast_probability,
                    realized=body.realized,
                ),
            )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise _http_from_control(exc, case_id, config) from exc
        return JSONResponse(content={"case_id": case_id, "outcome_recorded": True})

    # ── Test-only hooks (SPEC-037) ────────────────────────────────────────
    #
    # Compiled out of the normal service path by the env guard so the shipped
    # surface stays identical to production.  Enabled only by
    # ``AGENTADVISOR_TEST_HOOKS=1``.
    test_hooks = os.environ.get("AGENTADVISOR_TEST_HOOKS", "") == "1"
    if test_hooks:

        @application.post("/api/_test/kill-worker/{case_id}")
        async def _test_kill_worker(case_id: str) -> JSONResponse:
            from orchestrator.supervisor import RunLock

            case = _load_or_404(case_id, config)
            RunLock(case.root).release()
            return JSONResponse(content={"killed": True})

        @application.get("/api/_test/case-file/{case_id}")
        async def _test_case_file(case_id: str, path: str) -> JSONResponse:
            case = _load_or_404(case_id, config)
            target = _resolve_safe_path(case.root, path)
            if target is None or not target.exists():
                raise HTTPException(status_code=404, detail=f"File not found: {path}")
            content = target.read_text(encoding="utf-8")
            return JSONResponse(content={"path": path, "content": content})


def _reject_replay(is_replay: bool) -> None:
    if is_replay:
        raise HTTPException(
            status_code=409,
            detail="Replay mode is read-only; control POSTs are disabled.",
        )


def _http_from_control(exc: BaseException, case_id: str, config: ServiceConfig) -> HTTPException:
    response = _control_error_to_response(exc, case_id, config)
    body: bytes = bytes(response.body)
    return HTTPException(status_code=response.status_code, detail=body.decode("utf-8"))


# ── Path resolution helpers ──────────────────────────────────────────────────


def _resolve_safe_path(case_root: Path, relative: str) -> Path | None:
    """Resolve a relative path inside a case root, refusing traversal."""
    if not relative or not _SAFE_REL_RE.match(relative):
        return None
    target = (case_root / relative).resolve()
    try:
        target.relative_to(case_root.resolve())
    except ValueError:
        return None
    return target


def _resolve_artifact_path(case_root: Path, artifact_id: str) -> Path | None:
    """Resolve an artifact id to a case file path.

    ``artifact_id`` may be a relative path (e.g. ``shared/intake_record.yaml``)
    or a bare stem (e.g. ``intake_record``) which is searched under ``shared/``.
    """
    if not artifact_id:
        return None
    # Direct relative path.
    direct = _resolve_safe_path(case_root, artifact_id)
    if direct is not None and direct.exists() and direct.is_file():
        return direct
    # Bare stem: search common artifact dirs.
    if "/" not in artifact_id and not artifact_id.endswith(".yaml"):
        for sub in (
            "shared",
            "outputs",
            "analysis",
            "shared/evidence",
            "shared/assumptions",
            "shared/objections",
            "shared/tasks",
            "shared/gates",
            "shared/thesis",
        ):
            candidate = case_root / sub / f"{artifact_id}.yaml"
            if candidate.exists() and candidate.is_file():
                return candidate
    return direct


def _is_blocked(path: Path) -> bool:
    name = path.name
    if name in _BLOCKED_FILENAMES:
        return True
    if any(name.endswith(suffix) for suffix in _BLOCKED_SUFFIXES):
        return True
    if any(name.startswith(prefix) for prefix in _BLOCKED_PREFIXES):
        return True
    return False


def _slug_from_prompt(prompt: str) -> str:
    """Derive a filename-safe slug from a prompt."""
    stem = re.sub(r"[^a-z0-9]+", "-", prompt.strip().lower()).strip("-")
    if not stem:
        stem = "case"
    # Truncate to a reasonable length.
    return stem[:40]


async def _replay_generator(
    audit_path: Path,
    since: int,
    speed: float,
) -> AsyncIterator[str]:
    """Wrap the replay stream so it ends after the last recorded event."""
    async for frame in replay_stream(audit_path, since=since, speed=speed):
        yield frame


# ── Module-level app for ``uvicorn orchestrator.service.app:app`` ────────────
#
# Constructed lazily from env vars so importing the module never starts a
# server or touches the filesystem unexpectedly.  The CLI sets env vars before
# importing this module.


def _build_default_app() -> FastAPI:
    cases_root = Path(os.environ.get("AGENTADVISOR_CASES_ROOT", str(default_cases_root())))
    replay = os.environ.get("AGENTADVISOR_REPLAY_DIR")
    speed = float(os.environ.get("AGENTADVISOR_REPLAY_SPEED", "60.0"))
    replay_dir = Path(replay) if replay else None
    return create_app(cases_root=cases_root, replay_dir=replay_dir, speed=speed)


app = _build_default_app()
