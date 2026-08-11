"""Tests for compatibility.

The kuta tables are long, so most of these are checksums — the nine-way nakshatra
groupings, the 36-point total, the bounds on each factor. The rest pin the asymmetries
that make this system easy to implement wrongly.
"""

from __future__ import annotations

import pytest

from astro.core.ephemeris import NAKSHATRAS, compute_chart, julian_day
from astro.core.facts import build_facts
from astro.core.synastry import (
    GANA_GROUPS,
    MAX_POINTS,
    NADI_GROUPS,
    TOTAL_POINTS,
    VARNA_BY_SIGN,
    YONI_BY_NAKSHATRA,
    YONI_ENEMIES,
    Kuta,
    match,
    moon_nakshatra,
    seventh_house_reading,
)
from conftest import synthetic_chart

FIRST = build_facts(compute_chart(julian_day(1990, 1, 1, 6.5), 28.6139, 77.2090))
SECOND = build_facts(compute_chart(julian_day(1992, 6, 15, 4.0), 19.0760, 72.8777))


def at(sign: int, degree: float = 10.0) -> float:
    return sign * 30.0 + degree


def chart_with_moon(longitude: float):
    return build_facts(synthetic_chart(at(0), Moon=longitude))


# --- the tables --------------------------------------------------------------


def test_the_eight_factors_total_thirty_six():
    assert TOTAL_POINTS == 36
    assert sorted(MAX_POINTS.values()) == [1, 2, 3, 4, 5, 6, 7, 8]


def test_every_sign_has_a_varna():
    assert set(VARNA_BY_SIGN) == set(range(12))
    counts: dict[str, int] = {}
    for varna in VARNA_BY_SIGN.values():
        counts[varna] = counts.get(varna, 0) + 1
    assert set(counts.values()) == {3}, "each varna should cover exactly three signs"


def test_gana_and_nadi_split_the_twenty_seven_nakshatras_into_three_nines():
    for groups in (GANA_GROUPS, NADI_GROUPS):
        members = [n for group in groups.values() for n in group]
        assert len(members) == 27
        assert sorted(members) == list(range(1, 28))
        assert all(len(group) == 9 for group in groups.values())


def test_every_nakshatra_has_a_yoni_animal():
    assert len(YONI_BY_NAKSHATRA) == 27
    assert len(set(YONI_BY_NAKSHATRA)) == 14


def test_the_opposed_yoni_pairs_are_seven_distinct_pairs():
    assert len(YONI_ENEMIES) == 7
    for pair in YONI_ENEMIES:
        assert len(pair) == 2
        assert all(animal in YONI_BY_NAKSHATRA for animal in pair)


# --- scoring bounds ----------------------------------------------------------


def test_no_factor_can_exceed_its_maximum_or_go_negative():
    result = match(FIRST, SECOND)
    assert len(result.kutas) == 8
    for kuta in result.kutas:
        assert 0 <= kuta.points <= kuta.maximum
        assert kuta.maximum == MAX_POINTS[kuta.name]
        assert kuta.reason.strip()


def test_the_total_is_the_sum_of_the_factors():
    result = match(FIRST, SECOND)
    assert result.total == sum(kuta.points for kuta in result.kutas)
    assert result.maximum == 36


def test_a_chart_matched_against_itself_scores_the_maximum_except_where_it_cannot():
    """Same Moon means same everything, so only the factors that penalise sameness —
    nadi, and bhakoot's 1/1 which is not an afflicted pair — should differ."""
    result = match(FIRST, FIRST)
    by_name = {kuta.name: kuta for kuta in result.kutas}

    assert by_name["Varna"].points == 1
    assert by_name["Yoni"].points == 4
    assert by_name["Gana"].points == 6
    assert by_name["Graha Maitri"].points == 5
    assert by_name["Nadi"].points == 0, "identical nadi must score nothing"


def test_verdict_bands_follow_the_total():
    for total, expected in ((30, "strong"), (20, "workable"), (10, "weak")):
        fake = Kuta(name="Varna", points=0, maximum=1, reason="x")
        from astro.core.synastry import Match

        assert Match(total=total, maximum=36, kutas=(fake,), doshas=()).verdict == expected


# --- the asymmetries ---------------------------------------------------------


def test_the_comparison_is_not_symmetric():
    """Varna, tara and gana all read the two positions differently, so swapping the
    charts can change the total. Pinning this stops someone 'simplifying' it away."""
    forward = match(FIRST, SECOND)
    backward = match(SECOND, FIRST)
    assert forward.total != backward.total or any(
        a.points != b.points for a, b in zip(forward.kutas, backward.kutas)
    )


