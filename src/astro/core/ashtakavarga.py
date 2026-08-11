"""Ashtakavarga.

Each of the seven grahas is scored by eight contributors — the seven grahas and the
lagna. A contributor grants a benefic point (bindu) to certain houses counted from its
own position. Collecting those points per sign gives that graha's Bhinnashtakavarga
(BAV); adding the seven BAVs sign by sign gives the Sarvashtakavarga (SAV).

The tables below are the standard BPHS ones. They are self-checking: each graha's BAV
must total a fixed number (Sun 48, Moon 49, Mars 39, Mercury 54, Jupiter 56, Venus 52,
Saturn 39) and the SAV must total 337. A transcription slip in any single cell breaks
one of those totals, and the tests assert all of them.
"""

from __future__ import annotations

from dataclasses import dataclass

CONTRIBUTORS = (
    "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Lagna",
)
SUBJECTS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")

# BENEFIC_PLACES[subject][contributor] = houses, counted from the contributor, in which
# the subject receives a bindu.
BENEFIC_PLACES: dict[str, dict[str, tuple[int, ...]]] = {
    "Sun": {
        "Sun": (1, 2, 4, 7, 8, 9, 10, 11),
        "Moon": (3, 6, 10, 11),
        "Mars": (1, 2, 4, 7, 8, 9, 10, 11),
        "Mercury": (3, 5, 6, 9, 10, 11, 12),
        "Jupiter": (5, 6, 9, 11),
        "Venus": (6, 7, 12),
        "Saturn": (1, 2, 4, 7, 8, 9, 10, 11),
        "Lagna": (3, 4, 6, 10, 11, 12),
    },
    "Moon": {
        "Sun": (3, 6, 7, 8, 10, 11),
        "Moon": (1, 3, 6, 7, 10, 11),
        "Mars": (2, 3, 5, 6, 9, 10, 11),
        "Mercury": (1, 3, 4, 5, 7, 8, 10, 11),
        "Jupiter": (1, 4, 7, 8, 10, 11, 12),
        "Venus": (3, 4, 5, 7, 9, 10, 11),
        "Saturn": (3, 5, 6, 11),
        "Lagna": (3, 6, 10, 11),
    },
    "Mars": {
        "Sun": (3, 5, 6, 10, 11),
        "Moon": (3, 6, 11),
        "Mars": (1, 2, 4, 7, 8, 10, 11),
        "Mercury": (3, 5, 6, 11),
        "Jupiter": (6, 10, 11, 12),
        "Venus": (6, 8, 11, 12),
        "Saturn": (1, 4, 7, 8, 9, 10, 11),
        "Lagna": (1, 3, 6, 10, 11),
    },
    "Mercury": {
        "Sun": (5, 6, 9, 11, 12),
        "Moon": (2, 4, 6, 8, 10, 11),
        "Mars": (1, 2, 4, 7, 8, 9, 10, 11),
        "Mercury": (1, 3, 5, 6, 9, 10, 11, 12),
        "Jupiter": (6, 8, 11, 12),
        "Venus": (1, 2, 3, 4, 5, 8, 9, 11),
        "Saturn": (1, 2, 4, 7, 8, 9, 10, 11),
        "Lagna": (1, 2, 4, 6, 8, 10, 11),
    },
    "Jupiter": {
        "Sun": (1, 2, 3, 4, 7, 8, 9, 10, 11),
        "Moon": (2, 5, 7, 9, 11),
        "Mars": (1, 2, 4, 7, 8, 10, 11),
        "Mercury": (1, 2, 4, 5, 6, 9, 10, 11),
        "Jupiter": (1, 2, 3, 4, 7, 8, 10, 11),
        "Venus": (2, 5, 6, 9, 10, 11),
        "Saturn": (3, 5, 6, 12),
        "Lagna": (1, 2, 4, 5, 6, 7, 9, 10, 11),
    },
    "Venus": {
        "Sun": (8, 11, 12),
        "Moon": (1, 2, 3, 4, 5, 8, 9, 11, 12),
        # 3, 4, 6 — see KNOWN_VARIANTS: VedAstro reads 3, 5, 6 here. The cited text
        # supports 4, so that is what is used. Do not "fix" this without reading
        # ch. 66 v. 56-58 first.
        "Mars": (3, 4, 6, 9, 11, 12),
        "Mercury": (3, 5, 6, 9, 11),
        "Jupiter": (5, 8, 9, 10, 11),
        "Venus": (1, 2, 3, 4, 5, 8, 9, 10, 11),
        "Saturn": (3, 4, 5, 8, 9, 10, 11),
        "Lagna": (1, 2, 3, 4, 5, 8, 9, 11),
    },
    "Saturn": {
        "Sun": (1, 2, 4, 7, 8, 10, 11),
        "Moon": (3, 6, 11),
        "Mars": (3, 5, 6, 10, 11, 12),
        "Mercury": (6, 8, 9, 10, 11, 12),
        "Jupiter": (5, 6, 11, 12),
        "Venus": (6, 11, 12),
        "Saturn": (3, 5, 6, 11),
        "Lagna": (1, 3, 4, 6, 10, 11),
    },
}

