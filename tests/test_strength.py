"""Tests for dignity, relationship, combustion and aspects."""

from __future__ import annotations

import pytest

from astro.core.ephemeris import compute_chart, julian_day
from astro.core.strength import (
    DIGNITY_ORDER,
    EXALTATION,
    NATURAL_ENEMIES,
    NATURAL_FRIENDS,
    SEVEN,
    SIGN_LORDS,
    aspected_houses,
    compound_relation,
    condition_of,
    conditions,
    debilitation_sign,
    dignity_of,
    elongation_from_sun,
    in_moolatrikona,
    is_combust,
    is_natural_benefic,
    is_waxing,
    moon_is_benefic,
    owned_houses,
    planetary_war,
    sign_lord,
    temporal_relation,
    yogakaraka,
)
from conftest import synthetic_chart

ARIES, TAURUS, GEMINI, CANCER, LEO, VIRGO = 0, 1, 2, 3, 4, 5
LIBRA, SCORPIO, SAGITTARIUS, CAPRICORN, AQUARIUS, PISCES = 6, 7, 8, 9, 10, 11


def at(sign: int, degree: float = 15.0) -> float:
    return sign * 30.0 + degree


# --- lordship ---------------------------------------------------------------


def test_each_sign_has_its_traditional_lord():
    assert sign_lord(ARIES) == "Mars"
    assert sign_lord(CANCER) == "Moon"
    assert sign_lord(LEO) == "Sun"
    assert sign_lord(AQUARIUS) == "Saturn"


def test_the_five_non_luminaries_each_own_two_signs_and_the_luminaries_one():
    counts = {body: SIGN_LORDS.count(body) for body in SEVEN}
    assert counts == {
        "Sun": 1, "Moon": 1, "Mars": 2, "Mercury": 2,
        "Jupiter": 2, "Venus": 2, "Saturn": 2,
    }


def test_owned_houses_are_counted_from_the_lagna():
    chart = synthetic_chart(at(ARIES))  # Aries rising
    assert owned_houses(chart, "Mars") == (1, 8)  # Aries and Scorpio
    assert owned_houses(chart, "Sun") == (5,)  # Leo
    assert owned_houses(chart, "Rahu") == ()


# --- dignity ----------------------------------------------------------------


def test_exaltation_and_debilitation_are_opposite_signs():
    for body, (sign, _) in EXALTATION.items():
        assert debilitation_sign(body) == (sign + 6) % 12


def test_grahas_are_exalted_and_debilitated_in_the_expected_signs():
    assert dignity_of(synthetic_chart(Sun=at(ARIES, 10.0)), "Sun") == "exalted"
    assert dignity_of(synthetic_chart(Sun=at(LIBRA, 10.0)), "Sun") == "debilitated"
    assert dignity_of(synthetic_chart(Jupiter=at(CANCER, 5.0)), "Jupiter") == "exalted"
    assert dignity_of(synthetic_chart(Jupiter=at(CAPRICORN, 5.0)), "Jupiter") == "debilitated"
    assert dignity_of(synthetic_chart(Saturn=at(LIBRA, 20.0)), "Saturn") == "exalted"
    assert dignity_of(synthetic_chart(Saturn=at(ARIES, 20.0)), "Saturn") == "debilitated"
    assert dignity_of(synthetic_chart(Venus=at(PISCES, 27.0)), "Venus") == "exalted"
    assert dignity_of(synthetic_chart(Venus=at(VIRGO, 27.0)), "Venus") == "debilitated"
    assert dignity_of(synthetic_chart(Mars=at(CAPRICORN, 28.0)), "Mars") == "exalted"
    assert dignity_of(synthetic_chart(Mercury=at(VIRGO, 15.0)), "Mercury") == "exalted"
    assert dignity_of(synthetic_chart(Moon=at(TAURUS, 3.0)), "Moon") == "exalted"


def test_moolatrikona_is_a_degree_range_not_a_whole_sign():
    assert in_moolatrikona("Sun", at(LEO, 10.0))
    assert not in_moolatrikona("Sun", at(LEO, 25.0))  # past 20 degrees it is own sign
    assert dignity_of(synthetic_chart(Sun=at(LEO, 10.0)), "Sun") == "moolatrikona"
    assert dignity_of(synthetic_chart(Sun=at(LEO, 25.0)), "Sun") == "own"


def test_moolatrikona_outranks_own_sign_and_exaltation_outranks_both():
    order = DIGNITY_ORDER
    assert order.index("exalted") > order.index("moolatrikona") > order.index("own")
    assert order.index("debilitated") == 0


