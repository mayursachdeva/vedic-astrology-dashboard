"""Compatibility between two charts.

Two systems, reported side by side, because they answer different questions.

**Ashtakoota** is the popular thirty-six point matching. It is *not* in the ingested
BPHS — searching the text for kuta, yoni, gana, bhakoot and nadi returns nothing. It
belongs to the muhurta literature, so every kuta here is marked unlocated. It is still
computed, because it is what people mean when they ask about matching.

**The seventh-house reading** is what this BPHS actually says about partnership
(ch. 18, Effects of Yuvati Bhava): judge the 7th, its lord, and Venus. That is located
and cited.

Where a kuta's traditional table has finer gradations than are encoded here, the kuta
says so in its `precision` field rather than presenting an approximation as exact. The
nine-nakshatra groupings for gana and nadi are exact and self-checking.
"""

from __future__ import annotations

from dataclasses import dataclass

from astro.core.ephemeris import NAKSHATRAS, SIGNS, Chart
from astro.core.facts import ChartFacts
from astro.core.strength import natural_relation, sign_lord

# --- varna: the four groups by Moon sign ------------------------------------

VARNA_BY_SIGN = {
    3: "Brahmin", 7: "Brahmin", 11: "Brahmin",      # Cancer, Scorpio, Pisces
    0: "Kshatriya", 4: "Kshatriya", 8: "Kshatriya",  # Aries, Leo, Sagittarius
    1: "Vaishya", 5: "Vaishya", 9: "Vaishya",        # Taurus, Virgo, Capricorn
    2: "Shudra", 6: "Shudra", 10: "Shudra",          # Gemini, Libra, Aquarius
}
VARNA_RANK = {"Shudra": 1, "Vaishya": 2, "Kshatriya": 3, "Brahmin": 4}

# --- vashya: the five classes ------------------------------------------------

VASHYA_SIMPLE = {
    0: "Chatushpada", 1: "Chatushpada", 2: "Manava", 3: "Jalachara",
    4: "Vanachara", 5: "Manava", 6: "Manava", 7: "Keeta",
    10: "Manava", 11: "Jalachara",
}
# Sagittarius and Capricorn are split at the midpoint of the sign.
VASHYA_SPLIT = {8: ("Manava", "Chatushpada"), 9: ("Chatushpada", "Jalachara")}

# --- yoni: the animal of each nakshatra --------------------------------------

YONI_BY_NAKSHATRA = (
    "Horse", "Elephant", "Sheep", "Serpent", "Serpent", "Dog", "Cat", "Sheep", "Cat",
    "Rat", "Rat", "Cow", "Buffalo", "Tiger", "Buffalo", "Tiger", "Deer", "Deer",
    "Dog", "Monkey", "Mongoose", "Monkey", "Lion", "Horse", "Lion", "Cow", "Elephant",
)
# The seven pairs the tradition treats as sworn enemies, scoring nothing.
YONI_ENEMIES = frozenset(
    frozenset(pair)
    for pair in (
        ("Horse", "Buffalo"), ("Elephant", "Lion"), ("Sheep", "Monkey"),
        ("Serpent", "Mongoose"), ("Dog", "Deer"), ("Cat", "Rat"), ("Cow", "Tiger"),
    )
)

# --- gana and nadi: exact nine-way groupings ---------------------------------

GANA_GROUPS = {
    "Deva": (1, 5, 7, 8, 13, 15, 17, 22, 27),
    "Manushya": (2, 4, 6, 11, 12, 20, 21, 25, 26),
    "Rakshasa": (3, 9, 10, 14, 16, 18, 19, 23, 24),
}
GANA_POINTS = {
    ("Deva", "Deva"): 6, ("Deva", "Manushya"): 6, ("Deva", "Rakshasa"): 0,
    ("Manushya", "Deva"): 5, ("Manushya", "Manushya"): 6, ("Manushya", "Rakshasa"): 0,
    ("Rakshasa", "Deva"): 1, ("Rakshasa", "Manushya"): 0, ("Rakshasa", "Rakshasa"): 6,
}

