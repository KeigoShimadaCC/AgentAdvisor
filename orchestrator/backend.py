from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from collections import deque
from collections.abc import Callable, Iterable, Mapping
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

RAW_OUTPUT_TRUNCATE_LIMIT = 8_000
RAW_OUTPUT_HEAD_CHARS = 4_000

# Droid resolves the operator's own MCP servers by default, which would put
# machine-specific tools into an agent's context and break reproducibility. The
# settings file is merged for the run only and empties that registry.
DROID_SETTINGS_PATH = Path(__file__).resolve().parent / "droid_settings.json"


class BackendName(StrEnum):
    CURSOR = "cursor"
    DROID = "droid"


BACKEND_ENV_VAR = "AGENTADVISOR_BACKEND"


class RoleInvocation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: str = Field(min_length=1)
    model: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    workspace: Path
    timeout_s: float = Field(gt=0)
    read_only: bool = False
    allow_shell: bool = False
    env_overrides: Mapping[str, str] = Field(default_factory=dict)


class ResultStatus(StrEnum):
    OK = "ok"
    TIMEOUT = "timeout"
    EXIT_ERROR = "exit_error"
    UNPARSEABLE = "unparseable"
    AGENT_ERROR = "agent_error"


class TokenUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cache_read_tokens: int | None = Field(default=None, ge=0)
    cache_write_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class RoleResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ResultStatus
    result_text: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    duration_ms: int = Field(ge=0)
    usage: TokenUsage | None = None
    raw_stdout: str = ""
    raw_stderr: str = ""
    cli_version: str | None = None


class AgentBackend(Protocol):
    name: str

    def run(self, invocation: RoleInvocation) -> RoleResult: ...


def _build_cursor_cli_args(invocation: RoleInvocation, binary_path: str) -> list[str]:
    args = [
        binary_path,
        "-p",
        invocation.prompt,
        "--trust",
        "--force",
        "--model",
        invocation.model,
        "--output-format",
        "json",
    ]
    if invocation.read_only:
        args.extend(["--mode", "plan"])
    return args


def _build_droid_cli_args(invocation: RoleInvocation, binary_path: str) -> list[str]:
    """Argument vector for `droid exec`.

    Droid expresses permissions as an autonomy level rather than a permission
    file: no `--auto` is read-only, `low` permits file writes, and `medium` is
    the lowest level that permits running the analysis code the Analyst saves.
    """

    args = [
        binary_path,
        "exec",
        "--output-format",
        "json",
        "--cwd",
        str(invocation.workspace),
        "--model",
        invocation.model,
        "--settings",
        str(DROID_SETTINGS_PATH),
        "--disable-builtin-skills",
    ]
    if not invocation.read_only:
        args.extend(["--auto", "medium" if invocation.allow_shell else "low"])
    args.append(invocation.prompt)
    return args


def _coerce_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _truncate_raw_output(raw: str) -> str:
    if len(raw) <= RAW_OUTPUT_TRUNCATE_LIMIT:
        return raw
    tail_chars = RAW_OUTPUT_TRUNCATE_LIMIT - RAW_OUTPUT_HEAD_CHARS
    omitted = len(raw) - RAW_OUTPUT_TRUNCATE_LIMIT
    return (
        raw[:RAW_OUTPUT_HEAD_CHARS] + f"\n...<truncated {omitted} chars>...\n" + raw[-tail_chars:]
    )


# The two CLIs report the same four counters under different spellings.
CURSOR_USAGE_KEYS: Mapping[str, str] = {
    "input_tokens": "inputTokens",
    "output_tokens": "outputTokens",
    "cache_read_tokens": "cacheReadTokens",
    "cache_write_tokens": "cacheWriteTokens",
}
DROID_USAGE_KEYS: Mapping[str, str] = {
    "input_tokens": "input_tokens",
    "output_tokens": "output_tokens",
    "cache_read_tokens": "cache_read_input_tokens",
    "cache_write_tokens": "cache_creation_input_tokens",
}