# Where authorities disagree.
#
# The tables above are the standard published ones. Two other sources were checked cell
# by cell — the English BPHS in corpus_md/ (ch. 66, v. 43-68, which states the tables
# house by house) and VedAstro. Both agree with the tables above almost everywhere. The
# exceptions are listed here so that a future reader diffing against either source finds
# a decision rather than an apparent bug, and so nothing gets silently "corrected".
#
# Every entry is (subject, contributor): (what this file uses, what the other source has).
KNOWN_VARIANTS = {
    "vedastro": {
        # VedAstro places this bindu one house further on. The cited text supports 4,
        # and two independent readings of it agree, so 4 stands.
        ("Venus", "Mars"): ((3, 4, 6, 9, 11, 12), (3, 5, 6, 9, 11, 12)),
    },
    "bphs_english_edition": {
        # These four cells differ from the English edition in corpus_md/. In each case
        # VedAstro agrees with the table above, so the edition is treated as the outlier.
        ("Moon", "Moon"): ((1, 3, 6, 7, 10, 11), (1, 3, 6, 7, 9, 10, 11)),
        ("Moon", "Mars"): ((2, 3, 5, 6, 9, 10, 11), (2, 3, 5, 6, 10, 11)),
        ("Moon", "Jupiter"): ((1, 4, 7, 8, 10, 11, 12), (1, 2, 4, 7, 8, 10, 11)),
        ("Mercury", "Sun"): ((5, 6, 9, 11, 12), (6, 9, 11, 12)),
        ("Mercury", "Saturn"): (
            (1, 2, 4, 7, 8, 9, 10, 11),
            (1, 2, 4, 5, 7, 8, 9, 10, 11),
        ),
        # The edition also drops Jupiter from the 1st and 4th of its own varga, which
        # makes its Jupiter table total 54 where every authority requires 56. That is an
        # arithmetic error in the edition, not a variant reading.
        ("Jupiter", "Jupiter"): ((1, 2, 3, 4, 7, 8, 10, 11), (2, 3, 7, 8, 10, 11)),
    },
}

# The canonical BAV totals. These are the checksum on the table above.
EXPECTED_TOTALS = {
    "Sun": 48, "Moon": 49, "Mars": 39, "Mercury": 54,
    "Jupiter": 56, "Venus": 52, "Saturn": 39,
}
EXPECTED_SAV_TOTAL = 337

# Interpretation thresholds in common use: a sign with 30 or more bindus in the SAV is
# read as well supported, 25 or fewer as poorly supported. Kept here so the rule layer
# and the UI agree on one definition.
SAV_STRONG = 30
SAV_WEAK = 25


