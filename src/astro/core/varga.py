"""Divisional (varga) charts.

Each varga slices a 30-degree sign into equal parts and maps each part onto a sign of
the zodiac. The mapping rule differs per varga and is stated in BPHS as "count from
such-and-such sign", which reduces to a starting sign plus an offset. Expressing them
that way keeps sixteen scriptural rules in one readable table instead of sixteen
hand-written branches.

Trimsamsa (D30) is the exception: its five parts are unequal and are handled
separately, exactly as the text describes them.
"""

from __future__ import annotations

from dataclasses import dataclass

from astro.core.ephemeris import SIGNS, Chart

# Sign qualities, indexed from Aries = 0.
MOVABLE, FIXED, DUAL = 0, 1, 2
FIRE, EARTH, AIR, WATER = 0, 1, 2, 3

ARIES, TAURUS, GEMINI, CANCER, LEO, VIRGO = 0, 1, 2, 3, 4, 5
LIBRA, SCORPIO, SAGITTARIUS, CAPRICORN, AQUARIUS, PISCES = 6, 7, 8, 9, 10, 11

VARGA_NAMES = {
    1: "Rasi",
    2: "Hora",
    3: "Drekkana",
    4: "Chaturthamsa",
    7: "Saptamsa",
    9: "Navamsa",
    10: "Dasamsa",
    12: "Dwadasamsa",
    16: "Shodasamsa",
    20: "Vimsamsa",
    24: "Chaturvimsamsa",
    27: "Bhamsa",
    30: "Trimsamsa",
    40: "Khavedamsa",
    45: "Akshavedamsa",
    60: "Shashtiamsa",
}

SHODASAVARGA = tuple(VARGA_NAMES)


def quality(sign: int) -> int:
    """Movable, fixed or dual. Aries is movable and the pattern repeats every three."""
    return sign % 3


def element(sign: int) -> int:
    """Fire, earth, air or water. Aries is fire and the pattern repeats every four."""
    return sign % 4


def _by_quality(sign: int, movable: int, fixed: int, dual: int) -> int:
    return (movable, fixed, dual)[quality(sign)]


def _by_parity(sign: int, odd: int, even: int) -> int:
    """Odd signs are Aries, Gemini, Leo... which are the even indices."""
    return odd if sign % 2 == 0 else even


def _start_sign(divisor: int, sign: int) -> int:
    """The sign the varga's parts are counted from, per BPHS."""
    if divisor in (1, 12, 60):
        return sign  # counted from the sign itself
    if divisor == 3:
        return sign  # but stepping four signs per part; handled by _step
    if divisor == 4:
        return sign
    if divisor == 7:
        return sign if sign % 2 == 0 else (sign + 6) % 12  # even signs start from the 7th
    if divisor == 9:
        return _by_quality(sign, sign, (sign + 8) % 12, (sign + 4) % 12)
    if divisor == 10:
        return sign if sign % 2 == 0 else (sign + 8) % 12  # even signs start from the 9th
    if divisor == 16:
        return _by_quality(sign, ARIES, LEO, SAGITTARIUS)
    if divisor == 20:
        return _by_quality(sign, ARIES, SAGITTARIUS, LEO)
    if divisor == 24:
        return _by_parity(sign, LEO, CANCER)
    if divisor == 27:
        return (ARIES, CANCER, LIBRA, CAPRICORN)[element(sign)]
    if divisor == 40:
        return _by_parity(sign, ARIES, LIBRA)
    if divisor == 45:
        return _by_quality(sign, ARIES, LEO, SAGITTARIUS)
    raise ValueError(f"no rule for D{divisor}")


def _step(divisor: int) -> int:
    """Signs advanced per part. Only Drekkana and Chaturthamsa skip."""
    return {3: 4, 4: 3}.get(divisor, 1)


# Trimsamsa: five unequal spans per sign, each ruled by a planet and mapped to that
# planet's own sign. Odd signs run Mars, Saturn, Jupiter, Mercury, Venus; even signs
# run the same set in reverse, using each planet's other sign.
_TRIMSAMSA_ODD = (
    (5.0, "Mars", ARIES),
    (10.0, "Saturn", AQUARIUS),
    (18.0, "Jupiter", SAGITTARIUS),
    (25.0, "Mercury", GEMINI),
    (30.0, "Venus", LIBRA),
)
_TRIMSAMSA_EVEN = (
    (5.0, "Venus", TAURUS),
    (12.0, "Mercury", VIRGO),
    (20.0, "Jupiter", PISCES),
    (25.0, "Saturn", CAPRICORN),
    (30.0, "Mars", SCORPIO),
)


