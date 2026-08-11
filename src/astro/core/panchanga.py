"""Panchanga — the five limbs of the day.

Tithi, vara, nakshatra, yoga and karana. All five follow from the Sun and Moon
longitudes already available, which is why this is computed here rather than fetched
from a service: it is arithmetic on two numbers, and sending a family member's birth
data to a third party to get it back would be a poor trade.

The ingested BPHS uses these units rather than defining them — ch. 85 v. 1-4 lists
births on Amavasya, on Chaturdashi, in Krishna Paksha and in Bhadra karana among the
inauspicious ones, and ch. 92 v. 2 defines Tithi Gandanta by ghatikas of the Nanda and
Purna tithis. Those two readings are cited. The nitya yogas are not in the text and are
marked accordingly.
"""

from __future__ import annotations

from dataclasses import dataclass

import swisseph as swe

from astro.core.ephemeris import NAKSHATRAS, Chart, compute_chart

TITHI_NAMES = (
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi", "Saptami",
    "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi", "Trayodashi",
    "Chaturdashi", "Purnima",
)
# The five groups a tithi falls into, repeating every five.
TITHI_GROUPS = ("Nanda", "Bhadra", "Jaya", "Rikta", "Purna")

MOVABLE_KARANAS = ("Bava", "Balava", "Kaulava", "Taitila", "Gara", "Vanija", "Vishti")
FIXED_KARANAS = {1: "Kimstughna", 58: "Shakuni", 59: "Chatushpada", 60: "Naga"}
# Vishti is Bhadra, the karana BPHS ch. 85 names among the inauspicious births.
BHADRA = "Vishti"

NITYA_YOGAS = (
    "Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana", "Atiganda", "Sukarma",
    "Dhriti", "Shula", "Ganda", "Vriddhi", "Dhruva", "Vyaghata", "Harshana", "Vajra",
    "Siddhi", "Vyatipata", "Variyana", "Parigha", "Shiva", "Siddha", "Sadhya", "Shubha",
    "Shukla", "Brahma", "Indra", "Vaidhriti",
)

WEEKDAYS = (
    ("Sunday", "Sun"), ("Monday", "Moon"), ("Tuesday", "Mars"), ("Wednesday", "Mercury"),
    ("Thursday", "Jupiter"), ("Friday", "Venus"), ("Saturday", "Saturn"),
)

TITHI_ARC = 12.0  # degrees of Moon-Sun elongation per tithi
KARANA_ARC = 6.0
YOGA_ARC = 360.0 / 27.0

# A ghatika is 24 minutes; gandanta spans two of them at a tithi junction.
GHATIKA_DAYS = 24.0 / (60.0 * 24.0)


@dataclass(frozen=True)
class Limb:
    """One of the five, with the moment it gives way to the next."""

    name: str
    index: int
    ends_jd: float | None = None
    note: str = ""


@dataclass(frozen=True)
class Panchanga:
    jd: float
    tithi: Limb
    paksha: str
    vara: Limb
    nakshatra: Limb
    yoga: Limb
    karana: Limb
    flags: tuple[str, ...]

    @property
    def tithi_group(self) -> str:
        return TITHI_GROUPS[(self.tithi.index - 1) % 5]


def _elongation(chart: Chart) -> float:
    """Moon minus Sun, 0-360. Every limb but the vara falls out of this or its sum."""
    return (
        chart.positions["Moon"].longitude - chart.positions["Sun"].longitude
    ) % 360.0


def _sum_longitude(chart: Chart) -> float:
    return (
        chart.positions["Sun"].longitude + chart.positions["Moon"].longitude
    ) % 360.0