NADI_GROUPS = {
    "Adi": (1, 6, 7, 12, 13, 18, 19, 24, 25),
    "Madhya": (2, 5, 8, 11, 14, 17, 20, 23, 26),
    "Antya": (3, 4, 9, 10, 15, 16, 21, 22, 27),
}

MAX_POINTS = {
    "Varna": 1, "Vashya": 2, "Tara": 3, "Yoni": 4,
    "Graha Maitri": 5, "Gana": 6, "Bhakoot": 7, "Nadi": 8,
}
TOTAL_POINTS = sum(MAX_POINTS.values())  # 36

UNLOCATED = "Muhurta tradition — no verse located in the ingested texts"


@dataclass(frozen=True)
class Kuta:
    """One of the eight factors, with its reasoning attached."""

    name: str
    points: float
    maximum: int
    reason: str
    precision: str = "exact"  # or "simplified", when finer gradations are not encoded
    caveat: str = ""

    @property
    def fraction(self) -> float:
        return self.points / self.maximum


@dataclass(frozen=True)
class Dosha:
    name: str
    present: bool
    reason: str
    cancelled_by: str = ""


@dataclass(frozen=True)
class Match:
    total: float
    maximum: int
    kutas: tuple[Kuta, ...]
    doshas: tuple[Dosha, ...]

    @property
    def verdict(self) -> str:
        """The conventional reading of the total, which is a rough guide only."""
        if self.total >= 28:
            return "strong"
        if self.total >= 18:
            return "workable"
        return "weak"


def _group_of(index_from_one: int, groups: dict[str, tuple[int, ...]]) -> str:
    for name, members in groups.items():
        if index_from_one in members:
            return name
    raise ValueError(f"nakshatra {index_from_one} is in no group — the table is broken")


def moon_nakshatra(chart: Chart) -> int:
    """One-based nakshatra index of the Moon, which is what every kuta reads."""
    return chart.positions["Moon"].nakshatra + 1


def moon_sign(chart: Chart) -> int:
    return chart.positions["Moon"].sign


def varna_kuta(groom: Chart, bride: Chart) -> Kuta:
    groom_varna = VARNA_BY_SIGN[moon_sign(groom)]
    bride_varna = VARNA_BY_SIGN[moon_sign(bride)]
    ok = VARNA_RANK[groom_varna] >= VARNA_RANK[bride_varna]
    return Kuta(
        name="Varna",
        points=1 if ok else 0,
        maximum=1,
        reason=(
            f"{groom_varna} and {bride_varna}: "
            + ("the groom's group is not lower" if ok else "the groom's group is lower")
        ),
        caveat=(
            "This kuta ranks the partners against each other by a social ordering. It "
            "is reported because it is part of the traditional total, not because the "
            "ordering is endorsed."
        ),
    )


def _vashya_class(chart: Chart) -> str:
    sign = moon_sign(chart)
    if sign in VASHYA_SPLIT:
        first, second = VASHYA_SPLIT[sign]
        return first if chart.positions["Moon"].degree_in_sign < 15.0 else second
    return VASHYA_SIMPLE[sign]


def vashya_kuta(groom: Chart, bride: Chart) -> Kuta:
    a, b = _vashya_class(groom), _vashya_class(bride)
    if a == b:
        points = 2.0
    elif "Keeta" in (a, b) and {a, b} != {"Keeta", "Jalachara"}:
        points = 0.0
    elif {a, b} == {"Vanachara", "Chatushpada"}:
        points = 0.0
    else:
        points = 1.0
    return Kuta(
        name="Vashya",
        points=points,
        maximum=2,
        reason=f"{a} and {b}",
        precision="simplified",
        caveat=(
            "The traditional table has half-point gradations between some classes; "
            "only whole values are encoded here."
        ),
    )


def tara_kuta(groom: Chart, bride: Chart) -> Kuta:
    """Counted in both directions; each direction is worth half the points."""
    groom_star, bride_star = moon_nakshatra(groom), moon_nakshatra(bride)

    def favourable(from_star: int, to_star: int) -> bool:
        remainder = ((to_star - from_star) % 27 + 1) % 9
        return remainder not in (3, 5, 7)

    forward = favourable(bride_star, groom_star)
    backward = favourable(groom_star, bride_star)
    points = 1.5 * forward + 1.5 * backward
    return Kuta(
        name="Tara",
        points=points,
        maximum=3,
        reason=(
            f"counting between {NAKSHATRAS[bride_star - 1]} and "
            f"{NAKSHATRAS[groom_star - 1]}: "
            + ("both directions favourable" if forward and backward
               else "one direction favourable" if forward or backward
               else "neither direction favourable")
        ),
    )


