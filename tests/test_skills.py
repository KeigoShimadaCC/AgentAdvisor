from __future__ import annotations

import pytest

from orchestrator.skills import (
    MAX_PACKS_PER_CASE,
    MIN_PACK_SCORE,
    load_registry,
    packs_for_role,
    render_pack_section,
    score_pack,
    select_packs,
)


@pytest.fixture(autouse=True)
def _clear_registry_cache() -> None:
    load_registry.cache_clear()


def _pack(pack_id: str):
    return next(pack for pack in load_registry() if pack.pack_id == pack_id)


def test_every_registered_pack_file_exists() -> None:
    packs = load_registry()
    assert packs
    for pack in packs:
        assert pack.path.is_file(), pack.path


def test_multiword_keywords_score_double() -> None:
    pack = _pack("real-estate")
    assert score_pack(pack, "What down payment should I make?") == 2
    assert score_pack(pack, "Should I buy a condo?") == 1


def test_substrings_do_not_count_as_single_word_matches() -> None:
    pack = _pack("public-equity")
    assert score_pack(pack, "Should I restock the pantry?") == 0


def test_an_equity_question_selects_the_equity_pack() -> None:
    packs = select_packs("Should I buy NVIDIA stock at the current valuation?")

    assert [pack.pack_id for pack in packs][:1] == ["public-equity"]


def test_a_generic_question_selects_nothing() -> None:
    assert select_packs("Should I get a haircut before Friday?") == []


def test_a_single_weak_keyword_is_below_the_threshold() -> None:
    packs = select_packs("Is this a good index?")

    assert MIN_PACK_SCORE == 2
    assert packs == []


def test_selection_is_capped() -> None:
    text = (
        "Should I take the startup job offer with an equity grant and a valuation cap, "
        "buy a condo with a mortgage, or build vs buy a saas vendor platform for "
        "our analytics stack while holding nasdaq etf shares?"
    )
    packs = select_packs(text)

    assert len(packs) == MAX_PACKS_PER_CASE


def test_selection_is_deterministic_for_ties() -> None:
    text = "startup seed round versus buying a condo mortgage down payment"
    first = [pack.pack_id for pack in select_packs(text)]
    second = [pack.pack_id for pack in select_packs(text)]

    assert first == second


def test_verification_roles_never_receive_a_pack() -> None:
    packs = list(load_registry())

    assert packs_for_role(packs, "reviewer") == []
    assert packs_for_role(packs, "auditor") == []
    assert packs_for_role(packs, "challenger") == []


def test_analysis_roles_do_receive_packs() -> None:
    packs = [_pack("public-equity")]

    assert packs_for_role(packs, "researcher") == packs
    assert packs_for_role(packs, "analyst") == packs


def test_rendered_section_is_marked_as_non_overriding() -> None:
    section = render_pack_section([_pack("public-equity")])

    assert section.startswith("\n\n---\n\n# Domain specialist guidance")
    assert "never override your role instructions" in section
    assert "<!-- skill-pack: public-equity -->" in section


def test_rendering_no_packs_adds_nothing() -> None:
    assert render_pack_section([]) == ""