def tithi_index(chart: Chart) -> int:
    """1 to 30. 1-15 are the bright fortnight, 16-30 the dark."""
    return int(_elongation(chart) // TITHI_ARC) + 1


def tithi_name(index: int) -> str:
    if index == 30:
        return "Amavasya"
    return TITHI_NAMES[(index - 1) % 15]


def karana_index(chart: Chart) -> int:
    """1 to 60 — each tithi is two karanas."""
    return int(_elongation(chart) // KARANA_ARC) + 1


def karana_name(index: int) -> str:
    """Four karanas are fixed to particular half-tithis; the other seven repeat."""
    if index in FIXED_KARANAS:
        return FIXED_KARANAS[index]
    return MOVABLE_KARANAS[(index - 2) % 7]


def yoga_index(chart: Chart) -> int:
    return int(_sum_longitude(chart) // YOGA_ARC) + 1


def sunrise(jd: float, latitude: float, longitude: float) -> float | None:
    """The sunrise at or before `jd`, which is where the Indian day begins.

    Returns None inside a polar day or night, where the question has no answer; the
    caller must handle that rather than be handed a fabricated time.
    """
    result, times = swe.rise_trans(
        jd - 1.0,
        swe.SUN,
        swe.CALC_RISE | swe.BIT_DISC_CENTER,
        (longitude, latitude, 0.0),
    )
    if result < 0:
        return None
    latest = times[0]
    # Step forward while the next sunrise is still before the moment asked about.
    for _ in range(3):
        result, following = swe.rise_trans(
            latest + 0.01,
            swe.SUN,
            swe.CALC_RISE | swe.BIT_DISC_CENTER,
            (longitude, latitude, 0.0),
        )
        if result < 0 or following[0] > jd:
            break
        latest = following[0]
    return latest


def _next(jd: float, event: int, latitude: float, longitude: float) -> float | None:
    result, times = swe.rise_trans(
        jd, swe.SUN, event | swe.BIT_DISC_CENTER, (longitude, latitude, 0.0)
    )
    return None if result < 0 else times[0]


def day_span(
    jd: float, latitude: float, longitude: float
) -> tuple[float, float, float] | None:
    """Sunrise before `jd`, the sunset after it, and the following sunrise.

    Kala bala divides the day and the night into thirds, so it needs the boundaries
    rather than the length. Returns None inside a polar day or night, where they do
    not exist — the caller shows the reader a gap instead of a fabricated number.
    """
    rise = sunrise(jd, latitude, longitude)
    if rise is None:
        return None
    setting = _next(rise, swe.CALC_SET, latitude, longitude)
    following = _next(setting or rise + 0.5, swe.CALC_RISE, latitude, longitude)
    if setting is None or following is None:
        return None
    return rise, setting, following


def weekday_index(jd_ut: float, longitude: float) -> int:
    """Which weekday a moment falls on where it happened. 0 is Sunday.

    The longitude term is not a nicety. Julian days are counted in UT, and Delhi's
    sunrise at 05:24 local is 23:54 UT the day before — so a weekday read straight off
    the julian day put every Indian sunrise on the previous day, and reported Friday
    15 June 1990 as a Thursday. Julian day 0 was a Monday; the +1.5 puts Sunday at 0
    and moves the boundary from noon to midnight.
    """
    return int((jd_ut + longitude / 360.0 + 1.5) % 7)


def vara(jd: float, latitude: float, longitude: float) -> Limb:
    """The weekday, counted from sunrise rather than from midnight.

    Before sunrise the previous weekday is still running, which is why a birth at 4am
    belongs to the day before in every panchanga.
    """
    rise = sunrise(jd, latitude, longitude)
    reference = jd if rise is None else rise
    index = weekday_index(reference, longitude)
    name, lord = WEEKDAYS[index]
    return Limb(
        name=name,
        index=index,
        note=(
            f"ruled by {lord}"
            + ("" if rise is not None else "; no sunrise at this latitude, "
               "so the civil day was used instead")
        ),
    )


def _ends(chart_at, jd: float, value_at, current: int, arc_days_guess: float) -> float:
    """When the current limb gives way to the next, by scan and bisection."""
    step = arc_days_guess / 8.0
    probe = jd
    for _ in range(400):
        probe += step
        if value_at(chart_at(probe)) != current:
            low, high = probe - step, probe
            for _ in range(40):
                middle = (low + high) / 2.0
                if value_at(chart_at(middle)) == current:
                    low = middle
                else:
                    high = middle
            return high
    return jd + arc_days_guess * 2  # pragma: no cover - a limb always ends


def compute(jd: float, latitude: float, longitude: float, *, ayanamsa: str = "lahiri") -> Panchanga:
    """The five limbs at a moment, with the flags BPHS attaches to some of them."""

    def chart_at(moment: float) -> Chart:
        return compute_chart(moment, latitude, longitude, ayanamsa=ayanamsa)

    chart = chart_at(jd)

    tithi_number = tithi_index(chart)
    karana_number = karana_index(chart)
    yoga_number = yoga_index(chart)
    nakshatra_number = chart.positions["Moon"].nakshatra + 1

    tithi = Limb(
        name=tithi_name(tithi_number),
        index=tithi_number,
        ends_jd=_ends(chart_at, jd, tithi_index, tithi_number, 1.0),
    )
    karana = Limb(
        name=karana_name(karana_number),
        index=karana_number,
        ends_jd=_ends(chart_at, jd, karana_index, karana_number, 0.5),
    )
    yoga = Limb(
        name=NITYA_YOGAS[yoga_number - 1],
        index=yoga_number,
        ends_jd=_ends(chart_at, jd, yoga_index, yoga_number, 1.0),
        note="the nitya yogas are not in the ingested texts",
    )
    nakshatra = Limb(
        name=NAKSHATRAS[nakshatra_number - 1],
        index=nakshatra_number,
        ends_jd=_ends(
            chart_at,
            jd,
            lambda c: c.positions["Moon"].nakshatra,
            chart.positions["Moon"].nakshatra,
            1.0,
        ),
    )

    return Panchanga(
        jd=jd,
        tithi=tithi,
        paksha="Shukla" if tithi_number <= 15 else "Krishna",
        vara=vara(jd, latitude, longitude),
        nakshatra=nakshatra,
        yoga=yoga,
        karana=karana,
        flags=_flags(tithi, karana, jd),
    )


def _flags(tithi: Limb, karana: Limb, jd: float) -> tuple[str, ...]:
    """The readings BPHS attaches to particular tithis and karanas.

    Cited, because unlike the rest of the panchanga these are claims rather than
    definitions. Worded as conditions rather than as "born in ...", because the same
    function describes today's panchanga, where nobody was born.
    """
    flags: list[str] = []
    citation = "Brihat Parashara Hora Shastra, ch. 85, v. 1-4"

    if tithi.index == 30:
        flags.append(
            f"Amavasya — BPHS lists birth on it among the inauspicious "
            f"circumstances ({citation})"
        )
    elif tithi.index in (14, 29):
        flags.append(
            f"Chaturdashi — BPHS lists birth on it among the inauspicious "
            f"circumstances ({citation})"
        )
    if tithi.index > 15:
        flags.append(
            f"Krishna Paksha, the dark fortnight — BPHS lists birth in it among the "
            f"inauspicious circumstances ({citation})"
        )
    if karana.name == BHADRA:
        flags.append(
            f"Bhadra (Vishti) karana — BPHS lists birth in it among the inauspicious "
            f"circumstances ({citation})"
        )

    group = TITHI_GROUPS[(tithi.index - 1) % 5]
    if tithi.ends_jd is not None:
        if group == "Purna" and tithi.ends_jd - jd <= 2 * GHATIKA_DAYS:
            flags.append(
                "Tithi Gandanta: within the last two ghatikas of a Purna tithi "
                "(Brihat Parashara Hora Shastra, ch. 92, v. 2)"
            )
        if group == "Nanda":
            started = tithi.ends_jd - 1.0  # a tithi runs roughly a day
            if jd - started <= 2 * GHATIKA_DAYS:
                flags.append(
                    "Tithi Gandanta: within the first two ghatikas of a Nanda tithi "
                    "(Brihat Parashara Hora Shastra, ch. 92, v. 2)"
                )

    return tuple(flags)
