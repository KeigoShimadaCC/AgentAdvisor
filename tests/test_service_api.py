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


def _make_case_dir(root: Path, case_id: str, stage: str) -> None:
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
