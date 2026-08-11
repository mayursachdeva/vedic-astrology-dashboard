"""Shadbala — the six-fold strength of the grahas, from BPHS ch. 27.

Everything else in this project answers "where is it and what does that mean". Shadbala
answers "how much can it actually deliver", which is what decides whether a yoga
performs or sits there looking good on paper. It is the one classical measure that is
arithmetic all the way down, so it can be computed exactly rather than interpreted.

The unit is the virupa; sixty virupas make one rupa. Six sources are summed:

    Sthana Bala     positional — five parts (ch. 27 v. 2-6)
    Dig Bala        directional (v. 7)
    Kala Bala       temporal — six parts (v. 8-13, 15-17)
    Chesta Bala     motional (v. 18, 21-23)
    Naisargika Bala natural, a fixed table (v. 14)
    Drik Bala       aspectual (v. 19, using the drishti values of ch. 26)

and the total is measured against the minimum each graha needs (v. 32-33).

Every threshold here is the ingested text's, and where this edition is internally
inconsistent or silent the divergence is recorded in `KNOWN_VARIANTS` rather than
quietly resolved — the same discipline the ashtakavarga tables follow.

The module is arithmetic over an already-computed `Chart`, so it imports no ephemeris.
Declination, which Ayana Bala needs, is derived from the sidereal longitude, the
latitude and the chart's own ayanamsa.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from astro.core.ephemeris import Chart
from astro.core.panchanga import weekday_index
from astro.core.strength import (
    EXALTATION,
    MOOLATRIKONA,
    SEVEN,
    compound_relation,
    is_natural_benefic,
    is_waxing,
    natural_relation,
    sign_lord,
    temporal_relation,
)
from astro.core.varga import varga_sign

VIRUPAS_PER_RUPA = 60.0

# ch. 27 v. 2-4. The seven vargas of the Saptavargaja Bala and what each dignity is
# worth in them. The names in the text are the graha's mood — Mooltrikona, Svasth
# (own), Pramudit (great friend), Shant (friend), Din (neutral), Duhkhit (enemy),
# Khal (great enemy).
SAPTAVARGA = (1, 2, 3, 7, 9, 12, 30)
VARGA_DIGNITY_VALUE = {
    "moolatrikona": 45.0,
    "own": 30.0,
    "great_friend": 20.0,
    "friend": 15.0,
    "neutral": 10.0,
    "enemy": 4.0,
    "great_enemy": 2.0,
}

# v. 6. Which decanate each graha wants to be in.
DREKKANA_SEX = {
    "Sun": 1, "Mars": 1, "Jupiter": 1,       # male — first decanate
    "Moon": 2, "Venus": 2,                    # female — second
    "Mercury": 3, "Saturn": 3,                # hermaphrodite — third
}

# v. 7. The point each graha is weakest at; its strength is the distance from there.
# Named as angles rather than house cusps on purpose: under whole-sign houses a "cusp"
# is a sign boundary, which would make Dig Bala depend on the house system. The four
# angles do not.
DIG_BALA_WEAK_ANGLE = {
    "Sun": "nadir", "Mars": "nadir",
    "Jupiter": "descendant", "Mercury": "descendant",
    "Venus": "midheaven", "Moon": "midheaven",
    "Saturn": "ascendant",
}

# v. 8-9. Nathonnatha: the nocturnal grahas gain towards midnight, the diurnal towards
# noon, and Mercury is exempt.
NOCTURNAL = ("Moon", "Mars", "Saturn")
DIURNAL = ("Sun", "Jupiter", "Venus")

# v. 12. Tribhaga: who owns each third of the day and of the night.
DAY_THIRDS = ("Mercury", "Sun", "Saturn")
NIGHT_THIRDS = ("Moon", "Venus", "Mars")

# v. 13.
VARSHA_BALA, MASA_BALA, VARA_BALA, HORA_BALA = 15.0, 30.0, 45.0, 60.0

WEEKDAY_LORDS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
# The Chaldean order, slowest first. Each hora is ruled by the lord of the sixth weekday
# from the last, which is the same sequence read another way.
CHALDEAN = ("Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon")

# v. 14. Naisargika Bala is one rupa divided by seven, taken 1 to 7 times.
NAISARGIKA_RANK = {
    "Saturn": 1, "Mars": 2, "Mercury": 3, "Jupiter": 4,
    "Venus": 5, "Moon": 6, "Sun": 7,
}

# v. 15-17, in the note: Ayana Bala = (23°27' ± declination) * 1.2793. The sign depends
# on which way the graha wants to be off the equator.
NORTH_IS_STRONG = ("Sun", "Mars", "Jupiter", "Venus")
SOUTH_IS_STRONG = ("Moon", "Saturn")
MAXIMUM_DECLINATION = 23.45  # 23 degrees 27 minutes, as the text gives it
AYANA_FACTOR = 1.2793

# v. 21-23. The eight motions and what each is worth. The values are the text's, in its
# order; the names are Charak's (p. 184), whose middle three are the coherent reading —
# see KNOWN_VARIANTS["chesta_motion_names"].
MOTION_VALUE = {
    "vakra": 60.0,        # retrograde
    "anuvakra": 30.0,     # retrograde into the previous sign
    "vikala": 15.0,       # stationary
    "madhya": 30.0,       # about its usual pace
    "manda": 15.0,        # slow
    "mandatara": 7.5,     # slower still
    "sheeghra": 45.0,     # fast
    "atisheeghra": 30.0,  # fast enough to carry it into the next sign
}

# Mean sidereal daily motion, used only to say what "usual" means above.
MEAN_MOTION = {
    "Mars": 0.5240, "Mercury": 1.3833, "Jupiter": 0.0831,
    "Venus": 1.6021, "Saturn": 0.0335,
}

# v. 32-33. The Shad Bala Pinda each graha needs to count as strong, in virupas.
REQUIRED = {
    "Sun": 390.0, "Moon": 360.0, "Mars": 300.0, "Mercury": 420.0,
    "Jupiter": 390.0, "Venus": 330.0, "Saturn": 300.0,
}

KNOWN_VARIANTS = {
    "varsha_bala_divisor": (
        "v. 13 as printed in this edition says to divide the Ahargana by 60 to reach "
        "the year lord. 360 is used here instead. The text's own next step — multiply "
        "the quotient by 3 — only works for a 360-day year, since 360 days is 51 weeks "
        "and 3 days, so the weekday advances by 3 each year. The month rule in the same "
        "verse divides by 30 and advances by 2, which is the same reasoning and is "
        "consistent. Charak (p. 183) names 'the year of 360 days calculated from the "
        "beginning of the creation' outright. Read as a typo in this printing."
    ),
    "chesta_motion_names": (
        "v. 21-23 lists the eight motions as Vakra, Anuvakra, Vikal, Mand, Mandatar, "
        "Sama, Char, Atichar against the values 60, 30, 15, 30, 15, 7.5, 45, 30. "
        "Charak (p. 184) lists the same eight values against Vakra, Anuvakra, Vikala, "
        "Madhya, Manda, Mandatara, Sheeghra, Ati-sheeghra. The values agree; the middle "
        "three names do not, and Charak's are the coherent ones — his ladder runs "
        "slowest to fastest as Mandatara 7.5, Manda 15, Madhya 30, where this "
        "translation puts 7.5 on Sama, a graha moving at about its usual pace. Charak's "
        "names and ordering are followed, so a graha near its mean speed scores 30 "
        "rather than 7.5."
    ),
    "paksha_bala_of_the_moon": (
        "Charak (p. 182) doubles the Moon's Paksha Bala; BPHS ch. 27 v. 10-11 does not "
        "mention it. The verse is followed and the Moon's is not doubled, which leaves "
        "her total up to 60 virupas below what an implementation following Charak "
        "reports. Charak also fixes the benefics for this purpose as the Moon, Mercury, "
        "Jupiter and Venus, where the split here uses the chart's own reading of "
        "Mercury — so a Mercury sitting with malefics takes the malefic share."
    ),
    "chesta_bala_method": (
        "BPHS gives two ways to reach Chesta Bala. v. 24-25 computes a Chesta Kendra "
        "from the mean longitude and the seeghrocca; v. 21-23 assigns a fixed value to "
        "each of eight named motions. The second is used here, because the first needs "
        "mean longitudes that the ephemeris layer does not expose, and using it would "
        "mean inventing them. The two do not agree closely: the eight-fold table is a "
        "step function where the kendra method is continuous, so a graha just either "
        "side of a boundary can differ by 15 virupas or more."
    ),
    "chesta_motion_thresholds": (
        "The eight motions are named in v. 21-23 but their boundaries are not given. "
        "The bands used here are stated in `_motion` as fractions of each graha's mean "
        "daily motion, and are this implementation's choice, not the text's."
    ),
    "suns_doubled_ayana_in_chesta": (
        "v. 15-17 doubles the Sun's Ayana Bala. v. 18 then says his Chesta Bala "
        "'corresponds to his Ayan Bal', without saying which figure — the doubled one "
        "or the one before doubling. The doubled figure is used, following the common "
        "implementations, which is why the Sun is the one graha whose Chesta Bala can "
        "pass 60 virupas. Reading it the other way lowers his total by up to 60."
    ),
    "drishti_from_the_ladder_not_the_arithmetic": (
        "ch. 26 states the drishti values twice: as a ladder in v. 2-5 (a quarter on "
        "the 3rd and 10th, a half on the 5th and 9th, three quarters on the 4th and "
        "8th, all of it on the 7th, with each of Saturn, Mars and Jupiter taking the "
        "whole of its own pair) and as arithmetic in v. 6-12. In this translation the "
        "two do not agree: the arithmetic for Jupiter is discontinuous at the fifth "
        "aspect, the point of the rule, and the preamble to v. 6-8 would put 30 rather "
        "than a full 60 on the seventh. Charak (p. 186) tabulates the values every "
        "thirty degrees and matches the ladder exactly, so the ladder is implemented "
        "and the arithmetic treated as a corrupt statement of it."
    ),
}


# --- geometry ---------------------------------------------------------------


def _mean_obliquity(jd_ut: float) -> float:
    """The tilt of the ecliptic, degrees. Good to well under an arcsecond over the
    range any birth chart occupies, which is far finer than Ayana Bala needs."""
    centuries = (jd_ut - 2451545.0) / 36525.0
    return (
        23.439291
        - 0.0130042 * centuries
        - 1.64e-7 * centuries**2
        + 5.04e-7 * centuries**3
    )


def declination(chart: Chart, body: str) -> float:
    """The graha's angular distance north (+) or south (-) of the celestial equator.

    Derived rather than fetched: the ephemeris hands back sidereal longitude and
    ecliptic latitude, and the chart carries the ayanamsa needed to put the longitude
    back on the tropical circle where the obliquity applies.
    """
    position = chart.positions[body]
    tropical = math.radians((position.longitude + chart.ayanamsa_value) % 360.0)
    beta = math.radians(position.latitude)
    epsilon = math.radians(_mean_obliquity(chart.jd_ut))
    sine = math.sin(beta) * math.cos(epsilon) + math.cos(beta) * math.sin(
        epsilon
    ) * math.sin(tropical)
    return math.degrees(math.asin(max(-1.0, min(1.0, sine))))


def _arc(degrees: float) -> float:
    """A separation folded into 0-180, which is what every "if above 180, deduct from
    360" instruction in the chapter amounts to."""
    value = degrees % 360.0
    return 360.0 - value if value > 180.0 else value


