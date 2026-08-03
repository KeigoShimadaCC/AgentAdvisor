from __future__ import annotations

from pathlib import Path

import pytest

from orchestrator.backend import (
    CursorCLIBackend,
    DroidCLIBackend,
    ResultStatus,
    RoleInvocation,
)


@pytest.mark.live
def test_cursor_backend_live_echo(tmp_path: Path) -> None:
    token = "SPEC005_LIVE_TOKEN_9D1M"
    backend = CursorCLIBackend()
    invocation = RoleInvocation(
        role="researcher",
        model="composer-2.5",
        prompt=f"Reply with exactly {token} and nothing else.",
        workspace=tmp_path,
        timeout_s=90,
        read_only=False,
    )
    result = backend.run(invocation)

    assert result.status == ResultStatus.OK
    assert result.session_id
    assert result.result_text is not None and result.result_text.strip()
    assert result.usage is not None
    assert result.usage.input_tokens is not None


@pytest.mark.live
def test_droid_backend_live_writes_the_requested_artifact(tmp_path: Path) -> None:
    """The role contract is a written file, so a live echo alone would not prove much."""

    (tmp_path / "AGENTS.md").write_text(
        "# Role\nYou write exactly the file you are asked for, then stop.\n",
        encoding="utf-8",
    )
    backend = DroidCLIBackend()
    result = backend.run(
        RoleInvocation(
            role="researcher",
            model="claude-haiku-4-5-20251001",
            prompt=(
                "Read AGENTS.md. Write outputs/probe.yaml containing exactly "
                "'kind: probe' on one line, then reply with only DONE."
            ),
            workspace=tmp_path,
            timeout_s=180,
            read_only=False,
        )
    )

    assert result.status == ResultStatus.OK
    assert result.session_id
    assert result.cli_version is not None and result.cli_version.startswith("droid ")
    assert result.usage is not None and result.usage.input_tokens is not None
    assert (tmp_path / "outputs" / "probe.yaml").read_text(
        encoding="utf-8"
    ).strip() == "kind: probe"