@dataclass(frozen=True)
class Ashtakavarga:
    """Bindu counts by sign, indexed 0 = Aries."""

    bhinna: dict[str, tuple[int, ...]]  # per graha, 12 signs
    sarva: tuple[int, ...]  # 12 signs
    lagna_sign: int

    def bav(self, body: str, sign: int) -> int:
        return self.bhinna[body][sign % 12]

    def sav(self, sign: int) -> int:
        return self.sarva[sign % 12]

    def sav_by_house(self) -> tuple[int, ...]:
        """SAV read as houses 1-12 from the lagna rather than as signs."""
        return tuple(self.sarva[(self.lagna_sign + offset) % 12] for offset in range(12))

    def strongest_signs(self, count: int = 3) -> tuple[int, ...]:
        order = sorted(range(12), key=lambda sign: (-self.sarva[sign], sign))
        return tuple(order[:count])

    def weakest_signs(self, count: int = 3) -> tuple[int, ...]:
        order = sorted(range(12), key=lambda sign: (self.sarva[sign], sign))
        return tuple(order[:count])


def bhinnashtakavarga(subject: str, contributor_signs: dict[str, int]) -> tuple[int, ...]:
    """Bindus for one graha across the twelve signs.

    `contributor_signs` maps each of the eight contributors, including "Lagna", to the
    sign it occupies.
    """
    if subject not in BENEFIC_PLACES:
        raise ValueError(f"no ashtakavarga table for {subject!r}; expected one of {SUBJECTS}")
    missing = set(CONTRIBUTORS) - set(contributor_signs)
    if missing:
        raise ValueError(f"missing contributor positions: {sorted(missing)}")

    counts = [0] * 12
    for contributor, places in BENEFIC_PLACES[subject].items():
        base = contributor_signs[contributor] % 12
        for house in places:
            counts[(base + house - 1) % 12] += 1
    return tuple(counts)


def compute(chart) -> Ashtakavarga:
    """Full ashtakavarga for a computed chart.

    Reductions (trikona and ekadhipatya sodhana) are not applied. They matter only for
    shodhya pinda work, which nothing here uses yet, and applying them silently would
    change every number a reader might check against another program.
    """
    contributor_signs = {body: chart.positions[body].sign for body in SUBJECTS}
    contributor_signs["Lagna"] = chart.lagna_sign

    bhinna = {
        subject: bhinnashtakavarga(subject, contributor_signs) for subject in SUBJECTS
    }
    sarva = tuple(
        sum(bhinna[subject][sign] for subject in SUBJECTS) for sign in range(12)
    )
    return Ashtakavarga(bhinna=bhinna, sarva=sarva, lagna_sign=chart.lagna_sign)


# --- reductions: trikona and ekadhipatya sodhana, and the pindas --------------
#
# BPHS ch. 67, 68 and 69. These were deliberately left out of the first pass because
# nothing used them; they are needed for shodhya pinda and for the ashtakavarga
# longevity and transit work in ch. 70.
#
# The multiplier tables below come from ch. 69 v. 1-4, which states them twice — once in
# prose and once in a parenthetical table — and the two disagree. Where they do, the
# table is used, because it matches every other authority checked and the prose does
# not. Both readings are recorded in MULTIPLIER_VARIANTS so the disagreement is visible
# rather than silently resolved.

TRIKONA_GROUPS = ((0, 4, 8), (1, 5, 9), (2, 6, 10), (3, 7, 11))

# Signs each graha owns. The luminaries own one apiece, which is why ch. 68 exempts them.
OWNED_SIGN_PAIRS = {
    "Mars": (0, 7),
    "Venus": (1, 6),
    "Mercury": (2, 5),
    "Jupiter": (8, 11),
    "Saturn": (9, 10),
}

# Rasimana — the multiplier for each sign, Aries first.
RASI_MULTIPLIERS = (7, 10, 8, 4, 10, 6, 7, 8, 9, 5, 11, 12)

# Grahamana — the multiplier for each graha.
GRAHA_MULTIPLIERS = {
    "Sun": 5, "Moon": 5, "Mars": 8, "Mercury": 5,
    "Jupiter": 10, "Venus": 7, "Saturn": 5,
}

