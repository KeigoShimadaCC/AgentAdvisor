"""Guards that `live` and `live_slow` tests never run unless explicitly selected.

The check runs pytest in a subprocess rather than asserting from inside a marked
test, so that `pytest -m live` stays green for the real live suite.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.live
def test_live_marker_is_registered() -> None:
    assert True


@pytest.mark.live_slow
def test_live_slow_marker_is_registered() -> None:
    assert True


@pytest.mark.parametrize("marker", ["live", "live_slow"])
def test_marked_tests_are_deselected_by_default(marker: str) -> None:
    default = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests/test_markers.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert f"test_{marker}_marker_is_registered" not in default.stdout

    selected = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", marker, "tests/"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert f"test_{marker}_marker_is_registered" in selected.stdout


def test_unknown_markers_are_an_error() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", "no_such_marker", "tests/"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert "PytestUnknownMarkWarning" not in result.stdout
