"""Tests for the avasthas, the chara karakas, and the dasha-effect index.

Three layers added from parts of the library nothing else was reading. Each is
arithmetic over facts already computed, so what can go wrong is the mapping — a state
counted from the wrong end of the sign, a role handed to the wrong graha, a verse that
cites one planet's sub-period and prints another's paragraph. All three of those
happened; all three are pinned here.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from astro.core import avastha as A
from astro.core import karaka as K
from astro.corpus import index as texts
from astro.core.strength import SEVEN
from astro.service import build_natal_chart
from astro.store import Profile
from conftest import synthetic_chart

PROFILE = Profile(
    name="Sample Native",
    birth_local=datetime(1990, 1, 1, 12, 0),
    latitude=28.6139,
    longitude=77.2090,
    place="New Delhi",
    relation="self",
)
CHART = build_natal_chart(PROFILE).chart
BODIES = (*SEVEN, "Rahu", "Ketu")


def at(sign: int, degree: float) -> float:
    return sign * 30.0 + degree


# --- baladi -----------------------------------------------------------------


def test_baladi_runs_forward_in_odd_signs_and_backward_in_even_ones():
    """BPHS ch. 45 v. 3. Aries is an odd rasi and Taurus an even one, so the same
    degree means opposite states in the two."""
    early_odd = synthetic_chart(0.0, Saturn=at(0, 3.0))    # Aries, first six degrees
    early_even = synthetic_chart(0.0, Saturn=at(1, 3.0))   # Taurus, same degrees
    assert A.baladi(early_odd, "Saturn")[0] == "Bala"
    assert A.baladi(early_even, "Saturn")[0] == "Mrita"


def test_every_six_degree_step_lands_on_its_own_state():
    states = [
        A.baladi(synthetic_chart(0.0, Mars=at(0, degree)), "Mars")[0]
        for degree in (3.0, 9.0, 15.0, 21.0, 27.0)
    ]
    assert states == ["Bala", "Kumara", "Yuva", "Vriddha", "Mrita"]


def test_the_last_degree_of_a_sign_does_not_fall_off_the_table():
    """29.999 divided by six is four and a bit, which would index past the end."""
    assert A.baladi(synthetic_chart(0.0, Mars=at(0, 29.999)), "Mars")[0] == "Mrita"


def test_the_share_of_the_result_matches_the_verse():
    """v. 4: one fourth, half, full, negligible, nil."""
    shares = {name: share for name, _, share, _ in A.BALADI}
    assert shares["Bala"] == 0.25
    assert shares["Kumara"] == 0.5
    assert shares["Yuva"] == 1.0
    assert shares["Vriddha"] < shares["Kumara"]
    assert shares["Mrita"] == 0.0


# --- jagradadi and deeptadi -------------------------------------------------


def test_jagradadi_follows_the_dignity_ladder():
    """v. 5: own or exalted is awake, friend or neutral dreaming, enemy asleep."""
    assert A.jagradadi("exalted")[0] == "Jagrat"
    assert A.jagradadi("own")[0] == "Jagrat"
    assert A.jagradadi("friend")[0] == "Swapna"
    assert A.jagradadi("neutral")[0] == "Swapna"
    assert A.jagradadi("enemy")[0] == "Sushupti"
    assert A.jagradadi("debilitated")[0] == "Sushupti"


def test_deeptadi_names_all_nine_states_the_verse_lists():
    """v. 7 names them: Dipt, Swasth, Pramudit, Shanta, Din, Vikal, Duhkhit, Khal, Kop."""
    named = {name for name, _ in A.DEEPTADI_BY_DIGNITY.values()}
    named |= {A.VIKAL[0], A.KOP[0]}
    assert named == {
        "Dipt", "Swasth", "Pramudit", "Shanta", "Din", "Vikal", "Duhkhit", "Khal", "Kop",
    }


def scattered(**where: float):
    """A chart with every graha placed, so nothing lands beside Jupiter by accident.

    `synthetic_chart` parks whatever is not placed in the lagna's own sign, which put
    Mars there and made a test about malefic company pass for the wrong reason.
    """
    spread = {
        "Sun": at(6, 10.0), "Moon": at(7, 10.0), "Mars": at(8, 10.0),
        "Mercury": at(9, 10.0), "Jupiter": at(10, 10.0), "Venus": at(11, 10.0),
        "Saturn": at(4, 10.0), "Rahu": at(5, 10.0),
    }
    return synthetic_chart(0.0, **{**spread, **where})


def test_combustion_beats_malefic_company_and_both_beat_dignity():
    """The precedence the verse does not give; see KNOWN_VARIANTS."""
    assert "precedence" in " ".join(A.KNOWN_VARIANTS)
    alone = scattered(Jupiter=at(0, 10.0))
    assert A.deeptadi(alone, "Jupiter", "friend", combust=False)[0] == "Shanta"
    # Same dignity, now sharing a sign with a malefic.
    with_saturn = scattered(Jupiter=at(0, 10.0), Saturn=at(0, 20.0))
    assert A.deeptadi(with_saturn, "Jupiter", "friend", combust=False)[0] == "Vikal"
    # And combust, which wins over both.
    assert A.deeptadi(with_saturn, "Jupiter", "friend", combust=True)[0] == "Kop"


def test_a_graha_alone_in_its_sign_keeps_its_dignity_state():
    for dignity, expected in (
        ("exalted", "Dipt"), ("own", "Swasth"), ("great_friend", "Pramudit"),
        ("neutral", "Din"), ("enemy", "Duhkhit"), ("debilitated", "Khal"),
    ):
        chart = scattered(Jupiter=at(0, 10.0))
        assert A.deeptadi(chart, "Jupiter", dignity, combust=False)[0] == expected


def test_the_three_sets_are_independent_of_one_another():
    """A graha can be strong by dignity and still deliver a quarter of it, which is the
    reason for having the baladi state at all."""
    exalted_infant = synthetic_chart(0.0, Saturn=at(6, 2.0))  # Libra, exalted, 2 degrees
    assert A.baladi(exalted_infant, "Saturn")[0] == "Bala"
    assert A.jagradadi("exalted")[0] == "Jagrat"


def test_every_graha_gets_a_complete_set_on_a_real_chart():
    from astro.core.facts import build_facts

    facts = build_facts(CHART)
    for body in SEVEN:
        condition = facts.condition[body]
        state = A.payload(
            A.avasthas(CHART, body, condition.dignity, condition.combust)
        )
        assert state["baladi"] and state["jagradadi"] and state["deeptadi"]
        assert 0.0 <= state["share"] <= 1.0
        assert "_" not in state["delivers"]


# --- chara karakas ----------------------------------------------------------


def test_the_karakas_rank_by_degree_and_nothing_else():
    karakas = K.chara_karakas(CHART)
    degrees = [entry["degree"] for entry in karakas.values()]
    assert degrees == sorted(degrees, reverse=True)


def test_rahu_is_counted_backwards():
    """v. 3-8: deduct Rahu's longitude in the sign from 30, because it moves that way."""
    chart = synthetic_chart(0.0, Rahu=at(3, 2.0))  # two degrees in, so 28 by the rule
    assert K._reach(chart, "Rahu") == pytest.approx(28.0)
    assert K._reach(chart, "Sun") != 28.0


