from __future__ import annotations

import os
import stat
import time
from pathlib import Path

import pytest

from orchestrator.backend import (
    RAW_OUTPUT_TRUNCATE_LIMIT,
    CursorCLIBackend,
    ResultStatus,
    RoleInvocation,
)


@pytest.fixture
def fake_cursor_agent(tmp_path: Path) -> Path:
    script = tmp_path / "fake-cursor-agent.sh"
    script.write_text(
        """#!/bin/sh
set -eu

if [ -n "${FAKE_ARGS_FILE:-}" ]; then
  printf "%s\\n" "$@" > "${FAKE_ARGS_FILE}"
fi

mode="${FAKE_CURSOR_MODE:-ok}"

if [ "$mode" = "ok" ]; then
  cat <<'JSON'
{
  "is_error": false,
  "session_id": "sess-ok",
  "request_id": "req-ok",
  "duration_ms": 1234,
  "result": "ok result",
  "usage": {
    "inputTokens": 11,
    "outputTokens": 7,
    "cacheReadTokens": 3,
    "cacheWriteTokens": 2
  }
}
JSON
  exit 0
fi

if [ "$mode" = "agent_error" ]; then
  cat <<'JSON'
{
  "is_error": true,
  "session_id": "sess-err",
  "request_id": "req-err",
  "duration_ms": 999,
  "result": "agent failed",
  "usage": {
    "inputTokens": 5,
    "outputTokens": 1,
    "cacheReadTokens": 0,
    "cacheWriteTokens": 0
  }
}
JSON
  exit 0
fi

if [ "$mode" = "unparseable" ]; then
  echo "not-json-envelope"
  exit 0
fi

if [ "$mode" = "exit_error" ]; then
  echo "failed on purpose" >&2
  exit 17
fi

if [ "$mode" = "timeout" ]; then
  if [ -n "${FAKE_CHILD_PID_FILE:-}" ]; then
    sleep 120 &
    echo "$!" > "${FAKE_CHILD_PID_FILE}"
  fi
  sleep "${FAKE_SLEEP_SECONDS:-120}"
  exit 0
fi

if [ "$mode" = "huge_stdout" ]; then
  python3 - <<'PY'
import os
size = int(os.environ.get("FAKE_HUGE_SIZE", "30000"))
print("X" * size, end="")
PY
  exit 0
fi

echo "unknown mode: $mode" >&2
exit 2
""",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def _make_invocation(
    workspace: Path,
    *,
    timeout_s: float = 5.0,
    read_only: bool = False,
    env_overrides: dict[str, str] | None = None,
) -> RoleInvocation:
    return RoleInvocation(
        role="researcher",
        model="composer-2.5",
        prompt="Say hi",
        workspace=workspace,
        timeout_s=timeout_s,
        read_only=read_only,
        env_overrides=env_overrides or {},
    )


@pytest.mark.parametrize(
    ("mode", "expected_status"),
    [
        ("ok", ResultStatus.OK),
        ("agent_error", ResultStatus.AGENT_ERROR),
        ("unparseable", ResultStatus.UNPARSEABLE),
        ("exit_error", ResultStatus.EXIT_ERROR),
    ],
)
def test_cursor_backend_status_mappings(
    fake_cursor_agent: Path,
    tmp_path: Path,
    mode: str,
    expected_status: ResultStatus,
) -> None:
    backend = CursorCLIBackend(binary_path=str(fake_cursor_agent))
    invocation = _make_invocation(
        tmp_path,
        env_overrides={"FAKE_CURSOR_MODE": mode},
    )
    result = backend.run(invocation)
    assert result.status == expected_status

    if expected_status == ResultStatus.OK:
        assert result.session_id == "sess-ok"
        assert result.request_id == "req-ok"
        assert result.usage is not None
        assert result.usage.input_tokens == 11
        assert result.usage.output_tokens == 7
        assert result.usage.cache_read_tokens == 3
        assert result.usage.cache_write_tokens == 2
        assert result.result_text == "ok result"
    elif expected_status == ResultStatus.AGENT_ERROR:
        assert result.result_text == "agent failed"
        assert result.session_id == "sess-err"
    else:
        assert result.result_text is None


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def test_cursor_backend_timeout_kills_process_group(
    fake_cursor_agent: Path,
    tmp_path: Path,
) -> None:
    child_pid_file = tmp_path / "child.pid"
    backend = CursorCLIBackend(binary_path=str(fake_cursor_agent))
    invocation = _make_invocation(
        tmp_path,
        timeout_s=1.0,
        env_overrides={
            "FAKE_CURSOR_MODE": "timeout",
            "FAKE_SLEEP_SECONDS": "30",
            "FAKE_CHILD_PID_FILE": str(child_pid_file),
        },
    )

    started = time.monotonic()
    result = backend.run(invocation)
    elapsed = time.monotonic() - started

    assert result.status == ResultStatus.TIMEOUT
    assert elapsed <= invocation.timeout_s + 5.0

    assert child_pid_file.exists()
    child_pid = int(child_pid_file.read_text(encoding="utf-8").strip())
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and _pid_exists(child_pid):
        time.sleep(0.05)
    assert not _pid_exists(child_pid)


def test_cursor_backend_plan_mode_flag_behavior(
    fake_cursor_agent: Path,
    tmp_path: Path,
) -> None:
    backend = CursorCLIBackend(binary_path=str(fake_cursor_agent))

    args_file_read_only = tmp_path / "args_read_only.txt"
    read_only_result = backend.run(
        _make_invocation(
            tmp_path,
            read_only=True,
            env_overrides={
                "FAKE_CURSOR_MODE": "ok",
                "FAKE_ARGS_FILE": str(args_file_read_only),
            },
        )
    )
    assert read_only_result.status == ResultStatus.OK
    read_only_args = args_file_read_only.read_text(encoding="utf-8").splitlines()
    assert "--mode" in read_only_args
    idx = read_only_args.index("--mode")
    assert read_only_args[idx + 1] == "plan"

    args_file_default = tmp_path / "args_default.txt"
    default_result = backend.run(
        _make_invocation(
            tmp_path,
            read_only=False,
            env_overrides={
                "FAKE_CURSOR_MODE": "ok",
                "FAKE_ARGS_FILE": str(args_file_default),
            },
        )
    )
    assert default_result.status == ResultStatus.OK
    default_args = args_file_default.read_text(encoding="utf-8").splitlines()
    assert "--mode" not in default_args


def test_cursor_backend_truncates_huge_raw_stdout(
    fake_cursor_agent: Path,
    tmp_path: Path,
) -> None:
    backend = CursorCLIBackend(binary_path=str(fake_cursor_agent))
    result = backend.run(
        _make_invocation(
            tmp_path,
            env_overrides={
                "FAKE_CURSOR_MODE": "huge_stdout",
                "FAKE_HUGE_SIZE": "30000",
            },
        )
    )
    assert result.status == ResultStatus.UNPARSEABLE
    assert "...<truncated " in result.raw_stdout
    assert len(result.raw_stdout) <= RAW_OUTPUT_TRUNCATE_LIMIT + 100
