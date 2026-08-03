from __future__ import annotations

import stat
from pathlib import Path

import pytest

from orchestrator.backend import (
    BACKEND_ENV_VAR,
    DROID_SETTINGS_PATH,
    BackendName,
    CursorCLIBackend,
    DroidCLIBackend,
    ResultStatus,
    RoleInvocation,
    default_backend_name,
    make_backend,
)
from orchestrator.backend_models import BackendModelsError, ModelPair, resolve_models
from orchestrator.invoke_role import _build_attempt_plan
from orchestrator.pipeline import _DEFAULT_MODEL_TIER_MAP
from orchestrator.roles_config import (
    RoleConfigError,
    family,
    load_role_config,
    models_for,
    validate_director_challenger_family_diversity,
)

# The models `droid exec --help` lists on the account this backend targets.
DROID_MODEL_CATALOGUE = frozenset(
    {
        "claude-fable-5",
        "claude-opus-4-8",
        "claude-opus-4-8-fast",
        "claude-opus-4-7",
        "claude-opus-4-6",
        "claude-opus-4-5-20251101",
        "claude-sonnet-5",
        "claude-sonnet-4-6",
        "claude-sonnet-4-5-20250929",
        "claude-haiku-4-5-20251001",
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "gpt-5.5",
        "gpt-5.5-fast",
        "gpt-5.5-pro",
        "gpt-5.4",
        "gpt-5.4-fast",
        "gpt-5.4-mini",
        "gpt-5.3-codex",
        "gpt-5.3-codex-fast",
        "gpt-5.2",
        "gemini-3.1-pro-preview",
        "gemini-3.5-flash",
        "gemini-3-flash-preview",
        "glm-5.2",
        "glm-5.2-fast",
    }
)

ROLES: tuple[tuple[str, str | None], ...] = (
    ("intake", None),
    ("director", "framing"),
    ("structurer", None),
    ("planner", None),
    ("researcher", None),
    ("analyst", None),
    ("assumption_analyst", None),
    ("director", None),
    ("director", "b"),
    ("challenger", None),
    ("premortem", None),
    ("auditor", None),
    ("synthesizer", None),
    ("reviewer", None),
)


