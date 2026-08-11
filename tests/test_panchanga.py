"""Tests for the panchanga.

The definitional parts are checked against the arithmetic that produces them; the dated
parts against published almanac facts.
"""

from __future__ import annotations

import pytest
import swisseph as swe

from astro.core.ephemeris import compute_chart, julian_day
from astro.core.panchanga import (
    BHADRA,
    FIXED_KARANAS,
    MOVABLE_KARANAS,
    NITYA_YOGAS,
    TITHI_GROUPS,
    TITHI_NAMES,
    compute,
    karana_index,
    karana_name,
    sunrise,
    tithi_index,
    tithi_name,
    vara,
    yoga_index,
)

DELHI = (28.6139, 77.2090)


def ymd(jd: float) -> tuple[int, int, int]:
    year, month, day, _ = swe.revjul(jd, swe.GREG_CAL)
    return year, month, day


# --- the tables --------------------------------------------------------------


def test_there_are_fifteen_tithi_names_and_five_groups():
    assert len(TITHI_NAMES) == 15
    assert len(TITHI_GROUPS) == 5
    assert tithi_name(1) == "Pratipada"
    assert tithi_name(15) == "Purnima"
    assert tithi_name(16) == "Pratipada"  # the dark fortnight repeats the names
    assert tithi_name(30) == "Amavasya"


def test_the_karanas_are_seven_movable_and_four_fixed():
    assert len(MOVABLE_KARANAS) == 7
    assert len(FIXED_KARANAS) == 4
    assert BHADRA in MOVABLE_KARANAS


def test_the_movable_karanas_repeat_eight_times_across_the_month():
    """Karanas 2 to 57 are the seven movable ones, eight times over."""
    movable = [karana_name(index) for index in range(2, 58)]
    assert len(movable) == 56
    for name in MOVABLE_KARANAS:
        assert movable.count(name) == 8
    assert set(movable) == set(MOVABLE_KARANAS)


def test_the_fixed_karanas_sit_where_they_should():
    assert karana_name(1) == "Kimstughna"
    assert karana_name(58) == "Shakuni"
    assert karana_name(59) == "Chatushpada"
    assert karana_name(60) == "Naga"


def test_there_are_twenty_seven_nitya_yogas():
    assert len(NITYA_YOGAS) == 27
    assert len(set(NITYA_YOGAS)) == 27


# --- the arithmetic ----------------------------------------------------------


def test_a_new_moon_is_the_first_tithi_and_a_full_moon_the_sixteenth():
    """Tithi counts twelve degrees of the Moon's lead over the Sun."""
    from conftest import synthetic_chart

    assert tithi_index(synthetic_chart(Sun=0.0, Moon=1.0)) == 1
    assert tithi_index(synthetic_chart(Sun=0.0, Moon=13.0)) == 2
    assert tithi_index(synthetic_chart(Sun=0.0, Moon=181.0)) == 16
    assert tithi_index(synthetic_chart(Sun=0.0, Moon=359.0)) == 30


def test_each_tithi_is_exactly_two_karanas():
    from conftest import synthetic_chart

    for tithi in range(1, 31):
        start = (tithi - 1) * 12.0
        first = karana_index(synthetic_chart(Sun=0.0, Moon=start + 1.0))
        second = karana_index(synthetic_chart(Sun=0.0, Moon=start + 7.0))
        assert (first, second) == (tithi * 2 - 1, tithi * 2)


def test_the_yoga_is_driven_by_the_sum_of_the_luminaries():
    from conftest import synthetic_chart

    assert yoga_index(synthetic_chart(Sun=0.0, Moon=1.0)) == 1
    assert yoga_index(synthetic_chart(Sun=10.0, Moon=10.0)) == 2  # 20 deg > 13d20'
    assert yoga_index(synthetic_chart(Sun=180.0, Moon=179.0)) == 27


# --- against the almanac -----------------------------------------------------


def test_a_known_new_moon_bounds_amavasya():
    """New moon falls at 01:22 IST on 19 January 2026.

    Amavasya is the tithi that *ends* at conjunction, not one centred on it: the Moon
    catching the Sun is the boundary. So the hours before read 30 and the hours after
    read 1. Getting this backwards would misdate every Amavasya by a day.
    """
    before = julian_day(2026, 1, 18, 14.5)  # 20:00 IST on the 18th
    after = julian_day(2026, 1, 19, 2.0)  # 07:30 IST on the 19th
    assert tithi_index(compute_chart(before, *DELHI)) == 30
    assert tithi_index(compute_chart(after, *DELHI)) == 1


def test_a_known_full_moon_bounds_purnima():
    """Full moon at 15:55 IST on 3 January 2026, which is where Purnima ends."""
    before = julian_day(2026, 1, 3, 6.5)  # 12:00 IST
    after = julian_day(2026, 1, 3, 12.0)  # 17:30 IST
    assert tithi_index(compute_chart(before, *DELHI)) == 15
    assert tithi_name(15) == "Purnima"
    assert tithi_index(compute_chart(after, *DELHI)) == 16


