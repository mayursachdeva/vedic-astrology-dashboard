"""Tests for shadbala.

Shadbala is a stack of a dozen small formulas summed into one number, which is the worst
possible shape for a bug: any one of them can be wrong by fifteen virupas and the total
still looks reasonable. So the components are tested at the points where the text says
exactly what the answer must be — a graha at its exaltation degree, a birth at noon, a
full moon, the seventh aspect — rather than by checking the total against itself.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from astro.core import shadbala as S
from astro.core.ephemeris import julian_day
from astro.core.panchanga import day_span
from astro.core.strength import EXALTATION, SEVEN
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
NATAL = build_natal_chart(PROFILE)
CHART = NATAL.chart
SPAN = day_span(CHART.jd_ut, CHART.latitude, CHART.longitude)


def at(sign: int, degree: float = 10.0) -> float:
    return sign * 30.0 + degree


# --- sthana bala ------------------------------------------------------------


def test_uchcha_bala_is_full_at_exaltation_and_nil_at_the_fall():
    for body, (sign, degree) in EXALTATION.items():
        exalted = synthetic_chart(0.0, **{body: at(sign, degree)})
        fallen = synthetic_chart(0.0, **{body: (at(sign, degree) + 180.0) % 360.0})
        assert S.uchcha_bala(exalted, body) == pytest.approx(60.0)
        assert S.uchcha_bala(fallen, body) == pytest.approx(0.0)


def test_uchcha_bala_is_half_at_a_right_angle_to_the_fall():
    """The verse divides the arc by three, so ninety degrees away is thirty virupas."""
    sign, degree = EXALTATION["Sun"]
    chart = synthetic_chart(0.0, Sun=(at(sign, degree) + 90.0) % 360.0)
    assert S.uchcha_bala(chart, "Sun") == pytest.approx(30.0)


def test_kendradi_bala_splits_sixty_thirty_fifteen():
    # Aries rising, so the sign a graha stands in is its house minus one.
    for house, expected in ((1, 60.0), (4, 60.0), (2, 30.0), (11, 30.0), (3, 15.0), (12, 15.0)):
        chart = synthetic_chart(0.0, Saturn=at(house - 1, 5.0))
        assert chart.house_of("Saturn") == house
        assert S.kendradi_bala(chart, "Saturn") == expected


def test_the_moon_and_venus_want_even_signs_and_everyone_else_odd():
    """Scored across a whole sign, because the navamsa parity is counted too.

    A single degree proves nothing: the rasi may oblige while the navamsa does not, so
    one placement in the "right" sign can score no better than one in the wrong sign.
    Over a full sign the navamsa runs through all nine, leaving the rasi's fifteen
    virupas as the difference.
    """
    def across(body: str, sign: int) -> float:
        return sum(
            S.ojhayugma_bala(synthetic_chart(0.0, **{body: at(sign, degree)}), body)
            for degree in range(1, 30, 2)
        )

    even, odd = 1, 0  # Taurus and Aries
    for body, wanted in (("Venus", even), ("Moon", even), ("Sun", odd), ("Saturn", odd)):
        assert across(body, wanted) > across(body, 1 - wanted), body


def test_drekkana_bala_goes_to_the_decanate_that_matches_the_graha():
    # Male grahas want the first decanate, female the second, the rest the third.
    for body, decanate in (("Sun", 0), ("Venus", 1), ("Mercury", 2)):
        for candidate in range(3):
            chart = synthetic_chart(0.0, **{body: at(4, candidate * 10.0 + 5.0)})
            expected = 15.0 if candidate == decanate else 0.0
            assert S.drekkana_bala(chart, body) == expected


def test_saptavargaja_bala_is_higher_in_its_own_sign_than_in_an_enemys():
    own = synthetic_chart(0.0, Saturn=at(9, 15.0))     # Capricorn
    enemy = synthetic_chart(0.0, Saturn=at(4, 15.0))   # Leo, the Sun's
    assert S.saptavargaja_bala(own, "Saturn") > S.saptavargaja_bala(enemy, "Saturn")


# --- dig bala ---------------------------------------------------------------


def test_dig_bala_is_full_opposite_the_direction_the_graha_is_weakest_in():
    """Sun and Mars at the midheaven, Jupiter and Mercury at the ascendant, Venus and
    the Moon at the nadir, Saturn at the descendant."""
    strongest = {
        "Sun": "midheaven", "Mars": "midheaven",
        "Jupiter": "ascendant", "Mercury": "ascendant",
        "Venus": "nadir", "Moon": "nadir",
        "Saturn": "descendant",
    }
    angles = {
        "ascendant": CHART.ascendant,
        "descendant": (CHART.ascendant + 180.0) % 360.0,
        "midheaven": CHART.midheaven,
        "nadir": (CHART.midheaven + 180.0) % 360.0,
    }
    for body, angle in strongest.items():
        moved = _with_longitude(CHART, body, angles[angle])
        assert S.dig_bala(moved, body) == pytest.approx(60.0, abs=1e-6)
        opposite = _with_longitude(CHART, body, (angles[angle] + 180.0) % 360.0)
        assert S.dig_bala(opposite, body) == pytest.approx(0.0, abs=1e-6)


def _with_longitude(chart, body, longitude):
    from astro.core.ephemeris import Chart, _describe

    position = chart.positions[body]
    moved = dict(chart.positions)
    moved[body] = _describe(body, longitude, position.latitude, position.speed)
    return Chart(**{**chart.__dict__, "positions": moved})


def test_dig_bala_does_not_depend_on_the_house_system():
    """It is measured from the angles, not from the cusps. Under whole-sign houses a
    cusp is a sign boundary, and reading Dig Bala off one would make the same birth
    yield different strengths for no astronomical reason."""
    from astro.core.ephemeris import compute_chart

    whole = compute_chart(CHART.jd_ut, CHART.latitude, CHART.longitude)
    placidus = compute_chart(
        CHART.jd_ut, CHART.latitude, CHART.longitude, house_system="placidus"
    )
    assert whole.cusps != placidus.cusps
    for body in SEVEN:
        assert S.dig_bala(whole, body) == pytest.approx(S.dig_bala(placidus, body))


# --- kala bala --------------------------------------------------------------


def _at_hour(hour: float):
    profile = Profile(
        name="x", birth_local=datetime(1990, 6, 15, int(hour), int((hour % 1) * 60)),
        latitude=28.6139, longitude=77.2090, place="New Delhi", relation="self",
    )
    return build_natal_chart(profile).chart


def test_the_nocturnal_grahas_peak_at_midnight_and_the_diurnal_at_noon():
    # 77.209 E is 5h09m ahead of UT, so local mean noon is 06:51 UT — the clock hour
    # that matters is the local one, which is why these are read off the chart.
    midnight, noon = _at_hour(0.0), _at_hour(12.0)
    for body in S.NOCTURNAL:
        assert S.nathonnatha_bala(midnight, body) > 55.0
        assert S.nathonnatha_bala(noon, body) < 5.0
    for body in S.DIURNAL:
        assert S.nathonnatha_bala(noon, body) > 55.0
        assert S.nathonnatha_bala(midnight, body) < 5.0


def test_mercury_takes_the_whole_of_nathonnatha_at_any_hour():
    for hour in (0.0, 6.0, 12.0, 18.0):
        assert S.nathonnatha_bala(_at_hour(hour), "Mercury") == 60.0


def test_paksha_bala_follows_the_fortnight():
    full = synthetic_chart(0.0, Sun=at(0, 0.0), Moon=at(6, 0.0))   # opposition
    new = synthetic_chart(0.0, Sun=at(0, 0.0), Moon=at(0, 0.0))    # conjunction
    assert S.paksha_bala(full, "Jupiter") == pytest.approx(60.0)
    assert S.paksha_bala(new, "Jupiter") == pytest.approx(0.0)
    # The malefics take whatever the benefics leave.
    assert S.paksha_bala(full, "Saturn") == pytest.approx(0.0)
    assert S.paksha_bala(new, "Saturn") == pytest.approx(60.0)


def test_the_moon_is_judged_by_the_fortnight_not_by_her_brightness():
    """A crescent Moon is in the bright half and takes the benefics' small share.

    Judged instead by `is_natural_benefic`, which calls her malefic until she is bright,
    she collected the malefic remainder — nearly thirty virupas too many for a chart
    two days after the new moon.
    """
    crescent = synthetic_chart(0.0, Sun=at(0, 0.0), Moon=at(0, 24.0))
    assert S.paksha_bala(crescent, "Moon") == pytest.approx(8.0)
    assert S.paksha_bala(crescent, "Saturn") == pytest.approx(52.0)


def test_jupiter_holds_tribhaga_at_every_hour_and_the_rest_share_it():
    for hour in (7.0, 11.0, 16.0, 21.0, 2.0):
        chart = _at_hour(hour)
        span = day_span(chart.jd_ut, chart.latitude, chart.longitude)
        assert S.tribhaga_bala(chart, "Jupiter", span) == 60.0
        holders = [b for b in SEVEN if S.tribhaga_bala(chart, b, span) == 60.0]
        assert len(holders) == 2, holders  # Jupiter and exactly one third-owner


def test_the_weekday_turns_at_sunrise_not_at_midnight():
    """A birth before dawn belongs to the day before, and Vara Bala is 45 virupas."""
    before_dawn, after_dawn = _at_hour(4.0), _at_hour(9.0)
    early_span = day_span(before_dawn.jd_ut, before_dawn.latitude, before_dawn.longitude)
    late_span = day_span(after_dawn.jd_ut, after_dawn.latitude, after_dawn.longitude)
    lords = (S.vara_lord(before_dawn, early_span), S.vara_lord(after_dawn, late_span))
    assert lords[0] != lords[1]
    assert S.WEEKDAY_LORDS[(S.WEEKDAY_LORDS.index(lords[0]) + 1) % 7] == lords[1]


def test_the_hora_lords_run_in_chaldean_order_from_the_days_lord():
    chart = _at_hour(12.0)
    span = day_span(chart.jd_ut, chart.latitude, chart.longitude)
    rise, _, following = span
    hour = (following - rise) / 24.0
    day_lord = S.vara_lord(chart, span)
    seen = []
    for index in range(7):
        moment = type(chart)(**{**chart.__dict__, "jd_ut": rise + (index + 0.5) * hour})
        seen.append(S.hora_lord(moment, span))
    start = S.CHALDEAN.index(day_lord)
    assert seen == [S.CHALDEAN[(start + i) % 7] for i in range(7)]


def test_the_first_hora_of_the_day_belongs_to_the_days_own_lord():
    chart = _at_hour(12.0)
    span = day_span(chart.jd_ut, chart.latitude, chart.longitude)
    dawn = type(chart)(**{**chart.__dict__, "jd_ut": span[0] + 1e-4})
    assert S.hora_lord(dawn, span) == S.vara_lord(chart, span)


def test_the_year_lord_advances_three_weekdays_a_year():
    """Which is the reason 360, not this edition's printed 60, is the divisor.

    360 days is fifty-one weeks and three days, so the verse's own next step — multiply
    the elapsed years by three — only lands on the right weekday for a 360-day year.
    """
    assert "360" in S.KNOWN_VARIANTS["varsha_bala_divisor"]
    one = type(CHART)(**{**CHART.__dict__, "jd_ut": CHART.jd_ut})
    later = type(CHART)(**{**CHART.__dict__, "jd_ut": CHART.jd_ut + 360.0})
    first, second = S.varsha_lord(one), S.varsha_lord(later)
    step = (S.WEEKDAY_LORDS.index(second) - S.WEEKDAY_LORDS.index(first)) % 7
    assert step == 3


def test_ayana_bala_is_full_when_the_graha_is_where_it_wants_to_be():
    """Sixty when as far as it goes on the favoured side, nil on the far side.

    The extreme is the obliquity itself, a hair under the 23°27' the verse rounds to.
    """
    extreme = S._mean_obliquity(CHART.jd_ut)
    north = _with_declination(CHART, "Jupiter", extreme)
    south = _with_declination(CHART, "Jupiter", -extreme)
    assert S.ayana_bala(north, "Jupiter") == pytest.approx(60.0, abs=0.3)
    assert S.ayana_bala(south, "Jupiter") == pytest.approx(0.0, abs=0.3)
    # Saturn wants the other side.
    saturn_north = _with_declination(CHART, "Saturn", extreme)
    saturn_south = _with_declination(CHART, "Saturn", -extreme)
    assert S.ayana_bala(saturn_south, "Saturn") == pytest.approx(60.0, abs=0.3)
    assert S.ayana_bala(saturn_north, "Saturn") == pytest.approx(0.0, abs=0.3)


def _with_declination(chart, body, target):
    """A chart with `body` placed where its declination is `target`.

    Declination is derived from the tropical longitude, so this solves for the longitude
    rather than setting a field.
    """
    import math

    epsilon = math.radians(S._mean_obliquity(chart.jd_ut))
    tropical = math.degrees(math.asin(math.sin(math.radians(target)) / math.sin(epsilon)))
    sidereal = (tropical - chart.ayanamsa_value) % 360.0
    return _with_longitude_and_latitude(chart, body, sidereal)


def _with_longitude_and_latitude(chart, body, longitude):
    from astro.core.ephemeris import Chart, _describe

    moved = dict(chart.positions)
    moved[body] = _describe(body, longitude, 0.0, chart.positions[body].speed)
    return Chart(**{**chart.__dict__, "positions": moved})


def test_the_suns_ayana_bala_is_doubled():
    north = _with_declination(CHART, "Sun", 10.0)
    other = _with_declination(CHART, "Jupiter", 10.0)
    assert S.ayana_bala(north, "Sun") == pytest.approx(
        2.0 * S.ayana_bala(other, "Jupiter"), abs=0.3
    )


def test_declination_matches_the_solstice():
    """The Sun is as far south as it goes around 21 December."""
    from astro.core.ephemeris import compute_chart

    solstice = compute_chart(julian_day(1990, 12, 21, 12.0), 28.6139, 77.2090)
    assert S.declination(solstice, "Sun") == pytest.approx(-23.44, abs=0.05)


# --- chesta and naisargika --------------------------------------------------


def test_naisargika_bala_runs_from_saturn_up_to_the_sun():
    order = sorted(S.NAISARGIKA_RANK, key=S.naisargika_bala)
    assert order == ["Saturn", "Mars", "Mercury", "Jupiter", "Venus", "Moon", "Sun"]
    assert S.naisargika_bala("Sun") == pytest.approx(60.0)
    assert S.naisargika_bala("Saturn") == pytest.approx(60.0 / 7.0)


def test_a_retrograde_graha_takes_the_whole_of_chesta_bala():
    retro = synthetic_chart(0.0, Saturn=at(4, 10.0), retrograde=("Saturn",))
    assert S._motion(retro, "Saturn") == "vakra"
    assert S.chesta_bala(retro, "Saturn") == 60.0


def test_a_graha_at_its_usual_pace_scores_more_than_one_crawling():
    """Charak's ordering of the middle three motions, not this translation's.

    Read the other way round, a graha moving at about its mean speed takes 7.5 virupas
    and one barely moving takes 30 — which inverts the whole point of the measure.
    """
    assert S.MOTION_VALUE["madhya"] > S.MOTION_VALUE["manda"] > S.MOTION_VALUE["mandatara"]
    mean = S.MEAN_MOTION["Mars"]
    usual = _with_speed(CHART, "Mars", mean)
    slow = _with_speed(CHART, "Mars", mean * 0.7)
    crawling = _with_speed(CHART, "Mars", mean * 0.2)
    assert S._motion(usual, "Mars") == "madhya"
    assert S._motion(slow, "Mars") == "manda"
    assert S._motion(crawling, "Mars") == "mandatara"
    assert (
        S.chesta_bala(usual, "Mars")
        > S.chesta_bala(slow, "Mars")
        > S.chesta_bala(crawling, "Mars")
    )


def _with_speed(chart, body, speed):
    from astro.core.ephemeris import Chart, _describe

    position = chart.positions[body]
    moved = dict(chart.positions)
    moved[body] = _describe(body, position.longitude, position.latitude, speed)
    return Chart(**{**chart.__dict__, "positions": moved})


def test_the_sun_and_moon_take_their_chesta_from_the_verse_that_names_them():
    assert S.chesta_bala(CHART, "Sun") == S.ayana_bala(CHART, "Sun")
    assert S.chesta_bala(CHART, "Moon") == S.paksha_bala(CHART, "Moon")


def test_the_sun_is_the_one_graha_whose_chesta_can_pass_sixty():
    """Because his Ayana Bala is doubled and his Chesta Bala is a copy of it.

    Not a rounding slip — it follows from two verses read together, and the reading is
    contested. Asserted so that a later "cap everything at 60" cannot pass silently.
    """
    assert "doubled" in S.KNOWN_VARIANTS["suns_doubled_ayana_in_chesta"]
    north = _with_declination(CHART, "Sun", 20.0)
    assert S.chesta_bala(north, "Sun") > 60.0
    for body in SEVEN:
        if body != "Sun":
            assert S.chesta_bala(CHART, body) <= 60.0


# --- drishti and drik bala --------------------------------------------------


def drishti(who: str, separation: float) -> float:
    return S._drishti(S.DRISHTI_TABLE[who], separation)


def test_every_graha_aspects_the_seventh_fully():
    for who in S.DRISHTI_TABLE:
        assert drishti(who, 180.0) == pytest.approx(60.0), who


def test_the_drishti_ladder_matches_charaks_table_at_every_sign_boundary():
    """Charak (p. 186) tabulates all four columns every thirty degrees.

    A second text stating the same values is what settles ch. 26, whose own arithmetic
    contradicts its own ladder. Full = 60, three quarters = 45, half = 30, a quarter =
    15, and no aspect at all inside 30 degrees or past 300.
    """
    full, three_quarters, half, quarter, none = 60.0, 45.0, 30.0, 15.0, 0.0
    table = {
        #  arc:   Mars,          Jupiter,       Saturn,        the rest
        30:  (none, none, none, none),
        60:  (quarter, quarter, full, quarter),
        90:  (full, three_quarters, three_quarters, three_quarters),
        120: (half, full, half, half),
        150: (none, none, none, none),
        180: (full, full, full, full),
        210: (full, three_quarters, three_quarters, three_quarters),
        240: (half, full, half, half),
        270: (quarter, quarter, full, quarter),
        300: (none, none, none, none),
    }
    for arc, (mars, jupiter, saturn, rest) in table.items():
        assert drishti("Mars", arc) == pytest.approx(mars), ("Mars", arc)
        assert drishti("Jupiter", arc) == pytest.approx(jupiter), ("Jupiter", arc)
        assert drishti("Saturn", arc) == pytest.approx(saturn), ("Saturn", arc)
        assert drishti("general", arc) == pytest.approx(rest), ("general", arc)


def test_a_special_aspect_beats_the_general_ladder_at_its_own_angle():
    """Otherwise the special rules would be decorative."""
    assert drishti("Saturn", 60.0) > drishti("general", 60.0)
    assert drishti("Mars", 90.0) > drishti("general", 90.0)
    assert drishti("Jupiter", 120.0) > drishti("general", 120.0)


def test_a_graha_aspects_nothing_it_stands_on_or_just_behind():
    for who in S.DRISHTI_TABLE:
        assert drishti(who, 0.0) == 0.0
        assert drishti(who, 15.0) == 0.0
        assert drishti(who, 330.0) == 0.0


def test_drishti_is_measured_forward_from_the_giver():
    """Saturn aspects the third house ahead of it, not the third behind.

    The translation reads "deduct the longitude of the Grah that receives from that of
    the Grah which gives", which is the other way round and would put Saturn's special
    aspect on the eleventh.
    """
    chart = synthetic_chart(0.0, Saturn=at(0, 0.0), Mars=at(2, 0.0), Venus=at(10, 0.0))
    ahead = S.drishti_value(chart, "Saturn", "Mars")     # two signs on: the 3rd
    behind = S.drishti_value(chart, "Saturn", "Venus")   # two signs back: the 11th
    assert ahead == pytest.approx(60.0)
    assert behind < ahead


def test_drik_bala_is_negative_under_malefic_gaze_and_positive_under_benefic():
    watched = at(6, 0.0)  # the seventh from Aries
    malefic = synthetic_chart(0.0, Mercury=watched, Saturn=at(0, 0.0), Jupiter=at(3, 15.0),
                              Venus=at(4, 15.0), Sun=at(0, 2.0), Moon=at(0, 4.0),
                              Mars=at(0, 6.0), Rahu=at(1, 1.0))
    assert S.drik_bala(malefic, "Mercury") < 0

    benefic = synthetic_chart(0.0, Mercury=watched, Jupiter=at(0, 0.0), Venus=at(0, 2.0),
                              Sun=at(2, 15.0), Moon=at(6, 20.0), Mars=at(3, 15.0),
                              Saturn=at(4, 15.0), Rahu=at(1, 1.0))
    assert S.drik_bala(benefic, "Mercury") > 0


# --- the whole ---------------------------------------------------------------


def test_the_total_is_the_sum_of_its_six_parts():
    for body, bala in S.shadbala(CHART, SPAN).items():
        parts = sum(bala.sources.values())
        assert bala.total == pytest.approx(parts + bala.yuddha), body
        assert bala.sources["sthana"] == pytest.approx(sum(bala.sthana.values()))
        assert bala.sources["kala"] == pytest.approx(sum(bala.kala.values()))
        assert bala.rupas == pytest.approx(bala.total / 60.0)


def test_every_graha_lands_in_a_range_the_chapter_would_recognise():
    """Not a golden value — a bound. A component wired up wrong shows as a total far
    outside what the required minima of 300 to 420 virupas imply."""
    for body, bala in S.shadbala(CHART, SPAN).items():
        assert 100.0 < bala.total < 900.0, (body, bala.total)


def test_the_nodes_have_no_shadbala():
    """The chapter assigns them none, so none is reported rather than zero."""
    balas = S.shadbala(CHART, SPAN)
    assert set(balas) == set(SEVEN)
    assert "Rahu" not in balas and "Ketu" not in balas


def test_strength_moves_with_the_birth_time():
    """The nocturnal grahas gain at night and the diurnal lose, which is most of the
    point of Kala Bala.

    Compared on Nathonnatha, which is the part that encodes the hour. The totals and
    even the whole of Kala Bala can move the other way — twelve hours swings the
    ascendant halfway round the chart, and whoever happens to own the birth hora
    collects sixty virupas — so the check is that the day/night part is right and that
    it reaches the sum at all.
    """
    day, night = _at_hour(12.0), _at_hour(0.0)
    day_span_ = day_span(day.jd_ut, day.latitude, day.longitude)
    night_span_ = day_span(night.jd_ut, night.latitude, night.longitude)
    by_day = S.shadbala(day, day_span_)
    by_night = S.shadbala(night, night_span_)
    assert by_night["Saturn"].kala["nathonnatha"] > by_day["Saturn"].kala["nathonnatha"]
    assert by_day["Sun"].kala["nathonnatha"] > by_night["Sun"].kala["nathonnatha"]
    assert by_day["Sun"].total != by_night["Sun"].total


def test_the_weekday_is_the_one_at_the_birthplace_not_in_greenwich():
    """15 June 1990 was a Friday, and it is a Friday in Delhi at noon.

    Delhi's sunrise is 23:54 UT the day before, so a weekday read off the julian day
    without the longitude term called it a Thursday — and handed Vara Bala's 45 virupas
    to Jupiter instead of Venus.
    """
    from astro.core.panchanga import vara

    noon = _at_hour(12.0)
    span = day_span(noon.jd_ut, noon.latitude, noon.longitude)
    assert S.vara_lord(noon, span) == "Venus"
    assert vara(noon.jd_ut, noon.latitude, noon.longitude).name == "Friday"


def test_without_a_sunrise_the_hour_based_parts_are_left_out_rather_than_guessed():
    balas = S.shadbala(CHART, None)
    for body, bala in balas.items():
        assert bala.kala["hora"] == 0.0
        if body != "Jupiter":
            assert bala.kala["tribhaga"] == 0.0
    assert S.hora_lord(CHART, None) is None


def test_the_payload_says_which_graha_is_strongest():
    balas = S.shadbala(CHART, SPAN)
    data = S.payload(balas)
    assert data["strongest"] == max(balas, key=lambda b: balas[b].total)
    assert set(data["grahas"]) == set(SEVEN)
    for body, entry in data["grahas"].items():
        assert entry["required"] == S.REQUIRED[body]
        assert entry["strong"] == (entry["total"] >= entry["required"])


def test_a_planetary_war_widens_the_gap_between_the_two():
    """v. 20: the difference is added to the winner and taken from the loser."""
    peaceful = synthetic_chart(
        0.0, Mars=at(4, 5.0), Saturn=at(8, 20.0), Sun=at(0, 1.0), Moon=at(1, 1.0),
        Mercury=at(2, 1.0), Jupiter=at(3, 1.0), Venus=at(5, 1.0), Rahu=at(6, 1.0),
    )
    warring = synthetic_chart(
        0.0, Mars=at(4, 5.0), Saturn=at(4, 5.5), Sun=at(0, 1.0), Moon=at(1, 1.0),
        Mercury=at(2, 1.0), Jupiter=at(3, 1.0), Venus=at(5, 1.0), Rahu=at(6, 1.0),
    )
    calm = S.shadbala(peaceful)
    fought = S.shadbala(warring)
    assert all(bala.yuddha == 0.0 for bala in calm.values())
    combatants = [bala for bala in fought.values() if bala.yuddha != 0.0]
    assert len(combatants) == 2
    assert sum(bala.yuddha for bala in combatants) == pytest.approx(0.0)
    winner = max(combatants, key=lambda bala: bala.total)
    assert winner.yuddha > 0
