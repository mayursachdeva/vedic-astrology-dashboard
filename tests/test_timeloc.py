"""Tests for birth-time resolution.

Each case is a historical fact about Indian timekeeping that a naive "subtract 5:30"
implementation gets wrong.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from astro.core.timeloc import find_timezone, resolve

DELHI = (28.6139, 77.2090)
PORBANDAR = (21.6417, 69.6293)


def test_timezone_is_found_from_coordinates():
    assert find_timezone(*DELHI) == "Asia/Kolkata"


def test_modern_indian_birth_uses_ist():
    moment = resolve(datetime(1990, 1, 1, 12, 0), *DELHI)
    assert moment.timezone_name == "Asia/Kolkata"
    assert moment.offset_hours == 5.5
    assert moment.offset_label == "UTC+05:30"
    assert moment.utc_datetime == datetime(1990, 1, 1, 6, 30)
    assert moment.warnings == ()


def test_wartime_daylight_saving_is_applied_and_flagged():
    """India ran +6:30 from September 1942 to October 1945.

    A birth in that window is one hour earlier in UT than IST alone would suggest.
    """
    moment = resolve(datetime(1943, 6, 15, 12, 0), *DELHI)
    assert moment.offset_hours == 6.5
    assert moment.utc_datetime == datetime(1943, 6, 15, 5, 30)
    assert any("Daylight saving" in warning for warning in moment.warnings)


def test_just_outside_the_wartime_window_is_plain_ist():
    assert resolve(datetime(1946, 6, 15, 12, 0), *DELHI).offset_hours == 5.5


def test_pre_1906_birth_falls_back_to_local_mean_time_and_says_so():
    """Before 1906 India had no single standard zone; IANA uses Madras mean time."""
    moment = resolve(datetime(1869, 10, 2, 7, 12), *PORBANDAR)
    assert moment.offset_hours != 5.5
    assert 5.5 < moment.offset_hours < 6.0
    assert any("predates standard time" in warning for warning in moment.warnings)


def test_true_lmt_uses_the_birth_longitude_not_a_reference_city():
    """Porbandar sits about 18.7 degrees west of the meridian IANA anchors Asia/Kolkata
    to, which is roughly 75 minutes of local mean time — enough to move the lagna by
    most of a sign. This is the whole reason the option exists."""
    wall = datetime(1869, 10, 2, 7, 12)
    via_iana = resolve(wall, *PORBANDAR)
    via_lmt = resolve(wall, *PORBANDAR, use_true_lmt=True)

    assert via_lmt.basis == "true_lmt"
    assert via_lmt.offset_hours == pytest.approx(PORBANDAR[1] / 15.0)
    difference_minutes = abs(via_iana.offset_hours - via_lmt.offset_hours) * 60.0
    assert 70.0 < difference_minutes < 80.0


def test_ambiguous_wall_clock_time_is_flagged_rather_than_guessed_silently():
    """US clocks went back at 02:00 on 3 November 2024; 01:30 happened twice."""
    moment = resolve(datetime(2024, 11, 3, 1, 30), 40.7128, -74.0060)
    assert any("Ambiguous" in warning for warning in moment.warnings)


def test_nonexistent_wall_clock_time_is_flagged():
    """US clocks jumped 02:00 to 03:00 on 10 March 2024; 02:30 never happened."""
    moment = resolve(datetime(2024, 3, 10, 2, 30), 40.7128, -74.0060)
    assert any("never existed" in warning for warning in moment.warnings)


def test_julian_day_is_consistent_with_the_resolved_utc_time():
    from astro.core.ephemeris import julian_day

    moment = resolve(datetime(1990, 1, 1, 12, 0), *DELHI)
    assert moment.jd_ut == julian_day(1990, 1, 1, 6.5)


def test_aware_datetimes_are_rejected():
    from datetime import timezone as dt_timezone

    with pytest.raises(ValueError):
        resolve(datetime(1990, 1, 1, 12, 0, tzinfo=dt_timezone.utc), *DELHI)
