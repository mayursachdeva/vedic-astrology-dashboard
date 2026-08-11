"""Tests for ashtakavarga.

The BPHS tables are long and easy to mistype, so most of these are checksums: the
canonical per-graha totals and the 337-point SAV total. Any single wrong cell fails at
least one of them.
"""

from __future__ import annotations

import pytest

from astro.core.ashtakavarga import (
    BENEFIC_PLACES,
    CONTRIBUTORS,
    EXPECTED_SAV_TOTAL,
    EXPECTED_TOTALS,
    SUBJECTS,
    bhinnashtakavarga,
    compute,
)
from astro.core.ephemeris import compute_chart, julian_day

CHART = compute_chart(julian_day(1990, 1, 1, 6.5), 28.6139, 77.2090)


# --- the tables themselves --------------------------------------------------


@pytest.mark.parametrize("subject", SUBJECTS)
def test_each_table_totals_its_canonical_bindu_count(subject):
    total = sum(len(places) for places in BENEFIC_PLACES[subject].values())
    assert total == EXPECTED_TOTALS[subject]


def test_the_seven_tables_together_total_337():
    total = sum(
        len(places)
        for subject in SUBJECTS
        for places in BENEFIC_PLACES[subject].values()
    )
    assert total == EXPECTED_SAV_TOTAL


@pytest.mark.parametrize("subject", SUBJECTS)
def test_every_table_lists_all_eight_contributors(subject):
    assert tuple(BENEFIC_PLACES[subject]) == CONTRIBUTORS


@pytest.mark.parametrize("subject", SUBJECTS)
def test_house_numbers_are_in_range_and_never_repeated(subject):
    for contributor, places in BENEFIC_PLACES[subject].items():
        assert len(set(places)) == len(places), f"{subject} from {contributor} repeats a house"
        assert all(1 <= house <= 12 for house in places)
        assert list(places) == sorted(places), f"{subject} from {contributor} is unsorted"


# --- computation ------------------------------------------------------------


def test_bhinnashtakavarga_totals_match_the_canonical_counts():
    signs = {body: CHART.positions[body].sign for body in SUBJECTS}
    signs["Lagna"] = CHART.lagna_sign
    for subject in SUBJECTS:
        assert sum(bhinnashtakavarga(subject, signs)) == EXPECTED_TOTALS[subject]


def test_a_bindu_lands_the_correct_number_of_signs_from_its_contributor():
    """With every contributor stacked on Aries, Sun's own row (1,2,4,7,8,9,10,11) must
    put points on exactly those signs counted from Aries."""
    signs = {contributor: 0 for contributor in CONTRIBUTORS}
    counts = bhinnashtakavarga("Sun", signs)

    expected_signs = set()
    for places in BENEFIC_PLACES["Sun"].values():
        expected_signs.update(house - 1 for house in places)
    assert {sign for sign, count in enumerate(counts) if count} == expected_signs
    assert counts[0] == sum(1 for places in BENEFIC_PLACES["Sun"].values() if 1 in places)


def test_missing_contributors_are_rejected():
    with pytest.raises(ValueError, match="missing contributor"):
        bhinnashtakavarga("Sun", {"Sun": 0})


def test_unknown_subject_is_rejected():
    with pytest.raises(ValueError):
        bhinnashtakavarga("Rahu", {contributor: 0 for contributor in CONTRIBUTORS})


def test_compute_produces_a_consistent_sav_for_a_real_chart():
    varga = compute(CHART)

    assert set(varga.bhinna) == set(SUBJECTS)
    for subject in SUBJECTS:
        assert len(varga.bhinna[subject]) == 12
        assert sum(varga.bhinna[subject]) == EXPECTED_TOTALS[subject]

    assert len(varga.sarva) == 12
    assert sum(varga.sarva) == EXPECTED_SAV_TOTAL
    for sign in range(12):
        assert varga.sav(sign) == sum(
            varga.bav(subject, sign) for subject in SUBJECTS
        )


def test_no_sign_can_hold_more_bindus_than_there_are_contributors():
    varga = compute(CHART)
    for subject in SUBJECTS:
        assert all(0 <= count <= 8 for count in varga.bhinna[subject])
    assert all(0 <= count <= 56 for count in varga.sarva)


def test_sav_by_house_starts_at_the_lagna():
    varga = compute(CHART)
    by_house = varga.sav_by_house()
    assert len(by_house) == 12
    assert by_house[0] == varga.sav(CHART.lagna_sign)
    assert sum(by_house) == EXPECTED_SAV_TOTAL


