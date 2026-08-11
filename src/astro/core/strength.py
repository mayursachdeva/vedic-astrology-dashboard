"""Planetary condition: lordship, dignity, friendship, combustion and aspects.

These are the qualities the yoga rules read. Everything is derived from a computed
`Chart` and nothing here touches the ephemeris, so a rule can be tested against a
hand-built chart.

Scope note: this is dignity and relationship, not shadbala. The six-fold strength
calculation is a larger piece of machinery and no rule written so far needs a numeric
shadbala score, so it is deliberately absent rather than half-implemented.
"""

from __future__ import annotations

from dataclasses import dataclass

from astro.core.ephemeris import SIGNS, Chart

GRAHAS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu")
# The nodes own no sign and cast no ownership-based judgement, so several tables below
# cover only the seven physical grahas.
SEVEN = GRAHAS[:7]

SIGN_LORDS = (
    "Mars",     # Aries
    "Venus",    # Taurus
    "Mercury",  # Gemini
    "Moon",     # Cancer
    "Sun",      # Leo
    "Mercury",  # Virgo
    "Venus",    # Libra
    "Mars",     # Scorpio
    "Jupiter",  # Sagittarius
    "Saturn",   # Capricorn
    "Saturn",   # Aquarius
    "Jupiter",  # Pisces
)

# Exaltation sign and the exact degree of deepest exaltation. Debilitation is the
# opposite point, so it is derived rather than listed twice.
EXALTATION = {
    "Sun": (0, 10.0),      # Aries 10
    "Moon": (1, 3.0),      # Taurus 3
    "Mars": (9, 28.0),     # Capricorn 28
    "Mercury": (5, 15.0),  # Virgo 15
    "Jupiter": (3, 5.0),   # Cancer 5
    "Venus": (11, 27.0),   # Pisces 27
    "Saturn": (6, 20.0),   # Libra 20
}

# The nodes' exaltation is not agreed between texts; BPHS does not assign one. Left out
# on purpose so no rule can quietly depend on a contested value.

# Moolatrikona: sign plus the degree range within it.
MOOLATRIKONA = {
    "Sun": (4, 0.0, 20.0),      # Leo 0-20
    "Moon": (1, 4.0, 30.0),     # Taurus 4-30
    "Mars": (0, 0.0, 12.0),     # Aries 0-12
    "Mercury": (5, 16.0, 20.0),  # Virgo 16-20
    "Jupiter": (8, 0.0, 10.0),  # Sagittarius 0-10
    "Venus": (6, 0.0, 15.0),    # Libra 0-15
    "Saturn": (10, 0.0, 20.0),  # Aquarius 0-20
}

# Naisargika (natural) friendship, from BPHS. Anything not listed is neutral.
NATURAL_FRIENDS = {
    "Sun": {"Moon", "Mars", "Jupiter"},
    "Moon": {"Sun", "Mercury"},
    "Mars": {"Sun", "Moon", "Jupiter"},
    "Mercury": {"Sun", "Venus"},
    "Jupiter": {"Sun", "Moon", "Mars"},
    "Venus": {"Mercury", "Saturn"},
    "Saturn": {"Mercury", "Venus"},
}

NATURAL_ENEMIES = {
    "Sun": {"Venus", "Saturn"},
    "Moon": set(),
    "Mars": {"Mercury"},
    "Mercury": {"Moon"},
    "Jupiter": {"Mercury", "Venus"},
    "Venus": {"Sun", "Moon"},
    "Saturn": {"Sun", "Moon", "Mars"},
}

# Combustion (astangata) orbs in degrees of longitude from the Sun. Mercury and Venus
# take a tighter orb when retrograde.
COMBUSTION_ORBS = {
    "Moon": (12.0, 12.0),
    "Mars": (17.0, 17.0),
    "Mercury": (14.0, 12.0),
    "Jupiter": (11.0, 11.0),
    "Venus": (10.0, 8.0),
    "Saturn": (15.0, 15.0),
}

# Special aspects in addition to the seventh house, which every graha aspects.
SPECIAL_ASPECTS = {
    "Mars": (4, 8),
    "Jupiter": (5, 9),
    "Saturn": (3, 10),
    # Several traditions give the nodes the same aspects as Jupiter. Included because
    # BPHS-derived yoga rules commonly assume it; drop from this table to disable.
    "Rahu": (5, 9),
    "Ketu": (5, 9),
}

