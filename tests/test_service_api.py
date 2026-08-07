"""SPEC-033 — REST API tests via FastAPI TestClient (no browser)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from orchestrator.service.app import create_app

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "cases"


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    """A TestClient pointed at the fixture cases directory."""
    app = create_app(cases_root=FIXTURES)
    return TestClient(app)


# ── GET /api/cases ───────────────────────────────────────────────────────────


def test_list_cases_returns_both_fixtures(client: TestClient) -> None:
    resp = client.get("/api/cases")
    assert resp.status_code == 200
    ids = {c["case_id"] for c in resp.json()}
    assert "case-001-fixture-001" in ids
    assert "case-002-fixture-002-parked" in ids


def test_list_cases_empty_dir(tmp_path: Path) -> None:
    app = create_app(cases_root=tmp_path)
    c = TestClient(app)
    assert c.get("/api/cases").json() == []


# ── GET /api/cases/{id}/view ────────────────────────────────────────────────


def test_get_case_view_fixture_001(client: TestClient) -> None:
    resp = client.get("/api/cases/case-001-fixture-001/view")
    assert resp.status_code == 200
    view = resp.json()
    assert view["case_id"] == "case-001-fixture-001"
    assert view["view_version"] == 1
    assert view["is_terminal"] is True


def test_get_case_view_fixture_002_parked(client: TestClient) -> None:
    resp = client.get("/api/cases/case-002-fixture-002-parked/view")
    assert resp.status_code == 200
    view = resp.json()
    assert view["needs_you"] == "scope_checkpoint"


def test_get_case_view_unknown_case_404(client: TestClient) -> None:
    resp = client.get("/api/cases/nonexistent/view")
    assert resp.status_code == 404


# ── GET /api/cases/{id}/artifacts/{artifact_id} ─────────────────────────────


def test_get_artifact_by_path(client: TestClient) -> None:
    resp = client.get("/api/cases/case-001-fixture-001/artifacts/shared/intake_record.yaml")
    assert resp.status_code == 200
    body = resp.json()
    assert body["schema"] == "intake_record"
    assert isinstance(body["data"], dict)


def test_get_artifact_by_bare_stem(client: TestClient) -> None:
    resp = client.get("/api/cases/case-001-fixture-001/artifacts/intake_record")
    assert resp.status_code == 200
    body = resp.json()
    assert body["schema"] == "intake_record"


def test_get_artifact_not_found(client: TestClient) -> None:
    resp = client.get("/api/cases/case-001-fixture-001/artifacts/shared/missing.yaml")
    assert resp.status_code == 404


# ── GET /api/cases/{id}/files/{path} ────────────────────────────────────────


def test_get_file_passthrough(client: TestClient) -> None:
    resp = client.get("/api/cases/case-001-fixture-001/files/outputs/final_recommendation.md")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    assert len(resp.text) > 0


def test_get_file_traversal_blocked(client: TestClient) -> None:
    resp = client.get("/api/cases/case-001-fixture-001/files/../../etc/passwd")
    assert resp.status_code == 404


def test_get_file_blocked_hidden(client: TestClient) -> None:
    resp = client.get("/api/cases/case-001-fixture-001/files/.run.lock")
    assert resp.status_code == 404


# ── POST endpoints (wrong stage / validation) ───────────────────────────────


def test_scope_checkpoint_wrong_stage_409(client: TestClient) -> None:
    # fixture-001 is done, not awaiting framing
    resp = client.post(
        "/api/cases/case-001-fixture-001/checkpoints/scope",
        json={"decision": "approve"},
    )
    assert resp.status_code == 409


def test_delivery_checkpoint_wrong_stage_409(client: TestClient) -> None:
    resp = client.post(
        "/api/cases/case-001-fixture-001/checkpoints/delivery",
        json={"decision": "accept"},
    )
    assert resp.status_code == 409


def test_pause_unknown_case_404(client: TestClient) -> None:
    resp = client.post("/api/cases/case-999-nonexistent/pause")
    assert resp.status_code == 404


def test_resume_unknown_case_404(client: TestClient) -> None:
    resp = client.post("/api/cases/case-999-nonexistent/resume")
    assert resp.status_code == 404


def test_outcome_requires_done_stage(client: TestClient) -> None:
    # fixture-002 is parked, not done
    resp = client.post(
        "/api/cases/case-002-fixture-002-parked/outcome",
        json={"summary": "test", "followed": False, "realized": False},
    )
    assert resp.status_code == 409


# ── Replay mode ─────────────────────────────────────────────────────────────


def test_replay_mode_lists_only_replay_case(tmp_path: Path) -> None:
    app = create_app(
        cases_root=FIXTURES,
        replay_dir=FIXTURES / "case-001-fixture-001",
        speed=1000.0,
    )
    c = TestClient(app)
    resp = c.get("/api/cases")
    assert resp.status_code == 200
    cases = resp.json()
    assert len(cases) == 1
    assert cases[0]["case_id"] == "case-001-fixture-001"


def test_replay_mode_rejects_post(tmp_path: Path) -> None:
    app = create_app(
        cases_root=FIXTURES,
        replay_dir=FIXTURES / "case-001-fixture-001",
        speed=1000.0,
    )
    c = TestClient(app)
    resp = c.post(
        "/api/cases",
        json={"prompt": "test", "effort": "default"},
    )
    assert resp.status_code == 409


def test_replay_mode_scope_checkpoint_rejected(tmp_path: Path) -> None:
    app = create_app(
        cases_root=FIXTURES,
        replay_dir=FIXTURES / "case-001-fixture-001",
        speed=1000.0,
    )
    c = TestClient(app)
    resp = c.post(
        "/api/cases/case-001-fixture-001/checkpoints/scope",
        json={"decision": "approve"},
    )
    assert resp.status_code == 409


# ── Auto-resume on startup ──────────────────────────────────────────────────


def _make_state_yaml(case_id: str, stage: str) -> str:
    return (
        f"budget_counters: {{}}\n"
        f"case_id: {case_id}\n"
        f"created_at: '2026-08-04T00:00:00Z'\n"
        f"elapsed_s: 0.0\n"
        f"failure_cause: null\n"
        f"final_approved: false\n"
        f"final_revisions: 0\n"
        f"framing_approved: false\n"
        f"framing_revisions: 0\n"
        f"repair_cycle: 0\n"
        f"review_accepted: null\n"
        f"schema_version: 1\n"
        f"stage: {stage}\n"
        f"started_at_run: null\n"
        f"synthesis_retries: 0\n"
        f"updated_at: '2026-08-04T00:00:00Z'\n"
    )


def _make_case_dir(root: Path, case_id: str, stage: str, *, resumable: bool = True) -> None:
    case_dir = root / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "shared" / "evidence").mkdir(parents=True, exist_ok=True)
    (case_dir / "shared" / "assumptions").mkdir(parents=True, exist_ok=True)
    (case_dir / "shared" / "objections").mkdir(parents=True, exist_ok=True)
    (case_dir / "shared" / "tasks").mkdir(parents=True, exist_ok=True)
    (case_dir / "agents").mkdir(parents=True, exist_ok=True)
    (case_dir / "analysis").mkdir(parents=True, exist_ok=True)
    (case_dir / "outputs").mkdir(parents=True, exist_ok=True)
    (case_dir / "shared" / "task_graph.yaml").write_text("nodes: []\n", encoding="utf-8")
    (case_dir / "state.yaml").write_text(_make_state_yaml(case_id, stage))
    (case_dir / "audit.jsonl").write_text("")
    # A worker recovers the prompt from control_meta (or an IntakeRecord); a
    # case with neither cannot resume and auto-resume must skip it.
    if resumable:
        (case_dir / "shared" / "control_meta.yaml").write_text(
            "raw_prompt: Should I take the offer?\nbudget_profile: small\n",
            encoding="utf-8",
        )


def test_find_stuck_cases_detects_active_stages(tmp_path: Path) -> None:
    from orchestrator.service.app import _find_stuck_cases

    _make_case_dir(tmp_path, "case-001-stuck-investigation", "investigation")
    _make_case_dir(tmp_path, "case-002-stuck-synthesis", "synthesis")
    stuck = _find_stuck_cases(tmp_path)
    stuck_ids = {cid for cid, _ in stuck}
    assert "case-001-stuck-investigation" in stuck_ids
    assert "case-002-stuck-synthesis" in stuck_ids


def test_find_stuck_cases_ignores_halt_and_terminal(tmp_path: Path) -> None:
    from orchestrator.service.app import _find_stuck_cases

    _make_case_dir(tmp_path, "case-003-awaiting-framing", "awaiting_framing_approval")
    _make_case_dir(tmp_path, "case-004-awaiting-final", "awaiting_final_approval")
    _make_case_dir(tmp_path, "case-005-done", "done")
    _make_case_dir(tmp_path, "case-006-failed", "failed")
    stuck = _find_stuck_cases(tmp_path)
    assert stuck == []


def test_find_stuck_cases_empty_dir(tmp_path: Path) -> None:
    from orchestrator.service.app import _find_stuck_cases

    assert _find_stuck_cases(tmp_path) == []


def test_find_stuck_cases_skips_unresumable(tmp_path: Path) -> None:
    """A legacy case with no raw_prompt/IntakeRecord must be skipped, not resumed.

    Auto-resuming it just spawns a worker that crashes on every startup.
    """
    from orchestrator.service.app import _find_stuck_cases

    _make_case_dir(tmp_path, "case-010-resumable", "investigation", resumable=True)
    _make_case_dir(tmp_path, "case-011-legacy-broken", "investigation", resumable=False)
    stuck_ids = {cid for cid, _ in _find_stuck_cases(tmp_path)}
    assert "case-010-resumable" in stuck_ids
    assert "case-011-legacy-broken" not in stuck_ids


def test_control_post_endpoints_are_sync() -> None:
    """Control-plane POSTs must be sync ``def`` so FastAPI runs them in a threadpool.

    Each one calls a blocking control function (``new_case``/``approve_framing``/
    ``resume`` → ``_run_worker_to_halt`` → ``process.communicate()``) that blocks
    until a worker subprocess halts — seconds to minutes.  If any were declared
    ``async def`` they would run on uvicorn's single event loop and freeze every
    other request (case list polls, SSE, views) for the whole worker run, which
    is exactly the "Loading… forever" freeze this guards against.
    """
    import asyncio

    app = create_app(cases_root=FIXTURES)
    control_paths = {
        "/api/cases",
        "/api/cases/{case_id}/checkpoints/scope",
        "/api/cases/{case_id}/checkpoints/delivery",
        "/api/cases/{case_id}/pause",
        "/api/cases/{case_id}/resume",
        "/api/cases/{case_id}/outcome",
    }
    seen: set[str] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", set()) or set()
        if path in control_paths and "POST" in methods:
            seen.add(path)
            assert not asyncio.iscoroutinefunction(route.endpoint), (
                f"{path} POST must be a sync def so its blocking control call "
                "runs in a threadpool and never freezes the event loop."
            )
    assert seen == control_paths, f"missing control POST routes: {control_paths - seen}"


# ── SPEC-046: service additions ──────────────────────────────────────────────


def test_new_case_returns_202_without_waiting_for_the_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Creation must not block through intake and framing.

    Before this, ``POST /api/cases`` ran the worker to the first halt, so the
    client had no case id — and nothing to stream — for minutes.  The case has
    to be durable and resolvable when the response lands; the analysis catches
    up over SSE.
    """
    started: list[str] = []

    def _fake_worker(case_id: str, cases_root: Path) -> None:
        started.append(case_id)  # returns immediately, like the background runner

    monkeypatch.setattr("orchestrator.service.app.spawn_worker_background", _fake_worker)
    app = create_app(cases_root=tmp_path)
    c = TestClient(app)

    resp = c.post("/api/cases", json={"prompt": "Should I take the offer?", "effort": "light"})

    assert resp.status_code == 202
    case_id = resp.json()["case_id"]
    assert started == [case_id], "the worker was not handed the case"

    # Durable and resolvable the moment the response returns.
    assert (tmp_path / case_id / "state.yaml").exists()
    assert c.get(f"/api/cases/{case_id}/view").status_code == 200
    audit = (tmp_path / case_id / "audit.jsonl").read_text(encoding="utf-8")
    assert "control_case_created" in audit


