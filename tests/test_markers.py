import pytest


@pytest.mark.live
def test_live_marker_deselected_by_default() -> None:
    raise AssertionError("This test should be deselected unless -m live is requested.")
