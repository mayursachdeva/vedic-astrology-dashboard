"""Transits (gochara).

Two questions matter: where the grahas are now relative to the birth chart, and when
that changes. Both are computed from the ephemeris; nothing here is estimated.

On which transit doctrine to use — BPHS states one directly, in ch. 66 v. 70-72 and
ch. 70 v. 19-27: a graha transiting a sign that carries a bindu in its own
ashtakavarga gives favourable results, and an unfavourable one where the sign is
dot-marked. That is computable from tables already verified against the text, so it is
the primary signal here. The better-known Moon-gochara table with its vedha
obstructions is not in this text — it belongs to Brihat Samhita and Phaladeepika — so
it is offered alongside, clearly marked as coming from elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass

from astro.core.ashtakavarga import Ashtakavarga
from astro.core.ephemeris import SIGNS, Chart, compute_chart
from astro.core.strength import GRAHAS, SEVEN

# A graha transiting a sign holding this many bindus or more in its own ashtakavarga is
# read as well supported. Four of eight is the usual dividing line.
FAVOURABLE_BINDUS = 4

# Houses counted from the natal Moon in which each transiting graha is traditionally
# said to give good results. Not from BPHS — see the module docstring.
GOCHARA_GOOD_HOUSES = {
    "Sun": (3, 6, 10, 11),
    "Moon": (1, 3, 6, 7, 10, 11),
    "Mars": (3, 6, 11),
    "Mercury": (2, 4, 6, 8, 10, 11),
    "Jupiter": (2, 5, 7, 9, 11),
    "Venus": (1, 2, 3, 4, 5, 8, 9, 11, 12),
    "Saturn": (3, 6, 11),
    "Rahu": (3, 6, 10, 11),
    "Ketu": (3, 6, 10, 11),
}

# Saturn's passage through the 12th, 1st and 2nd from the natal Moon.
SADE_SATI_HOUSES = (12, 1, 2)
SADE_SATI_PHASE = {12: "rising", 1: "peak", 2: "setting"}

# Sign changes are found by scanning then bisecting. The step only has to be shorter
# than the fastest stay in a sign; the Moon crosses one in about two and a quarter days.
_SCAN_STEP_DAYS = {"Moon": 0.25, "Sun": 2.0, "Mercury": 2.0, "Venus": 2.0}
_DEFAULT_SCAN_STEP = 5.0
_BISECT_ROUNDS = 40


@dataclass(frozen=True)
class Gochara:
    """One graha's transit standing, by both doctrines, with the numbers behind them."""

    body: str
    sign: int
    degree_in_sign: float
    retrograde: bool
    house_from_moon: int
    house_from_lagna: int
    bindus: int  # the graha's own ashtakavarga score for the sign it is crossing
    supported: bool  # the BPHS ashtakavarga reading
    traditionally_good: bool  # the Moon-gochara table

    @property
    def sign_name(self) -> str:
        return SIGNS[self.sign]

    @property
    def agrees(self) -> bool:
        """Whether the two doctrines point the same way. When they do not, the report
        should say so rather than pick one silently."""
        return self.supported == self.traditionally_good


@dataclass(frozen=True)
class Contact:
    """A transiting graha meeting a natal point."""

    transiting: str
    natal_point: str  # a graha name, or "Lagna"
    kind: str  # "conjunction" or "aspect"
    separation: float  # degrees, for a conjunction; zero for a whole-sign aspect
    natal_house: int


@dataclass(frozen=True)
class Window:
    """A dated span: a sign transit, a retrograde loop, a combustion, a sade sati leg."""

    body: str
    kind: str
    start_jd: float
    end_jd: float
    label: str
    detail: str = ""

    @property
    def days(self) -> float:
        return self.end_jd - self.start_jd


def transit_chart(natal: Chart, jd: float) -> Chart:
    """Positions at `jd`, computed with the natal chart's own settings.

    Reusing the ayanamsa and node convention matters: comparing a Lahiri natal chart
    against a Raman transit would silently shift everything by a degree.
    """
    return compute_chart(
        jd,
        natal.latitude,
        natal.longitude,
        ayanamsa=natal.ayanamsa,
        house_system=natal.house_system,
        node_type=natal.node_type,
    )


