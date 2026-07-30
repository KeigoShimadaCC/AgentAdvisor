from __future__ import annotations

from pathlib import Path

import pytest

from orchestrator.backend import CursorCLIBackend, ResultStatus, RoleInvocation


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
