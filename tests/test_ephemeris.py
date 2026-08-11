"""Golden tests for the ephemeris layer.

These anchor the computation against facts that can be checked outside this codebase:
published ayanamsa values, panchang event times, and astronomical events with known
dates. Internal-consistency tests catch the rest. If any of these fail, nothing built
on top of the ephemeris can be trusted, so this file runs first.
"""

from __future__ import annotations

import swisseph as swe

from astro.core.ephemeris import (
    NAKSHATRAS,
    SIGNS,
    Chart,
    _describe,
    compute_chart,
    julian_day,
)

ARCSEC = 1.0 / 3600.0
ARCMIN = 1.0 / 60.0

# Delhi, used as a generic reference location for house-independent checks.
DELHI = (28.6139, 77.2090)


def _chart(year, month, day, hour_ut, lat=DELHI[0], lon=DELHI[1], **kw) -> Chart:
    return compute_chart(julian_day(year, month, day, hour_ut), lat, lon, **kw)


def _sidereal_sun(jd: float) -> float:
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    return swe.calc_ut(jd, swe.SUN, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)[0][0]


# --- external anchors -------------------------------------------------------


def test_lahiri_ayanamsa_at_j2000_matches_published_value():
    """Lahiri (Chitrapaksha) ayanamsa at J2000.0 is 23 deg 51' 11".

    Guards against using swe.get_ayanamsa_ut, which omits the precession correction
    and reads about 14 arcseconds high.
    """
    chart = _chart(2000, 1, 1, 12.0)
    expected = 23 + 51 * ARCMIN + 11 * ARCSEC
    assert abs(chart.ayanamsa_value - expected) < 1 * ARCSEC


def test_ayanamsa_precesses_at_roughly_50_arcsec_per_year():
    a1950 = _chart(1950, 1, 1, 0.0).ayanamsa_value
    a2050 = _chart(2050, 1, 1, 0.0).ayanamsa_value
    per_year = (a2050 - a1950) / 100.0 * 3600.0
    assert 50.0 < per_year < 50.6


def test_mesha_sankranti_2026_matches_published_panchang():
    """Sidereal Sun enters Aries on 14 April 2026 at 09:32 IST (Lahiri).

    A whole-chart check: it depends on the solar longitude and the ayanamsa together,
    so an error in either shifts the crossing by minutes or days.
    """
    low, high = julian_day(2026, 4, 12, 0.0), julian_day(2026, 4, 16, 0.0)
    for _ in range(80):
        mid = (low + high) / 2.0
        if _sidereal_sun(mid) > 180.0:
            low = mid
        else:
            high = mid

    year, month, day, hour_ut = swe.revjul(high, swe.GREG_CAL)
    hour_ist = hour_ut + 5.5
    assert (year, month, day) == (2026, 4, 14)
    assert abs(hour_ist - 9.533) < 2.0 / 60.0  # within two minutes of 09:32 IST


def test_jupiter_retrograde_on_1990_01_01():
    """Jupiter was retrograde in early January 1990 and direct by mid-May."""
    assert _chart(1990, 1, 1, 6.5).positions["Jupiter"].retrograde
    assert not _chart(1990, 6, 1, 6.5).positions["Jupiter"].retrograde


# --- internal consistency ---------------------------------------------------


def test_ketu_is_exactly_opposite_rahu():
    chart = _chart(1990, 1, 1, 6.5)
    rahu = chart.positions["Rahu"].longitude
    ketu = chart.positions["Ketu"].longitude
    assert abs((ketu - rahu) % 360.0 - 180.0) < 1e-9
    assert chart.positions["Rahu"].retrograde
    assert chart.positions["Ketu"].retrograde


def test_whole_sign_cusps_land_on_sign_boundaries_starting_at_the_lagna():
    chart = _chart(1990, 1, 1, 6.5)
    assert chart.cusps[0] == chart.lagna_sign * 30.0
    for index, cusp in enumerate(chart.cusps):
        assert cusp % 30.0 == 0.0
        assert cusp == (chart.lagna_sign + index) % 12 * 30.0


def test_house_of_counts_whole_signs_from_the_lagna():
    chart = _chart(1990, 1, 1, 6.5)
    for body, position in chart.positions.items():
        expected = (position.sign - chart.lagna_sign) % 12 + 1
        assert chart.house_of(body) == expected
        assert 1 <= chart.house_of(body) <= 12


def test_sign_nakshatra_and_pada_are_derived_consistently():
    chart = _chart(1990, 1, 1, 6.5)
    for position in chart.positions.values():
        assert 0.0 <= position.longitude < 360.0
        assert position.sign == int(position.longitude // 30)
        assert position.sign_name == SIGNS[position.sign]
        assert abs(position.degree_in_sign - position.longitude % 30.0) < 1e-9
        assert position.nakshatra == int(position.longitude / (360.0 / 27.0))
        assert position.nakshatra_name == NAKSHATRAS[position.nakshatra]
        assert 1 <= position.pada <= 4


def test_nakshatra_boundaries_are_exact():
    """Each nakshatra spans 13 deg 20', each pada 3 deg 20'."""
    arc = 360.0 / 27.0
    for index in range(27):
        for pada in range(4):
            # Just inside each pada, and just before its end.
            start = _describe("probe", index * arc + pada * arc / 4.0 + 1e-9, 0.0, 1.0)
            end = _describe("probe", index * arc + (pada + 1) * arc / 4.0 - 1e-9, 0.0, 1.0)
            for position in (start, end):
                assert position.nakshatra == index
                assert position.nakshatra_name == NAKSHATRAS[index]
                assert position.pada == pada + 1


# --- settings are honoured, not ignored -------------------------------------


def test_ayanamsa_choice_changes_longitudes():
    lahiri = _chart(1990, 1, 1, 6.5, ayanamsa="lahiri")
    raman = _chart(1990, 1, 1, 6.5, ayanamsa="raman")
    delta = lahiri.positions["Sun"].longitude - raman.positions["Sun"].longitude
    # Raman runs about 1.1 degrees behind Lahiri, so Lahiri longitudes read lower.
    assert -1.5 < delta < -0.5


def test_true_and_mean_node_differ_but_stay_close():
    mean = _chart(1990, 1, 1, 6.5, node_type="mean").positions["Rahu"].longitude
    true = _chart(1990, 1, 1, 6.5, node_type="true").positions["Rahu"].longitude
    difference = abs((mean - true + 180.0) % 360.0 - 180.0)
    assert 0.0 < difference < 2.0


def test_house_system_choice_is_applied():
    whole = _chart(1990, 1, 1, 6.5, house_system="whole_sign")
    placidus = _chart(1990, 1, 1, 6.5, house_system="placidus")
    assert abs(whole.ascendant - placidus.ascendant) < 1e-6  # same lagna degree
    assert whole.cusps != placidus.cusps


def test_unknown_settings_are_rejected_rather_than_silently_defaulted():
    import pytest

    for kwargs in (
        {"ayanamsa": "nonsense"},
        {"house_system": "nonsense"},
        {"node_type": "nonsense"},
    ):
        with pytest.raises(ValueError):
            _chart(1990, 1, 1, 6.5, **kwargs)
