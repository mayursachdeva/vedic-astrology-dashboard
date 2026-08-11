"""Cross-checks against an independent implementation.

The BPHS tables and the yoga rules are long enough that a checksum is not proof — a
wrong cell that keeps a row's length passes every internal test. The fix is to diff
against a second implementation that was written from the texts independently.

The reference values below were taken from VedAstro (github.com/VedAstro/VedAstro, MIT)
for one synthetic chart and are frozen here as literals. That keeps the test offline
and deterministic: it does not call any service, and no birth data leaves the machine.

Re-deriving them requires the `vedastro` package, which is a REST client to
vedastro.org — do not point it at a family member's birth data. Self-host their Docker
image if the reference set ever needs regenerating from real charts.
"""

from __future__ import annotations

import pytest

from astro.core.ashtakavarga import compute as compute_ashtakavarga
from astro.core.dasha import chain_at, vimshottari
from astro.core.ephemeris import compute_chart, julian_day
from astro.core.varga import varga_sign

# 1 January 1990, 12:00 IST, New Delhi (28.6139 N, 77.2090 E), Lahiri ayanamsa.
# A made-up date used purely as a reference chart.
REFERENCE_JD = julian_day(1990, 1, 1, 6.5)
REFERENCE_PLACE = (28.6139, 77.2090)
CHART = compute_chart(REFERENCE_JD, *REFERENCE_PLACE)

# VedAstro's sidereal longitudes for that moment.
VEDASTRO_LONGITUDES = {
    "Sun": 256.8597222222222,
    "Moon": 306.46527777777777,
    "Mars": 226.11805555555554,
    "Mercury": 272.01444444444445,
    "Jupiter": 71.4588888888889,
    "Venus": 282.52972222222223,
    "Saturn": 261.90972222222223,
    "Rahu": 294.7263888888889,
    "Ketu": 114.72638888888889,
}

# Bhinnashtakavarga rows by sign, Aries first.
VEDASTRO_BAV = {
    "Sun": (2, 3, 6, 5, 4, 4, 4, 4, 7, 3, 3, 3),
    "Moon": (6, 6, 2, 5, 4, 4, 4, 3, 4, 4, 3, 4),
    "Mars": (3, 5, 4, 2, 4, 3, 2, 4, 5, 1, 2, 4),
}

# Venus is the one row where the two implementations disagree, because VedAstro reads
# Venus-from-Mars as 3, 5, 6 where the cited text reads 3, 4, 6. See KNOWN_VARIANTS.
# For this chart Mars sits in Scorpio, so the single bindu lands in Aquarius here and
# in Pisces there — and nowhere else in the row.
VEDASTRO_VENUS = (6, 4, 3, 4, 2, 5, 7, 4, 1, 5, 4, 7)
AQUARIUS, PISCES = 10, 11

# Sarvashtakavarga as VedAstro reports it: by house, starting at the lagna (Pisces for
# this chart), not by sign starting at Aries. Their per-planet rows are sign-indexed and
# their SAV row is house-indexed, which is an easy thing to transcribe wrongly.
VEDASTRO_SAV_BY_HOUSE = (30, 29, 31, 30, 24, 27, 30, 30, 29, 32, 25, 20)


def test_longitudes_agree_to_within_an_arcsecond():
    for body, expected in VEDASTRO_LONGITUDES.items():
        difference = abs(CHART.positions[body].longitude - expected) * 3600.0
        assert difference < 1.0, f"{body} differs by {difference:.2f} arcsec"


def test_lagna_agrees_to_within_ten_arcseconds():
    """VedAstro reports the ascendant as Pisces 13 deg 55' 27".

    A looser tolerance than the planets: ascendant algorithms differ slightly in how
    they handle the obliquity term, and ten arcseconds is under half a second of birth
    time, which no birth record is accurate to anyway.
    """
    expected = 11 * 30.0 + 13 + 55 / 60.0 + 27 / 3600.0
    assert abs(CHART.ascendant - expected) * 3600.0 < 10.0


def test_navamsa_of_the_sun_agrees():
    """VedAstro puts the Sun's navamsa in Virgo."""
    assert varga_sign(9, CHART.positions["Sun"].longitude) == 5


def test_dasha_chain_at_birth_agrees_to_three_levels():
    """VedAstro reports Mars mahadasha, Moon bhukti, Venus antaram at birth."""
    periods = vimshottari(CHART.positions["Moon"].longitude, REFERENCE_JD, depth=3)
    chain = chain_at(periods, REFERENCE_JD)
    assert [period.lord for period in chain] == ["Mars", "Moon", "Venus"]


@pytest.mark.parametrize("body", sorted(VEDASTRO_BAV))
def test_bhinnashtakavarga_rows_agree(body):
    computed = compute_ashtakavarga(CHART).bhinna[body]
    assert computed == VEDASTRO_BAV[body]


def test_venus_differs_from_vedastro_in_exactly_one_place():
    """The disagreement is real, understood, and confined to two signs.

    This is deliberately not an equality assertion. Diffing the two implementations
    surfaced the Venus-from-Mars cell; reading BPHS ch. 66 v. 56-58 settled it in favour
    of the text. What matters now is that the difference does not spread: if a future
    change makes any other sign diverge, this fails.
    """
    ours = compute_ashtakavarga(CHART).bhinna["Venus"]

    for sign in range(12):
        if sign in (AQUARIUS, PISCES):
            continue
        assert ours[sign] == VEDASTRO_VENUS[sign], f"new divergence at sign {sign}"

    assert (ours[AQUARIUS], ours[PISCES]) == (5, 6)
    assert (VEDASTRO_VENUS[AQUARIUS], VEDASTRO_VENUS[PISCES]) == (4, 7)
    assert sum(ours) == sum(VEDASTRO_VENUS) == 52  # the bindu moves, it is not lost


def test_sarvashtakavarga_matches_vedastro_apart_from_that_one_bindu():
    ours = compute_ashtakavarga(CHART).sav_by_house()
    assert sum(ours) == sum(VEDASTRO_SAV_BY_HOUSE) == 337

    differences = {
        house: (ours[house], VEDASTRO_SAV_BY_HOUSE[house])
        for house in range(12)
        if ours[house] != VEDASTRO_SAV_BY_HOUSE[house]
    }
    # Pisces is house 1 and Aquarius house 12 for this lagna.
    assert differences == {0: (29, 30), 11: (21, 20)}


def test_the_two_indexings_are_consistent():
    """Guard against the transcription trap above: reading a house-indexed row as if it
    were sign-indexed silently rotates every value."""
    varga = compute_ashtakavarga(CHART)
    lagna = CHART.lagna_sign
    for house in range(12):
        assert varga.sav_by_house()[house] == varga.sarva[(lagna + house) % 12]
