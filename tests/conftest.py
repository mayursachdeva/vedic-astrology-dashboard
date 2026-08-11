"""Shared test helpers.

`synthetic_chart` builds a chart from chosen longitudes instead of a birth time. Yoga
rules need charts that contain a specific configuration, and searching real birth data
for one is slow and fragile; placing the grahas directly states the intent of each test
in one line.
"""

from __future__ import annotations

import pytest

from astro.core.ephemeris import Chart, _describe

GRAHAS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu")


def synthetic_chart(
    ascendant: float = 0.0,
    *,
    retrograde: tuple[str, ...] = (),
    **longitudes: float,
) -> Chart:
    """A chart with the given longitudes.

    Ketu is placed opposite Rahu automatically unless given explicitly, since a chart
    with the nodes anywhere else is not a chart.

    Grahas you do not place are parked together in the lagna's sign. That is convenient
    but not neutral: it can create a conjunction, a debilitation, or a dispositor in a
    kendra that fires the very rule under test. When a fixture depends on nothing else
    being true, place every graha explicitly.
    """
    unknown = set(longitudes) - set(GRAHAS)
    if unknown:
        raise ValueError(f"not grahas: {sorted(unknown)}")

    placements = dict(longitudes)
    if "Rahu" in placements and "Ketu" not in placements:
        placements["Ketu"] = (placements["Rahu"] + 180.0) % 360.0

    # Anything unplaced goes to a distinct degree of the sign the lagna occupies, far
    # enough apart that no accidental conjunction or war is created.
    filler = iter(range(len(GRAHAS)))
    positions = {}
    for body in GRAHAS:
        longitude = placements.get(body)
        if longitude is None:
            longitude = (ascendant + 0.5 + next(filler) * 2.0) % 360.0
        speed = -1.0 if body in retrograde or body in ("Rahu", "Ketu") else 1.0
        positions[body] = _describe(body, longitude, 0.0, speed)

    lagna_sign = int(ascendant % 360.0 // 30)
    return Chart(
        jd_ut=2447893.0,
        latitude=28.6139,
        longitude=77.2090,
        ayanamsa="lahiri",
        ayanamsa_value=23.7,
        node_type="mean",
        house_system="whole_sign",
        ascendant=ascendant % 360.0,
        midheaven=(ascendant + 270.0) % 360.0,
        cusps=tuple(((lagna_sign + offset) % 12) * 30.0 for offset in range(12)),
        positions=positions,
    )


@pytest.fixture()
def chart_factory():
    return synthetic_chart
