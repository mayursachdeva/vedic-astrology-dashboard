"""Tests for Vimshottari dasha.

The arithmetic is fully determined, so these assert exact values rather than ranges.
Dates are checked to the day: a dasha boundary that drifts by a month makes every
prediction built on it wrong.
"""

from __future__ import annotations

import pytest
import swisseph as swe

from astro.core.dasha import (
    CYCLE_YEARS,
    DASHA_SEQUENCE,
    DASHA_YEARS,
    JULIAN_YEAR_DAYS,
    balance_at_birth,
    chain_at,
    nakshatra_lord,
    vimshottari,
)
from astro.core.ephemeris import NAKSHATRA_ARC, compute_chart, julian_day

BIRTH_JD = julian_day(1990, 1, 1, 6.5)


def _ymd(jd: float) -> tuple[int, int, int]:
    year, month, day, _ = swe.revjul(jd, swe.GREG_CAL)
    return year, month, day


# --- the fixed table --------------------------------------------------------


def test_the_cycle_is_120_years():
    assert CYCLE_YEARS == 120
    assert len(DASHA_SEQUENCE) == 9


def test_nakshatra_lords_repeat_three_times_across_the_27():
    assert nakshatra_lord(0) == "Ketu"  # Ashwini
    assert nakshatra_lord(1) == "Venus"  # Bharani
    assert nakshatra_lord(8) == "Mercury"  # Ashlesha
    for index in range(27):
        assert nakshatra_lord(index) == nakshatra_lord(index % 9)


# --- balance at birth -------------------------------------------------------


def test_moon_at_the_very_start_of_ashwini_gives_a_full_ketu_dasha():
    lord, years = balance_at_birth(0.0)
    assert lord == "Ketu"
    assert years == pytest.approx(7.0)


def test_moon_halfway_through_a_nakshatra_gives_half_the_period():
    lord, years = balance_at_birth(NAKSHATRA_ARC * 1.5)  # middle of Bharani
    assert lord == "Venus"
    assert years == pytest.approx(10.0)


def test_moon_at_the_very_end_of_a_nakshatra_leaves_almost_nothing():
    lord, years = balance_at_birth(NAKSHATRA_ARC - 1e-9)
    assert lord == "Ketu"
    assert years == pytest.approx(0.0, abs=1e-8)


# --- sequence structure -----------------------------------------------------


def test_first_mahadasha_starts_before_birth_by_the_elapsed_portion():
    """The Moon is partway through its nakshatra at birth, so the mahadasha it is in
    began earlier. Winding back is what makes its antardashas divide correctly."""
    moon = NAKSHATRA_ARC * 0.25  # quarter of the way into Ashwini
    periods = vimshottari(moon, BIRTH_JD)
    elapsed_days = 0.25 * 7 * JULIAN_YEAR_DAYS
    assert periods[0].lord == "Ketu"
    assert periods[0].start_jd == pytest.approx(BIRTH_JD - elapsed_days)
    assert periods[0].end_jd > BIRTH_JD


def test_mahadashas_run_in_order_without_gaps_and_total_120_years():
    periods = vimshottari(0.0, BIRTH_JD)
    assert [p.lord for p in periods] == [lord for lord, _ in DASHA_SEQUENCE]

    for earlier, later in zip(periods, periods[1:]):
        assert earlier.end_jd == pytest.approx(later.start_jd)

    for period in periods:
        assert period.duration_days == pytest.approx(
            DASHA_YEARS[period.lord] * JULIAN_YEAR_DAYS
        )

    total = periods[-1].end_jd - periods[0].start_jd
    assert total == pytest.approx(CYCLE_YEARS * JULIAN_YEAR_DAYS)


def test_antardashas_start_with_their_own_lord_and_fill_the_parent_exactly():
    periods = vimshottari(0.0, BIRTH_JD)
    for maha in periods:
        assert maha.children[0].lord == maha.lord
        assert len(maha.children) == 9
        assert maha.children[0].start_jd == pytest.approx(maha.start_jd)
        assert maha.children[-1].end_jd == pytest.approx(maha.end_jd)
        covered = sum(child.duration_days for child in maha.children)
        assert covered == pytest.approx(maha.duration_days)


