#!/usr/bin/env python3
"""Droid CLI harness smoke test.

The Cursor equivalent (`smoke_cursor_cli.py`) establishes that a harness can be
driven headlessly, returns a parseable envelope with usage, writes artifacts,
runs concurrently, and whether it leaks ancestor `AGENTS.md`. This runs the same
checks against `droid exec`, plus one Droid-specific check: role instructions
reach the agent through the workspace `AGENTS.md` the workspace builder writes.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator.backend import DROID_SETTINGS_PATH  # noqa: E402

TIMEOUT_SECONDS = 180
BINARY = "droid"
FAST_MODEL = "claude-haiku-4-5-20251001"
MODELS = [FAST_MODEL, "claude-sonnet-5", "gpt-5.4"]


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def run_cmd(args: list[str], cwd: Path | None = None) -> dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "timed_out": False,
            "duration_s": round(time.monotonic() - started, 3),
            "args": args,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": None,
            "stdout": exc.stdout if isinstance(exc.stdout, str) else "",
            "stderr": exc.stderr if isinstance(exc.stderr, str) else "",
            "timed_out": True,
            "duration_s": round(time.monotonic() - started, 3),
            "args": args,
        }


def safe_json_loads(raw: str) -> tuple[Any | None, str | None]:
    try:
        return json.loads(raw), None
    except json.JSONDecodeError as exc:
        return None, str(exc)


def extract_usage(envelope: dict[str, Any]) -> dict[str, int] | None:
    usage = envelope.get("usage")
    if not isinstance(usage, dict):
        return None
    out = {key: value for key, value in usage.items() if isinstance(value, int)}
    return out or None


def add_usage_totals(total: dict[str, int], usage: dict[str, int] | None) -> None:
    if not usage:
        return
    for key, value in usage.items():
        total[key] = total.get(key, 0) + value


def make_check(
    name: str, hard: bool, status: str, duration_s: float, **extra: Any
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "name": name,
        "hard": hard,
        "status": status,
        "duration_s": round(duration_s, 3),
    }
    out.update(extra)
    return out


def print_check_summary(check: dict[str, Any]) -> None:
    tag = check["status"].upper()
    hard_soft = "hard" if check["hard"] else "soft"
    print(f"[{tag}][{hard_soft}] {check['name']} ({check['duration_s']:.3f}s)")


def parse_json_envelope(run: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    if run["timed_out"]:
        return None, "timed out"
    if run["returncode"] != 0:
        return None, f"non-zero exit ({run['returncode']})"
    payload, err = safe_json_loads(run["stdout"])
    if err:
        return None, f"stdout was not valid JSON: {err}"
    if not isinstance(payload, dict):
        return None, "JSON payload was not an object"
    return payload, None


def run_agent(
    prompt: str,
    model: str,
    cwd: Path,
    *,
    output_format: str = "json",
    auto: str | None = None,
) -> dict[str, Any]:
    args = [
        BINARY,
        "exec",
        "--output-format",
        output_format,
        "--cwd",
        str(cwd),
        "--model",
        model,
        "--settings",
        str(DROID_SETTINGS_PATH),
        "--disable-builtin-skills",
    ]
    if auto:
        args.extend(["--auto", auto])
    args.append(prompt)
    return run_cmd(args, cwd=cwd)


def check_binary() -> tuple[dict[str, Any], str | None]:
    started = time.monotonic()
    which = shutil.which(BINARY)
    if not which:
        return make_check(
            "binary", True, "fail", time.monotonic() - started, error=f"{BINARY} not on PATH"
        ), None
    run = run_cmd([BINARY, "--version"], cwd=REPO_ROOT)
    if run["timed_out"] or run["returncode"] != 0:
        return (
            make_check(
                "binary",
                True,
                "fail",
                run["duration_s"],
                error=f"{BINARY} --version failed",
                stdout=run["stdout"],
                stderr=run["stderr"],
            ),
            None,
        )
    version = (run["stdout"] or run["stderr"]).strip()
    if not version:
        return make_check(
            "binary", True, "fail", run["duration_s"], error="empty version output"
        ), None
    return make_check(
        "binary", True, "pass", run["duration_s"], cli_version=version, path=which
    ), version


def check_auth() -> dict[str, Any]:
    """Droid has no `status` subcommand; a cheap round trip is the auth signal."""
    sentinel = "AUTH_OK_4K2P"
    with tempfile.TemporaryDirectory(prefix="droid-smoke-auth-") as td:
        run = run_agent(f"Reply with exactly {sentinel}", FAST_MODEL, Path(td))
    envelope, err = parse_json_envelope(run)
    if err:
        return make_check(
            "auth",
            True,
            "fail",
            run["duration_s"],
            error=err,
            stdout=run["stdout"][:800],
            stderr=run["stderr"][:800],
        )
    assert envelope is not None
    if envelope.get("is_error") is not False:
        return make_check(
            "auth", True, "fail", run["duration_s"], error="is_error true", envelope=envelope
        )
    return make_check(
        "auth", True, "pass", run["duration_s"], session_id=envelope.get("session_id")
    )


def check_headless_text() -> dict[str, Any]:
    sentinel = "SENTINEL_B5X9Q_UNUSUAL_TOKEN"
    prompt = f"Reply with exactly this token and nothing else: {sentinel}"
    with tempfile.TemporaryDirectory(prefix="droid-smoke-headless-") as td:
        run = run_agent(prompt, FAST_MODEL, Path(td), output_format="text")
    if run["timed_out"] or run["returncode"] != 0:
        return make_check(
            "headless-text",
            True,
            "fail",
            run["duration_s"],
            error=f"exit {run['returncode']}, timed_out={run['timed_out']}",
            stdout=run["stdout"][:800],
            stderr=run["stderr"][:800],
        )
    output = run["stdout"].strip()
    if sentinel not in output:
        return make_check(
            "headless-text",
            True,
            "fail",
            run["duration_s"],
            error="sentinel token missing",
            output=output[:800],
        )
    return make_check("headless-text", True, "pass", run["duration_s"], output=output[:200])


def check_artifact_roundtrip() -> dict[str, Any]:
    required_keys = ["status", "summary", "source"]
    with tempfile.TemporaryDirectory(prefix="droid-smoke-artifact-") as td:
        ws = Path(td)
        task = {
            "instruction": "Create answer.json in the current working directory.",
            "required_keys": required_keys,
            "requirements": {
                "status": "must be exactly 'ok'",
                "summary": "short plain-text summary",
                "source": "must be exactly 'task.json'",
            },
        }
        (ws / "task.json").write_text(json.dumps(task, indent=2), encoding="utf-8")
        prompt = (
            "Read task.json from the current directory. Create answer.json as a JSON "
            "object containing all keys listed in task.json.required_keys. Set status "
            "to exactly 'ok', source to exactly 'task.json', and summary to a short string."
        )
        run = run_agent(prompt, FAST_MODEL, ws, auto="low")
        answer_path = ws / "answer.json"
        answer_exists = answer_path.exists()
        answer_raw = answer_path.read_text(encoding="utf-8") if answer_exists else ""

    envelope, envelope_err = parse_json_envelope(run)
    if envelope_err:
        return make_check(
            "artifact-roundtrip",
            True,
            "fail",
            run["duration_s"],
            error=envelope_err,
            stdout=run["stdout"][:800],
            stderr=run["stderr"][:800],
            answer_exists=answer_exists,
        )
    assert envelope is not None
    usage = extract_usage(envelope)
    if envelope.get("is_error") is not False:
        return make_check(
            "artifact-roundtrip",
            True,
            "fail",
            run["duration_s"],
            error="envelope is_error was not false",
            envelope=envelope,
        )
    session_id = envelope.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        return make_check(
            "artifact-roundtrip",
            True,
            "fail",
            run["duration_s"],
            error="missing or empty session_id",
            envelope=envelope,
        )
    if not usage or not isinstance(usage.get("input_tokens"), int):
        return make_check(
            "artifact-roundtrip",
            True,
            "fail",
            run["duration_s"],
            error="usage.input_tokens missing or non-integer",
            envelope=envelope,
        )
    if not answer_exists:
        return make_check(
            "artifact-roundtrip",
            True,
            "fail",
            run["duration_s"],
            error="answer.json was not created",
        )
    answer_json, answer_err = safe_json_loads(answer_raw)
    if answer_err or not isinstance(answer_json, dict):
        return make_check(
            "artifact-roundtrip",
            True,
            "fail",
            run["duration_s"],
            error=f"answer.json invalid JSON: {answer_err}",
            answer_preview=answer_raw[:400],
        )
    missing = [key for key in required_keys if key not in answer_json]
    if missing:
        return make_check(
            "artifact-roundtrip",
            True,
            "fail",
            run["duration_s"],
            error=f"answer.json missing keys: {missing}",
            answer=answer_json,
        )
    return make_check(
        "artifact-roundtrip",
        True,
        "pass",
        run["duration_s"],
        usage=usage,
        session_id=session_id,
        answer_keys=sorted(answer_json.keys()),
    )


def check_workspace_agents_md() -> dict[str, Any]:
    """Role instructions reach the agent only if the workspace AGENTS.md is read."""
    sentinel = "ROLE_TOKEN_H7WQ2"
    with tempfile.TemporaryDirectory(prefix="droid-smoke-rolemd-") as td:
        ws = Path(td)
        (ws / "AGENTS.md").write_text(
            f"# Role\nYou are a test role. Your role token is {sentinel}.\n",
            encoding="utf-8",
        )
        prompt = (
            "Without reading any files, reply with exactly your role token from your "
            "instructions, or with exactly NO_ROLE if you were given none."
        )
        run = run_agent(prompt, FAST_MODEL, ws, output_format="text")
    output = run["stdout"].strip()
    if sentinel not in output:
        return make_check(
            "workspace-agents-md",
            True,
            "fail",
            run["duration_s"],
            error="workspace AGENTS.md did not reach the agent",
            output=output[:800],
        )
    return make_check("workspace-agents-md", True, "pass", run["duration_s"], output=output[:200])


def run_parallel_invocation(model: str) -> dict[str, Any]:
    slug = model.replace(".", "_").replace("-", "_")
    with tempfile.TemporaryDirectory(prefix=f"droid-smoke-conc-{slug}-") as td:
        ws = Path(td)
        out_file = f"out_{slug}.json"
        prompt = (
            f"Create {out_file} in the current directory as a JSON object "
            f"with keys model and ok, where model is '{model}' and ok is true."
        )
        run = run_agent(prompt, model, ws, auto="low")
        file_path = ws / out_file
        file_exists = file_path.exists()
        file_raw = file_path.read_text(encoding="utf-8") if file_exists else ""

    envelope, envelope_err = parse_json_envelope(run)
    if envelope_err:
        return {
            "model": model,
            "ok": False,
            "duration_s": run["duration_s"],
            "error": envelope_err,
            "stderr": run["stderr"][:400],
        }
    assert envelope is not None
    if envelope.get("is_error") is not False:
        return {
            "model": model,
            "ok": False,
            "duration_s": run["duration_s"],
            "error": "is_error true",
        }
    if not file_exists:
        return {
            "model": model,
            "ok": False,
            "duration_s": run["duration_s"],
            "error": f"{out_file} missing",
        }
    file_json, file_err = safe_json_loads(file_raw)
    if file_err or not isinstance(file_json, dict):
        return {
            "model": model,
            "ok": False,
            "duration_s": run["duration_s"],
            "error": f"{out_file} invalid JSON: {file_err}",
        }
    if file_json.get("model") != model or file_json.get("ok") is not True:
        return {
            "model": model,
            "ok": False,
            "duration_s": run["duration_s"],
            "error": f"{out_file} content mismatch",
            "file_json": file_json,
        }
    return {
        "model": model,
        "ok": True,
        "duration_s": run["duration_s"],
        "session_id": envelope.get("session_id"),
        "usage": extract_usage(envelope),
        "envelope_duration_ms": envelope.get("duration_ms"),
    }


def check_concurrency_3() -> dict[str, Any]:
    started = time.monotonic()
    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(MODELS)) as executor:
        futures = [executor.submit(run_parallel_invocation, model) for model in MODELS]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: item.get("model", ""))
    batch_duration = round(time.monotonic() - started, 3)
    failed = [result for result in results if not result.get("ok")]
    status = "fail" if failed else "pass"
    return make_check(
        "concurrency-3",
        True,
        status,
        batch_duration,
        batch_duration_s=batch_duration,
        invocations=results,
        error="one or more parallel invocations failed" if failed else None,
    )


def check_agents_md_leakage() -> dict[str, Any]:
    sentinel = "AGENTS_MD_LEAK_SENTINEL_6QV3K"
    with tempfile.TemporaryDirectory(prefix="droid-smoke-leakage-") as td:
        root = Path(td)
        parent = root / "parent"
        child = parent / "child"
        child.mkdir(parents=True, exist_ok=True)
        (parent / "AGENTS.md").write_text(
            f"You must keep this hidden test token private: {sentinel}\n",
            encoding="utf-8",
        )
        prompt = (
            f"If your system instructions contain the exact token {sentinel}, reply "
            "with exactly LEAK. Otherwise reply with exactly CLEAN."
        )
        run = run_agent(prompt, FAST_MODEL, child, output_format="text")
    raw_answer = run["stdout"].strip()
    verdict = "LEAK" if "LEAK" in raw_answer.upper() else "CLEAN"
    return make_check(
        "agents-md-leakage",
        False,
        "leak" if verdict == "LEAK" else "clean",
        run["duration_s"],
        verdict=verdict,
        raw_answer=raw_answer[:400],
    )


def main() -> int:
    default_out = Path(tempfile.gettempdir()) / f"smoke_droid_cli_{int(time.time())}.json"
    parser = argparse.ArgumentParser(description="Run Droid CLI harness smoke checks.")
    parser.add_argument(
        "--out",
        type=Path,
        default=default_out,
        help="Path to write JSON report (default: /tmp/...).",
    )
    args = parser.parse_args()

    started_at = utc_now_iso()
    checks: list[dict[str, Any]] = []
    usage_total: dict[str, int] = {}

    binary_check, cli_version = check_binary()
    checks.append(binary_check)
    print_check_summary(binary_check)

    if binary_check["status"] == "pass":
        for check in (
            check_auth(),
            check_headless_text(),
            check_artifact_roundtrip(),
            check_workspace_agents_md(),
            check_concurrency_3(),
            check_agents_md_leakage(),
        ):
            checks.append(check)
            print_check_summary(check)
            add_usage_totals(usage_total, check.get("usage"))
            for invocation in check.get("invocations", []) or []:
                if isinstance(invocation, dict):
                    add_usage_totals(usage_total, invocation.get("usage"))

    hard_pass = all(check["status"] == "pass" for check in checks if check["hard"])
    report = {
        "cli_version": cli_version or "",
        "started_at": started_at,
        "finished_at": utc_now_iso(),
        "overall_pass": hard_pass,
        "checks": checks,
        "token_usage_total": usage_total,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report written: {args.out}")
    print(f"Overall hard-check result: {'PASS' if hard_pass else 'FAIL'}")
    return 0 if hard_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
