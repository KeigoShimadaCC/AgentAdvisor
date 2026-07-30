from __future__ import annotations

from pathlib import Path


class WorkspaceNotIsolated(RuntimeError):
    def __init__(self, offending_agents_md: Path) -> None:
        self.offending_agents_md = offending_agents_md
        super().__init__(
            f"Workspace is not isolated; ancestor AGENTS.md found: {offending_agents_md}"
        )


def assert_isolated(workspace_path: Path) -> None:
    """Raise if any ancestor `AGENTS.md` exists above `workspace_path`.

    This guard enforces the empirical finding documented in
    `report-and-findings/2026-07-31-agents-md-leakage.md`: `cursor-agent`
    loads `AGENTS.md` from workspace ancestors, local `AGENTS.md` is additive,
    and no disable flag was found.
    """

    current = workspace_path.resolve().parent
    while True:
        candidate = current / "AGENTS.md"
        if candidate.exists():
            raise WorkspaceNotIsolated(candidate)
        if current.parent == current:
            break
        current = current.parent