def hora(longitude: float) -> tuple[int, str]:
    """D2 sign and its ruler. Hora alternates between the Sun's sign and the Moon's
    rather than counting forward, so it does not fit the start-plus-offset table: an
    odd sign gives the Sun's hora first, an even sign the Moon's."""
    longitude %= 360.0
    sign = int(longitude // 30)
    second_half = (longitude % 30.0) >= 15.0
    sun_first = sign % 2 == 0
    return (LEO, "Sun") if sun_first != second_half else (CANCER, "Moon")


def trimsamsa(longitude: float) -> tuple[int, str]:
    """D30 sign and its ruling planet. Parts are unequal, so this is not a plain index."""
    longitude %= 360.0
    sign = int(longitude // 30)
    degree = longitude % 30.0
    table = _TRIMSAMSA_ODD if sign % 2 == 0 else _TRIMSAMSA_EVEN
    for upper_bound, planet, mapped_sign in table:
        if degree < upper_bound:
            return mapped_sign, planet
    return table[-1][2], table[-1][1]  # exactly 30.0 cannot occur, but stay total


def varga_sign(divisor: int, longitude: float) -> int:
    """The sign a longitude occupies in the D{divisor} chart."""
    if divisor not in VARGA_NAMES:
        raise ValueError(
            f"D{divisor} is not one of the shodasavarga: {sorted(VARGA_NAMES)}"
        )
    if divisor == 2:
        return hora(longitude)[0]
    if divisor == 30:
        return trimsamsa(longitude)[0]

    longitude %= 360.0
    sign = int(longitude // 30)
    part = int((longitude % 30.0) / (30.0 / divisor))
    # Guard the top edge: floating point can push a longitude a hair past the last part.
    part = min(part, divisor - 1)
    return (_start_sign(divisor, sign) + part * _step(divisor)) % 12


@dataclass(frozen=True)
class VargaChart:
    """A divisional chart: which sign each body falls in, and the varga lagna."""

    divisor: int
    name: str
    lagna_sign: int
    signs: dict[str, int]

    def house_of(self, body: str) -> int:
        return (self.signs[body] - self.lagna_sign) % 12 + 1

    def occupants(self, sign: int) -> tuple[str, ...]:
        return tuple(body for body, s in self.signs.items() if s == sign)

    def sign_name(self, body: str) -> str:
        return SIGNS[self.signs[body]]


def varga_chart(chart: Chart, divisor: int) -> VargaChart:
    """Project a computed chart into one of its divisional charts.

    Only signs carry over — a varga has no meaningful degrees, so nothing here pretends
    to compute them.
    """
    return VargaChart(
        divisor=divisor,
        name=VARGA_NAMES[divisor],
        lagna_sign=varga_sign(divisor, chart.ascendant),
        signs={
            body: varga_sign(divisor, position.longitude)
            for body, position in chart.positions.items()
        },
    )


# BPHS ch. 6 v. 12. Each of a sign's nine navamsas is divine, human or devilish, and
# which comes first depends on the sign's own quality: movable signs run Deva first,
# fixed signs Manushya first, dual signs Rakshasa first. The classes then repeat.
NAVAMSA_CLASSES = (
    ("Deva", "divine"), ("Manushya", "human"), ("Rakshasa", "devilish"),
)
_FIRST_CLASS = (0, 1, 2)  # movable, fixed, dual — indices into NAVAMSA_CLASSES


def navamsa_class(longitude: float) -> tuple[str, str]:
    """Whether the navamsa a body stands in is a divine, human or devilish one.

    A ninth of a sign is 3°20'. The class of the first navamsa is set by the sign's
    quality and the three then cycle, so it is arithmetic rather than a table.
    """
    sign = int(longitude % 360.0 // 30)
    ninth = int((longitude % 30.0) // (30.0 / 9.0))
    start = _FIRST_CLASS[quality(sign)]
    return NAVAMSA_CLASSES[(start + ninth) % 3]


# ch. 7 v. 1-8, which says what each division is read for, in the chapter's own words.
VARGA_PURPOSE = {
    1: "the physique", 2: "wealth", 3: "happiness through co-born",
    4: "fortunes", 7: "sons and grandsons", 9: "the spouse",
    10: "power and position", 12: "parents",
    16: "benefits and adversities through conveyances", 20: "worship",
    24: "learning", 27: "strength and weakness", 30: "evil effects",
    40: "auspicious and inauspicious effects",
    45: "all indications", 60: "all indications",
}