def test_strongest_and_weakest_signs_are_ordered_and_disjoint_at_the_extremes():
    varga = compute(CHART)
    strongest = varga.strongest_signs(3)
    weakest = varga.weakest_signs(3)

    assert varga.sav(strongest[0]) >= varga.sav(strongest[-1])
    assert varga.sav(weakest[0]) <= varga.sav(weakest[-1])
    assert varga.sav(strongest[0]) >= varga.sav(weakest[0])


def test_rotating_the_whole_chart_rotates_the_bindus():
    """Ashtakavarga depends only on relative positions, so shifting every contributor by
    one sign must shift every result by one sign."""
    base = {contributor: 3 for contributor in CONTRIBUTORS}
    shifted = {contributor: 4 for contributor in CONTRIBUTORS}

    for subject in SUBJECTS:
        original = bhinnashtakavarga(subject, base)
        moved = bhinnashtakavarga(subject, shifted)
        assert moved == original[-1:] + original[:-1]


# --- reductions and pindas (BPHS ch. 67-69) ---------------------------------


def test_trikona_groups_are_the_four_sets_of_three_equidistant_signs():
    from astro.core.ashtakavarga import TRIKONA_GROUPS

    assert len(TRIKONA_GROUPS) == 4
    members = [sign for group in TRIKONA_GROUPS for sign in group]
    assert sorted(members) == list(range(12))
    for group in TRIKONA_GROUPS:
        assert len(group) == 3
        first, second, third = group
        assert (second - first) % 12 == 4 and (third - second) % 12 == 4


def test_trikona_shodhana_subtracts_the_smallest_of_each_trikona():
    from astro.core.ashtakavarga import trikona_shodhana

    counts = (3, 0, 0, 0, 5, 0, 0, 0, 7, 0, 0, 0)  # Aries 3, Leo 5, Sagittarius 7
    reduced = trikona_shodhana(counts)
    assert (reduced[0], reduced[4], reduced[8]) == (0, 2, 4)


def test_a_trikona_containing_a_zero_is_left_alone():
    """The verse says so explicitly, and it also follows from subtracting the minimum."""
    from astro.core.ashtakavarga import trikona_shodhana

    counts = (0, 0, 0, 0, 5, 0, 0, 0, 7, 0, 0, 0)
    reduced = trikona_shodhana(counts)
    assert (reduced[0], reduced[4], reduced[8]) == (0, 5, 7)


def test_three_equal_values_in_a_trikona_all_fall_to_zero():
    from astro.core.ashtakavarga import trikona_shodhana

    counts = (4, 0, 0, 0, 4, 0, 0, 0, 4, 0, 0, 0)
    reduced = trikona_shodhana(counts)
    assert (reduced[0], reduced[4], reduced[8]) == (0, 0, 0)


def test_trikona_shodhana_never_increases_a_count():
    from astro.core.ashtakavarga import trikona_shodhana

    original = compute(CHART).bhinna["Sun"]
    reduced = trikona_shodhana(original)
    assert all(after <= before for after, before in zip(reduced, original))
    assert all(value >= 0 for value in reduced)


def test_ekadhipatya_leaves_the_luminaries_signs_untouched():
    """The Sun and Moon own one sign each, so Cancer and Leo are never reduced."""
    from astro.core.ashtakavarga import ekadhipatya_shodhana

    counts = tuple(range(1, 13))
    reduced = ekadhipatya_shodhana(counts, frozenset())
    assert reduced[3] == counts[3]  # Cancer
    assert reduced[4] == counts[4]  # Leo


def test_ekadhipatya_is_skipped_when_either_owned_sign_is_empty_of_points():
    from astro.core.ashtakavarga import ekadhipatya_shodhana

    counts = [0] * 12
    counts[0], counts[7] = 0, 6  # Mars owns Aries and Scorpio
    reduced = ekadhipatya_shodhana(tuple(counts), frozenset())
    assert (reduced[0], reduced[7]) == (0, 6)


def test_two_empty_signs_with_different_counts_both_take_the_smaller():
    from astro.core.ashtakavarga import ekadhipatya_shodhana

    counts = [0] * 12
    counts[0], counts[7] = 5, 3
    reduced = ekadhipatya_shodhana(tuple(counts), frozenset())
    assert (reduced[0], reduced[7]) == (3, 3)


