"""Tests for divisional charts.

Each varga is checked against the rule as BPHS states it, using worked examples that
can be verified by hand from the text rather than by re-running this code.
"""

from __future__ import annotations

import pytest

from astro.core.ephemeris import SIGNS, compute_chart, julian_day
from astro.core.varga import (
    SHODASAVARGA,
    _step,
    VARGA_NAMES,
    element,
    hora,
    quality,
    trimsamsa,
    varga_chart,
    varga_sign,
)

ARIES, TAURUS, GEMINI, CANCER, LEO, VIRGO = 0, 1, 2, 3, 4, 5
LIBRA, SCORPIO, SAGITTARIUS, CAPRICORN, AQUARIUS, PISCES = 6, 7, 8, 9, 10, 11


def at(sign: int, degree: float) -> float:
    return sign * 30.0 + degree


# --- sign classification ----------------------------------------------------


def test_quality_cycles_movable_fixed_dual():
    assert [quality(s) for s in range(12)] == [0, 1, 2] * 4
    assert quality(ARIES) == 0 and quality(TAURUS) == 1 and quality(GEMINI) == 2


def test_element_cycles_fire_earth_air_water():
    assert [element(s) for s in range(12)] == [0, 1, 2, 3] * 3


# --- individual varga rules -------------------------------------------------


def test_d1_is_the_rasi_itself():
    for sign in range(12):
        assert varga_sign(1, at(sign, 15.0)) == sign


def test_d2_hora_alternates_between_leo_and_cancer_rather_than_counting_forward():
    """Odd signs give the Sun's hora (Leo) first, even signs the Moon's (Cancer).

    The second half must fall back to the other luminary's sign, not advance to the
    next sign the way every other varga does.
    """
    assert varga_sign(2, at(ARIES, 5.0)) == LEO
    assert varga_sign(2, at(ARIES, 20.0)) == CANCER
    assert varga_sign(2, at(TAURUS, 5.0)) == CANCER
    assert varga_sign(2, at(TAURUS, 20.0)) == LEO


def test_d2_hora_reports_its_ruler_and_only_ever_uses_two_signs():
    assert hora(at(ARIES, 5.0)) == (LEO, "Sun")
    assert hora(at(ARIES, 20.0)) == (CANCER, "Moon")
    assert hora(at(TAURUS, 5.0)) == (CANCER, "Moon")
    for step in range(0, 3600):
        assert hora(step / 10.0)[0] in (LEO, CANCER)


def test_d2_hora_boundary_falls_at_exactly_fifteen_degrees():
    assert varga_sign(2, at(ARIES, 14.999)) == LEO
    assert varga_sign(2, at(ARIES, 15.0)) == CANCER


def test_d3_drekkana_gives_the_same_fifth_and_ninth_signs():
    assert varga_sign(3, at(ARIES, 5.0)) == ARIES
    assert varga_sign(3, at(ARIES, 15.0)) == LEO  # 5th from Aries
    assert varga_sign(3, at(ARIES, 25.0)) == SAGITTARIUS  # 9th from Aries
    assert varga_sign(3, at(TAURUS, 15.0)) == VIRGO  # 5th from Taurus


def test_d4_chaturthamsa_gives_the_kendras_from_the_sign():
    for index, expected in enumerate((ARIES, CANCER, LIBRA, CAPRICORN)):
        assert varga_sign(4, at(ARIES, index * 7.5 + 1.0)) == expected


def test_d7_saptamsa_starts_from_the_sign_for_odd_and_the_seventh_for_even():
    assert varga_sign(7, at(ARIES, 1.0)) == ARIES
    assert varga_sign(7, at(ARIES, 29.0)) == LIBRA  # 7th part from Aries
    assert varga_sign(7, at(TAURUS, 1.0)) == SCORPIO  # 7th from Taurus
    assert varga_sign(7, at(TAURUS, 29.0)) == TAURUS


