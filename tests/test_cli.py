from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from test_pipeline_stub import PipelineStubBackend

from orchestrator.artifacts import FramingApproval, FramingDecision
from orchestrator.case_store import Case, create_case, load_case
from orchestrator.cli import EXIT_OK, EXIT_USER_ERROR, main
from orchestrator.state_machine import CaseStage, load_case_state

PROMPT = "I have $50k and want semiconductor exposure. Nvidia or ETF?"
REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("AGENTADVISOR_RUNTIME_ROOT", str(tmp_path / "runtime"))
    monkeypatch.setenv("AGENTADVISOR_MEMORY_ROOT", str(tmp_path / "memory"))
    monkeypatch.setenv("AGENTADVISOR_CASES_ROOT", str(tmp_path / "cases"))
    return tmp_path / "cases"


def _backend_for(cases_root: Path) -> PipelineStubBackend:
    """The stub scripts artifacts per role, so it needs the case it is answering for."""

    class LazyBackend(PipelineStubBackend):
        def __init__(self) -> None:
            super().__init__(Case(root=cases_root / "case-001-cli"))

    return LazyBackend()


def _run(*argv: str, backend: object | None = None) -> int:
    return main(list(argv), backend=backend)  # type: ignore[arg-type]


def _start_case(cases_root: Path) -> tuple[str, PipelineStubBackend]:
    backend = _backend_for(cases_root)
    code = _run("new", PROMPT, "--slug", "cli", "--budget-profile", "small", backend=backend)
    assert code == EXIT_OK
    return "case-001-cli", backend