def test_the_atma_karaka_is_whichever_has_gone_furthest():
    chart = synthetic_chart(
        0.0, Sun=at(0, 29.0), Moon=at(1, 5.0), Mars=at(2, 6.0), Mercury=at(3, 7.0),
        Jupiter=at(4, 8.0), Venus=at(5, 9.0), Saturn=at(6, 10.0), Rahu=at(7, 25.0),
    )
    assert K.atma_karaka(chart) == "Sun"
    assert K.chara_karakas(chart)["Atma Karaka"]["body"] == "Sun"


def test_all_eight_roles_are_filled_and_none_is_given_twice():
    karakas = K.chara_karakas(CHART)
    assert len(karakas) == 8
    assert len({entry["body"] for entry in karakas.values()}) == 8
    assert [role for role in karakas] == [name for name, _, _ in K.KARAKAS]


def test_the_scheme_records_why_it_uses_eight_and_not_seven():
    assert "seven_or_eight" in K.KNOWN_VARIANTS
    assert "Ketu" not in K.BODIES  # the verse's eight are the seven grahas plus Rahu


# --- the dasha-effect index -------------------------------------------------


def test_every_mahadasha_chapter_is_the_one_about_that_lord():
    """The chapters are numbered in Vimshottari order and titled only "Effects of the
    Antar Dashas in the Dasha of", so which lord each belongs to has to be read from
    the verses themselves."""
    for lord, chapter in texts.DASHA_CHAPTERS.items():
        alias = texts.SANSKRIT_GRAHAS[lord]
        body = " ".join(
            " ".join(hit.body.split()) for hit in texts.lookup(
                texts.BPHS, chapter=str(chapter)
            )
        )
        assert f"Dasha of {alias}" in body, (lord, chapter)


def test_almost_every_pair_of_periods_has_a_verse():
    found = sum(
        1 for maha in BODIES for antar in BODIES
        if texts.antardasha_effect(maha, antar)
    )
    assert found >= 80, f"only {found} of 81 pairs resolved"


def test_the_excerpt_is_about_the_sub_period_it_was_asked_for():
    """The ingestion glued the tail of one verse group onto the next, so a passage can
    open with Rahu's sub-period and carry Jupiter's header at the end. Returning the
    whole passage cited the right verse and showed the wrong planet's paragraph."""
    for maha in BODIES:
        for antar in BODIES:
            found = texts.antardasha_effect(maha, antar)
            if found is None:
                continue
            text, _ = found
            alias = texts.SANSKRIT_GRAHAS[antar]
            assert alias in text or antar in text, (maha, antar, text[:70])


def test_a_lords_own_sub_period_is_found_despite_being_written_possessively():
    """"in her Antar Dasha", not "the Antar Dasha of Candr" — which the name search
    misses for six of the nine lords."""
    for lord in BODIES:
        assert texts.antardasha_effect(lord, lord), lord


def test_the_missing_pair_comes_back_empty_rather_than_as_a_neighbour():
    """Mercury's chapter lost Ketu's header in the scan. Nothing is better than the
    paragraph next to it."""
    assert texts.antardasha_effect("Mercury", "Ketu") is None
