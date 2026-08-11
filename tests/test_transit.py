"""Tests for transits.

The dated results — ingresses, stations, sade sati — are checked against astronomical
facts that can be verified outside this codebase, because a transit window that is off
by weeks makes every prediction built on it wrong.
"""

from __future__ import annotations

import pytest
import swisseph as swe

from astro.core.ashtakavarga import compute as compute_ashtakavarga
from astro.core.ephemeris import SIGNS, compute_chart, julian_day
from astro.core.strength import GRAHAS
from astro.core.transit import (
    FAVOURABLE_BINDUS,
    GOCHARA_GOOD_HOUSES,
    combustion_windows,
    confluence,
    contacts,
    gochara,
    retrograde_windows,
    sade_sati,
    sign_transits,
    transit_chart,
)

NATAL = compute_chart(julian_day(1990, 1, 1, 6.5), 28.6139, 77.2090)
VARGA = compute_ashtakavarga(NATAL)


def ymd(jd: float) -> tuple[int, int, int]:
    year, month, day, _ = swe.revjul(jd, swe.GREG_CAL)
    return year, month, day


# --- positions --------------------------------------------------------------


def test_transit_chart_uses_the_natal_settings():
    """Comparing a Lahiri natal chart against a Raman transit would shift everything."""
    moving = transit_chart(NATAL, julian_day(2026, 8, 10, 0.0))
    assert moving.ayanamsa == NATAL.ayanamsa
    assert moving.node_type == NATAL.node_type
    assert moving.house_system == NATAL.house_system


def test_transit_at_the_birth_moment_reproduces_the_natal_chart():
    moving = transit_chart(NATAL, NATAL.jd_ut)
    for body in GRAHAS:
        assert moving.positions[body].longitude == pytest.approx(
            NATAL.positions[body].longitude
        )


# --- gochara ----------------------------------------------------------------


def test_gochara_covers_every_graha_with_both_readings():
    standings = gochara(NATAL, VARGA, julian_day(2026, 8, 10, 0.0))
    assert set(standings) == set(GRAHAS)
    for body, standing in standings.items():
        assert 1 <= standing.house_from_moon <= 12
        assert 1 <= standing.house_from_lagna <= 12
        assert isinstance(standing.supported, bool)
        assert standing.traditionally_good == (
            standing.house_from_moon in GOCHARA_GOOD_HOUSES[body]
        )


def test_the_bindu_reading_matches_the_natal_ashtakavarga():
    standings = gochara(NATAL, VARGA, julian_day(2026, 8, 10, 0.0))
    for body, standing in standings.items():
        if body in ("Rahu", "Ketu"):
            assert standing.bindus == 0  # the nodes have no ashtakavarga of their own
            continue
        assert standing.bindus == VARGA.bav(body, standing.sign)
        assert standing.supported == (standing.bindus >= FAVOURABLE_BINDUS)


def test_house_from_moon_is_counted_from_the_natal_moon_not_the_lagna():
    jd = julian_day(2026, 8, 10, 0.0)
    standings = gochara(NATAL, VARGA, jd)
    moving = transit_chart(NATAL, jd)
    moon_sign = NATAL.positions["Moon"].sign
    for body, standing in standings.items():
        expected = (moving.positions[body].sign - moon_sign) % 12 + 1
        assert standing.house_from_moon == expected


def test_the_two_doctrines_are_reported_separately():
    """They disagree often, and the point of carrying both is to be able to say so."""
    standings = gochara(NATAL, VARGA, julian_day(2026, 8, 10, 0.0))
    for standing in standings.values():
        assert standing.agrees == (standing.supported == standing.traditionally_good)


# --- contacts ---------------------------------------------------------------


def test_a_transit_over_a_natal_point_is_found_as_a_conjunction():
    """At the birth moment every graha sits exactly on its own natal position."""
    found = contacts(NATAL, NATAL.jd_ut, orb=1.0)
    conjunctions = {
        (contact.transiting, contact.natal_point)
        for contact in found
        if contact.kind == "conjunction"
    }
    for body in GRAHAS:
        assert (body, body) in conjunctions


def test_conjunctions_respect_the_orb():
    tight = contacts(NATAL, NATAL.jd_ut, orb=0.001)
    wide = contacts(NATAL, NATAL.jd_ut, orb=10.0)
    assert len(wide) >= len(tight)
    for contact in tight:
        if contact.kind == "conjunction":
            assert contact.separation <= 0.001


def test_the_lagna_is_available_as_a_natal_point():
    found = contacts(NATAL, julian_day(2026, 8, 10, 0.0), orb=5.0)
    assert any(contact.natal_point == "Lagna" for contact in found)


# --- dated windows ----------------------------------------------------------