# --- sthana bala (v. 2-6) ---------------------------------------------------


def uchcha_bala(chart: Chart, body: str) -> float:
    """Distance from the graha's fall, divided by three. Sixty at exaltation, nil at
    debilitation."""
    sign, degree = EXALTATION[body]
    debilitation = (sign * 30.0 + degree + 180.0) % 360.0
    return _arc(chart.positions[body].longitude - debilitation) / 3.0


def _varga_dignity(body: str, varga_sign_index: int, natal_house_distance: int) -> str:
    """How a graha stands in one divisional sign.

    Own sign and moolatrikona are read from the divisional sign itself; friendship is
    the compound relation, since that is what the chapter's seven moods describe.
    """
    if body in MOOLATRIKONA:
        mool_sign, low, high = MOOLATRIKONA[body]
        if varga_sign_index == mool_sign:
            return "moolatrikona"
    lord = sign_lord(varga_sign_index)
    if lord == body:
        return "own"
    return compound_relation(
        natural_relation(body, lord), temporal_relation(natal_house_distance)
    )


def saptavargaja_bala(chart: Chart, body: str) -> float:
    """The graha's standing across seven divisional charts, added up (v. 2-4).

    Moolatrikona is tested against the divisional sign, so it can be reached in a varga
    the graha does not hold in the rasi. That is the plain reading of "similarly these
    values occur for the other 6 divisional occupations"; some implementations restrict
    it to the rasi and will come out up to 15 virupas lower.
    """
    longitude = chart.positions[body].longitude
    total = 0.0
    for divisor in SAPTAVARGA:
        sign = varga_sign(divisor, longitude)
        lord = sign_lord(sign)
        # The temporal relation is a natal fact — where the dispositor stands from the
        # graha in the birth chart — and does not move with the varga.
        if lord == body:
            distance = 1
        else:
            distance = (
                chart.positions[lord].sign - chart.positions[body].sign
            ) % 12 + 1
        total += VARGA_DIGNITY_VALUE[_varga_dignity(body, sign, distance)]
    return total