def test_d9_navamsa_matches_the_movable_fixed_dual_rule():
    assert varga_sign(9, at(ARIES, 1.0)) == ARIES  # movable: from the sign
    assert varga_sign(9, at(TAURUS, 1.0)) == CAPRICORN  # fixed: from the 9th
    assert varga_sign(9, at(GEMINI, 1.0)) == LIBRA  # dual: from the 5th


def test_d9_navamsa_is_continuous_around_the_zodiac():
    """The 108 navamsas run unbroken from 0 Aries, so the nth is (n mod 12) from Aries."""
    step = 30.0 / 9.0
    for index in range(108):
        longitude = index * step + step / 2.0
        assert varga_sign(9, longitude) == index % 12


def test_d9_of_a_movable_sign_ends_where_the_next_begins():
    assert varga_sign(9, at(ARIES, 29.9)) == SAGITTARIUS
    assert varga_sign(9, at(TAURUS, 0.1)) == CAPRICORN


def test_d10_dasamsa_starts_from_the_sign_for_odd_and_the_ninth_for_even():
    assert varga_sign(10, at(ARIES, 1.0)) == ARIES
    assert varga_sign(10, at(TAURUS, 1.0)) == CAPRICORN  # 9th from Taurus
    assert varga_sign(10, at(ARIES, 29.0)) == CAPRICORN  # 10th part from Aries


def test_d12_dwadasamsa_counts_from_the_sign_itself():
    for index in range(12):
        assert varga_sign(12, at(TAURUS, index * 2.5 + 1.0)) == (TAURUS + index) % 12


def test_d16_and_d45_start_from_aries_leo_or_sagittarius_by_quality():
    for divisor in (16, 45):
        assert varga_sign(divisor, at(ARIES, 0.1)) == ARIES  # movable
        assert varga_sign(divisor, at(TAURUS, 0.1)) == LEO  # fixed
        assert varga_sign(divisor, at(GEMINI, 0.1)) == SAGITTARIUS  # dual


def test_d20_starts_from_aries_sagittarius_or_leo_by_quality():
    assert varga_sign(20, at(ARIES, 0.1)) == ARIES
    assert varga_sign(20, at(TAURUS, 0.1)) == SAGITTARIUS
    assert varga_sign(20, at(GEMINI, 0.1)) == LEO


def test_d24_starts_from_leo_for_odd_signs_and_cancer_for_even():
    assert varga_sign(24, at(ARIES, 0.1)) == LEO
    assert varga_sign(24, at(TAURUS, 0.1)) == CANCER


def test_d27_starts_from_the_element_leader():
    assert varga_sign(27, at(ARIES, 0.1)) == ARIES  # fire
    assert varga_sign(27, at(TAURUS, 0.1)) == CANCER  # earth
    assert varga_sign(27, at(GEMINI, 0.1)) == LIBRA  # air
    assert varga_sign(27, at(CANCER, 0.1)) == CAPRICORN  # water


def test_d40_starts_from_aries_for_odd_signs_and_libra_for_even():
    assert varga_sign(40, at(ARIES, 0.1)) == ARIES
    assert varga_sign(40, at(TAURUS, 0.1)) == LIBRA


def test_d60_counts_double_the_degrees_from_the_sign_itself():
    assert varga_sign(60, at(TAURUS, 0.1)) == TAURUS
    assert varga_sign(60, at(TAURUS, 0.6)) == GEMINI  # 0.6 deg -> part 1
    assert varga_sign(60, at(TAURUS, 29.9)) == (TAURUS + 59) % 12


# --- trimsamsa is unequal ---------------------------------------------------


def test_trimsamsa_odd_sign_spans_are_5_5_8_7_5_degrees():
    expected = [
        (2.0, "Mars", ARIES),
        (7.0, "Saturn", AQUARIUS),
        (12.0, "Jupiter", SAGITTARIUS),
        (20.0, "Mercury", GEMINI),
        (27.0, "Venus", LIBRA),
    ]
    for degree, planet, sign in expected:
        assert trimsamsa(at(ARIES, degree)) == (sign, planet)