def test_sign_transits_tile_the_span_without_gaps_or_overlaps():
    start, end = julian_day(2026, 1, 1, 0.0), julian_day(2027, 1, 1, 0.0)
    windows = sign_transits(NATAL, "Mars", start, end)

    assert windows[0].start_jd == start
    assert windows[-1].end_jd == end
    for earlier, later in zip(windows, windows[1:]):
        assert earlier.end_jd == pytest.approx(later.start_jd)


def test_the_sun_changes_sign_twelve_times_a_year():
    start, end = julian_day(2026, 1, 1, 0.0), julian_day(2027, 1, 1, 0.0)
    windows = sign_transits(NATAL, "Sun", start, end)
    # Twelve ingresses inside the year gives thirteen spans, the first and last clipped.
    assert len(windows) == 13


def test_a_solar_ingress_lands_on_the_published_date():
    """The Sun enters sidereal Aries on 14 April 2026 (Mesha Sankranti)."""
    windows = sign_transits(
        NATAL, "Sun", julian_day(2026, 4, 1, 0.0), julian_day(2026, 5, 1, 0.0)
    )
    ingress = next(
        window for window in windows if window.label == "Sun in Aries"
    )
    assert ymd(ingress.start_jd) == (2026, 4, 14)


def test_saturn_spends_about_two_and_a_half_years_in_each_sign():
    """Dwell per sign, counting only passages that genuinely completed.

    Three things make the naive version of this wrong, and all three are correct
    behaviour rather than bugs. Saturn retrogrades back over a boundary and re-enters,
    so one sign yields several windows. A sign clipped by the edge of the span shows a
    partial stay. And a sign entered near the end and retrograded straight back out
    looks complete but is not — Saturn returns to it after the span closes.

    So a passage counts only when the sign was entered from the previous sign and
    finally left into the next one.
    """
    start, end = julian_day(2020, 1, 1, 0.0), julian_day(2030, 1, 1, 0.0)
    windows = sign_transits(NATAL, "Saturn", start, end)
    signs = [SIGNS.index(window.label.removeprefix("Saturn in ")) for window in windows]

    assert sum(window.days for window in windows) == pytest.approx(end - start)

    completed: dict[int, float] = {}
    for sign in set(signs):
        first = signs.index(sign)
        last = len(signs) - 1 - signs[::-1].index(sign)
        entered_forwards = first > 0 and signs[first - 1] == (sign - 1) % 12
        left_forwards = last < len(signs) - 1 and signs[last + 1] == (sign + 1) % 12
        if entered_forwards and left_forwards:
            completed[sign] = sum(
                window.days
                for window, index in zip(windows, signs)
                if index == sign
            )

    assert completed, "a decade must contain at least one complete Saturn sign passage"
    for sign, days in completed.items():
        # The mean is 896 days, but Saturn's orbit is eccentric enough that measured
        # dwell runs from roughly 857 to 1015 days depending on the sign.
        assert 820 < days < 1050, f"{SIGNS[sign]} lasted {days:.0f} days"


def test_a_sign_can_be_entered_more_than_once_when_the_planet_retrogrades():
    """The behaviour the previous test got wrong, pinned deliberately."""
    windows = sign_transits(
        NATAL, "Saturn", julian_day(2020, 1, 1, 0.0), julian_day(2030, 1, 1, 0.0)
    )
    labels = [window.label for window in windows]
    assert len(labels) > len(set(labels)), "expected at least one retrograde re-entry"


def test_mercury_retrogrades_about_three_times_a_year():
    windows = retrograde_windows(
        NATAL, "Mercury", julian_day(2026, 1, 1, 0.0), julian_day(2027, 1, 1, 0.0)
    )
    assert 2 <= len(windows) <= 4
    for window in windows:
        assert 15 < window.days < 30  # each loop runs about three weeks


def test_the_luminaries_and_nodes_report_no_retrograde_windows():
    span = (julian_day(2026, 1, 1, 0.0), julian_day(2027, 1, 1, 0.0))
    for body in ("Sun", "Moon", "Rahu", "Ketu"):
        assert retrograde_windows(NATAL, body, *span) == []


def test_retrograde_windows_actually_contain_retrograde_motion():
    windows = retrograde_windows(
        NATAL, "Mars", julian_day(2024, 1, 1, 0.0), julian_day(2027, 1, 1, 0.0)
    )
    for window in windows:
        middle = (window.start_jd + window.end_jd) / 2.0
        assert transit_chart(NATAL, middle).positions["Mars"].retrograde