def test_antardasha_length_is_its_share_of_the_cycle():
    """Venus antardasha inside a Ketu mahadasha runs 7 * 20 / 120 years."""
    ketu = vimshottari(0.0, BIRTH_JD)[0]
    venus = next(child for child in ketu.children if child.lord == "Venus")
    assert venus.duration_days == pytest.approx(
        7 * 20 / 120 * JULIAN_YEAR_DAYS
    )


def test_pratyantardashas_fill_their_antardasha_exactly():
    ketu = vimshottari(0.0, BIRTH_JD, depth=3)[0]
    for antar in ketu.children:
        assert len(antar.children) == 9
        covered = sum(child.duration_days for child in antar.children)
        assert covered == pytest.approx(antar.duration_days)


def test_depth_controls_how_far_the_tree_is_built():
    assert vimshottari(0.0, BIRTH_JD, depth=1)[0].children == ()
    assert vimshottari(0.0, BIRTH_JD, depth=2)[0].children[0].children == ()
    assert vimshottari(0.0, BIRTH_JD, depth=3)[0].children[0].children != ()


def test_depth_below_one_is_rejected():
    with pytest.raises(ValueError):
        vimshottari(0.0, BIRTH_JD, depth=0)


# --- dated boundaries -------------------------------------------------------


def test_boundary_dates_are_exact_for_a_clean_starting_point():
    """Moon exactly at 0 Aries, born 06:30 UT on 1 January 1990: Ketu runs 7 Julian
    years (2556.75 days) and Venus 20 more (7305 days), landing both boundaries on
    1 January."""
    periods = vimshottari(0.0, BIRTH_JD)
    assert _ymd(periods[0].start_jd) == (1990, 1, 1)
    assert periods[0].duration_days == pytest.approx(2556.75)
    assert _ymd(periods[0].end_jd) == (1997, 1, 1)
    assert periods[1].duration_days == pytest.approx(7305.0)
    assert _ymd(periods[1].end_jd) == (2017, 1, 1)


def test_savana_year_shifts_boundaries_measurably():
    julian = vimshottari(0.0, BIRTH_JD)[0]
    savana = vimshottari(0.0, BIRTH_JD, year_days=360.0)[0]
    difference_days = julian.end_jd - savana.end_jd
    assert difference_days == pytest.approx(7 * (JULIAN_YEAR_DAYS - 360.0))


# --- lookup -----------------------------------------------------------------


def test_chain_at_returns_the_nested_periods_active_at_a_moment():
    periods = vimshottari(0.0, BIRTH_JD, depth=3)
    chain = chain_at(periods, BIRTH_JD + 1.0)
    assert [period.level for period in chain] == [1, 2, 3]
    assert all(period.contains(BIRTH_JD + 1.0) for period in chain)
    # The day after birth sits at the very start of everything.
    assert [period.lord for period in chain] == ["Ketu", "Ketu", "Ketu"]


def test_chain_at_is_empty_outside_the_computed_cycle():
    periods = vimshottari(0.0, BIRTH_JD)
    assert chain_at(periods, BIRTH_JD - 1000.0) == ()
    assert chain_at(periods, BIRTH_JD + 200 * JULIAN_YEAR_DAYS) == ()


def test_every_instant_in_the_cycle_lands_in_exactly_one_chain():
    periods = vimshottari(123.456, BIRTH_JD, depth=3)
    span = periods[-1].end_jd - periods[0].start_jd
    for step in range(0, 100):
        jd = periods[0].start_jd + span * step / 100.0
        chain = chain_at(periods, jd)
        assert len(chain) == 3, f"no complete chain at offset {step}%"


# --- integration with a real chart ------------------------------------------


def test_dasha_derives_from_the_computed_moon_of_a_real_chart():
    chart = compute_chart(BIRTH_JD, 28.6139, 77.2090)
    moon = chart.positions["Moon"]
    assert moon.nakshatra_name == "Dhanishta"

    lord, years = balance_at_birth(moon.longitude)
    assert lord == nakshatra_lord(moon.nakshatra) == "Mars"
    assert 0.0 < years < DASHA_YEARS["Mars"]

    chain = chain_at(vimshottari(moon.longitude, BIRTH_JD), BIRTH_JD)
    assert chain[0].lord == "Mars"
