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