def test_two_empty_signs_with_equal_counts_both_fall_to_zero():
    from astro.core.ashtakavarga import ekadhipatya_shodhana

    counts = [0] * 12
    counts[0], counts[7] = 4, 4
    reduced = ekadhipatya_shodhana(tuple(counts), frozenset())
    assert (reduced[0], reduced[7]) == (0, 0)


def test_two_occupied_signs_are_left_alone():
    from astro.core.ashtakavarga import ekadhipatya_shodhana

    counts = [0] * 12
    counts[0], counts[7] = 5, 3
    reduced = ekadhipatya_shodhana(tuple(counts), frozenset({0, 7}))
    assert (reduced[0], reduced[7]) == (5, 3)


def test_an_occupied_sign_reduces_its_empty_partner_and_is_itself_unchanged():
    """The occupied sign keeps its number; the empty one is reduced by it, which comes
    to zero whenever the occupied value is the larger."""
    from astro.core.ashtakavarga import ekadhipatya_shodhana

    counts = [0] * 12
    counts[0], counts[7] = 2, 6  # Aries occupied with the smaller count
    reduced = ekadhipatya_shodhana(tuple(counts), frozenset({0}))
    assert (reduced[0], reduced[7]) == (2, 4)

    counts[0], counts[7] = 6, 2  # Aries occupied with the larger count
    reduced = ekadhipatya_shodhana(tuple(counts), frozenset({0}))
    assert (reduced[0], reduced[7]) == (6, 0)


def test_the_multiplier_tables_are_complete():
    from astro.core.ashtakavarga import GRAHA_MULTIPLIERS, RASI_MULTIPLIERS

    assert len(RASI_MULTIPLIERS) == 12
    assert all(1 <= value <= 12 for value in RASI_MULTIPLIERS)
    assert set(GRAHA_MULTIPLIERS) == set(SUBJECTS)


def test_the_prose_and_table_disagreement_in_the_verse_is_declared():
    """Ch. 69 v. 1-4 states the multipliers twice and the two do not match. The table
    is used because it agrees with every other authority; the prose reading is recorded
    so nobody 'corrects' the code back to it without noticing."""
    from astro.core.ashtakavarga import (
        GRAHA_MULTIPLIERS,
        MULTIPLIER_VARIANTS,
        RASI_MULTIPLIERS,
    )

    assert MULTIPLIER_VARIANTS["Capricorn"] == (5, 6)
    assert RASI_MULTIPLIERS[9] == 5
    assert MULTIPLIER_VARIANTS["Mars"] == (8, 3)
    assert GRAHA_MULTIPLIERS["Mars"] == 8
    for name, (used, prose) in MULTIPLIER_VARIANTS.items():
        assert used != prose
        if name in GRAHA_MULTIPLIERS:
            assert GRAHA_MULTIPLIERS[name] == used


def test_pinda_is_the_two_sums_added():
    from astro.core.ashtakavarga import RASI_MULTIPLIERS, sodhya_pinda

    counts = tuple([1] * 12)
    result = sodhya_pinda(counts, {})
    assert result["rasi_pinda"] == sum(RASI_MULTIPLIERS)
    assert result["graha_pinda"] == 0
    assert result["sodhya_pinda"] == result["rasi_pinda"]


def test_a_graha_in_a_sign_adds_its_own_multiplier():
    from astro.core.ashtakavarga import GRAHA_MULTIPLIERS, sodhya_pinda

    counts = [0] * 12
    counts[0] = 3
    plain = sodhya_pinda(tuple(counts), {})
    with_jupiter = sodhya_pinda(tuple(counts), {0: ("Jupiter",)})
    assert with_jupiter["graha_pinda"] == 3 * GRAHA_MULTIPLIERS["Jupiter"]
    assert with_jupiter["sodhya_pinda"] > plain["sodhya_pinda"]


def test_reductions_only_ever_lower_the_totals_for_a_real_chart():
    from astro.core.ashtakavarga import reduced_ashtakavarga

    result = reduced_ashtakavarga(CHART)
    assert set(result) == set(SUBJECTS)
    for subject, values in result.items():
        assert sum(values["reduced"]) <= sum(values["after_trikona"]) <= sum(values["before"])
        assert sum(values["before"]) == EXPECTED_TOTALS[subject]
        assert all(value >= 0 for value in values["reduced"])
        assert values["sodhya_pinda"] == values["rasi_pinda"] + values["graha_pinda"]