def yoni_kuta(groom: Chart, bride: Chart) -> Kuta:
    a = YONI_BY_NAKSHATRA[moon_nakshatra(groom) - 1]
    b = YONI_BY_NAKSHATRA[moon_nakshatra(bride) - 1]
    if a == b:
        points, note = 4.0, "the same animal"
    elif frozenset((a, b)) in YONI_ENEMIES:
        points, note = 0.0, "a traditionally opposed pair"
    else:
        points, note = 2.0, "neither the same nor opposed"
    return Kuta(
        name="Yoni",
        points=points,
        maximum=4,
        reason=f"{a} and {b} — {note}",
        precision="simplified",
        caveat=(
            "The full table grades fourteen animals against each other on a five-point "
            "scale. Only the three values that sources agree on are encoded: 4 for the "
            "same animal, 0 for the seven opposed pairs, 2 otherwise. The intermediate "
            "1 and 3 are omitted rather than guessed."
        ),
    )


def graha_maitri_kuta(groom: Chart, bride: Chart) -> Kuta:
    groom_lord = sign_lord(moon_sign(groom))
    bride_lord = sign_lord(moon_sign(bride))
    if groom_lord == bride_lord:
        return Kuta("Graha Maitri", 5, 5, f"both Moon signs ruled by {groom_lord}")

    forward = natural_relation(groom_lord, bride_lord)
    backward = natural_relation(bride_lord, groom_lord)
    scores = {
        frozenset(("friend", "friend")): 5.0,
        frozenset(("friend", "neutral")): 4.0,
        frozenset(("neutral", "neutral")): 3.0,
        frozenset(("neutral", "enemy")): 1.0,
        frozenset(("friend", "enemy")): 0.5,
        frozenset(("enemy", "enemy")): 0.0,
    }
    points = scores.get(frozenset((forward, backward)), 0.0)
    return Kuta(
        name="Graha Maitri",
        points=points,
        maximum=5,
        reason=f"{groom_lord} sees {bride_lord} as {backward}, and is seen as {forward}",
    )


def gana_kuta(groom: Chart, bride: Chart) -> Kuta:
    a = _group_of(moon_nakshatra(groom), GANA_GROUPS)
    b = _group_of(moon_nakshatra(bride), GANA_GROUPS)
    return Kuta(
        name="Gana",
        points=GANA_POINTS[(a, b)],
        maximum=6,
        reason=f"{a} and {b}",
    )


def bhakoot_kuta(groom: Chart, bride: Chart) -> Kuta:
    groom_sign, bride_sign = moon_sign(groom), moon_sign(bride)
    forward = (bride_sign - groom_sign) % 12 + 1
    backward = (groom_sign - bride_sign) % 12 + 1
    # The classical afflicted pairs, counted inclusively in both directions. Two signs
    # five apart read as 6 and 8 from each other, four apart as 5 and 9, one apart as
    # 2 and 12 — so the pairs are {6,8}, {5,9} and {2,12}, not {6,9} or {5,10}.
    pair = {forward, backward}
    bad = pair in ({6, 8}, {5, 9}, {2, 12})
    return Kuta(
        name="Bhakoot",
        points=0 if bad else 7,
        maximum=7,
        reason=(
            f"{SIGNS[groom_sign]} and {SIGNS[bride_sign]} stand {forward} and "
            f"{backward} from each other"
            + (" — one of the afflicted pairs" if bad else "")
        ),
    )


def nadi_kuta(groom: Chart, bride: Chart) -> Kuta:
    a = _group_of(moon_nakshatra(groom), NADI_GROUPS)
    b = _group_of(moon_nakshatra(bride), NADI_GROUPS)
    same = a == b
    return Kuta(
        name="Nadi",
        points=0 if same else 8,
        maximum=8,
        reason=f"{a} and {b}" + (" — the same, which scores nothing" if same else ""),
    )