# Directional strength: the house where each graha is at its strongest.
DIG_BALA_HOUSE = {
    "Jupiter": 1, "Mercury": 1,
    "Moon": 4, "Venus": 4,
    "Saturn": 7,
    "Sun": 10, "Mars": 10,
}

KENDRAS = (1, 4, 7, 10)
TRIKONAS = (1, 5, 9)
DUSTHANAS = (6, 8, 12)
UPACHAYAS = (3, 6, 10, 11)

# Dignity ranked from best to worst, so rules can compare rather than enumerate.
DIGNITY_ORDER = (
    "debilitated",
    "great_enemy",
    "enemy",
    "neutral",
    "friend",
    "great_friend",
    "own",
    "moolatrikona",
    "exalted",
)


def sign_lord(sign: int) -> str:
    return SIGN_LORDS[sign % 12]


def debilitation_sign(body: str) -> int:
    """The sign opposite the exaltation sign."""
    return (EXALTATION[body][0] + 6) % 12


def is_own_sign(body: str, sign: int) -> bool:
    return body in SEVEN and sign_lord(sign) == body


def in_moolatrikona(body: str, longitude: float) -> bool:
    if body not in MOOLATRIKONA:
        return False
    sign, low, high = MOOLATRIKONA[body]
    return int(longitude // 30) == sign and low <= longitude % 30.0 < high


def temporal_relation(house_distance: int) -> str:
    """Tatkalika friendship: grahas in the 2nd, 3rd, 4th, 10th, 11th and 12th from each
    other are temporary friends; the rest are temporary enemies."""
    return "friend" if house_distance in (2, 3, 4, 10, 11, 12) else "enemy"


def natural_relation(body: str, other: str) -> str:
    if body == other:
        return "own"
    if other in NATURAL_FRIENDS.get(body, ()):
        return "friend"
    if other in NATURAL_ENEMIES.get(body, ()):
        return "enemy"
    return "neutral"


def compound_relation(natural: str, temporal: str) -> str:
    """Panchadha maitri: natural and temporal relations combined into five grades."""
    table = {
        ("friend", "friend"): "great_friend",
        ("friend", "enemy"): "neutral",
        ("neutral", "friend"): "friend",
        ("neutral", "enemy"): "enemy",
        ("enemy", "friend"): "neutral",
        ("enemy", "enemy"): "great_enemy",
    }
    return table.get((natural, temporal), natural)


@dataclass(frozen=True)
class Condition:
    """How a single graha stands in a chart."""

    body: str
    sign: int
    house: int
    dignity: str
    retrograde: bool
    combust: bool
    combustion_orb: float | None
    in_planetary_war: bool
    has_dig_bala: bool
    aspects_houses: tuple[int, ...]
    aspects_bodies: tuple[str, ...]
    owns_houses: tuple[int, ...]
    is_benefic: bool

    @property
    def dignity_rank(self) -> int:
        return DIGNITY_ORDER.index(self.dignity)

    @property
    def is_strong(self) -> bool:
        return self.dignity in ("exalted", "moolatrikona", "own", "great_friend")

    @property
    def is_weak(self) -> bool:
        return self.dignity in ("debilitated", "great_enemy", "enemy") or self.combust


def elongation_from_sun(chart: Chart, body: str) -> float:
    """Angular distance from the Sun, 0 to 180 degrees."""
    difference = chart.positions[body].longitude - chart.positions["Sun"].longitude
    return abs((difference + 180.0) % 360.0 - 180.0)


def is_waxing(chart: Chart) -> bool:
    """True during the bright fortnight, when the Moon is ahead of the Sun."""
    difference = (
        chart.positions["Moon"].longitude - chart.positions["Sun"].longitude
    ) % 360.0
    return difference < 180.0


def moon_is_benefic(chart: Chart) -> bool:
    """BPHS treats the Moon as benefic while it is bright — from the eighth tithi of the
    waxing fortnight to the eighth of the waning one, an elongation of 72 to 288
    degrees. A dark Moon is counted among the malefics."""
    difference = (
        chart.positions["Moon"].longitude - chart.positions["Sun"].longitude
    ) % 360.0
    return 72.0 <= difference <= 288.0


def is_combust(chart: Chart, body: str) -> tuple[bool, float | None]:
    """Whether a graha is burnt by proximity to the Sun, and by what margin."""
    if body not in COMBUSTION_ORBS:
        return False, None
    direct_orb, retrograde_orb = COMBUSTION_ORBS[body]
    orb = retrograde_orb if chart.positions[body].retrograde else direct_orb
    distance = elongation_from_sun(chart, body)
    return distance < orb, distance


def dignity_of(chart: Chart, body: str) -> str:
    """The graha's standing in the sign it occupies."""
    position = chart.positions[body]
    sign = position.sign

    if body in EXALTATION:
        if sign == EXALTATION[body][0]:
            return "exalted"
        if sign == debilitation_sign(body):
            return "debilitated"
    if in_moolatrikona(body, position.longitude):
        return "moolatrikona"
    if is_own_sign(body, sign):
        return "own"
    if body not in SEVEN:
        # The nodes own nothing, so they take the dignity of their dispositor's
        # relationship rather than a sign-based one. Neutral is the honest default.
        return "neutral"

    lord = sign_lord(sign)
    if lord == body:
        return "own"
    natural = natural_relation(body, lord)
    distance = (chart.positions[lord].sign - position.sign) % 12 + 1
    return compound_relation(natural, temporal_relation(distance))


def aspected_houses(body: str, house: int) -> tuple[int, ...]:
    """Houses a graha aspects, counting from the house it occupies."""
    offsets = (7,) + SPECIAL_ASPECTS.get(body, ())
    return tuple(sorted((house + offset - 1 - 1) % 12 + 1 for offset in offsets))


def is_natural_benefic(chart: Chart, body: str) -> bool:
    """Jupiter and Venus always; the Moon while bright; Mercury unless it keeps malefic
    company. The Sun, Mars, Saturn and the nodes are malefic by nature."""
    if body in ("Jupiter", "Venus"):
        return True
    if body == "Moon":
        return moon_is_benefic(chart)
    if body == "Mercury":
        companions = [
            other
            for other in GRAHAS
            if other != "Mercury"
            and chart.positions[other].sign == chart.positions["Mercury"].sign
        ]
        return not any(
            other in ("Sun", "Mars", "Saturn", "Rahu", "Ketu")
            or (other == "Moon" and not moon_is_benefic(chart))
            for other in companions
        )
    return False


def planetary_war(chart: Chart, body: str, orb: float = 1.0) -> bool:
    """Two grahas within one degree are at war. The luminaries and the nodes do not
    take part."""
    if body in ("Sun", "Moon", "Rahu", "Ketu"):
        return False
    for other in SEVEN:
        if other == body or other in ("Sun", "Moon"):
            continue
        separation = abs(
            (chart.positions[body].longitude - chart.positions[other].longitude + 180.0)
            % 360.0
            - 180.0
        )
        if separation < orb:
            return True
    return False


def owned_houses(chart: Chart, body: str) -> tuple[int, ...]:
    """Which houses a graha rules, counted from the lagna."""
    if body not in SEVEN:
        return ()
    return tuple(
        (sign - chart.lagna_sign) % 12 + 1
        for sign in range(12)
        if sign_lord(sign) == body
    )


def condition_of(chart: Chart, body: str) -> Condition:
    position = chart.positions[body]
    house = chart.house_of(body)
    combust, orb = is_combust(chart, body)
    houses = aspected_houses(body, house)
    return Condition(
        body=body,
        sign=position.sign,
        house=house,
        dignity=dignity_of(chart, body),
        retrograde=position.retrograde,
        combust=combust,
        combustion_orb=orb,
        in_planetary_war=planetary_war(chart, body),
        has_dig_bala=DIG_BALA_HOUSE.get(body) == house,
        aspects_houses=houses,
        aspects_bodies=tuple(
            other
            for other in GRAHAS
            if other != body and chart.house_of(other) in houses
        ),
        owns_houses=owned_houses(chart, body),
        is_benefic=is_natural_benefic(chart, body),
    )


def conditions(chart: Chart) -> dict[str, Condition]:
    return {body: condition_of(chart, body) for body in GRAHAS}


def yogakaraka(chart: Chart) -> tuple[str, ...]:
    """Grahas ruling both a kendra and a trikona from the lagna.

    For a given lagna this is at most one graha, and it is treated as the single most
    helpful planet in the chart. The first house counts as both, so its lord is
    excluded — otherwise every lagna lord would qualify trivially.
    """
    result = []
    for body in SEVEN:
        houses = set(owned_houses(chart, body))
        if houses & set(KENDRAS) - {1} and houses & set(TRIKONAS) - {1}:
            result.append(body)
    return tuple(result)


def sign_name(sign: int) -> str:
    return SIGNS[sign % 12]