def test_sunrise_is_found_and_lands_at_a_plausible_hour():
    jd = julian_day(2026, 6, 21, 0.0)
    rise = sunrise(jd + 0.5, *DELHI)
    assert rise is not None
    hour_ist = (rise - int(rise) - 0.5) * 24 + 5.5
    assert 5.0 < hour_ist % 24 < 6.5  # Delhi midsummer sunrise is about 05:24 IST


def test_sunrise_precedes_the_moment_asked_about():
    jd = julian_day(2026, 6, 21, 12.0)
    rise = sunrise(jd, *DELHI)
    assert rise is not None and rise <= jd


def test_the_weekday_is_correct_for_a_known_date():
    """10 August 2026 is a Monday."""
    assert vara(julian_day(2026, 8, 10, 12.0), *DELHI).name == "Monday"
    assert vara(julian_day(2026, 8, 11, 12.0), *DELHI).name == "Tuesday"


def test_the_weekday_before_sunrise_is_still_the_previous_day():
    """The Indian day begins at sunrise, so 03:00 belongs to the day before."""
    before = vara(julian_day(2026, 8, 10, 21.5), *DELHI)  # 03:00 IST on the 11th
    after = vara(julian_day(2026, 8, 11, 6.0), *DELHI)  # 11:30 IST on the 11th
    assert before.name == "Monday"
    assert after.name == "Tuesday"


def test_the_weekday_names_its_ruling_planet():
    assert "Moon" in vara(julian_day(2026, 8, 10, 12.0), *DELHI).note


# --- the whole panchanga -----------------------------------------------------


def test_every_limb_is_present_and_dated():
    result = compute(julian_day(2026, 8, 10, 6.0), *DELHI)

    assert 1 <= result.tithi.index <= 30
    assert result.paksha in ("Shukla", "Krishna")
    assert result.tithi_group in TITHI_GROUPS
    assert 1 <= result.karana.index <= 60
    assert 1 <= result.yoga.index <= 27
    assert 1 <= result.nakshatra.index <= 27

    for limb in (result.tithi, result.karana, result.yoga, result.nakshatra):
        assert limb.ends_jd is not None
        assert limb.ends_jd > result.jd, f"{limb.name} must end after the moment asked"


def test_limbs_end_within_a_plausible_span():
    result = compute(julian_day(2026, 8, 10, 6.0), *DELHI)
    assert result.tithi.ends_jd - result.jd < 1.5
    assert result.karana.ends_jd - result.jd < 1.0
    assert result.nakshatra.ends_jd - result.jd < 1.5


def test_the_paksha_follows_the_tithi():
    for jd in (julian_day(2026, 2, 25, 6.0), julian_day(2026, 3, 10, 6.0)):
        result = compute(jd, *DELHI)
        assert result.paksha == ("Shukla" if result.tithi.index <= 15 else "Krishna")


def test_the_nitya_yoga_admits_it_is_not_in_the_text():
    result = compute(julian_day(2026, 8, 10, 6.0), *DELHI)
    assert "not in the ingested texts" in result.yoga.note


# --- the flags BPHS attaches -------------------------------------------------


def test_an_amavasya_birth_is_flagged_with_its_citation():
    jd = julian_day(2026, 1, 18, 14.5)  # 20:00 IST, still Amavasya
    flags = compute(jd, *DELHI).flags
    assert any("Amavasya" in flag for flag in flags)
    for flag in flags:
        assert "ch. 85" in flag or "ch. 92" in flag


def test_a_dark_fortnight_birth_is_flagged():
    result = compute(julian_day(2026, 3, 10, 6.0), *DELHI)
    assert result.paksha == "Krishna"
    assert any("Krishna Paksha" in flag for flag in result.flags)


def test_flags_describe_a_condition_rather_than_assuming_a_birth():
    """The same function reports today's panchanga, where nobody was born."""
    for jd in (julian_day(2026, 1, 18, 14.5), julian_day(2026, 3, 10, 6.0)):
        for flag in compute(jd, *DELHI).flags:
            assert not flag.startswith("Born"), flag
            assert "BPHS lists birth" in flag or "Gandanta" in flag


def test_a_bright_uneventful_day_carries_no_flags():
    """Flags must be selective: a chart with nothing notable should say nothing."""
    for day in range(1, 12):
        result = compute(julian_day(2026, 3, day, 6.0), *DELHI)
        if result.paksha == "Shukla" and result.tithi.index not in (14, 15):
            if result.karana.name != BHADRA:
                assert result.flags == (), (
                    f"{result.tithi.name} {result.karana.name} should be unflagged"
                )
                return
    pytest.fail("no quiet day found in the sampled range")


def test_bhadra_karana_is_flagged_when_it_occurs():
    """Vishti recurs every few days, so a fortnight must contain one."""
    found = False
    for day in range(1, 16):
        result = compute(julian_day(2026, 3, day, 6.0), *DELHI)
        if result.karana.name == BHADRA:
            found = True
            assert any("Bhadra" in flag for flag in result.flags)
    assert found, "Vishti should occur at least once in a fortnight"