def gochara(natal: Chart, ashtakavarga: Ashtakavarga, jd: float) -> dict[str, Gochara]:
    """Every graha's transit standing against a natal chart."""
    moving = transit_chart(natal, jd)
    moon_sign = natal.positions["Moon"].sign

    result: dict[str, Gochara] = {}
    for body in GRAHAS:
        position = moving.positions[body]
        # The nodes have no ashtakavarga of their own, so the bindu reading does not
        # apply to them; they fall back to the traditional table alone.
        bindus = ashtakavarga.bav(body, position.sign) if body in SEVEN else 0
        house_from_moon = (position.sign - moon_sign) % 12 + 1
        result[body] = Gochara(
            body=body,
            sign=position.sign,
            degree_in_sign=position.degree_in_sign,
            retrograde=position.retrograde,
            house_from_moon=house_from_moon,
            house_from_lagna=(position.sign - natal.lagna_sign) % 12 + 1,
            bindus=bindus,
            supported=bindus >= FAVOURABLE_BINDUS if body in SEVEN else False,
            traditionally_good=house_from_moon in GOCHARA_GOOD_HOUSES[body],
        )
    return result


def contacts(natal: Chart, jd: float, *, orb: float = 3.0) -> list[Contact]:
    """Transiting grahas conjunct or aspecting natal points.

    Conjunctions use a degree orb, since an exact one is a real event with a date.
    Aspects use whole-sign graha drishti, which is how the classical texts count them —
    a planet aspects a house, not a degree.
    """
    from astro.core.strength import aspected_houses

    moving = transit_chart(natal, jd)
    natal_points = {body: natal.positions[body].longitude for body in GRAHAS}
    natal_points["Lagna"] = natal.ascendant

    found: list[Contact] = []
    for body in GRAHAS:
        longitude = moving.positions[body].longitude
        transit_house = (moving.positions[body].sign - natal.lagna_sign) % 12 + 1

        for point, natal_longitude in natal_points.items():
            separation = abs((longitude - natal_longitude + 180.0) % 360.0 - 180.0)
            natal_house = (
                (int(natal_longitude // 30) - natal.lagna_sign) % 12 + 1
            )
            if separation <= orb:
                found.append(
                    Contact(
                        transiting=body,
                        natal_point=point,
                        kind="conjunction",
                        separation=separation,
                        natal_house=natal_house,
                    )
                )
            elif natal_house in aspected_houses(body, transit_house):
                found.append(
                    Contact(
                        transiting=body,
                        natal_point=point,
                        kind="aspect",
                        separation=0.0,
                        natal_house=natal_house,
                    )
                )
    return found


# --- finding when things change ---------------------------------------------


def _bisect(is_after, low: float, high: float) -> float:
    """The instant between `low` and `high` where `is_after` flips from False to True."""
    for _ in range(_BISECT_ROUNDS):
        middle = (low + high) / 2.0
        if is_after(middle):
            high = middle
        else:
            low = middle
    return high


def _longitude_at(natal: Chart, body: str, jd: float) -> float:
    return transit_chart(natal, jd).positions[body].longitude


def _speed_at(natal: Chart, body: str, jd: float) -> float:
    return transit_chart(natal, jd).positions[body].speed


def sign_transits(natal: Chart, body: str, from_jd: float, to_jd: float) -> list[Window]:
    """When a graha enters and leaves each sign over a span.

    The first and last windows are clipped to the span, so their start or end is the
    edge of the range rather than a real ingress.
    """
    step = _SCAN_STEP_DAYS.get(body, _DEFAULT_SCAN_STEP)
    boundaries: list[float] = []

    previous_jd = from_jd
    previous_sign = int(_longitude_at(natal, body, from_jd) // 30)
    jd = from_jd + step
    while jd <= to_jd:
        sign = int(_longitude_at(natal, body, jd) // 30)
        if sign != previous_sign:
            target = sign
            crossed = _bisect(
                lambda moment: int(_longitude_at(natal, body, moment) // 30) == target,
                previous_jd,
                jd,
            )
            boundaries.append(crossed)
            previous_sign = sign
        previous_jd = jd
        jd += step

    windows: list[Window] = []
    edges = [from_jd, *boundaries, to_jd]
    for start, end in zip(edges, edges[1:]):
        if end - start < 1e-6:
            continue
        sign = int(_longitude_at(natal, body, (start + end) / 2.0) // 30)
        windows.append(
            Window(
                body=body,
                kind="sign_transit",
                start_jd=start,
                end_jd=end,
                label=f"{body} in {SIGNS[sign]}",
            )
        )
    return windows


def _state_windows(
    natal: Chart, body: str, from_jd: float, to_jd: float, kind: str, is_on, label: str
) -> list[Window]:
    """Spans over which a boolean condition holds, with edges found by bisection."""
    step = _SCAN_STEP_DAYS.get(body, 1.0)
    windows: list[Window] = []

    previous_jd = from_jd
    active = is_on(from_jd)
    start = from_jd if active else None

    jd = from_jd + step
    while jd <= to_jd:
        now = is_on(jd)
        if now != active:
            edge = _bisect(lambda moment: is_on(moment) == now, previous_jd, jd)
            if now:
                start = edge
            elif start is not None:
                windows.append(
                    Window(body=body, kind=kind, start_jd=start, end_jd=edge, label=label)
                )
                start = None
            active = now
        previous_jd = jd
        jd += step

    if active and start is not None:
        windows.append(Window(body=body, kind=kind, start_jd=start, end_jd=to_jd, label=label))
    return windows


def retrograde_windows(natal: Chart, body: str, from_jd: float, to_jd: float) -> list[Window]:
    if body in ("Sun", "Moon"):
        return []  # never retrograde
    if body in ("Rahu", "Ketu"):
        return []  # always retrograde by convention, so a window says nothing
    return _state_windows(
        natal, body, from_jd, to_jd, "retrograde",
        lambda jd: _speed_at(natal, body, jd) < 0,
        f"{body} retrograde",
    )


def combustion_windows(natal: Chart, body: str, from_jd: float, to_jd: float) -> list[Window]:
    from astro.core.strength import COMBUSTION_ORBS, is_combust

    if body not in COMBUSTION_ORBS:
        return []
    return _state_windows(
        natal, body, from_jd, to_jd, "combust",
        lambda jd: is_combust(transit_chart(natal, jd), body)[0],
        f"{body} combust",
    )


def sade_sati(natal: Chart, from_jd: float, to_jd: float) -> list[Window]:
    """Saturn's passage through the 12th, 1st and 2nd from the natal Moon.

    Not stated in BPHS as ingested — the doctrine is later — but it is the single most
    asked-about transit, so it is computed and labelled with where it comes from.
    """
    moon_sign = natal.positions["Moon"].sign
    windows = []
    for window in sign_transits(natal, "Saturn", from_jd, to_jd):
        sign = int(_longitude_at(natal, "Saturn", (window.start_jd + window.end_jd) / 2.0) // 30)
        house = (sign - moon_sign) % 12 + 1
        if house in SADE_SATI_HOUSES:
            phase = SADE_SATI_PHASE[house]
            windows.append(
                Window(
                    body="Saturn",
                    kind="sade_sati",
                    start_jd=window.start_jd,
                    end_jd=window.end_jd,
                    label=f"Sade sati — {phase} phase",
                    detail=(
                        f"Saturn crossing {SIGNS[sign]}, the {house}th from the natal "
                        "Moon. Doctrine not found in the ingested texts."
                    ),
                )
            )
    return windows


def confluence(
    natal: Chart,
    ashtakavarga: Ashtakavarga,
    dasha_chain: tuple,
    jd: float,
) -> dict:
    """How well the ruling dasha lords are supported by their own transits right now.

    This is a scoring heuristic, not scripture, and is labelled as such wherever it is
    shown. The reasoning it encodes is standard: a period tends to deliver its promise
    when the graha ruling it is also well placed in transit, and to stall when it is
    not. The components are returned alongside the score so a reader can see what drove
    it rather than being handed a number.
    """
    standings = gochara(natal, ashtakavarga, jd)
    components = []
    # A mahadasha colours years and an antardasha months, so the outer level counts for
    # more when the two disagree.
    weights = [3, 2, 1]

    for period, weight in zip(dasha_chain, weights):
        standing = standings[period.lord]
        components.append(
            {
                "level": period.level_name,
                "lord": period.lord,
                "sign": standing.sign_name,
                "bindus": standing.bindus,
                "supported": standing.supported,
                "traditionally_good": standing.traditionally_good,
                "weight": weight,
                "contribution": weight * (1 if standing.supported else -1),
            }
        )

    total = sum(component["contribution"] for component in components)
    possible = sum(weights[: len(components)]) or 1
    return {
        "score": total,
        "normalised": round(total / possible, 3),
        "reading": "supported" if total > 0 else "obstructed" if total < 0 else "mixed",
        "components": components,
        "basis": (
            "Ashtakavarga transit doctrine, Brihat Parashara Hora Shastra ch. 66 "
            "v. 70-72. The weighting across dasha levels is this project's own "
            "heuristic, not from the text."
        ),
    }
