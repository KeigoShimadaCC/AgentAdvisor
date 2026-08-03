"""FastAPI service — the ``advisor ui`` REST surface (SPEC-033).

Bound to ``127.0.0.1`` only.  The service is a *reader* of case files and a
*client* of :mod:`orchestrator.control` — it never mutates case state
directly, preserving SPEC-027's single-writer discipline.

The app is constructed via :func:`create_app` so tests can inject a fixture
``cases_root`` without starting a server.  A module-level ``app`` is also
exposed for ASGI servers that import a global.
"""

from __future__ import annotations

import os
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
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
)
from orchestrator.memory import MemoryStore, memory_root
from orchestrator.service.caseview import build_case_view
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


# ── Request/response models ──────────────────────────────────────────────────


class CaseSummary(BaseModel):
    """One row in the case library list."""

    model_config = {"extra": "forbid"}

    case_id: str
    stage: str
    title: str
    updated: str


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
    ) -> None:
        self.cases_root = cases_root or default_cases_root()
        self.replay_dir = replay_dir
        self.speed = speed


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
    config = ServiceConfig(cases_root=cases_root, replay_dir=replay_dir, speed=speed)
    application = FastAPI(title="Advisor UI", version="1")
    application.state.config = config

    _register_routes(application, config)
    return application


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
    @application.post("/api/cases", status_code=201)
    async def post_new_case(body: NewCaseRequest) -> JSONResponse:
        _reject_replay(is_replay)
        slug = body.slug or _slug_from_prompt(body.prompt)
        try:
            case_id = new_case(
                body.prompt,
                slug=slug,
                budget_profile=body.effort,
                cases_root=config.cases_root,
            )
        except Exception as exc:  # noqa: BLE001
            raise _http_from_control(exc, "new", config) from exc
        return JSONResponse(
            status_code=201,
            content={"case_id": case_id, "stage": "awaiting_framing_approval"},
        )

    # ── POST /api/cases/{case_id}/checkpoints/scope ──────────────────────
    @application.post("/api/cases/{case_id}/checkpoints/scope")
    async def post_scope_checkpoint(case_id: str, body: ScopeCheckpointRequest) -> JSONResponse:
        _reject_replay(is_replay)
        try:
            if body.decision == "approve":
                approval = FramingApproval(
                    decision=FramingDecision.APPROVE,
                    approved_by=body.approved_by,
                    approved_at=datetime.now(UTC),
                )
                approve_framing(case_id, approval, cases_root=config.cases_root)
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
    async def post_delivery_checkpoint(
        case_id: str, body: DeliveryCheckpointRequest
    ) -> JSONResponse:
        _reject_replay(is_replay)
        try:
            if body.decision == "accept":
                approval = FinalApproval(
                    decision=FinalDecision.ACCEPT,
                    approved_by=body.approved_by,
                    approved_at=datetime.now(UTC),
                )
                approve_final(case_id, approval, cases_root=config.cases_root)
            elif body.decision == "revise":
                if not body.note:
                    raise HTTPException(
                        status_code=422,
                        detail="note is required for a delivery revision.",
                    )
                request_final_revision(case_id, note=body.note, cases_root=config.cases_root)
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
    async def post_pause(case_id: str) -> JSONResponse:
        _reject_replay(is_replay)
        try:
            pause(case_id, cases_root=config.cases_root)
        except Exception as exc:  # noqa: BLE001
            raise _http_from_control(exc, case_id, config) from exc
        return JSONResponse(content={"case_id": case_id, "paused": True})

    # ── POST /api/cases/{case_id}/resume ─────────────────────────────────
    @application.post("/api/cases/{case_id}/resume")
    async def post_resume(case_id: str) -> JSONResponse:
        _reject_replay(is_replay)
        try:
            resume(case_id, cases_root=config.cases_root)
        except Exception as exc:  # noqa: BLE001
            raise _http_from_control(exc, case_id, config) from exc
        stage = _case_stage_value(case_id, config)
        return JSONResponse(content={"case_id": case_id, "stage": stage})

    # ── POST /api/cases/{case_id}/outcome ────────────────────────────────
    @application.post("/api/cases/{case_id}/outcome")
    async def post_outcome(case_id: str, body: OutcomeRequest) -> JSONResponse:
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