KUTA_FUNCTIONS = (
    varna_kuta, vashya_kuta, tara_kuta, yoni_kuta,
    graha_maitri_kuta, gana_kuta, bhakoot_kuta, nadi_kuta,
)


def doshas(groom: ChartFacts, bride: ChartFacts) -> tuple[Dosha, ...]:
    """The afflictions traditionally checked alongside the points, with cancellations.

    Mangal dosha is the one people ask about. The classical position is that it matters
    when one partner has it and the other does not — two afflicted charts are held to
    cancel each other.
    """
    found = []

    mars_houses = (1, 2, 4, 7, 8, 12)
    groom_mangal = groom.house_of("Mars") in mars_houses
    bride_mangal = bride.house_of("Mars") in mars_houses
    if groom_mangal or bride_mangal:
        both = groom_mangal and bride_mangal
        who = (
            "both charts"
            if both
            else "the first chart" if groom_mangal else "the second chart"
        )
        found.append(
            Dosha(
                name="Mangal dosha",
                present=not both,
                reason=f"Mars occupies one of the 1st, 2nd, 4th, 7th, 8th or 12th in {who}",
                cancelled_by=(
                    "Present in both charts, which the tradition treats as cancelling."
                    if both
                    else ""
                ),
            )
        )

    a, b = moon_nakshatra(groom.chart), moon_nakshatra(bride.chart)
    if _group_of(a, NADI_GROUPS) == _group_of(b, NADI_GROUPS):
        same_sign = moon_sign(groom.chart) == moon_sign(bride.chart)
        found.append(
            Dosha(
                name="Nadi dosha",
                present=not same_sign,
                reason="both Moons fall in the same nadi group",
                cancelled_by=(
                    "Both Moons share a sign, a commonly accepted cancellation."
                    if same_sign
                    else ""
                ),
            )
        )

    forward = (moon_sign(bride.chart) - moon_sign(groom.chart)) % 12 + 1
    backward = (moon_sign(groom.chart) - moon_sign(bride.chart)) % 12 + 1
    if {forward, backward} in ({6, 9}, {5, 10}, {2, 12}):
        friendly = natural_relation(
            sign_lord(moon_sign(groom.chart)), sign_lord(moon_sign(bride.chart))
        ) == "friend"
        found.append(
            Dosha(
                name="Bhakoot dosha",
                present=not friendly,
                reason=f"the Moon signs stand {forward} and {backward} apart",
                cancelled_by=(
                    "The lords of the two Moon signs are natural friends."
                    if friendly
                    else ""
                ),
            )
        )

    return tuple(found)


def match(groom: ChartFacts, bride: ChartFacts) -> Match:
    """The full thirty-six point comparison.

    The argument names follow the tradition's own framing. Nothing in the computation
    depends on the gender of either person; the two positions are simply not
    symmetrical in varna, tara and gana, so which chart goes first changes the result.
    """
    kutas = tuple(function(groom.chart, bride.chart) for function in KUTA_FUNCTIONS)
    return Match(
        total=sum(kuta.points for kuta in kutas),
        maximum=TOTAL_POINTS,
        kutas=kutas,
        doshas=doshas(groom, bride),
    )


def seventh_house_reading(facts: ChartFacts) -> dict:
    """What this BPHS actually says to judge for partnership: the 7th, its lord, Venus.

    Cited, unlike the kutas — ch. 18 is the Yuvati Bhava chapter and ch. 11 v. 8 gives
    the house's indications.
    """
    lord = facts.lord_of(7)
    venus = facts.condition["Venus"]
    return {
        "house": 7,
        "sign": SIGNS[facts.sign_of_house(7)],
        "occupants": list(facts.occupants(7)),
        "lord": lord,
        "lord_house": facts.lord_placed_in(7),
        "lord_dignity": facts.dignity(lord),
        "venus_house": venus.house,
        "venus_dignity": venus.dignity,
        "venus_combust": venus.combust,
        "support": facts.sav_of_house(7),
        "aspected_by": list(facts.bodies_aspecting(7)),
        "citation": "Brihat Parashara Hora Shastra, ch. 18 and ch. 11, v. 8",
    }