MULTIPLIER_VARIANTS = {
    # (what is used, what the prose of the same verse says)
    "Capricorn": (5, 6),
    "Mars": (8, 3),
    "Mercury": (5, 6),
    "Sun": (5, 6),
    "Moon": (5, 6),
    "Saturn": (5, 6),
}


def trikona_shodhana(counts: tuple[int, ...]) -> tuple[int, ...]:
    """BPHS ch. 67 v. 1-5.

    The twelve signs form four trikonas of three. Within each, the smallest value is
    subtracted from all three. The verse's two special cases both follow from that: if
    any of the three has no rekha nothing changes, and if all three are equal they all
    become zero.
    """
    if len(counts) != 12:
        raise ValueError(f"expected 12 signs, got {len(counts)}")
    reduced = list(counts)
    for group in TRIKONA_GROUPS:
        smallest = min(counts[sign] for sign in group)
        for sign in group:
            reduced[sign] = counts[sign] - smallest
    return tuple(reduced)


def ekadhipatya_shodhana(
    counts: tuple[int, ...], occupied: frozenset[int]
) -> tuple[int, ...]:
    """BPHS ch. 68 v. 1-5, applied to the trikona-reduced figures.

    Handles the two signs owned by one graha. `occupied` is the set of signs holding a
    graha. Cancer and Leo are never touched, since the Sun and Moon own one sign each.
    """
    if len(counts) != 12:
        raise ValueError(f"expected 12 signs, got {len(counts)}")
    reduced = list(counts)

    for first, second in OWNED_SIGN_PAIRS.values():
        a, b = reduced[first], reduced[second]
        # "not to be done if one Rasi has got a number and the other is bereft of any"
        if a == 0 or b == 0:
            continue

        first_has, second_has = first in occupied, second in occupied
        if first_has and second_has:
            continue  # "if both the Rasis are with Grahas, no Shodhana is to be done"

        if not first_has and not second_has:
            # Different values: both take the smaller. Equal: both fall to zero.
            reduced[first] = reduced[second] = 0 if a == b else min(a, b)
            continue

        # One occupied, one not. The occupied sign is never changed; the empty one is
        # reduced by it, which is zero when the occupied value is the larger.
        if first_has:
            reduced[second] = max(0, b - a)
        else:
            reduced[first] = max(0, a - b)

    return tuple(reduced)


def reduce_counts(counts: tuple[int, ...], occupied: frozenset[int]) -> tuple[int, ...]:
    """Both reductions in the order the text gives them."""
    return ekadhipatya_shodhana(trikona_shodhana(counts), occupied)


def sodhya_pinda(
    counts: tuple[int, ...], occupants: dict[int, tuple[str, ...]]
) -> dict:
    """BPHS ch. 69 v. 1-4, from already-reduced figures.

    Each sign's reduced count is multiplied by that sign's measure, and again by the
    measure of any graha standing in it. The two sums are the rasi pinda and the graha
    pinda; together they are the sodhya pinda.
    """
    rasi = sum(counts[sign] * RASI_MULTIPLIERS[sign] for sign in range(12))
    graha = sum(
        counts[sign] * GRAHA_MULTIPLIERS[body]
        for sign, bodies in occupants.items()
        for body in bodies
        if body in GRAHA_MULTIPLIERS
    )
    return {"rasi_pinda": rasi, "graha_pinda": graha, "sodhya_pinda": rasi + graha}


def reduced_ashtakavarga(chart) -> dict:
    """Every graha's bhinnashtakavarga after both reductions, with its pindas."""
    base = compute(chart)
    occupants: dict[int, list[str]] = {}
    for body in SUBJECTS:
        occupants.setdefault(chart.positions[body].sign, []).append(body)
    occupied = frozenset(occupants)
    frozen = {sign: tuple(bodies) for sign, bodies in occupants.items()}

    result = {}
    for subject in SUBJECTS:
        reduced = reduce_counts(base.bhinna[subject], occupied)
        result[subject] = {
            "before": base.bhinna[subject],
            "after_trikona": trikona_shodhana(base.bhinna[subject]),
            "reduced": reduced,
            **sodhya_pinda(reduced, frozen),
        }
    return result