def test_a_graha_in_its_own_sign_is_recognised():
    assert dignity_of(synthetic_chart(Mars=at(SCORPIO)), "Mars") == "own"


# --- friendship -------------------------------------------------------------


def test_natural_friendship_is_not_symmetric():
    """The Moon counts no enemies, yet Mercury counts the Moon as one. Asserting
    symmetry here would be wrong, so this pins the asymmetry instead."""
    assert NATURAL_ENEMIES["Moon"] == set()
    assert "Moon" in NATURAL_ENEMIES["Mercury"]
    assert "Mercury" in NATURAL_FRIENDS["Moon"]


def test_no_graha_is_both_a_friend_and_an_enemy():
    for body in SEVEN:
        assert not NATURAL_FRIENDS[body] & NATURAL_ENEMIES[body]
        assert body not in NATURAL_FRIENDS[body]
        assert body not in NATURAL_ENEMIES[body]


def test_temporal_friendship_follows_house_distance():
    for distance in (2, 3, 4, 10, 11, 12):
        assert temporal_relation(distance) == "friend"
    for distance in (1, 5, 6, 7, 8, 9):
        assert temporal_relation(distance) == "enemy"


def test_compound_relation_combines_the_two_grades():
    assert compound_relation("friend", "friend") == "great_friend"
    assert compound_relation("enemy", "enemy") == "great_enemy"
    assert compound_relation("friend", "enemy") == "neutral"
    assert compound_relation("neutral", "friend") == "friend"


# --- combustion and the Moon's phase ----------------------------------------


def test_a_graha_close_to_the_sun_is_combust():
    chart = synthetic_chart(Sun=at(LEO, 10.0), Mercury=at(LEO, 15.0))
    combust, orb = is_combust(chart, "Mercury")
    assert combust and orb == pytest.approx(5.0)


def test_a_graha_beyond_its_orb_is_not_combust():
    chart = synthetic_chart(Sun=at(LEO, 10.0), Mercury=at(VIRGO, 5.0))  # 25 degrees away
    combust, orb = is_combust(chart, "Mercury")
    assert not combust and orb == pytest.approx(25.0)


def test_retrograde_venus_takes_a_tighter_orb():
    direct = synthetic_chart(Sun=at(LEO, 10.0), Venus=at(LEO, 19.0))
    retro = synthetic_chart(Sun=at(LEO, 10.0), Venus=at(LEO, 19.0), retrograde=("Venus",))
    assert is_combust(direct, "Venus")[0]
    assert not is_combust(retro, "Venus")[0]


def test_the_sun_and_the_nodes_are_never_combust():
    chart = synthetic_chart(Sun=at(LEO, 10.0), Rahu=at(LEO, 11.0))
    assert is_combust(chart, "Sun") == (False, None)
    assert is_combust(chart, "Rahu") == (False, None)


def test_elongation_never_exceeds_half_a_circle():
    chart = synthetic_chart(Sun=at(ARIES, 0.0), Moon=at(LIBRA, 20.0))
    assert 0.0 <= elongation_from_sun(chart, "Moon") <= 180.0


def test_the_moon_is_waxing_while_ahead_of_the_sun():
    assert is_waxing(synthetic_chart(Sun=at(ARIES, 0.0), Moon=at(CANCER, 0.0)))
    assert not is_waxing(synthetic_chart(Sun=at(ARIES, 0.0), Moon=at(CAPRICORN, 0.0)))


def test_a_dark_moon_is_counted_among_the_malefics():
    new_moon = synthetic_chart(Sun=at(ARIES, 0.0), Moon=at(ARIES, 5.0))
    full_moon = synthetic_chart(Sun=at(ARIES, 0.0), Moon=at(LIBRA, 0.0))
    assert not moon_is_benefic(new_moon)
    assert moon_is_benefic(full_moon)
    assert not is_natural_benefic(new_moon, "Moon")
    assert is_natural_benefic(full_moon, "Moon")


def test_jupiter_and_venus_are_always_benefic_and_saturn_never():
    chart = synthetic_chart()
    assert is_natural_benefic(chart, "Jupiter")
    assert is_natural_benefic(chart, "Venus")
    assert not is_natural_benefic(chart, "Saturn")
    assert not is_natural_benefic(chart, "Rahu")


