"""ChartFacts — the contract between computation and interpretation.

Rules read this and nothing else. They never call the ephemeris, never see a Julian
Day, and never recompute a dignity. That keeps a rule to a statement about a chart's
shape, which is what the scriptures actually say, and lets a rule be tested against a
chart built by hand in one line.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from astro.core.ashtakavarga import Ashtakavarga
from astro.core.ashtakavarga import compute as compute_ashtakavarga
from astro.core.ephemeris import SIGNS, Chart
from astro.core.strength import (
    DUSTHANAS,
    GRAHAS,
    KENDRAS,
    SEVEN,
    TRIKONAS,
    UPACHAYAS,
    Condition,
    conditions,
    is_waxing,
    sign_lord,
    yogakaraka,
)
from astro.core.varga import varga_chart

MALEFIC_BY_NATURE = ("Sun", "Mars", "Saturn", "Rahu", "Ketu")


@dataclass(frozen=True)
class ChartFacts:
    """A chart flattened into the shapes rules ask about."""

    chart: Chart
    lagna_sign: int
    lagna_lord: str
    condition: dict[str, Condition]
    ashtakavarga: Ashtakavarga
    benefics: frozenset[str]
    malefics: frozenset[str]
    yogakarakas: tuple[str, ...]
    moon_waxing: bool
    _occupants: dict[int, tuple[str, ...]] = field(repr=False, default_factory=dict)
    _navamsa_sign: dict[str, int] = field(repr=False, default_factory=dict)

    # --- placement ----------------------------------------------------------

    def house_of(self, body: str) -> int:
        return self.condition[body].house

    def sign_of(self, body: str) -> int:
        return self.condition[body].sign

    def occupants(self, house: int) -> tuple[str, ...]:
        return self._occupants.get(house, ())

    def is_empty(self, house: int) -> bool:
        return not self.occupants(house)

    def sign_of_house(self, house: int) -> int:
        return (self.lagna_sign + house - 1) % 12

    def house_of_sign(self, sign: int) -> int:
        return (sign - self.lagna_sign) % 12 + 1

    # --- lordship -----------------------------------------------------------

    def lord_of(self, house: int) -> str:
        return sign_lord(self.sign_of_house(house))

    def lord_placed_in(self, house: int) -> int:
        """Which house the lord of `house` occupies."""
        return self.house_of(self.lord_of(house))

    def houses_owned_by(self, body: str) -> tuple[int, ...]:
        return self.condition[body].owns_houses

    # --- relationships between placements -----------------------------------

    def distance(self, body: str, from_body: str) -> int:
        """House distance counting from `from_body`, inclusive, so 1 means conjunct."""
        return (self.sign_of(body) - self.sign_of(from_body)) % 12 + 1

    def conjunct(self, first: str, second: str) -> bool:
        return self.sign_of(first) == self.sign_of(second)

    def aspects_body(self, body: str, target: str) -> bool:
        return target in self.condition[body].aspects_bodies

    def aspects_house(self, body: str, house: int) -> bool:
        return house in self.condition[body].aspects_houses

    def bodies_aspecting(self, house: int) -> tuple[str, ...]:
        return tuple(
            body for body in GRAHAS if house in self.condition[body].aspects_houses
        )

    # --- qualities ----------------------------------------------------------

    def dignity(self, body: str) -> str:
        return self.condition[body].dignity

    def is_benefic(self, body: str) -> bool:
        return body in self.benefics

    def navamsa_sign(self, body: str) -> int:
        return self._navamsa_sign[body]

    def is_vargottama(self, body: str) -> bool:
        """Same sign in the rasi and the navamsa — a mark of stability and strength."""
        return self.sign_of(body) == self.navamsa_sign(body)

    # --- ashtakavarga -------------------------------------------------------

    def sav_of_house(self, house: int) -> int:
        return self.ashtakavarga.sav(self.sign_of_house(house))

    def bav_of(self, body: str, house: int) -> int:
        return self.ashtakavarga.bav(body, self.sign_of_house(house))

    # --- named house groups -------------------------------------------------

    def in_kendra(self, body: str) -> bool:
        return self.house_of(body) in KENDRAS

    def in_trikona(self, body: str) -> bool:
        return self.house_of(body) in TRIKONAS

    def in_dusthana(self, body: str) -> bool:
        return self.house_of(body) in DUSTHANAS

    def in_upachaya(self, body: str) -> bool:
        return self.house_of(body) in UPACHAYAS

    def kendra_from(self, body: str, other: str) -> bool:
        return self.distance(body, other) in KENDRAS

    # --- display ------------------------------------------------------------

    def sign_name(self, sign: int) -> str:
        return SIGNS[sign % 12]

    def describe(self, body: str) -> str:
        condition = self.condition[body]
        parts = [
            f"{body} in {SIGNS[condition.sign]}",
            f"house {condition.house}",
            condition.dignity,
        ]
        if condition.retrograde and body not in ("Rahu", "Ketu"):
            parts.append("retrograde")
        if condition.combust:
            parts.append("combust")
        return ", ".join(parts)


def build_facts(chart: Chart) -> ChartFacts:
    condition = conditions(chart)
    navamsa = varga_chart(chart, 9)

    occupants: dict[int, list[str]] = {house: [] for house in range(1, 13)}
    for body in GRAHAS:
        occupants[condition[body].house].append(body)

    benefics = frozenset(body for body in GRAHAS if condition[body].is_benefic)

    return ChartFacts(
        chart=chart,
        lagna_sign=chart.lagna_sign,
        lagna_lord=sign_lord(chart.lagna_sign),
        condition=condition,
        ashtakavarga=compute_ashtakavarga(chart),
        benefics=benefics,
        malefics=frozenset(GRAHAS) - benefics,
        yogakarakas=yogakaraka(chart),
        moon_waxing=is_waxing(chart),
        _occupants={house: tuple(bodies) for house, bodies in occupants.items()},
        _navamsa_sign=dict(navamsa.signs),
    )


__all__ = ["ChartFacts", "build_facts", "GRAHAS", "SEVEN", "MALEFIC_BY_NATURE"]