def ojhayugma_bala(chart: Chart, body: str) -> float:
    """Odd and even signs, in the rasi and again in the navamsa (v. 4½).

    The Moon and Venus want even signs, everything else odd; fifteen virupas for each
    chart that obliges.
    """
    wants_even = body in ("Moon", "Venus")
    longitude = chart.positions[body].longitude
    total = 0.0
    for divisor in (1, 9):
        sign = varga_sign(divisor, longitude)
        if (sign % 2 == 1) == wants_even:  # sign 0 is Aries, an odd rasi
            total += 15.0
    return total


def kendradi_bala(chart: Chart, body: str) -> float:
    """Angle sixty, succedent thirty, cadent fifteen (v. 5).

    The verse reads "a Grah in a Kon gets full strength"; kona means trine, but the
    three-way split it describes is the kendra/panaphara/apoklima one and every
    commentary reads it as kendra. Followed here.
    """
    house = chart.house_of(body)
    if house in (1, 4, 7, 10):
        return 60.0
    if house in (2, 5, 8, 11):
        return 30.0
    return 15.0


def drekkana_bala(chart: Chart, body: str) -> float:
    """Fifteen virupas for a graha in the decanate that suits its sex (v. 6)."""
    degree = chart.positions[body].degree_in_sign
    decanate = min(int(degree // 10.0) + 1, 3)
    return 15.0 if DREKKANA_SEX[body] == decanate else 0.0


# --- dig bala (v. 7) --------------------------------------------------------


def dig_bala(chart: Chart, body: str) -> float:
    """Distance from the direction the graha is weakest in, divided by three."""
    angles = {
        "ascendant": chart.ascendant,
        "descendant": (chart.ascendant + 180.0) % 360.0,
        "midheaven": chart.midheaven,
        "nadir": (chart.midheaven + 180.0) % 360.0,
    }
    weak = angles[DIG_BALA_WEAK_ANGLE[body]]
    return _arc(chart.positions[body].longitude - weak) / 3.0


# --- kala bala (v. 8-13, 15-17) ---------------------------------------------


def _local_day_fraction(chart: Chart) -> float:
    """Where the birth falls in the local day, 0 at local mean midnight to 1.

    Local mean time, not the zone's: the chapter's day is the one over the birthplace,
    and the Hora Bala verse says so outright — "Horas are to be calculated for mean
    local time and not standard time of births".
    """
    return ((chart.jd_ut + 0.5 + chart.longitude / 360.0) % 1.0)


def nathonnatha_bala(chart: Chart, body: str) -> float:
    """Night strength for the nocturnal grahas, day strength for the diurnal (v. 8-9).

    Sixty at the hour that suits the graha, nil twelve hours later, straight line
    between. Mercury takes the full sixty at any hour, as the verse allows.
    """
    if body == "Mercury":
        return 60.0
    hours_from_midnight = _local_day_fraction(chart) * 24.0
    unnata = min(hours_from_midnight, 24.0 - hours_from_midnight)  # hours towards noon
    night_strength = 60.0 * (1.0 - unnata / 12.0)
    return night_strength if body in NOCTURNAL else 60.0 - night_strength


def _benefic_for_paksha(chart: Chart, body: str) -> bool:
    """Which side of the paksha rule a graha falls on.

    The Moon is judged by the fortnight, not by her brightness. `is_natural_benefic`
    calls her malefic until she is far enough from the Sun to be bright, which is the
    right test for a yoga and the wrong one here: the verse divides the benefics from
    the malefics by paksha, and the Moon belongs to the bright half from the moment it
    begins. A crescent Moon judged the other way collects the malefic remainder and
    reads nearly thirty virupas too strong.
    """
    if body == "Moon":
        return is_waxing(chart)
    return is_natural_benefic(chart, body)


def paksha_bala(chart: Chart, body: str) -> float:
    """The Moon's distance from the Sun, divided by three, to the benefics (v. 10-11).

    Full at the full moon and nil at the new; the malefics take the remainder, so the
    dark fortnight is theirs.
    """
    elongation = _arc(
        chart.positions["Moon"].longitude - chart.positions["Sun"].longitude
    )
    benefic_share = elongation / 3.0
    return benefic_share if _benefic_for_paksha(chart, body) else 60.0 - benefic_share


def tribhaga_bala(chart: Chart, body: str, span: tuple[float, float, float] | None) -> float:
    """One rupa to whoever owns this third of the day or night (v. 12).

    Jupiter takes it at every hour. `span` is (sunrise, sunset, next sunrise); None
    inside a polar day or night, where the thirds do not exist and only Jupiter's
    share can be stated.
    """
    if body == "Jupiter":
        return 60.0
    if span is None:
        return 0.0
    rise, setting, following = span
    moment = chart.jd_ut
    if rise <= moment < setting:
        third = int((moment - rise) / ((setting - rise) / 3.0))
        owner = DAY_THIRDS[min(third, 2)]
    else:
        start = setting if moment >= setting else setting - 1.0
        end = following if moment >= setting else rise
        third = int((moment - start) / ((end - start) / 3.0))
        owner = NIGHT_THIRDS[min(max(third, 0), 2)]
    return 60.0 if owner == body else 0.0


# The Ahargana anchor the chapter gives: days elapsed since the beginning of creation
# as of 1 January 1860, from Burgess's Surya Siddhanta. Only its remainders modulo 7,
# 30 and 360 matter, so an error in the absolute figure would move the year and month
# lords but nothing else.
AHARGANA_AT_1860 = 714_404_108_573
JD_1860_JAN_1 = 2_400_520.5


def ahargana(chart: Chart) -> int:
    return AHARGANA_AT_1860 + int(math.floor(chart.jd_ut - JD_1860_JAN_1))


def _weekday_index(chart: Chart, span: tuple[float, float, float] | None) -> int:
    """Counted from sunrise when there is one.

    The Indian day begins there, so a birth at four in the morning still belongs to the
    weekday before — and Vara Bala is 45 virupas handed to the wrong graha if that is
    missed. Shares `panchanga.weekday_index` rather than repeating it, since the
    longitude correction inside it is easy to leave out and was.
    """
    reference = span[0] if span else chart.jd_ut
    return weekday_index(reference, chart.longitude)


def varsha_lord(chart: Chart) -> str:
    """The weekday the astrological year of birth opened on (v. 13)."""
    years = ahargana(chart) // 360  # see KNOWN_VARIANTS["varsha_bala_divisor"]
    return WEEKDAY_LORDS[(years * 3 + 1) % 7]


def masa_lord(chart: Chart) -> str:
    """The weekday the month of birth opened on (v. 13)."""
    months = ahargana(chart) // 30
    return WEEKDAY_LORDS[(months * 2 + 1) % 7]


def vara_lord(chart: Chart, span: tuple[float, float, float] | None = None) -> str:
    return WEEKDAY_LORDS[_weekday_index(chart, span)]


def hora_lord(chart: Chart, span: tuple[float, float, float] | None) -> str | None:
    """Who rules the planetary hour of birth (v. 13).

    The day from sunrise to sunrise is cut into twenty-four; the first hour belongs to
    the lord of the weekday and each following one steps through the Chaldean order.
    """
    if span is None:
        return None
    rise, _, following = span
    index = int((chart.jd_ut - rise) / ((following - rise) / 24.0))
    day_lord = vara_lord(chart, span)
    start = CHALDEAN.index(day_lord)
    return CHALDEAN[(start + index) % 7]


def ayana_bala(chart: Chart, body: str) -> float:
    """Declination, taken the way the graha likes it (v. 15-17).

    Sixty when it is as far as it can be on its favoured side of the equator, nil on
    the far side; Mercury counts every declination as favourable, and the Sun's result
    is doubled.
    """
    kranti = declination(chart, body)
    if body == "Mercury":
        signed = abs(kranti)
    elif body in NORTH_IS_STRONG:
        signed = kranti
    elif body in SOUTH_IS_STRONG:
        signed = -kranti
    else:
        signed = kranti
    value = (MAXIMUM_DECLINATION + signed) * AYANA_FACTOR
    return value * 2.0 if body == "Sun" else value


# --- chesta bala (v. 18, 21-23) ---------------------------------------------


def _motion(chart: Chart, body: str) -> str:
    """Which of the eight motions the graha is in.

    The bands are not the text's — see KNOWN_VARIANTS["chesta_motion_thresholds"]. A
    graha is called anuvakra or atisheeghra when its current speed would carry it across
    a sign boundary within a day, which is what "entering the previous/next Rāśi" has to
    mean for an instantaneous chart.
    """
    position = chart.positions[body]
    mean = MEAN_MOTION[body]
    ratio = position.speed / mean

    if abs(ratio) < 1e-3:
        return "vikala"
    if ratio < 0:
        return "anuvakra" if position.degree_in_sign + position.speed < 0 else "vakra"
    if ratio > 1.0:
        crossing = position.degree_in_sign + position.speed >= 30.0
        return "atisheeghra" if crossing else "sheeghra"
    if ratio > 0.9:
        return "madhya"
    return "manda" if ratio > 0.5 else "mandatara"


def chesta_bala(chart: Chart, body: str) -> float:
    """What the graha's motion is worth.

    The Sun's is its Ayana Bala and the Moon's is her Paksha Bala, both stated outright
    in v. 18. The other five are read off the eight-fold motion table.
    """
    if body == "Sun":
        return ayana_bala(chart, body)
    if body == "Moon":
        return paksha_bala(chart, body)
    return MOTION_VALUE[_motion(chart, body)]


# --- naisargika bala (v. 14) ------------------------------------------------


def naisargika_bala(body: str) -> float:
    return VIRUPAS_PER_RUPA / 7.0 * NAISARGIKA_RANK[body]


# --- drik bala (v. 19, over the drishti values of ch. 26) -------------------


# ch. 26 v. 2-5 gives the ladder: a quarter on the 3rd and 10th, a half on the 5th and
# 9th, three quarters on the 4th and 8th, the whole of it on the 7th — and Saturn, Mars
# and Jupiter take a full drishti on their own pair instead of the fraction. As virupas
# at each sign boundary that is the table below, with straight lines between.
#
# Written as a table rather than decoded from v. 6-12's arithmetic, which is where the
# translation used here is at its least reliable: its clauses for Jupiter are
# discontinuous at the fifth aspect, and its preamble contradicts its own clauses about
# what happens past opposition. Charak (pp. 186) tabulates the same values for every
# thirty degrees and agrees with the ladder in v. 2-5 exactly, so the table is what is
# implemented and the arithmetic is treated as a corrupt statement of it.
_LADDER = {30: 0.0, 60: 15.0, 90: 45.0, 120: 30.0, 150: 0.0,
           180: 60.0, 210: 45.0, 240: 30.0, 270: 15.0, 300: 0.0}
DRISHTI_TABLE = {
    "general": _LADDER,
    "Saturn": {**_LADDER, 60: 60.0, 270: 60.0},    # the third and the tenth
    "Mars": {**_LADDER, 90: 60.0, 210: 60.0},      # the fourth and the eighth
    "Jupiter": {**_LADDER, 120: 60.0, 240: 60.0},  # the fifth and the ninth
}
_POINTS = sorted(_LADDER)


def _drishti(table: dict[int, float], separation: float) -> float:
    """The table read at any separation, straight lines between its points.

    Nothing below 30 degrees and nothing above 300: a graha does not aspect what it
    stands on, nor what stands just behind it.
    """
    d = separation % 360.0
    if d <= _POINTS[0] or d >= _POINTS[-1]:
        return 0.0
    for lower, upper in zip(_POINTS, _POINTS[1:]):
        if lower <= d <= upper:
            share = (d - lower) / (upper - lower)
            return table[lower] + share * (table[upper] - table[lower])
    return 0.0


def drishti_value(chart: Chart, giver: str, receiver: str) -> float:
    """What one graha's gaze is worth on another, in virupas."""
    separation = (
        chart.positions[receiver].longitude - chart.positions[giver].longitude
    ) % 360.0
    return _drishti(DRISHTI_TABLE.get(giver, DRISHTI_TABLE["general"]), separation)


def drik_bala(chart: Chart, body: str) -> float:
    """A quarter of the benefic gaze the graha receives, less a quarter of the malefic.

    v. 19: "Reduce one fourth of the Drishti Pinda, if a Grah receives malefic Drishtis
    and add a fourth, if it receives a Drishti from a benefic."
    """
    total = 0.0
    for giver in SEVEN:
        if giver == body:
            continue
        value = drishti_value(chart, giver, body)
        total += value if is_natural_benefic(chart, giver) else -value
    return total / 4.0


# --- the sum ----------------------------------------------------------------


@dataclass(frozen=True)
class Bala:
    """One graha's strength, kept in parts so a reader can see where it came from."""

    body: str
    sthana: dict[str, float]
    dig: float
    kala: dict[str, float]
    chesta: float
    naisargika: float
    drik: float
    yuddha: float = 0.0
    sources: dict[str, float] = field(default_factory=dict)

    @property
    def total(self) -> float:
        return sum(self.sources.values()) + self.yuddha

    @property
    def rupas(self) -> float:
        return self.total / VIRUPAS_PER_RUPA

    @property
    def required(self) -> float:
        return REQUIRED[self.body]

    @property
    def ratio(self) -> float:
        """Strength as a multiple of what the graha needs. One is the pass mark."""
        return self.total / self.required

    @property
    def strong(self) -> bool:
        return self.total >= self.required


def _sources(sthana: dict, dig: float, kala: dict, chesta: float,
             naisargika: float, drik: float) -> dict[str, float]:
    return {
        "sthana": sum(sthana.values()),
        "dig": dig,
        "kala": sum(kala.values()),
        "chesta": chesta,
        "naisargika": naisargika,
        "drik": drik,
    }


def shadbala(chart: Chart, span: tuple[float, float, float] | None = None) -> dict[str, Bala]:
    """The six-fold strength of each of the seven grahas.

    `span` is (sunrise, sunset, next sunrise) around the birth, which Tribhaga and Hora
    Bala need; pass None and those two contribute nothing rather than a guess. The
    nodes are absent because the chapter assigns them no strength.
    """
    year, month, day = varsha_lord(chart), masa_lord(chart), vara_lord(chart, span)
    hora = hora_lord(chart, span)

    balas: dict[str, Bala] = {}
    for body in SEVEN:
        sthana = {
            "uchcha": uchcha_bala(chart, body),
            "saptavargaja": saptavargaja_bala(chart, body),
            "ojhayugma": ojhayugma_bala(chart, body),
            "kendradi": kendradi_bala(chart, body),
            "drekkana": drekkana_bala(chart, body),
        }
        kala = {
            "nathonnatha": nathonnatha_bala(chart, body),
            "paksha": paksha_bala(chart, body),
            "tribhaga": tribhaga_bala(chart, body, span),
            "varsha": VARSHA_BALA if body == year else 0.0,
            "masa": MASA_BALA if body == month else 0.0,
            "vara": VARA_BALA if body == day else 0.0,
            "hora": HORA_BALA if body == hora else 0.0,
            "ayana": ayana_bala(chart, body),
        }
        dig = dig_bala(chart, body)
        chesta = chesta_bala(chart, body)
        natural = naisargika_bala(body)
        drik = drik_bala(chart, body)
        balas[body] = Bala(
            body=body, sthana=sthana, dig=dig, kala=kala, chesta=chesta,
            naisargika=natural, drik=drik,
            sources=_sources(sthana, dig, kala, chesta, natural, drik),
        )

    return _apply_yuddha(chart, balas)


# Grahas that can fight: the five star-planets. The luminaries and the nodes are out.
COMBATANTS = ("Mars", "Mercury", "Jupiter", "Venus", "Saturn")
WAR_ORB = 1.0


def _apply_yuddha(chart: Chart, balas: dict[str, Bala]) -> dict[str, Bala]:
    """v. 20 — when two star-planets fight, the gap between them widens.

    "The difference between the Shad Balas of the two should be added to the victor's
    Shad Bal and deducted from the Shad Bal of the vanquished." Which one wins is not
    stated in the chapter; the stronger is taken as the victor, which is the common
    convention and the only one the verse's arithmetic can be applied with.
    """
    adjustments: dict[str, float] = {}
    for i, first in enumerate(COMBATANTS):
        for second in COMBATANTS[i + 1 :]:
            gap = _arc(
                chart.positions[first].longitude - chart.positions[second].longitude
            )
            if gap > WAR_ORB:
                continue
            difference = abs(balas[first].total - balas[second].total)
            winner, loser = (
                (first, second)
                if balas[first].total >= balas[second].total
                else (second, first)
            )
            adjustments[winner] = adjustments.get(winner, 0.0) + difference
            adjustments[loser] = adjustments.get(loser, 0.0) - difference

    if not adjustments:
        return balas
    return {
        body: (
            bala
            if body not in adjustments
            else Bala(
                body=bala.body, sthana=bala.sthana, dig=bala.dig, kala=bala.kala,
                chesta=bala.chesta, naisargika=bala.naisargika, drik=bala.drik,
                yuddha=adjustments[body], sources=bala.sources,
            )
        )
        for body, bala in balas.items()
    }


# --- bhava bala (v. 26-31) --------------------------------------------------

# v. 26-27 sorts the rasis by which angle a bhava's strength is measured from. The
# grouping is the signs' own nature — biped signs answer to the descendant, quadruped
# to the nadir, watery to the ascendant, and the footless to the midheaven.
BHAVA_WEAK_ANGLE = {
    2: "descendant", 5: "descendant", 6: "descendant", 10: "descendant",
    0: "nadir", 1: "nadir", 4: "nadir", 9: "nadir",
    3: "ascendant", 7: "ascendant",
    11: "midheaven",
    # Sagittarius is split in the verse: its first half goes with the biped signs and
    # its second with the quadruped. Handled in `_bhava_angle`, which sees the degree.
    8: None,
}

# v. 30. A bhava gains a rupa for holding Jupiter or Mercury and loses one for holding
# Saturn, Mars or the Sun.
BHAVA_GUESTS = {"Jupiter": 60.0, "Mercury": 60.0, "Saturn": -60.0, "Mars": -60.0,
                "Sun": -60.0}

# v. 31, with the rising natures from ch. 4. Head-rising signs gain by day, back-rising
# by night, and the dual signs at twilight.
SEERSHODAYA = (2, 4, 5, 6, 7, 10)   # Gemini, Leo, Virgo, Libra, Scorpio, Aquarius
PRISHTODAYA = (0, 1, 3, 8, 9)       # Aries, Taurus, Cancer, Sagittarius, Capricorn
UBHAYODAYA = (11,)                  # Pisces rises with both, ch. 4 v. 22-24
DUAL_SIGNS = (2, 5, 8, 11)


def _bhava_angle(sign: int, degree_in_sign: float) -> str:
    angle = BHAVA_WEAK_ANGLE[sign % 12]
    if angle is not None:
        return angle
    return "descendant" if degree_in_sign < 15.0 else "nadir"


@dataclass(frozen=True)
class BhavaBala:
    house: int
    dig: float
    drik: float
    lord: str
    lord_bala: float
    guests: float
    rising: float

    @property
    def total(self) -> float:
        return self.dig + self.drik + self.lord_bala + self.guests + self.rising

    @property
    def rupas(self) -> float:
        return self.total / VIRUPAS_PER_RUPA


def bhava_bala(
    chart: Chart, balas: dict[str, Bala], span: tuple[float, float, float] | None = None
) -> dict[int, BhavaBala]:
    """The strength of each of the twelve bhavas (v. 26-31).

    A house is strong when its lord is strong, when it sits where its own nature wants
    to be, when benefics look at it, and when good company stands in it. That is the
    whole of the verse, and it is the closest the texts come to answering "how is this
    part of my life set up" with a number.

    One departure worth naming: the verse measures from the bhava's cusp, and this
    project uses whole-sign houses, which have no cusps in that sense. The bhava is
    taken to run from the lagna's own degree in each successive sign, which is what the
    equal-division reading gives and keeps the first bhava's measurement identical to
    the ascendant's.
    """
    angles = {
        "ascendant": chart.ascendant,
        "descendant": (chart.ascendant + 180.0) % 360.0,
        "midheaven": chart.midheaven,
        "nadir": (chart.midheaven + 180.0) % 360.0,
    }
    day = _daytime(chart, span)
    out: dict[int, BhavaBala] = {}

    for house in range(1, 13):
        madhya = (chart.ascendant + (house - 1) * 30.0) % 360.0
        sign = int(madhya // 30) % 12
        dig = _arc(madhya - angles[_bhava_angle(sign, madhya % 30.0)]) / 3.0

        # The same drishti values the grahas are judged by, thrown at a point rather
        # than at a graha, and a quarter of the net taken as the verse asks.
        received = 0.0
        for giver in SEVEN:
            separation = (madhya - chart.positions[giver].longitude) % 360.0
            value = _drishti(DRISHTI_TABLE.get(giver, DRISHTI_TABLE["general"]), separation)
            received += value if is_natural_benefic(chart, giver) else -value
            # "If Guru, or Budh give a Drishti to a Bhava, add that Grah's Drik Bal also."
            if giver in ("Jupiter", "Mercury") and value > 0:
                received += balas[giver].drik

        occupants = [
            body for body in SEVEN
            if (chart.positions[body].sign - chart.lagna_sign) % 12 + 1 == house
        ]
        guests = sum(BHAVA_GUESTS.get(body, 0.0) for body in occupants)

        if day is None:
            rising = 0.0
        elif sign in DUAL_SIGNS and day == "twilight":
            rising = 15.0
        elif sign in SEERSHODAYA and day == "day":
            rising = 15.0
        elif sign in (*PRISHTODAYA, *UBHAYODAYA) and day == "night":
            rising = 15.0
        else:
            rising = 0.0

        lord = sign_lord(sign)
        out[house] = BhavaBala(
            house=house, dig=dig, drik=received / 4.0, lord=lord,
            lord_bala=balas[lord].total, guests=guests, rising=rising,
        )
    return out


TWILIGHT = 0.75 / 24.0  # three quarters of an hour either side of sunrise and sunset


def _daytime(chart: Chart, span: tuple[float, float, float] | None) -> str | None:
    """Day, night, or twilight, which v. 31 needs and cannot be guessed without a
    sunrise. None at a polar latitude, where that part is left out."""
    if span is None:
        return None
    rise, setting, _ = span
    moment = chart.jd_ut
    if abs(moment - rise) < TWILIGHT or abs(moment - setting) < TWILIGHT:
        return "twilight"
    return "day" if rise <= moment < setting else "night"


def strongest(balas: dict[str, Bala]) -> str:
    """The graha with the most strength, which v. 37-38 says a house's promise runs
    through."""
    return max(balas, key=lambda body: balas[body].total)


def payload(balas: dict[str, Bala]) -> dict:
    """Serialisable form, in the shape the interface reads."""
    return {
        "unit": "virupa",
        "per_rupa": VIRUPAS_PER_RUPA,
        "strongest": strongest(balas),
        "grahas": {
            body: {
                "total": round(bala.total, 2),
                "rupas": round(bala.rupas, 2),
                "required": bala.required,
                "ratio": round(bala.ratio, 3),
                "strong": bala.strong,
                "sources": {name: round(value, 2) for name, value in bala.sources.items()},
                "sthana": {name: round(value, 2) for name, value in bala.sthana.items()},
                "kala": {name: round(value, 2) for name, value in bala.kala.items()},
                "yuddha": round(bala.yuddha, 2),
            }
            for body, bala in balas.items()
        },
    }