@pytest.fixture
def fake_droid(tmp_path: Path) -> Path:
    script = tmp_path / "fake-droid.sh"
    script.write_text(
        """#!/bin/sh
set -eu

if [ -n "${FAKE_ARGS_FILE:-}" ]; then
  printf "%s\\n" "$@" > "${FAKE_ARGS_FILE}"
fi

mode="${FAKE_DROID_MODE:-ok}"

if [ "$mode" = "ok" ]; then
  cat <<'JSON'
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "duration_ms": 1942,
  "num_turns": 1,
  "result": "ok result",
  "session_id": "sess-droid",
  "usage": {
    "input_tokens": 11,
    "output_tokens": 7,
    "cache_read_input_tokens": 3,
    "cache_creation_input_tokens": 2,
    "thinking_tokens": 5
  }
}
JSON
  exit 0
fi

if [ "$mode" = "banner" ]; then
  echo "Full command output saved to: /tmp/droid-terminal/session.log"
  echo '{"type":"result","is_error":false,"result":"after banner","session_id":"sess-banner"}'
  exit 0
fi

if [ "$mode" = "agent_error" ]; then
  echo '{"type":"result","is_error":true,"result":"agent failed","session_id":"sess-err"}'
  exit 0
fi

if [ "$mode" = "unparseable" ]; then
  echo "not-json-envelope"
  exit 0
fi

if [ "$mode" = "exit_error" ]; then
  echo "Invalid model: nope" >&2
  exit 1
fi

if [ "$mode" = "late_crash" ]; then
  printf '%s' \
    '{"type":"result","is_error":false,"result":"ok despite crash"' \
    ',"session_id":"sess-late","usage":{"input_tokens":1,"output_tokens":2}}'
  exit 42
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
    read_only: bool = False,
    allow_shell: bool = False,
    env_overrides: dict[str, str] | None = None,
) -> RoleInvocation:
    return RoleInvocation(
        role="researcher",
        model="claude-sonnet-5",
        prompt="Say hi",
        workspace=workspace,
        timeout_s=5.0,
        read_only=read_only,
        allow_shell=allow_shell,
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
def test_droid_backend_status_mappings(
    fake_droid: Path, tmp_path: Path, mode: str, expected_status: ResultStatus
) -> None:
    backend = DroidCLIBackend(binary_path=str(fake_droid))
    result = backend.run(
        _make_invocation(tmp_path, env_overrides={"FAKE_DROID_MODE": mode}),
    )
    assert result.status == expected_status


def test_droid_backend_reads_snake_case_usage_counters(fake_droid: Path, tmp_path: Path) -> None:
    backend = DroidCLIBackend(binary_path=str(fake_droid))
    result = backend.run(_make_invocation(tmp_path, env_overrides={"FAKE_DROID_MODE": "ok"}))

    assert result.status is ResultStatus.OK
    assert result.result_text == "ok result"
    assert result.session_id == "sess-droid"
    assert result.duration_ms == 1942
    assert result.usage is not None
    assert result.usage.input_tokens == 11
    assert result.usage.output_tokens == 7
    assert result.usage.cache_read_tokens == 3
    assert result.usage.cache_write_tokens == 2
    assert result.usage.total_tokens == 18


def test_droid_backend_tolerates_a_banner_line_before_the_envelope(
    fake_droid: Path, tmp_path: Path
) -> None:
    backend = DroidCLIBackend(binary_path=str(fake_droid))
    result = backend.run(_make_invocation(tmp_path, env_overrides={"FAKE_DROID_MODE": "banner"}))

    assert result.status is ResultStatus.OK
    assert result.result_text == "after banner"


def test_droid_backend_recovers_a_result_when_the_process_exits_nonzero(
    fake_droid: Path, tmp_path: Path
) -> None:
    """Droid can crash during post-completion cleanup but still print a valid envelope."""

    backend = DroidCLIBackend(binary_path=str(fake_droid))
    result = backend.run(
        _make_invocation(tmp_path, env_overrides={"FAKE_DROID_MODE": "late_crash"})
    )

    assert result.status is ResultStatus.OK
    assert result.result_text == "ok despite crash"
    assert result.session_id == "sess-late"


def test_droid_backend_maps_permissions_to_autonomy_levels(
    fake_droid: Path, tmp_path: Path
) -> None:
    backend = DroidCLIBackend(binary_path=str(fake_droid))

    def args_for(**kwargs: bool) -> list[str]:
        args_file = tmp_path / f"args-{'-'.join(sorted(kwargs))}-{len(kwargs)}.txt"
        result = backend.run(
            _make_invocation(
                tmp_path,
                env_overrides={"FAKE_DROID_MODE": "ok", "FAKE_ARGS_FILE": str(args_file)},
                **kwargs,
            )
        )
        assert result.status is ResultStatus.OK
        return args_file.read_text(encoding="utf-8").splitlines()

    read_only = args_for(read_only=True)
    assert "--auto" not in read_only

    writer = args_for(read_only=False)
    assert writer[writer.index("--auto") + 1] == "low"

    shell_user = args_for(allow_shell=True)
    assert shell_user[shell_user.index("--auto") + 1] == "medium"


def test_droid_backend_isolates_the_run_from_operator_mcp_servers(
    fake_droid: Path, tmp_path: Path
) -> None:
    args_file = tmp_path / "args.txt"
    backend = DroidCLIBackend(binary_path=str(fake_droid))
    backend.run(
        _make_invocation(
            tmp_path,
            env_overrides={"FAKE_DROID_MODE": "ok", "FAKE_ARGS_FILE": str(args_file)},
        )
    )
    args = args_file.read_text(encoding="utf-8").splitlines()

    assert args[0] == "exec"
    assert args[args.index("--settings") + 1] == str(DROID_SETTINGS_PATH)
    assert "--disable-builtin-skills" in args
    assert args[args.index("--cwd") + 1] == str(tmp_path)
    assert args[-1] == "Say hi"
    assert DROID_SETTINGS_PATH.exists()


def test_backend_selection_prefers_the_explicit_name_over_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(BACKEND_ENV_VAR, "droid")
    assert default_backend_name() is BackendName.DROID
    assert isinstance(make_backend(), DroidCLIBackend)
    assert isinstance(make_backend("cursor"), CursorCLIBackend)

    monkeypatch.delenv(BACKEND_ENV_VAR)
    assert default_backend_name() is BackendName.CURSOR
    assert isinstance(make_backend(), CursorCLIBackend)
    assert make_backend("droid").name == BackendName.DROID


def test_unknown_backend_name_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(BACKEND_ENV_VAR, "gemini-cli")
    with pytest.raises(ValueError, match="AGENTADVISOR_BACKEND"):
        default_backend_name()
    with pytest.raises(ValueError):
        make_backend("gemini-cli")


def test_cursor_models_stay_the_role_config_models() -> None:
    for role, variant in ROLES:
        config = load_role_config(role, variant)
        assert models_for(config, BackendName.CURSOR) == ModelPair(
            default_model=config.default_model,
            escalation_model=config.escalation_model,
        )


def test_every_role_resolves_to_a_model_droid_offers() -> None:
    for role, variant in ROLES:
        config = load_role_config(role, variant)
        pair = models_for(config, BackendName.DROID)
        assert pair.default_model in DROID_MODEL_CATALOGUE, config.stem
        assert pair.escalation_model in DROID_MODEL_CATALOGUE, config.stem
        assert pair.default_model != config.default_model, config.stem


def test_every_droid_model_is_priced_into_the_budget_tier_map() -> None:
    for role, variant in ROLES:
        config = load_role_config(role, variant)
        pair = models_for(config, BackendName.DROID)
        assert pair.default_model in _DEFAULT_MODEL_TIER_MAP, config.stem
        assert pair.escalation_model in _DEFAULT_MODEL_TIER_MAP, config.stem


def test_no_droid_role_defaults_to_a_high_tier_model() -> None:
    """A high-tier default would exhaust `max_high_tier_calls` before synthesis."""

    for role, variant in ROLES:
        config = load_role_config(role, variant)
        default_model = models_for(config, BackendName.DROID).default_model
        assert _DEFAULT_MODEL_TIER_MAP[default_model] != "high", config.stem


def test_director_and_challenger_stay_in_different_families_on_droid() -> None:
    validate_director_challenger_family_diversity(backend=BackendName.DROID)

    director = models_for(load_role_config("director"), BackendName.DROID).default_model
    challenger = models_for(load_role_config("challenger"), BackendName.DROID).default_model
    assert family(director, canonical=True) != family(challenger, canonical=True)


def test_director_tracks_stay_in_different_families_on_droid() -> None:
    track_a = models_for(load_role_config("director"), BackendName.DROID).default_model
    track_b = models_for(load_role_config("director", "b"), BackendName.DROID).default_model
    assert family(track_a, canonical=True) != family(track_b, canonical=True)


def test_family_diversity_guard_still_fires_on_droid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    same_family = ModelPair(default_model="claude-sonnet-5", escalation_model="gpt-5.4")
    monkeypatch.setattr("orchestrator.roles_config.resolve_models", lambda **_kwargs: same_family)
    with pytest.raises(RoleConfigError, match="family diversity"):
        validate_director_challenger_family_diversity(backend=BackendName.DROID)


def test_attempt_plan_follows_the_backend_the_invocation_runs_on() -> None:
    config = load_role_config("challenger")

    cursor_plan = _build_attempt_plan(config, BackendName.CURSOR)
    droid_plan = _build_attempt_plan(config, BackendName.DROID)

    assert cursor_plan == [config.default_model, config.default_model, config.escalation_model]
    assert droid_plan[0] == droid_plan[1] != droid_plan[2]
    assert set(droid_plan).isdisjoint(cursor_plan)


def test_resolve_models_falls_back_to_the_role_config_for_an_unknown_backend() -> None:
    fallback = ModelPair(default_model="composer-2.5", escalation_model="cursor-grok-4.5-low")
    resolved = resolve_models(
        backend="no-such-backend", role_stem="planner", tier="low", fallback=fallback
    )
    assert resolved == fallback


def test_resolve_models_rejects_a_tier_the_backend_has_not_priced() -> None:
    fallback = ModelPair(default_model="composer-2.5", escalation_model="cursor-grok-4.5-low")
    with pytest.raises(BackendModelsError, match="tier 'frontier'"):
        resolve_models(
            backend=BackendName.DROID,
            role_stem="not-a-role",
            tier="frontier",
            fallback=fallback,
        )