def test_new_case_uses_the_background_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The endpoint must pass the non-blocking runner, not the default."""
    from orchestrator.service import app as app_module

    captured: dict[str, object] = {}
    real_new_case = app_module.new_case

    def _spy(prompt: str, **kwargs: object) -> str:
        captured.update(kwargs)
        return real_new_case(prompt, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(app_module, "new_case", _spy)
    monkeypatch.setattr(app_module, "spawn_worker_background", lambda *_a, **_k: None)
    c = TestClient(create_app(cases_root=tmp_path))

    c.post("/api/cases", json={"prompt": "Build or buy?"})

    assert captured["worker_runner"] is app_module.spawn_worker_background


def test_case_list_carries_needs_you_matching_the_projection(client: TestClient) -> None:
    """One rule, one implementation.

    The client used to re-derive this from a stage string, which is a second
    copy of a rule the projection already owns.
    """
    listed = {c["case_id"]: c["needs_you"] for c in client.get("/api/cases").json()}
    assert listed, "no fixture cases listed"

    for case_id, needs_you in listed.items():
        projected = client.get(f"/api/cases/{case_id}/view").json()["needs_you"]
        assert needs_you == projected, f"{case_id}: list says {needs_you}, view says {projected}"

    # The parked fixture is the one that should be asking for a signature.
    assert listed["case-002-fixture-002-parked"] == "scope_checkpoint"


def test_calibration_endpoint_reports_an_empty_history_honestly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no outcomes, it must say so rather than imply a score."""
    monkeypatch.setenv("AGENTADVISOR_MEMORY_ROOT", str(tmp_path / "memory"))
    c = TestClient(create_app(cases_root=tmp_path))

    resp = c.get("/api/calibration")

    assert resp.status_code == 200
    body = resp.json()
    assert body["sample_size"] == 0
    assert body["brier_score"] is None
    assert "calibration is unknown" in body["interpretation"]