def _extract_usage(usage_obj: Any, usage_keys: Mapping[str, str]) -> TokenUsage | None:
    if not isinstance(usage_obj, dict):
        return None

    def _as_non_negative_int(field: str) -> int | None:
        value = usage_obj.get(usage_keys[field])
        if isinstance(value, int) and value >= 0:
            return value
        return None

    usage = TokenUsage(
        input_tokens=_as_non_negative_int("input_tokens"),
        output_tokens=_as_non_negative_int("output_tokens"),
        cache_read_tokens=_as_non_negative_int("cache_read_tokens"),
        cache_write_tokens=_as_non_negative_int("cache_write_tokens"),
    )
    if usage.input_tokens is not None or usage.output_tokens is not None:
        usage = usage.model_copy(
            update={
                "total_tokens": (usage.input_tokens or 0) + (usage.output_tokens or 0),
            }
        )
    if usage == TokenUsage():
        return None
    return usage


@lru_cache(maxsize=8)
def _detect_cli_version(binary_path: str) -> str | None:
    try:
        completed = subprocess.run(
            [binary_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return None
    output = (completed.stdout or completed.stderr or "").strip()
    if not output:
        return None
    return output.splitlines()[0]


def _kill_process_group(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=5)


def _parse_envelope(stdout: str) -> dict[str, Any] | None:
    """Both CLIs emit one JSON object on stdout, sometimes after banner lines."""

    candidates = [stdout, *reversed(stdout.splitlines())]
    for candidate in candidates:
        text = candidate.strip()
        if not text.startswith("{"):
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _run_json_cli(
    *,
    invocation: RoleInvocation,
    binary_path: str,
    args: list[str],
    usage_keys: Mapping[str, str],
    version_prefix: str = "",
) -> RoleResult:
    started = time.monotonic()
    env = os.environ.copy()
    env.update(dict(invocation.env_overrides))

    def _version() -> str | None:
        detected = _detect_cli_version(binary_path)
        if detected is None:
            return None
        return f"{version_prefix}{detected}"

    try:
        process = subprocess.Popen(
            args,
            cwd=invocation.workspace,
            # Both CLIs accept a prompt on stdin, so an inherited stdin is a
            # second, unintended input channel into the agent.
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            env=env,
        )
    except OSError as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        return RoleResult(
            status=ResultStatus.EXIT_ERROR,
            duration_ms=duration_ms,
            raw_stdout="",
            raw_stderr=_truncate_raw_output(str(exc)),
            cli_version=_version(),
        )

    try:
        stdout, stderr = process.communicate(timeout=invocation.timeout_s)
    except subprocess.TimeoutExpired as exc:
        _kill_process_group(process)
        duration_ms = int((time.monotonic() - started) * 1000)
        return RoleResult(
            status=ResultStatus.TIMEOUT,
            duration_ms=duration_ms,
            raw_stdout=_truncate_raw_output(_coerce_output(exc.stdout)),
            raw_stderr=_truncate_raw_output(_coerce_output(exc.stderr)),
            cli_version=_version(),
        )

    duration_ms = int((time.monotonic() - started) * 1000)
    raw_stdout = _truncate_raw_output(stdout)
    raw_stderr = _truncate_raw_output(stderr)
    cli_version = _version()

    # Both CLIs can exit non-zero after the agent has already produced a valid
    # result on stdout (Droid in particular can crash during post-completion
    # cleanup). Try to parse the envelope regardless of the exit code: a valid
    # envelope with is_error=false means the agent succeeded even if the process
    # tripped on its way out.
    envelope = _parse_envelope(stdout)
    if envelope is None:
        if process.returncode != 0:
            return RoleResult(
                status=ResultStatus.EXIT_ERROR,
                duration_ms=duration_ms,
                raw_stdout=raw_stdout,
                raw_stderr=raw_stderr,
                cli_version=cli_version,
            )
        return RoleResult(
            status=ResultStatus.UNPARSEABLE,
            duration_ms=duration_ms,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
            cli_version=cli_version,
        )

    envelope_duration_ms = envelope.get("duration_ms")
    if isinstance(envelope_duration_ms, int) and envelope_duration_ms >= 0:
        effective_duration_ms = envelope_duration_ms
    else:
        effective_duration_ms = duration_ms
    usage = _extract_usage(envelope.get("usage"), usage_keys)
    result_value = envelope.get("result")
    result_text = result_value if isinstance(result_value, str) else None
    session_id = envelope.get("session_id")
    request_id = envelope.get("request_id")
    is_error = envelope.get("is_error")
    status = ResultStatus.AGENT_ERROR if is_error is True else ResultStatus.OK

    return RoleResult(
        status=status,
        result_text=result_text,
        session_id=session_id if isinstance(session_id, str) else None,
        request_id=request_id if isinstance(request_id, str) else None,
        duration_ms=effective_duration_ms,
        usage=usage,
        raw_stdout=raw_stdout,
        raw_stderr=raw_stderr,
        cli_version=cli_version,
    )


class CursorCLIBackend:
    name: str = BackendName.CURSOR

    def __init__(self, binary_path: str = "cursor-agent") -> None:
        self._binary_path = binary_path

    def run(self, invocation: RoleInvocation) -> RoleResult:
        return _run_json_cli(
            invocation=invocation,
            binary_path=self._binary_path,
            args=_build_cursor_cli_args(invocation=invocation, binary_path=self._binary_path),
            usage_keys=CURSOR_USAGE_KEYS,
        )


class DroidCLIBackend:
    """Factory's `droid exec` as a second harness, on a separate model quota.

    Role instructions still arrive as the workspace `AGENTS.md` the workspace
    builder writes, which Droid loads for the working directory it is given.
    """

    name: str = BackendName.DROID

    def __init__(self, binary_path: str = "droid") -> None:
        self._binary_path = binary_path

    def run(self, invocation: RoleInvocation) -> RoleResult:
        return _run_json_cli(
            invocation=invocation,
            binary_path=self._binary_path,
            args=_build_droid_cli_args(invocation=invocation, binary_path=self._binary_path),
            usage_keys=DROID_USAGE_KEYS,
            # `droid --version` prints a bare semver that would be ambiguous in
            # an audit log shared with Cursor's date-stamped versions.
            version_prefix="droid ",
        )


def default_backend_name() -> BackendName:
    raw = os.environ.get(BACKEND_ENV_VAR, "").strip().lower()
    if not raw:
        return BackendName.CURSOR
    try:
        return BackendName(raw)
    except ValueError as exc:
        valid = ", ".join(sorted(name.value for name in BackendName))
        raise ValueError(f"{BACKEND_ENV_VAR}='{raw}' is not one of: {valid}") from exc


def make_backend(name: str | BackendName | None = None) -> AgentBackend:
    resolved = default_backend_name() if name is None else BackendName(name)
    if resolved is BackendName.DROID:
        return DroidCLIBackend()
    return CursorCLIBackend()


class StubBackend:
    def __init__(
        self,
        scripted_results: Iterable[RoleResult],
        side_effects: Iterable[Callable[[RoleInvocation], None]] | None = None,
        name: str = BackendName.CURSOR,
    ) -> None:
        self.name = name
        self._results = deque(scripted_results)
        self._side_effects = deque(side_effects or [])
        self.invocations: list[RoleInvocation] = []

    def run(self, invocation: RoleInvocation) -> RoleResult:
        self.invocations.append(invocation)
        if self._side_effects:
            side_effect = self._side_effects.popleft()
            side_effect(invocation)
        if not self._results:
            raise RuntimeError("StubBackend has no scripted results remaining")
        return self._results.popleft()
