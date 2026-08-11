"""Swiss Ephemeris wrapper — the only module in the project that imports swisseph.

Everything here is a pure function of its arguments: no globals, no network, no I/O
beyond the ephemeris files. Ayanamsa, house system and node convention are always
explicit parameters, never process-wide state, so two charts computed with different
settings can coexist in one process.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import swisseph as swe

# Optional: point at a directory of .se1 files for full Swiss Ephemeris precision.
# Without it pyswisseph falls back to the built-in Moshier model, accurate to well
# under an arcsecond for any plausible birth date. ponytail: not worth shipping
# 100MB of data files for precision nobody can perceive in a chart.
_EPHE_PATH = os.environ.get("ASTRO_EPHE_PATH")
if _EPHE_PATH:
    swe.set_ephe_path(_EPHE_PATH)

SIGNS = (
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
)

NAKSHATRAS = (
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta",
    "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
)

NAKSHATRA_ARC = 360.0 / 27.0
PADA_ARC = NAKSHATRA_ARC / 4.0

# Traditional seven grahas plus the two nodes. Outer planets are not Parashari.
_GRAHAS = (
    ("Sun", swe.SUN),
    ("Moon", swe.MOON),
    ("Mars", swe.MARS),
    ("Mercury", swe.MERCURY),
    ("Jupiter", swe.JUPITER),
    ("Venus", swe.VENUS),
    ("Saturn", swe.SATURN),
)

AYANAMSAS = {
    "lahiri": swe.SIDM_LAHIRI,
    "raman": swe.SIDM_RAMAN,
    "krishnamurti": swe.SIDM_KRISHNAMURTI,
    "true_chitra": swe.SIDM_TRUE_CITRA,
}

# swisseph house-system letters. Whole sign is the Parashari default.
HOUSE_SYSTEMS = {
    "whole_sign": b"W",
    "placidus": b"P",
    "equal": b"E",
    "sripati": b"O",  # Porphyry; Sripati is derived from it
}


@dataclass(frozen=True)
class Position:
    """A body's sidereal position, with the derived values every rule needs."""

    body: str
    longitude: float  # sidereal ecliptic longitude, 0-360
    latitude: float
    speed: float  # degrees per day; negative means retrograde
    retrograde: bool
    sign: int  # 0 = Aries
    sign_name: str
    degree_in_sign: float
    nakshatra: int  # 0 = Ashwini
    nakshatra_name: str
    pada: int  # 1-4


@dataclass(frozen=True)
class Chart:
    """A computed natal or transit chart. Carries the settings used to build it,
    because a set of longitudes without its ayanamsa is meaningless."""

    jd_ut: float
    latitude: float
    longitude: float
    ayanamsa: str
    ayanamsa_value: float
    node_type: str
    house_system: str
    ascendant: float
    midheaven: float
    cusps: tuple[float, ...]  # 12 house cusps, sidereal
    positions: dict[str, Position]

    @property
    def lagna_sign(self) -> int:
        return int(self.ascendant // 30)

    def house_of(self, body: str) -> int:
        """House number 1-12 containing `body`, by whole-sign counting from the lagna."""
        sign = self.positions[body].sign
        return (sign - self.lagna_sign) % 12 + 1


def julian_day(year: int, month: int, day: int, hour_ut: float) -> float:
    """Julian day (UT) from a UTC calendar date and fractional hour."""
    return swe.julday(year, month, day, hour_ut, swe.GREG_CAL)


def _describe(body: str, lon: float, lat: float, speed: float) -> Position:
    lon = lon % 360.0
    nak = int(lon // NAKSHATRA_ARC)
    return Position(
        body=body,
        longitude=lon,
        latitude=lat,
        speed=speed,
        retrograde=speed < 0,
        sign=int(lon // 30),
        sign_name=SIGNS[int(lon // 30)],
        degree_in_sign=lon % 30.0,
        nakshatra=nak,
        nakshatra_name=NAKSHATRAS[nak],
        pada=int((lon % NAKSHATRA_ARC) // PADA_ARC) + 1,
    )


def compute_chart(
    jd_ut: float,
    latitude: float,
    longitude: float,
    *,
    ayanamsa: str = "lahiri",
    house_system: str = "whole_sign",
    node_type: str = "mean",
) -> Chart:
    """Compute a sidereal chart.

    `latitude`/`longitude` are the birth place in degrees, east and north positive.
    `node_type` is "mean" or "true" — Rahu's convention differs between traditions and
    the choice moves the node by up to ~1.5 degrees, so it is recorded on the result.
    """
    if ayanamsa not in AYANAMSAS:
        raise ValueError(f"unknown ayanamsa {ayanamsa!r}; expected one of {sorted(AYANAMSAS)}")
    if house_system not in HOUSE_SYSTEMS:
        raise ValueError(
            f"unknown house system {house_system!r}; expected one of {sorted(HOUSE_SYSTEMS)}"
        )
    if node_type not in ("mean", "true"):
        raise ValueError(f"node_type must be 'mean' or 'true', got {node_type!r}")

    swe.set_sid_mode(AYANAMSAS[ayanamsa])
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL

    positions: dict[str, Position] = {}
    for name, planet_id in _GRAHAS:
        values, _ = swe.calc_ut(jd_ut, planet_id, flags)
        positions[name] = _describe(name, values[0], values[1], values[3])

    node_id = swe.MEAN_NODE if node_type == "mean" else swe.TRUE_NODE
    node_values, _ = swe.calc_ut(jd_ut, node_id, flags)
    # The nodes are always retrograde in the conventional treatment; swisseph reports
    # the true (occasionally positive) speed for the true node, so force the flag.
    rahu = _describe("Rahu", node_values[0], node_values[1], node_values[3])
    positions["Rahu"] = Position(**{**rahu.__dict__, "retrograde": True})
    ketu = _describe("Ketu", node_values[0] + 180.0, -node_values[1], node_values[3])
    positions["Ketu"] = Position(**{**ketu.__dict__, "retrograde": True})

    cusps, ascmc = swe.houses_ex(
        jd_ut, latitude, longitude, HOUSE_SYSTEMS[house_system], flags
    )

    return Chart(
        jd_ut=jd_ut,
        latitude=latitude,
        longitude=longitude,
        ayanamsa=ayanamsa,
        # get_ayanamsa_ex_ut, not get_ayanamsa_ut: the plain call omits the precession
        # correction and reads ~14" high (23d51'25" vs the published 23d51'11" for
        # Lahiri at J2000), which would silently contradict the longitudes above.
        ayanamsa_value=swe.get_ayanamsa_ex_ut(jd_ut, swe.FLG_SWIEPH)[1],
        node_type=node_type,
        house_system=house_system,
        ascendant=ascmc[0] % 360.0,
        midheaven=ascmc[1] % 360.0,
        cusps=tuple(c % 360.0 for c in cusps[:12]),
        positions=positions,
    )