def test_new_creates_a_case_and_halts_at_the_framing_gate(
    env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    case_id, _ = _start_case(env)
    output = capsys.readouterr().out

    state = load_case_state(load_case(case_id, cases_root=env))
    assert state.stage is CaseStage.AWAITING_FRAMING_APPROVAL
    assert case_id in output
    assert "waiting for framing approval" in output
    assert f"advisor approve {case_id}" in output


def test_status_reports_the_same_stage_the_state_machine_holds(
    env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    case_id, _ = _start_case(env)
    capsys.readouterr()

    assert _run("status", case_id) == EXIT_OK
    output = capsys.readouterr().out

    state = load_case_state(load_case(case_id, cases_root=env))
    assert state.stage.value in output
    assert "Budget:" in output
    assert "agent_invocations" in output


def test_status_json_is_machine_readable(env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    case_id, _ = _start_case(env)
    capsys.readouterr()

    assert _run("status", case_id, "--json") == EXIT_OK
    payload = json.loads(capsys.readouterr().out)

    assert payload["case_id"] == case_id
    assert payload["stage"] == "awaiting_framing_approval"
    assert payload["awaiting"] == "framing approval"
    assert payload["budget"]["agent_invocations"][1] > 0
    assert set(payload["tasks"]) >= {"planned", "completed", "failed"}


def test_full_lifecycle_reaches_a_report(env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    case_id, backend = _start_case(env)

    assert _run("approve", case_id, "--budget-profile", "small", backend=backend) == EXIT_OK
    state = load_case_state(load_case(case_id, cases_root=env))
    assert state.stage is CaseStage.AWAITING_FINAL_APPROVAL

    assert _run("approve", case_id, "--budget-profile", "small", backend=backend) == EXIT_OK
    state = load_case_state(load_case(case_id, cases_root=env))
    assert state.stage is CaseStage.DONE
    capsys.readouterr()

    assert _run("report", case_id) == EXIT_OK
    report = capsys.readouterr().out
    assert "Final Recommendation" in report or "final_recommendation.md" in report


def test_approving_records_an_auditable_framing_artifact(env: Path) -> None:
    case_id, backend = _start_case(env)
    _run("approve", case_id, "--budget-profile", "small", backend=backend)

    approval = load_case(case_id, cases_root=env).read_artifact(FramingApproval)
    assert approval.decision is FramingDecision.APPROVE
    assert approval.approved_by == "user"


def test_framing_edits_are_recorded_rather_than_silently_applied(env: Path, tmp_path: Path) -> None:
    case_id, backend = _start_case(env)
    edits = tmp_path / "edits.yaml"
    edits.write_text(yaml.safe_dump({"alternatives": ["hold cash"]}), encoding="utf-8")

    assert (
        _run(
            "approve",
            case_id,
            "--edit",
            str(edits),
            "--budget-profile",
            "small",
            backend=backend,
        )
        == EXIT_OK
    )

    approval = load_case(case_id, cases_root=env).read_artifact(FramingApproval)
    assert approval.decision is FramingDecision.EDIT
    assert approval.edits == {"alternatives": ["hold cash"]}


def test_approving_outside_a_gate_is_a_user_error(
    env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    create_case("cli", cases_root=env)

    assert _run("approve", "case-001-cli") == EXIT_USER_ERROR
    assert "not an approval gate" in capsys.readouterr().err


def test_edit_flags_are_rejected_at_the_final_gate(
    env: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    case_id, backend = _start_case(env)
    _run("approve", case_id, "--budget-profile", "small", backend=backend)
    edits = tmp_path / "edits.yaml"
    edits.write_text(yaml.safe_dump({"alternatives": ["hold cash"]}), encoding="utf-8")
    capsys.readouterr()

    code = _run("approve", case_id, "--edit", str(edits), backend=backend)

    assert code == EXIT_USER_ERROR
    assert "framing gate only" in capsys.readouterr().err


def test_resume_refuses_while_a_gate_is_open(env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    case_id, backend = _start_case(env)
    capsys.readouterr()

    assert _run("resume", case_id, backend=backend) == EXIT_USER_ERROR
    assert "advisor approve" in capsys.readouterr().err


def test_resume_without_an_intake_record_explains_itself(
    env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    create_case("cli", cases_root=env)

    assert _run("resume", "case-001-cli") == EXIT_USER_ERROR
    assert "advisor new" in capsys.readouterr().err


def test_report_before_there_is_one_is_a_user_error(
    env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    case_id, _ = _start_case(env)
    capsys.readouterr()

    assert _run("report", case_id) == EXIT_USER_ERROR
    assert "no report yet" in capsys.readouterr().err


def test_an_unknown_case_id_is_a_user_error(env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _run("status", "case-404-nope") == EXIT_USER_ERROR
    assert "does not exist" in capsys.readouterr().err


def test_a_malformed_case_id_is_a_user_error(env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _run("status", "../../etc") == EXIT_USER_ERROR
    assert "Invalid case_id" in capsys.readouterr().err


def test_list_shows_each_case_with_its_stage(env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    case_id, _ = _start_case(env)
    capsys.readouterr()

    assert _run("list", "--json") == EXIT_OK
    rows = json.loads(capsys.readouterr().out)

    assert [row["case_id"] for row in rows] == [case_id]
    assert rows[0]["awaiting"] == "framing approval"


def test_list_on_an_empty_root_says_so(env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _run("list") == EXIT_OK
    assert "No cases yet" in capsys.readouterr().out


def test_an_empty_prompt_is_rejected_before_a_case_is_created(
    env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run("new", "   ") == EXIT_USER_ERROR
    assert "empty" in capsys.readouterr().err
    assert not env.exists() or not list(env.iterdir())


def test_the_installed_entry_point_runs(env: Path) -> None:
    """The console script must actually be wired, not merely importable."""
    result = subprocess.run(
        [sys.executable, "-m", "orchestrator.cli", "list"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={
            "PATH": "/usr/bin:/bin",
            "AGENTADVISOR_CASES_ROOT": str(env),
            "PYTHONPATH": str(REPO_ROOT),
        },
    )

    assert result.returncode == EXIT_OK, result.stderr
    assert "No cases yet" in result.stdout
