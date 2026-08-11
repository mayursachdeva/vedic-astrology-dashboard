"""The states a graha is in — BPHS ch. 45.

Dignity says where a planet is comfortable and shadbala says how much it can do. The
avasthas answer a third question the other two do not: how much of what it promises
actually arrives. A planet can sit exalted, strong by every measure, and still be in the
first six degrees of its sign, which the texts read as an infant — a quarter of its
results, however good they would otherwise be.

Three of the five sets are computed here. All three are arithmetic over facts already
on the chart, and each carries the verse that defines it:

    Baladi      v. 3-4    by degree in the sign; how much of the result arrives
    Jagradadi   v. 5-6    by dignity; how awake the planet is
    Deeptadi    v. 7-10   by dignity and company; the mood it acts in

The other two are left out. Lajjitadi turns on conditions the chapter states loosely,
and Sayanadi needs the ghati of birth and a formula whose scan is unreadable in the copy
here; guessing at either would produce a confident state with nothing behind it.
"""

from __future__ import annotations

from dataclasses import dataclass

from astro.core.ephemeris import Chart
from astro.core.strength import SEVEN, is_natural_benefic

# v. 3-4. Five states, six degrees each, running forward in odd rasis and backward in
# even ones, with the share of the result each one delivers.
BALADI = (
    ("Bala", "infant", 0.25, "a quarter of what it would otherwise give"),
    ("Kumara", "adolescent", 0.5, "half of what it would otherwise give"),
    ("Yuva", "young adult", 1.0, "the whole of what it promises"),
    ("Vriddha", "old", 0.15, "very little of what it promises"),
    ("Mrita", "dead", 0.0, "almost nothing of what it promises"),
)

# v. 5-6. Awake, dreaming, asleep — and full, medium or nil results with them.
JAGRADADI = {
    "awake": ("Jagrat", "awake and alert", "its results arrive in full"),
    "dreaming": ("Swapna", "dreaming", "its results arrive at half strength"),
    "sleeping": ("Sushupti", "asleep", "its results barely arrive"),
}

# v. 7-10, in the order the verse lists them. Seven follow the dignity ladder; two —
# Vikal and Kop — are conditions that can fall on a planet of any dignity.
DEEPTADI_BY_DIGNITY = {
    "exalted": ("Dipt", "burning bright"),
    "moolatrikona": ("Swasth", "at home"),
    "own": ("Swasth", "at home"),
    "great_friend": ("Pramudit", "delighted"),
    "friend": ("Shanta", "at peace"),
    "neutral": ("Din", "flat"),
    "enemy": ("Duhkhit", "unhappy"),
    "great_enemy": ("Khal", "ill-tempered"),
    "debilitated": ("Khal", "ill-tempered"),
}
VIKAL = ("Vikal", "crippled")
KOP = ("Kop", "furious")

KNOWN_VARIANTS = {
    "deeptadi_precedence": (
        "v. 7-10 lists the nine states without saying which wins when two apply — a "
        "graha in a friendly rasi that also sits with a malefic answers to both Shanta "
        "and Vikal. The two conditions are taken to override the dignity ladder, and "
        "Kop to override Vikal, on the reading that being burnt by the Sun is the "
        "loudest thing that can be said about a planet. The verse does not say so."
    ),
    "dipt_and_moolatrikona": (
        "BPHS puts Dipt on exaltation alone. Charak (p. 171) gives it to a graha in "
        "exaltation *or its moolatrikona*. BPHS is followed, so a moolatrikona graha "
        "reads as Swasth here and as Dipt in an implementation following Charak."
    ),
    "baladi_by_drekkana": (
        "Some reckon the baladi state from the drekkana of the sign rather than from "
        "six-degree steps, as the Avasthas monograph notes. The six-degree reading is "
        "BPHS ch. 45 v. 3 and is what is used."
    ),
}


@dataclass(frozen=True)
class Avasthas:
    body: str
    baladi: str
    baladi_plain: str
    share: float
    delivers: str
    jagradadi: str
    jagradadi_plain: str
    arrives: str
    deeptadi: str
    deeptadi_plain: str


def baladi(chart: Chart, body: str) -> tuple[str, str, float, str]:
    """Which sixth of the sign the graha stands in, counted the way the sign runs."""
    position = chart.positions[body]
    step = int(position.degree_in_sign // 6.0)
    step = min(step, 4)
    # Odd rasis run forward, even ones backward. Aries is sign 0 here and is odd.
    if position.sign % 2 == 1:
        step = 4 - step
    return BALADI[step]


def jagradadi(dignity: str) -> tuple[str, str, str]:
    if dignity in ("exalted", "own", "moolatrikona"):
        return JAGRADADI["awake"]
    if dignity in ("great_friend", "friend", "neutral"):
        return JAGRADADI["dreaming"]
    return JAGRADADI["sleeping"]


def deeptadi(chart: Chart, body: str, dignity: str, combust: bool) -> tuple[str, str]:
    """The mood the graha acts in.

    Combustion wins, then malefic company, then the dignity ladder — a precedence the
    verse does not state; see KNOWN_VARIANTS["deeptadi_precedence"].
    """
    if combust:
        return KOP
    sign = chart.positions[body].sign
    with_malefic = any(
        other != body
        and chart.positions[other].sign == sign
        and not is_natural_benefic(chart, other)
        for other in SEVEN
    )
    if with_malefic:
        return VIKAL
    return DEEPTADI_BY_DIGNITY.get(dignity, ("Din", "flat"))


def avasthas(chart: Chart, body: str, dignity: str, combust: bool) -> Avasthas:
    state, plain, share, delivers = baladi(chart, body)
    awake, awake_plain, arrives = jagradadi(dignity)
    mood, mood_plain = deeptadi(chart, body, dignity, combust)
    return Avasthas(
        body=body,
        baladi=state, baladi_plain=plain, share=share, delivers=delivers,
        jagradadi=awake, jagradadi_plain=awake_plain, arrives=arrives,
        deeptadi=mood, deeptadi_plain=mood_plain,
    )


def payload(state: Avasthas) -> dict:
    return {
        "baladi": state.baladi,
        "baladi_plain": state.baladi_plain,
        "share": state.share,
        "delivers": state.delivers,
        "jagradadi": state.jagradadi,
        "jagradadi_plain": state.jagradadi_plain,
        "arrives": state.arrives,
        "deeptadi": state.deeptadi,
        "deeptadi_plain": state.deeptadi_plain,
    }