def test_mercury_is_combust_several_times_a_year():
    windows = combustion_windows(
        NATAL, "Mercury", julian_day(2026, 1, 1, 0.0), julian_day(2027, 1, 1, 0.0)
    )
    assert windows
    for window in windows:
        middle = (window.start_jd + window.end_jd) / 2.0
        moving = transit_chart(NATAL, middle)
        separation = abs(
            (
                moving.positions["Mercury"].longitude
                - moving.positions["Sun"].longitude
                + 180.0
            )
            % 360.0
            - 180.0
        )
        assert separation < 14.0


def test_the_sun_is_never_combust():
    assert combustion_windows(
        NATAL, "Sun", julian_day(2026, 1, 1, 0.0), julian_day(2027, 1, 1, 0.0)
    ) == []


# --- sade sati --------------------------------------------------------------


def test_sade_sati_is_saturn_in_the_twelfth_first_or_second_from_the_natal_moon():
    windows = sade_sati(NATAL, julian_day(2020, 1, 1, 0.0), julian_day(2040, 1, 1, 0.0))
    assert windows, "twenty years must contain part of a sade sati"

    moon_sign = NATAL.positions["Moon"].sign
    for window in windows:
        middle = (window.start_jd + window.end_jd) / 2.0
        saturn_sign = transit_chart(NATAL, middle).positions["Saturn"].sign
        assert (saturn_sign - moon_sign) % 12 + 1 in (12, 1, 2)


def test_sade_sati_phases_run_in_order_and_last_about_seven_years_together():
    windows = sade_sati(NATAL, julian_day(2020, 1, 1, 0.0), julian_day(2045, 1, 1, 0.0))
    labels = [window.label for window in windows]
    assert any("rising" in label for label in labels)

    # Consecutive legs must be contiguous: Saturn leaves one sign as it enters the next.
    runs = []
    current = [windows[0]]
    for window in windows[1:]:
        if window.start_jd == pytest.approx(current[-1].end_jd):
            current.append(window)
        else:
            runs.append(current)
            current = [window]
    runs.append(current)

    complete = [run for run in runs if len(run) == 3]
    for run in complete:
        total = run[-1].end_jd - run[0].start_jd
        assert 2400 < total < 2900  # seven and a half years, give or take


def test_sade_sati_says_where_the_doctrine_comes_from():
    windows = sade_sati(NATAL, julian_day(2020, 1, 1, 0.0), julian_day(2040, 1, 1, 0.0))
    for window in windows:
        assert "not found in the ingested texts" in window.detail


# --- confluence -------------------------------------------------------------


def test_confluence_explains_itself_rather_than_returning_a_bare_number():
    from astro.core.dasha import chain_at, vimshottari

    jd = julian_day(2026, 8, 10, 0.0)
    chain = chain_at(vimshottari(NATAL.positions["Moon"].longitude, NATAL.jd_ut), jd)
    result = confluence(NATAL, VARGA, chain, jd)

    assert result["reading"] in ("supported", "obstructed", "mixed")
    assert len(result["components"]) == len(chain)
    for component in result["components"]:
        assert component["lord"]
        assert component["contribution"] in (component["weight"], -component["weight"])
    assert "heuristic" in result["basis"]
    assert "ch. 66" in result["basis"]


def test_confluence_weights_the_mahadasha_above_the_antardasha():
    from astro.core.dasha import chain_at, vimshottari

    jd = julian_day(2026, 8, 10, 0.0)
    chain = chain_at(vimshottari(NATAL.positions["Moon"].longitude, NATAL.jd_ut), jd)
    weights = [c["weight"] for c in confluence(NATAL, VARGA, chain, jd)["components"]]
    assert weights == sorted(weights, reverse=True)


def test_a_station_date_matches_an_independent_computation():
    """Saturn turns direct on 11 December 2026 in sidereal terms.

    Verified by solving for the speed sign change straight from swisseph rather than
    through this module. Tropical gives the 10th: near a station the speed is almost
    zero, so the ayanamsa drift of about 50 arcseconds a year is enough to move the
    crossing by a day. This module works in sidereal throughout, so the sidereal answer
    is the right one to match.
    """
    windows = retrograde_windows(
        NATAL, "Saturn", julian_day(2026, 8, 1, 0.0), julian_day(2027, 3, 1, 0.0)
    )
    assert len(windows) == 1
    assert ymd(windows[0].end_jd) == (2026, 12, 11)


def test_a_retrograde_window_open_at_the_start_of_the_span_is_reported():
    """Saturn turned retrograde on 26 July 2026, before this span opens. The window is
    still real and must not be dropped just because its start is off-screen."""
    start = julian_day(2026, 8, 1, 0.0)
    windows = retrograde_windows(NATAL, "Saturn", start, julian_day(2027, 3, 1, 0.0))
    assert windows[0].start_jd == start