def test_calibration_endpoint_flags_a_small_sample_as_noise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Under five outcomes the honesty is in the wording, so it is asserted.

    A UI that turned this into a confident dial would undo the property
    ``calibration.py`` was written to protect.
    """
    from orchestrator.calibration import summarize_calibration

    monkeypatch.setenv("AGENTADVISOR_MEMORY_ROOT", str(tmp_path / "memory"))
    c = TestClient(create_app(cases_root=tmp_path))

    monkeypatch.setattr(
        "orchestrator.memory.MemoryStore.calibration",
        lambda _self: summarize_calibration(
            [
                _outcome(0.7, realized=True),
                _outcome(0.4, realized=False),
            ]
        ),
    )

    body = c.get("/api/calibration").json()
    assert body["sample_size"] == 2
    assert "noise, not a calibration estimate" in body["interpretation"]


def _outcome(probability: float, *, realized: bool):
    from datetime import UTC, datetime

    from orchestrator.artifacts import OutcomeRecord

    return OutcomeRecord(
        recorded_at=datetime.now(UTC),
        outcome_summary="recorded for a calibration test",
        recommendation_followed=True,
        forecast_outcome_name="the recommended option outperformed",
        forecast_probability=probability,
        realized=realized,
    )


def test_needs_you_is_correct_for_every_state(tmp_path: Path) -> None:
    """All four needs-you states, not just the two the fixtures happen to hold.

    The fixtures cover `none` and `scope_checkpoint`; a rule with four branches
    needs all four exercised, or the two untested ones are free to drift.
    """
    from datetime import UTC, datetime

    from orchestrator.artifacts.yaml_io import dump_model_to_yaml_text
    from orchestrator.case_store import create_case
    from orchestrator.state_machine import CaseStage, CaseState

    expected = {
        CaseStage.INVESTIGATION: "none",
        CaseStage.AWAITING_FRAMING_APPROVAL: "scope_checkpoint",
        CaseStage.AWAITING_FINAL_APPROVAL: "delivery_checkpoint",
        CaseStage.FAILED: "interrupted",
    }

    for stage in expected:
        slug = f"needs-you-{stage.value.replace(chr(95), chr(45))}"
        case = create_case(slug, cases_root=tmp_path)
        now = datetime.now(UTC)
        state = CaseState(case_id=case.root.name, stage=stage, created_at=now, updated_at=now)
        (case.root / "state.yaml").write_text(dump_model_to_yaml_text(state), encoding="utf-8")

    c = TestClient(create_app(cases_root=tmp_path))
    listed = {row["case_id"]: row["needs_you"] for row in c.get("/api/cases").json()}

    for stage, want in expected.items():
        slug = f"needs-you-{stage.value.replace(chr(95), chr(45))}"
        case_id = next(cid for cid in listed if cid.endswith(slug))
        assert listed[case_id] == want, f"{stage.value}: listed {listed[case_id]}, want {want}"
        # And the list must agree with the projection for the same case.
        projected = c.get(f"/api/cases/{case_id}/view").json()["needs_you"]
        assert listed[case_id] == projected


# ── GET /api/effort-history (SPEC-050) ───────────────────────────────────────


def _make_timed_case(
    root: Path, slug: str, *, profile: str, stage: str, start: str, end: str
) -> None:
    """A real case layout with a known duration and budget profile."""
    import json

    from orchestrator.case_store import create_case

    case = create_case(slug, cases_root=root)
    (case.root / "state.yaml").write_text(
        "\n".join(
            [
                f"case_id: {case.root.name}",
                "created_at: '2026-08-01T00:00:00Z'",
                "elapsed_s: 0.0",
                "failure_cause: null",
                "final_approved: true",
                "final_revisions: 0",
                "framing_approved: true",
                "framing_revisions: 0",
                "repair_cycle: 0",
                "review_accepted: true",
                "schema_version: 1",
                f"stage: {stage}",
                "synthesis_retries: 0",
                "updated_at: '2026-08-01T00:00:00Z'",
            ]
        ),
        encoding="utf-8",
    )
    (case.root / "shared" / "control_meta.yaml").write_text(
        f"budget_profile: {profile}\nraw_prompt: a decision\n", encoding="utf-8"
    )
    lines = [
        json.dumps({"ts": start, "event_type": "case_created", "payload": {}}),
        json.dumps({"ts": end, "event_type": "case_finalized", "payload": {}}),
    ]
    (case.root / "audit.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_effort_history_reports_measured_durations_per_profile(tmp_path: Path) -> None:
    """The whole point of the endpoint: report what runs took, not what we hoped."""
    _make_timed_case(
        tmp_path,
        "effort-a",
        profile="default",
        stage="done",
        start="2026-08-01T00:00:00Z",
        end="2026-08-01T01:00:00Z",
    )
    _make_timed_case(
        tmp_path,
        "effort-b",
        profile="default",
        stage="done",
        start="2026-08-01T00:00:00Z",
        end="2026-08-01T03:00:00Z",
    )
    _make_timed_case(
        tmp_path,
        "effort-c",
        profile="deep",
        stage="done",
        start="2026-08-01T00:00:00Z",
        end="2026-08-01T05:00:00Z",
    )

    body = TestClient(create_app(cases_root=tmp_path)).get("/api/effort-history").json()

    assert body["profiles"]["default"]["samples"] == 2
    assert body["profiles"]["default"]["p50_s"] == 3600.0
    assert body["profiles"]["default"]["p90_s"] == 10800.0
    assert body["profiles"]["deep"]["samples"] == 1
    assert body["profiles"]["deep"]["p50_s"] == 18000.0


def test_effort_history_counts_only_completed_cases(tmp_path: Path) -> None:
    """A case still running has a duration, but not a duration of a *completed* case.

    Counting it would quote a number smaller than what finishing actually costs,
    which is the same failure as the authored estimate this endpoint replaces.
    """
    _make_timed_case(
        tmp_path,
        "done-case",
        profile="default",
        stage="done",
        start="2026-08-01T00:00:00Z",
        end="2026-08-01T02:00:00Z",
    )
    _make_timed_case(
        tmp_path,
        "running-case",
        profile="default",
        stage="investigation",
        start="2026-08-01T00:00:00Z",
        end="2026-08-01T00:05:00Z",
    )

    body = TestClient(create_app(cases_root=tmp_path)).get("/api/effort-history").json()
    assert body["profiles"]["default"]["samples"] == 1
    assert body["profiles"]["default"]["p50_s"] == 7200.0


def test_effort_history_is_empty_rather_than_absent_with_no_cases(tmp_path: Path) -> None:
    body = TestClient(create_app(cases_root=tmp_path)).get("/api/effort-history").json()
    assert body == {"profiles": {}}


def test_effort_history_survives_a_corrupt_case(tmp_path: Path) -> None:
    """One unreadable case must not hide every other case's timing."""
    _make_timed_case(
        tmp_path,
        "good-case",
        profile="default",
        stage="done",
        start="2026-08-01T00:00:00Z",
        end="2026-08-01T01:00:00Z",
    )
    broken = tmp_path / "case-999-broken"
    broken.mkdir()
    (broken / "state.yaml").write_text("{{{ not yaml", encoding="utf-8")

    body = TestClient(create_app(cases_root=tmp_path)).get("/api/effort-history").json()
    assert body["profiles"]["default"]["samples"] == 1


def test_effort_history_percentile_returns_an_observed_duration(tmp_path: Path) -> None:
    """Nearest-rank, not interpolating.

    With the two or three runs a real history starts with, an interpolating
    percentile invents a number between two observations and presents it with
    the authority of a measurement. Every value returned here is a duration some
    case actually took.
    """
    from orchestrator.service.app import _percentile

    observations = [60.0, 300.0, 4000.0]
    for fraction in (0.5, 0.9):
        assert _percentile(observations, fraction) in observations