def test_varna_scores_on_the_ordering_and_says_it_is_only_reported():
    high = chart_with_moon(at(3))  # Cancer, Brahmin
    low = chart_with_moon(at(2))  # Gemini, Shudra
    from astro.core.synastry import varna_kuta

    assert varna_kuta(high.chart, low.chart).points == 1
    assert varna_kuta(low.chart, high.chart).points == 0
    assert "not because the ordering is endorsed" in varna_kuta(
        high.chart, low.chart
    ).caveat


def test_nadi_scores_nothing_for_the_same_group_and_everything_otherwise():
    from astro.core.synastry import nadi_kuta

    adi = chart_with_moon(0.0)  # Ashwini, Adi
    also_adi = chart_with_moon((6 - 1) * (360 / 27) + 1.0)  # Ardra, Adi
    madhya = chart_with_moon((2 - 1) * (360 / 27) + 1.0)  # Bharani, Madhya

    assert nadi_kuta(adi.chart, also_adi.chart).points == 0
    assert nadi_kuta(adi.chart, madhya.chart).points == 8


def test_bhakoot_penalises_the_classical_pairs_only():
    from astro.core.synastry import bhakoot_kuta

    base = chart_with_moon(at(0))  # Aries
    # offset -> expected points. Counted inclusively, an offset of 1 gives the 2/12
    # pair, 4 gives 5/9 and 5 gives 6/8 — all afflicted. Everything else scores full.
    expectations = {0: 7, 1: 0, 2: 7, 3: 7, 4: 0, 5: 0, 6: 7, 7: 0, 8: 0, 9: 7, 10: 7, 11: 0}
    for offset, expected in expectations.items():
        other = chart_with_moon(at((0 + offset) % 12))
        assert bhakoot_kuta(base.chart, other.chart).points == expected, (
            f"offset {offset}: {bhakoot_kuta(base.chart, other.chart).reason}"
        )


# --- honesty about precision -------------------------------------------------


def test_simplified_factors_declare_themselves():
    result = match(FIRST, SECOND)
    simplified = [kuta for kuta in result.kutas if kuta.precision == "simplified"]
    assert {kuta.name for kuta in simplified} == {"Vashya", "Yoni"}
    for kuta in simplified:
        assert kuta.caveat.strip(), f"{kuta.name} is simplified but says nothing about it"


def test_the_yoni_caveat_admits_which_values_are_missing():
    from astro.core.synastry import yoni_kuta

    caveat = yoni_kuta(FIRST.chart, SECOND.chart).caveat
    assert "1 and 3 are omitted" in caveat


# --- doshas ------------------------------------------------------------------


def test_mangal_dosha_in_both_charts_is_reported_as_cancelled():
    afflicted = build_facts(synthetic_chart(at(0), Mars=at(0, 5.0)))  # Mars in the 1st
    result = match(afflicted, afflicted)
    mangal = next(d for d in result.doshas if d.name == "Mangal dosha")
    assert mangal.present is False
    assert "cancelling" in mangal.cancelled_by


def test_mangal_dosha_in_one_chart_only_is_reported_as_present():
    afflicted = build_facts(synthetic_chart(at(0), Mars=at(0, 5.0)))
    clear = build_facts(synthetic_chart(at(0), Mars=at(2, 5.0)))  # Mars in the 3rd
    result = match(afflicted, clear)
    mangal = next(d for d in result.doshas if d.name == "Mangal dosha")
    assert mangal.present is True


def test_every_dosha_gives_a_reason():
    for pair in ((FIRST, SECOND), (SECOND, FIRST), (FIRST, FIRST)):
        for dosha in match(*pair).doshas:
            assert dosha.reason.strip()
            if not dosha.present:
                assert dosha.cancelled_by.strip()


# --- the located alternative -------------------------------------------------


def test_the_seventh_house_reading_is_cited_where_the_kutas_are_not():
    reading = seventh_house_reading(FIRST)
    assert "ch. 18" in reading["citation"]
    assert reading["lord"]
    assert 1 <= reading["lord_house"] <= 12
    assert isinstance(reading["support"], int)


def test_moon_nakshatra_is_one_based_to_match_the_tables():
    for facts in (FIRST, SECOND):
        index = moon_nakshatra(facts.chart)
        assert 1 <= index <= 27
        assert NAKSHATRAS[index - 1] == facts.chart.positions["Moon"].nakshatra_name
