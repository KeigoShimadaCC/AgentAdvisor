import orchestrator


def test_version_is_non_empty_string() -> None:
    assert isinstance(orchestrator.__version__, str)
    assert orchestrator.__version__
