"""The chara karakas — BPHS ch. 32.

Every other layer in this project reads the chart by house and by sign. This one reads
it by degree alone: rank the grahas by how far each has travelled into whatever sign it
occupies, and the order they come out in assigns them roles — the soul, the counsellor,
the sibling, the mother, and so on down. Nothing about where they sit matters.

It is worth having because it says something none of the rest does. A reader can be told
which single planet their chart runs through, and it is not the one ruling their
ascendant or the one strongest by shadbala; it is whichever has gone furthest into its
sign, which is a fact about them and about nobody born in a different minute.
"""

from __future__ import annotations

from astro.core.ephemeris import Chart

# v. 13-17, in the order the verse lists them, and what each one signifies.
KARAKAS = (
    ("Atma Karaka", "the self", "the chart's own ruler — its concerns run through it"),
    ("Amatya Karaka", "the counsellor", "career, and whoever advises the native"),
    ("Bhratru Karaka", "siblings", "brothers, sisters, and the native's courage"),
    ("Matru Karaka", "the mother", "the mother, and the comfort of home"),
    ("Pitru Karaka", "the father", "the father, and inherited fortune"),
    ("Putra Karaka", "children", "children, and what the native creates"),
    ("Gnati Karaka", "obstacles", "rivals, illness, and what has to be overcome"),
    ("Stri Karaka", "the partner", "the husband or wife"),
)

# v. 1-2 records the disagreement and v. 3-8 gives Rahu's rule, so the eight-karaka
# scheme is the one implemented.
BODIES = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu")

KNOWN_VARIANTS = {
    "seven_or_eight": (
        "v. 1-2 says the karakas come 'from among the 7 Grahas, viz. Sūrya to Śani', "
        "then reports that some include Rahu always and some only on a tie. Eight are "
        "used here, because v. 3-8 goes on to give Rahu's own rule — deduct his "
        "longitude in the sign from 30 — and v. 13-17 names eight karakas, which the "
        "seven-graha reading cannot fill. An implementation using seven drops Stri "
        "Karaka and shifts every role below Rahu up by one."
    ),
    "matru_and_putra": (
        "v. 13-17: 'Some consider Matru Karak and Putr Karak, as identical.' Kept "
        "separate here, as the verse's own list does."
    ),
}


def _reach(chart: Chart, body: str) -> float:
    """How far into its sign the graha has travelled.

    Rahu counts backwards — 30 less its degree — because it moves that way, which is
    v. 3-8's rule and the reason it can be ranked beside the rest at all.
    """
    degree = chart.positions[body].degree_in_sign
    return 30.0 - degree if body == "Rahu" else degree


def chara_karakas(chart: Chart) -> dict[str, dict]:
    """Which graha holds each role, ranked by degree travelled.

    Ties are possible and the verse says what they mean: two grahas on the same
    longitude take the same karaka and the list comes up one short. Rather than break
    the tie arbitrarily, both are reported under the role and the shortfall is left
    visible.
    """
    ranked = sorted(BODIES, key=lambda body: -_reach(chart, body))
    out: dict[str, dict] = {}
    for index, body in enumerate(ranked):
        if index >= len(KARAKAS):
            break
        name, plain, means = KARAKAS[index]
        out[name] = {
            "body": body,
            "plain": plain,
            "means": means,
            "degree": round(_reach(chart, body), 4),
            "counted_backwards": body == "Rahu",
        }
    return out


def atma_karaka(chart: Chart) -> str:
    """The graha the whole chart is said to run through."""
    return max(BODIES, key=lambda body: _reach(chart, body))


def payload(chart: Chart) -> dict:
    karakas = chara_karakas(chart)
    return {
        "atma_karaka": atma_karaka(chart),
        "karakas": [
            {"role": role, **detail} for role, detail in karakas.items()
        ],
    }