def test_trimsamsa_even_sign_reverses_the_order_and_uses_the_other_signs():
    expected = [
        (2.0, "Venus", TAURUS),
        (8.0, "Mercury", VIRGO),
        (15.0, "Jupiter", PISCES),
        (22.0, "Saturn", CAPRICORN),
        (27.0, "Mars", SCORPIO),
    ]
    for degree, planet, sign in expected:
        assert trimsamsa(at(TAURUS, degree)) == (sign, planet)


def test_trimsamsa_boundaries_belong_to_the_later_span():
    assert trimsamsa(at(ARIES, 4.999))[1] == "Mars"
    assert trimsamsa(at(ARIES, 5.0))[1] == "Saturn"


def test_trimsamsa_never_maps_to_a_luminary_sign():
    """The five trimsamsa rulers exclude the Sun and Moon, so Cancer and Leo never appear."""
    for step in range(0, 3600):
        sign, _ = trimsamsa(step / 10.0)
        assert sign not in (CANCER, LEO)


# --- totality and edges -----------------------------------------------------


@pytest.mark.parametrize("divisor", SHODASAVARGA)
def test_every_varga_returns_a_valid_sign_across_the_whole_zodiac(divisor):
    for step in range(0, 3600):
        assert 0 <= varga_sign(divisor, step / 10.0) <= 11


@pytest.mark.parametrize("divisor", SHODASAVARGA)
def test_part_boundaries_do_not_skip_or_repeat_a_part(divisor):
    """Sampling either side of every internal boundary must show exactly one change,
    catching off-by-one rounding at the edges of a part."""
    if divisor in (2, 30):
        return  # handled by their own tests; their parts are not uniform counts
    width = 30.0 / divisor
    step = _step(divisor)
    for index in range(1, divisor):
        before = varga_sign(divisor, at(ARIES, index * width - 1e-9))
        after = varga_sign(divisor, at(ARIES, index * width + 1e-9))
        assert after == (before + step) % 12


def test_the_shodasavarga_is_the_expected_sixteen():
    assert len(SHODASAVARGA) == 16
    assert VARGA_NAMES[9] == "Navamsa"
    assert VARGA_NAMES[30] == "Trimsamsa"


def test_unknown_divisor_is_rejected():
    with pytest.raises(ValueError):
        varga_sign(5, 100.0)


# --- projection of a real chart ---------------------------------------------


def test_varga_chart_projects_every_body_and_the_lagna():
    chart = compute_chart(julian_day(1990, 1, 1, 6.5), 28.6139, 77.2090)
    navamsa = varga_chart(chart, 9)

    assert navamsa.name == "Navamsa"
    assert set(navamsa.signs) == set(chart.positions)
    assert navamsa.lagna_sign == varga_sign(9, chart.ascendant)
    for body, position in chart.positions.items():
        assert navamsa.signs[body] == varga_sign(9, position.longitude)


def test_varga_chart_house_numbering_is_relative_to_its_own_lagna():
    chart = compute_chart(julian_day(1990, 1, 1, 6.5), 28.6139, 77.2090)
    navamsa = varga_chart(chart, 9)
    for body in navamsa.signs:
        expected = (navamsa.signs[body] - navamsa.lagna_sign) % 12 + 1
        assert navamsa.house_of(body) == expected
    assert navamsa.sign_name("Sun") == SIGNS[navamsa.signs["Sun"]]


def test_d1_projection_reproduces_the_rasi_chart():
    chart = compute_chart(julian_day(1990, 1, 1, 6.5), 28.6139, 77.2090)
    rasi = varga_chart(chart, 1)
    assert rasi.lagna_sign == chart.lagna_sign
    for body in chart.positions:
        assert rasi.house_of(body) == chart.house_of(body)