def test_mercury_turns_malefic_in_malefic_company():
    alone = synthetic_chart(Mercury=at(GEMINI, 5.0), Saturn=at(PISCES, 5.0))
    with_saturn = synthetic_chart(Mercury=at(GEMINI, 5.0), Saturn=at(GEMINI, 20.0))
    assert is_natural_benefic(alone, "Mercury")
    assert not is_natural_benefic(with_saturn, "Mercury")


# --- planetary war ----------------------------------------------------------


def test_two_grahas_within_a_degree_are_at_war():
    chart = synthetic_chart(Mars=at(GEMINI, 10.0), Saturn=at(GEMINI, 10.5))
    assert planetary_war(chart, "Mars")
    assert planetary_war(chart, "Saturn")


def test_the_luminaries_and_nodes_do_not_go_to_war():
    chart = synthetic_chart(Sun=at(GEMINI, 10.0), Mars=at(GEMINI, 10.2))
    assert not planetary_war(chart, "Sun")
    assert not planetary_war(chart, "Mars")  # its only close neighbour is the Sun


# --- aspects ----------------------------------------------------------------


def test_every_graha_aspects_the_seventh_from_itself():
    assert 7 in aspected_houses("Venus", 1)
    assert aspected_houses("Venus", 1) == (7,)
    assert aspected_houses("Venus", 10) == (4,)


def test_mars_jupiter_and_saturn_have_their_special_aspects():
    assert aspected_houses("Mars", 1) == (4, 7, 8)
    assert aspected_houses("Jupiter", 1) == (5, 7, 9)
    assert aspected_houses("Saturn", 1) == (3, 7, 10)


def test_aspects_wrap_around_the_chart():
    assert aspected_houses("Saturn", 12) == (2, 6, 9)


def test_condition_reports_which_bodies_a_graha_aspects():
    # Jupiter in house 1 aspects houses 5, 7 and 9; put the Sun in the 7th.
    chart = synthetic_chart(at(ARIES), Jupiter=at(ARIES, 5.0), Sun=at(LIBRA, 5.0))
    condition = condition_of(chart, "Jupiter")
    assert condition.aspects_houses == (5, 7, 9)
    assert "Sun" in condition.aspects_bodies


# --- yogakaraka -------------------------------------------------------------


def test_saturn_is_the_yogakaraka_for_taurus_and_libra_lagnas():
    assert yogakaraka(synthetic_chart(at(TAURUS))) == ("Saturn",)
    assert yogakaraka(synthetic_chart(at(LIBRA))) == ("Saturn",)


def test_mars_is_the_yogakaraka_for_cancer_and_leo_lagnas():
    assert yogakaraka(synthetic_chart(at(CANCER))) == ("Mars",)
    assert yogakaraka(synthetic_chart(at(LEO))) == ("Mars",)


def test_venus_is_the_yogakaraka_for_capricorn_and_aquarius_lagnas():
    assert yogakaraka(synthetic_chart(at(CAPRICORN))) == ("Venus",)
    assert yogakaraka(synthetic_chart(at(AQUARIUS))) == ("Venus",)


def test_most_lagnas_have_no_yogakaraka():
    assert yogakaraka(synthetic_chart(at(ARIES))) == ()
    assert yogakaraka(synthetic_chart(at(GEMINI))) == ()


# --- assembling conditions --------------------------------------------------


def test_conditions_cover_every_graha_for_a_real_chart():
    chart = compute_chart(julian_day(1990, 1, 1, 6.5), 28.6139, 77.2090)
    found = conditions(chart)

    assert len(found) == 9
    for body, condition in found.items():
        assert condition.body == body
        assert 1 <= condition.house <= 12
        assert condition.dignity in DIGNITY_ORDER
        assert condition.sign == chart.positions[body].sign


def test_dig_bala_is_recognised_in_the_right_house():
    # Jupiter has directional strength in the first house.
    chart = synthetic_chart(at(ARIES), Jupiter=at(ARIES, 5.0))
    assert condition_of(chart, "Jupiter").has_dig_bala
    moved = synthetic_chart(at(ARIES), Jupiter=at(LIBRA, 5.0))
    assert not condition_of(moved, "Jupiter").has_dig_bala


def test_strong_and_weak_shortcuts_agree_with_the_dignity():
    exalted = condition_of(synthetic_chart(Sun=at(ARIES, 10.0)), "Sun")
    fallen = condition_of(synthetic_chart(Sun=at(LIBRA, 10.0)), "Sun")
    assert exalted.is_strong and not exalted.is_weak
    assert fallen.is_weak and not fallen.is_strong
