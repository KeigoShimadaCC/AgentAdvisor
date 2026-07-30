#!/usr/bin/env python3
"""Cursor CLI harness smoke test (SPEC-002)."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import shutil
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TIMEOUT_SECONDS = 120
MODELS = ["composer-2.5", "gpt-5.2", "cursor-grok-4.5-low"]


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def run_cmd(args: list[str], cwd: Path | None = None) -> dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
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
    out: dict[str, int] = {}
    for key, value in usage.items():
        if isinstance(value, int):
            out[key] = value
    return out if out else None


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


def run_agent(prompt: str, model: str, output_format: str, cwd: Path) -> dict[str, Any]:
    args = [
        "cursor-agent",
        "-p",
        prompt,
        "--trust",
        "--force",
        "--model",
        model,
        "--output-format",
        output_format,
    ]
    return run_cmd(args, cwd=cwd)


def check_binary(repo_root: Path) -> tuple[dict[str, Any], str | None]:
    started = time.monotonic()
    which = shutil.which("cursor-agent")
    if not which:
        return make_check(
            "binary", True, "fail", time.monotonic() - started, error="cursor-agent not on PATH"
        ), None
    run = run_cmd(["cursor-agent", "--version"], cwd=repo_root)
    if run["timed_out"]:
        return make_check(
            "binary", True, "fail", run["duration_s"], error="cursor-agent --version timed out"
        ), None
    if run["returncode"] != 0:
        return (
            make_check(
                "binary",
                True,
                "fail",
                run["duration_s"],
                error="cursor-agent --version failed",
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


def check_auth(repo_root: Path) -> dict[str, Any]:
    run = run_cmd(["cursor-agent", "status"], cwd=repo_root)
    output = f"{run['stdout']}\n{run['stderr']}".strip()
    lowered = output.lower()
    if run["timed_out"]:
        return make_check(
            "auth", True, "fail", run["duration_s"], error="cursor-agent status timed out"
        )
    if run["returncode"] != 0:
        return make_check(
            "auth",
            True,
            "fail",
            run["duration_s"],
            error=f"status exit {run['returncode']}",
            output=output,
        )
    positive = any(
        s in lowered for s in ["logged in", "authenticated", "auth: yes", "auth yes", "signed in"]
    )
    negative = any(
        s in lowered for s in ["not logged", "logged out", "unauthenticated", "auth: no", "auth no"]
    )
    if positive and not negative:
        return make_check("auth", True, "pass", run["duration_s"], output=output)
    if negative:
        return make_check(
            "auth",
            True,
            "fail",
            run["duration_s"],
            error="status indicates not logged in",
            output=output,
        )
    return make_check(
        "auth",
        True,
        "fail",
        run["duration_s"],
        error="unrecognized status output (captured for inspection)",
        output=output,
    )


def check_headless_text() -> dict[str, Any]:
    sentinel = "SENTINEL_B5X9Q_UNUSUAL_TOKEN"
    prompt = f"Reply with exactly this token and nothing else: {sentinel}"
    with tempfile.TemporaryDirectory(prefix="smoke-headless-") as td:
        run = run_agent(prompt=prompt, model="composer-2.5", output_format="text", cwd=Path(td))
    if run["timed_out"]:
        return make_check(
            "headless-text", True, "fail", run["duration_s"], error="invocation timed out"
        )
    if run["returncode"] != 0:
        return make_check(
            "headless-text",
            True,
            "fail",
            run["duration_s"],
            error=f"non-zero exit {run['returncode']}",
            stdout=run["stdout"],
            stderr=run["stderr"],
        )
    output = run["stdout"].strip()
    if sentinel not in output:
        return make_check(
            "headless-text",
            True,
            "fail",
            run["duration_s"],
            error="sentinel token missing",
            output=output,
        )
    return make_check("headless-text", True, "pass", run["duration_s"], output=output)


def check_artifact_roundtrip() -> dict[str, Any]:
    required_keys = ["status", "summary", "source"]
    with tempfile.TemporaryDirectory(prefix="smoke-artifact-") as td:
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
        run = run_agent(prompt=prompt, model="composer-2.5", output_format="json", cwd=ws)
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
            stdout=run["stdout"],
            stderr=run["stderr"],
            answer_exists=answer_exists,
            answer_preview=answer_raw[:400],
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
    if not usage or not isinstance(usage.get("inputTokens"), int):
        return make_check(
            "artifact-roundtrip",
            True,
            "fail",
            run["duration_s"],
            error="usage.inputTokens missing or non-integer",
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
    missing = [k for k in required_keys if k not in answer_json]
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


def run_parallel_invocation(model: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"smoke-concurrency-{model.replace('.', '-')}-") as td:
        ws = Path(td)
        out_file = f"out_{model.replace('.', '_').replace('-', '_')}.json"
        prompt = (
            f"Create {out_file} in the current directory as a JSON object "
            f"with keys model and ok, where model is '{model}' and ok is true."
        )
        run = run_agent(prompt=prompt, model=model, output_format="json", cwd=ws)
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
            "stdout": run["stdout"],
            "stderr": run["stderr"],
            "file_exists": file_exists,
        }
    assert envelope is not None
    usage = extract_usage(envelope)
    if envelope.get("is_error") is not False:
        return {
            "model": model,
            "ok": False,
            "duration_s": run["duration_s"],
            "error": "is_error true",
            "envelope": envelope,
        }
    if not file_exists:
        return {
            "model": model,
            "ok": False,
            "duration_s": run["duration_s"],
            "error": f"{out_file} missing",
            "envelope": envelope,
        }
    file_json, file_err = safe_json_loads(file_raw)
    if file_err or not isinstance(file_json, dict):
        return {
            "model": model,
            "ok": False,
            "duration_s": run["duration_s"],
            "error": f"{out_file} invalid JSON: {file_err}",
            "file_preview": file_raw[:400],
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
        "usage": usage,
        "envelope_duration_ms": envelope.get("duration_ms"),
    }


def check_concurrency_3() -> dict[str, Any]:
    started = time.monotonic()
    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(run_parallel_invocation, model) for model in MODELS]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda x: x.get("model", ""))
    batch_duration = round(time.monotonic() - started, 3)
    failed = [r for r in results if not r.get("ok")]
    if failed:
        return make_check(
            "concurrency-3",
            True,
            "fail",
            batch_duration,
            batch_duration_s=batch_duration,
            invocations=results,
            error="one or more parallel invocations failed",
        )
    return make_check(
        "concurrency-3",
        True,
        "pass",
        batch_duration,
        batch_duration_s=batch_duration,
        invocations=results,
    )


def check_agents_md_leakage() -> dict[str, Any]:
    sentinel = "AGENTS_MD_LEAK_SENTINEL_6QV3K"
    with tempfile.TemporaryDirectory(prefix="smoke-leakage-") as td:
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
        run = run_agent(prompt=prompt, model="composer-2.5", output_format="text", cwd=child)
    if run["timed_out"]:
        return make_check(
            "agents-md-leakage",
            False,
            "clean",
            run["duration_s"],
            verdict="CLEAN",
            note="timed out",
            raw_answer="",
        )
    raw_answer = run["stdout"].strip()
    upper = raw_answer.upper()
    verdict = "LEAK" if "LEAK" in upper else "CLEAN"
    status = "leak" if verdict == "LEAK" else "clean"
    return make_check(
        "agents-md-leakage",
        False,
        status,
        run["duration_s"],
        verdict=verdict,
        raw_answer=raw_answer,
    )


def main() -> int:
    default_out = Path(tempfile.gettempdir()) / f"smoke_cursor_cli_{int(time.time())}.json"
    parser = argparse.ArgumentParser(description="Run Cursor CLI harness smoke checks.")
    parser.add_argument(
        "--out",
        type=Path,
        default=default_out,
        help="Path to write JSON report (default: /tmp/...).",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    started_at = utc_now_iso()
    checks: list[dict[str, Any]] = []
    usage_total: dict[str, int] = {}
    cli_version = ""

    binary_check, version = check_binary(repo_root)
    checks.append(binary_check)
    print_check_summary(binary_check)
    if version:
        cli_version = version

    auth_check = check_auth(repo_root)
    checks.append(auth_check)
    print_check_summary(auth_check)

    headless_check = check_headless_text()
    checks.append(headless_check)
    print_check_summary(headless_check)

    artifact_check = check_artifact_roundtrip()
    checks.append(artifact_check)
    print_check_summary(artifact_check)
    add_usage_totals(usage_total, artifact_check.get("usage"))

    concurrency_check = check_concurrency_3()
    checks.append(concurrency_check)
    print_check_summary(concurrency_check)
    for inv in concurrency_check.get("invocations", []):
        if isinstance(inv, dict):
            add_usage_totals(usage_total, inv.get("usage"))

    leakage_check = check_agents_md_leakage()
    checks.append(leakage_check)
    print_check_summary(leakage_check)

    hard_pass = all(c["status"] == "pass" for c in checks if c["hard"])
    report = {
        "cli_version": cli_version,
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
