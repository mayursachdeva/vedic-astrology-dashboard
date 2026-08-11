"""Vimshottari dasha.

The Moon's position at birth fixes the whole 120-year sequence: the nakshatra it
occupies names the ruling planet, and how far through that nakshatra it has travelled
gives the unexpired balance of the first period. Everything below follows from those
two numbers by proportion, so this module is pure arithmetic with no ephemeris calls.
"""

from __future__ import annotations

from dataclasses import dataclass

from astro.core.ephemeris import NAKSHATRA_ARC

# The fixed order and lengths. They total 120 years, which is the cycle length.
DASHA_SEQUENCE: tuple[tuple[str, int], ...] = (
    ("Ketu", 7),
    ("Venus", 20),
    ("Sun", 6),
    ("Moon", 10),
    ("Mars", 7),
    ("Rahu", 18),
    ("Jupiter", 16),
    ("Saturn", 19),
    ("Mercury", 17),
)

CYCLE_YEARS = sum(years for _, years in DASHA_SEQUENCE)  # 120

DASHA_YEARS = dict(DASHA_SEQUENCE)
_LORD_ORDER = [lord for lord, _ in DASHA_SEQUENCE]

# A dasha year is a Julian year of 365.25 days. Some traditions use a 360-day savana
# year instead, which shifts long-range period boundaries by years, so it is exposed as
# a parameter rather than hard-coded into the arithmetic.
JULIAN_YEAR_DAYS = 365.25
SAVANA_YEAR_DAYS = 360.0

LEVEL_NAMES = {
    1: "mahadasha",
    2: "antardasha",
    3: "pratyantardasha",
    4: "sookshma",
    5: "prana",
}


@dataclass(frozen=True)
class DashaPeriod:
    """One period in the tree. Times are Julian Days (UT) so they compose directly with
    the ephemeris; format them for display at the edge, not here."""

    lord: str
    level: int  # 1 = mahadasha, 2 = antardasha, 3 = pratyantardasha
    start_jd: float
    end_jd: float
    children: tuple["DashaPeriod", ...] = ()

    @property
    def level_name(self) -> str:
        return LEVEL_NAMES.get(self.level, f"level {self.level}")

    @property
    def duration_days(self) -> float:
        return self.end_jd - self.start_jd

    def contains(self, jd: float) -> bool:
        return self.start_jd <= jd < self.end_jd


def nakshatra_lord(nakshatra_index: int) -> str:
    """Ruling planet of a nakshatra. The nine lords repeat three times over the 27."""
    return _LORD_ORDER[nakshatra_index % 9]


def _lords_from(lord: str) -> list[str]:
    """The nine lords in sequence, starting at `lord` and wrapping."""
    start = _LORD_ORDER.index(lord)
    return _LORD_ORDER[start:] + _LORD_ORDER[:start]


def _subdivide(
    lord: str, level: int, start_jd: float, span_days: float, max_level: int
) -> tuple[DashaPeriod, ...]:
    """Split a period into sub-periods.

    Each sub-period takes the same share of its parent as its lord's years take of the
    120-year cycle, and the sequence starts with the parent's own lord.
    """
    if level > max_level:
        return ()

    periods: list[DashaPeriod] = []
    cursor = start_jd
    for sub_lord in _lords_from(lord):
        sub_span = span_days * DASHA_YEARS[sub_lord] / CYCLE_YEARS
        periods.append(
            DashaPeriod(
                lord=sub_lord,
                level=level,
                start_jd=cursor,
                end_jd=cursor + sub_span,
                children=_subdivide(sub_lord, level + 1, cursor, sub_span, max_level),
            )
        )
        cursor += sub_span
    return tuple(periods)


def vimshottari(
    moon_longitude: float,
    birth_jd: float,
    *,
    depth: int = 3,
    year_days: float = JULIAN_YEAR_DAYS,
) -> tuple[DashaPeriod, ...]:
    """The full mahadasha sequence from birth, each subdivided to `depth` levels.

    The first mahadasha is truncated to its unexpired balance: if the Moon is 40% of the
    way through its nakshatra at birth, 40% of that lord's period has already run.
    Returns one full 120-year cycle measured from the notional start of the first
    period, so the last entry ends 120 years after that point, not after birth.
    """
    if depth < 1:
        raise ValueError(f"depth must be at least 1, got {depth}")

    longitude = moon_longitude % 360.0
    index = int(longitude // NAKSHATRA_ARC)
    fraction_elapsed = (longitude % NAKSHATRA_ARC) / NAKSHATRA_ARC

    first_lord = nakshatra_lord(index)
    first_span = DASHA_YEARS[first_lord] * year_days
    # Wind back to where this mahadasha notionally began, so sub-periods of the first
    # dasha divide the whole period correctly rather than only its remaining tail.
    notional_start = birth_jd - fraction_elapsed * first_span

    periods: list[DashaPeriod] = []
    cursor = notional_start
    for lord in _lords_from(first_lord):
        span = DASHA_YEARS[lord] * year_days
        periods.append(
            DashaPeriod(
                lord=lord,
                level=1,
                start_jd=cursor,
                end_jd=cursor + span,
                children=_subdivide(lord, 2, cursor, span, depth),
            )
        )
        cursor += span
    return tuple(periods)


def balance_at_birth(
    moon_longitude: float, *, year_days: float = JULIAN_YEAR_DAYS
) -> tuple[str, float]:
    """Ruling lord at birth and the unexpired years of its mahadasha."""
    longitude = moon_longitude % 360.0
    index = int(longitude // NAKSHATRA_ARC)
    lord = nakshatra_lord(index)
    remaining_fraction = 1.0 - (longitude % NAKSHATRA_ARC) / NAKSHATRA_ARC
    return lord, DASHA_YEARS[lord] * remaining_fraction


def chain_at(periods: tuple[DashaPeriod, ...], jd: float) -> tuple[DashaPeriod, ...]:
    """The nested periods active at `jd`, outermost first.

    Returns an empty tuple if `jd` falls outside the computed range — the caller should
    treat that as "beyond the cycle", not as an error.
    """
    chain: list[DashaPeriod] = []
    current = periods
    while current:
        for period in current:
            if period.contains(jd):
                chain.append(period)
                current = period.children
                break
        else:
            break
    return tuple(chain)
