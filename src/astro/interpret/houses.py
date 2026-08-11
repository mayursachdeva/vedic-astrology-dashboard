"""Everything one house of the chart has to say, gathered in one place.

A reader who clicks the ninth house wants one answer, not six lookups: what this part of
life is, what its sign does to it, who runs it and where that ruler has gone, who is
standing in it and what that does, what star those planets fall in, whether the whole
arrangement is working, and what the texts prescribe if it is not.

Nothing here is written by this module. The significations, the sign's character, the
effect of the lord's placement, the classical verses on a graha in this bhava, the
nakshatra's nature, the mantra and the daily observance all come from the ingested texts
through `corpus.index`, and arrive with the chapter and verse attached. What this module
adds is the arithmetic — dignity, strength, support, aspects — and the joining sentences
that say which passage applies and why.

That division matters. It is the reason a reading of a house cannot say something the
library does not, and the reason every claim on the screen can be opened and checked.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from astro.corpus import index as texts
from astro.core.ephemeris import SIGNS, Chart
from astro.core.avastha import avasthas as compute_avasthas
from astro.core.avastha import payload as avastha_payload
from astro.core.facts import ChartFacts
from astro.core.shadbala import Bala, BhavaBala
from astro.core.strength import (
    SEVEN, compound_relation, natural_relation, sign_lord, temporal_relation,
)
from astro.core.varga import VARGA_PURPOSE, navamsa_class, varga_chart
from astro.interpret.glossary import HOUSE_MEANINGS, plainly
from astro.interpret.life_stages import DIGNITY_PHRASES, houses_named

# A placement the texts would call weak, and the point at which this module starts
# offering what they prescribe for it. Anything gentler is left alone: a remedy attached
# to every planet in every house is noise, and reads as a shop rather than a reading.
POOR_DIGNITIES = ("debilitated", "great_enemy", "enemy")

ORDINALS = {
    1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth",
    7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth", 11: "eleventh", 12: "twelfth",
}


# The scan of BPHS renders every apostrophe as a low double quote, so "Karm's Lord"
# comes out as "Karm‟s Lord" and lands on the screen as Karm"s. Fixed at the point the
# text leaves the corpus, not in the corpus, which stays as it was scanned.
_SCANNED_QUOTES = str.maketrans({"‟": "’", "„": "’", "‛": "’"})


def _cite(hit) -> dict | None:
    if hit is None:
        return None
    return {
        "text": " ".join(hit.body.split()).translate(_SCANNED_QUOTES),
        "citation": hit.citation,
        "work": hit.work,
        "chapter": hit.chapter,
        "verse": hit.verses,
        "page": hit.page,
    }


@dataclass(frozen=True)
class Occupant:
    body: str
    sign: str
    degree: float
    house: int
    dignity: str
    plain: str
    retrograde: bool
    combust: bool
    rules: tuple[int, ...]
    reaches: tuple[int, ...]
    vargottama: bool
    varga_class: dict | None
    rasi_house: int
    standing: str
    reasons: tuple[str, ...]
    nakshatra: dict
    strength: dict | None
    avastha: dict
    classical: tuple[dict, ...]


@dataclass(frozen=True)
class HouseReading:
    house: int
    varga: str
    sign: int
    sign_name: str
    headline: str
    represents: dict | None
    sign_says: dict | None
    lord: dict
    occupants: tuple[Occupant, ...]
    aspected_by: tuple[dict, ...]
    support: dict | None
    strength: dict | None
    read_for: dict | None
    verdict: str
    verdict_because: tuple[str, ...]
    remedies: tuple[dict, ...] = field(default_factory=tuple)


def _standing(
    facts: ChartFacts, body: str, bala: Bala | None
) -> tuple[str, tuple[str, ...]]:
    """Whether a graha is in a position to deliver, and what says so.

    Two independent measures, because they disagree often: dignity says how comfortable
    it is, shadbala says how much it can actually do. A planet failing both is the one
    worth prescribing for.
    """
    condition = facts.condition[body]
    reasons: list[str] = []
    against = 0

    if condition.dignity in POOR_DIGNITIES:
        reasons.append(f"{body} {DIGNITY_PHRASES.get(condition.dignity, condition.dignity)}")
        against += 1
    if condition.combust:
        reasons.append(f"{body} is hidden by the Sun's glare (combust)")
        against += 1
    if bala is not None and not bala.strong:
        reasons.append(
            f"{body} has {round(bala.ratio * 100)}% of the strength the texts ask of it"
        )
        against += 1

    if against == 0:
        if condition.dignity in ("exalted", "moolatrikona", "own"):
            reasons.append(f"{body} {DIGNITY_PHRASES.get(condition.dignity, '')}")
        if bala is not None and bala.strong:
            reasons.append(f"{body} has the strength to act ({round(bala.ratio * 100)}%)")
        return "well placed", tuple(r for r in reasons if r.strip())
    return ("under pressure" if against == 1 else "poorly placed"), tuple(reasons)


def _occupant(
    facts: ChartFacts, chart: Chart, body: str, house: int, balas: dict[str, Bala],
    table=None,
) -> Occupant:
    """One graha standing in the house.

    In a divisional chart the sign and house are the division's; the dignity, the
    strength and the star stay the birth chart's, because that is where they are defined
    and quietly recomputing them against a varga sign would report a different planet.
    The payload says which is which so a reader is not left to assume.
    """
    position = chart.positions[body]
    condition = facts.condition[body]
    sign_here = table.sign_name(body) if table else position.sign_name
    bala = balas.get(body)
    standing, reasons = _standing(facts, body, bala)

    # In a division the dignity that matters is the one in the divisional sign, not the
    # birth chart's. Reporting "neutral" beside a navamsa sign the graha is exalted in
    # described a different planet.
    dignity = (
        _dignity_in(facts, body, table.signs[body]) if table else condition.dignity
    )

    note = texts.nakshatra_note(position.nakshatra_name)
    strength = None
    if bala is not None:
        strength = {
            "rupas": round(bala.rupas, 2),
            "needed": round(bala.required / 60.0, 2),
            "ratio": round(bala.ratio, 2),
            "strong": bala.strong,
        }

    return Occupant(
        body=body,
        sign=sign_here,
        degree=round(position.degree_in_sign, 2),
        house=house,
        dignity=dignity,
        plain=DIGNITY_PHRASES.get(dignity, dignity.replace("_", " ")),
        retrograde=position.retrograde,
        combust=condition.combust,
        # What it answers for and what it reaches, which used to live in a separate
        # planet card. That card fought this reading for the same pixels and lost;
        # everything it said is here, with more behind it.
        rules=tuple(condition.owns_houses),
        reaches=tuple(condition.aspects_houses),
        # The one fact the ninth-part chart exists to surface: the same sign in both.
        vargottama=facts.is_vargottama(body),
        # ch. 6 v. 12 — every navamsa is divine, human or devilish.
        varga_class=(
            dict(zip(("name", "plain"), navamsa_class(position.longitude)))
            if table and table.divisor == 9 else None
        ),
        # Where it stands in the birth chart, which is what conduct is keyed to even
        # while a division is being read.
        rasi_house=facts.house_of(body),
        standing=standing,
        reasons=reasons,
        nakshatra={
            "name": position.nakshatra_name,
            "pada": position.pada,
            "says": _cite(note),
        },
        strength=strength,
        # How much of what it promises actually arrives, and in what mood — the third
        # question, which dignity and shadbala between them do not answer.
        avastha=avastha_payload(
            compute_avasthas(chart, body, condition.dignity, condition.combust)
        ),
        # BPHS has no planet-by-house table, but its chapter on this bhava names grahas
        # in its conditions. Those are the classical statements that bear on this
        # placement, and they are shown as found rather than summarised.
        classical=tuple(
            _cite(hit) for hit in texts.verses_naming(house, body)[:3]
        ),
    )


def _guidance(body: str, house: int, standing: str, why: tuple[str, ...]) -> dict:
    """Everything the library prescribes around one graha in one house.

    Offered for every graha the house involves, not only the struggling ones. Gating it
    on trouble meant nine houses out of twelve showed nothing at all — no conduct, no
    mantra, nothing to do — which is not the same as there being nothing to say. What
    the gate now decides is emphasis: `indicated` marks the graha the texts would have
    you attend to first.
    """
    conduct = texts.conduct(body, house)
    profile = texts.planet_profile(body)
    practice = texts.practice(body)
    return {
        "body": body,
        "indicated": standing != "well placed",
        "because": list(why),
        # Lal Kitab's measures for this graha in this house: things to do and not do,
        # rather than a rite. This is the part a reader can act on tomorrow.
        # The spread comes first: `_cite` carries a "text" of its own — the whole
        # page — and putting it second silently replaced the cell with the page.
        "conduct": (
            {**_cite(conduct[1]), "text": conduct[0].translate(_SCANNED_QUOTES)}
            if conduct else None
        ),
        # What the graha is: its deity, its colour, and what is given away for it.
        "profile": (
            {**_cite(profile[1]), "text": profile[0].translate(_SCANNED_QUOTES)}
            if profile else None
        ),
        "mantra": texts.mantra(body),
        "practice": _cite(practice),
    }


def house_reading(
    chart: Chart,
    facts: ChartFacts,
    house: int,
    *,
    balas: dict[str, Bala],
    bhava: dict[int, BhavaBala] | None = None,
    varga: str = "D1",
) -> HouseReading:
    """Assemble the whole of one house.

    `varga` selects the chart the houses are read in. D1 is the life itself; D9 is the
    same twelve subjects read for what underlies them, so the same structure serves
    both. The measures that only exist for the birth chart — ashtakavarga support and
    bhava bala — are left out of a divisional reading rather than computed from a chart
    the texts never intended them for.
    """
    birth = varga == "D1"
    table = None if birth else varga_chart(chart, int(varga[1:]))
    if birth:
        sign = facts.sign_of_house(house)
        where = facts.house_of
    else:
        sign = (table.lagna_sign + house - 1) % 12
        where = table.house_of

    occupant_names = [body for body in (*SEVEN, "Rahu", "Ketu") if where(body) == house]
    lord = sign_lord(sign)
    lord_house = where(lord)

    occupants = tuple(
        _occupant(facts, chart, body, house, balas, table)
        for body in occupant_names
    )

    aspecting = (
        facts.bodies_aspecting(house) if birth else _varga_aspects(facts, table, house)
    )
    support = None
    if birth:
        sav = facts.sav_of_house(house)
        support = {
            "points": sav,
            "of": 56,
            "reading": "strong" if sav >= 30 else "weak" if sav <= 25 else "average",
        }

    strength = None
    if bhava is not None and birth:
        this = bhava[house]
        ranked = sorted(bhava.values(), key=lambda b: -b.total)
        rank = [b.house for b in ranked].index(house) + 1
        strength = {
            "rupas": round(this.rupas, 2),
            "rank": rank,
            "of": 12,
            # One phrasing, shared by the verdict and the panel, and always counted
            # from whichever end is shorter — "the tenth strongest" is a riddle.
            "reading": (
                f"it is the {ORDINALS[rank]} strongest of the twelve" if rank <= 6
                else f"it is the {ORDINALS[13 - rank]} weakest of the twelve"
            ),
            "parts": {
                "direction": round(this.dig, 1),
                "aspects": round(this.drik, 1),
                "its ruler": round(this.lord_bala, 1),
                "who stands in it": round(this.guests, 1),
                "the hour of birth": round(this.rising, 1),
            },
        }

    lord_standing, lord_why = _standing(facts, lord, balas.get(lord))
    lord_dignity = (
        _dignity_in(facts, lord, table.signs[lord]) if table else facts.dignity(lord)
    )
    verdict, because = _verdict(support, strength, occupants, lord, lord_standing)

    # Every graha the house involves — those standing in it and the one ruling it —
    # gets its guidance. A graha both standing here and ruling here appears once, and
    # whatever is struggling is listed first.
    involved: dict[str, tuple[str, tuple[str, ...]]] = {
        occupant.body: (occupant.standing, occupant.reasons) for occupant in occupants
    }
    involved.setdefault(lord, (lord_standing, lord_why))
    # Conduct is Lal Kitab's, and Lal Kitab is about the birth chart. Keyed to where
    # each graha actually stands there, even while a division is on screen — the
    # alternative is prescribing for a house the native does not have.
    where_really = {occupant.body: occupant.rasi_house for occupant in occupants}
    where_really.setdefault(lord, facts.house_of(lord))
    guidance = [
        _guidance(body, where_really[body], standing, why)
        for body, (standing, why) in involved.items()
    ]
    unique = sorted(guidance, key=lambda entry: not entry["indicated"])

    return HouseReading(
        house=house,
        varga=varga,
        sign=sign,
        sign_name=SIGNS[sign],
        headline=_headline(house, sign, lord, lord_house, verdict),
        represents=_cite(texts.significations(house)),
        sign_says=_sign_says(sign),
        lord={
            "name": lord,
            "sits_in_house": lord_house,
            # Both halves from the same chart. The house was the division's and the
            # sign the birth chart's, so one sentence described two different places.
            "sits_in_sign": (
                table.sign_name(lord) if table else SIGNS[chart.positions[lord].sign]
            ),
            "dignity": lord_dignity,
            "plain": DIGNITY_PHRASES.get(lord_dignity, lord_dignity.replace("_", " ")),
            "standing": lord_standing,
            "vargottama": facts.is_vargottama(lord),
            "says": _cite(texts.lord_in_house(house, lord_house)),
        },
        occupants=occupants,
        aspected_by=tuple(
            {"body": body, "benefic": facts.is_benefic(body)} for body in aspecting
        ),
        support=support,
        strength=strength,
        read_for=_read_for(varga),
        verdict=verdict,
        verdict_because=because,
        remedies=tuple(unique),
    )


def _sign_says(sign: int) -> dict | None:
    excerpt = texts.sign_excerpt(sign)
    if excerpt is None:
        return None
    text, passage = excerpt
    return {**_cite(passage), "text": text}


def _headline(house: int, sign: int, lord: str, lord_house: int, verdict: str) -> str:
    """One sentence naming the subject, the sign, and where its ruler went.

    A lord in its own house needs saying differently: "the house of work and standing,
    run by Saturn from the house of work and standing" is a circle.
    """
    where = (
        "standing in it"
        if lord_house == house
        else f"ruling it from {houses_named([lord_house])}"
    )
    return f"The house of {HOUSE_MEANINGS[house]}, in {SIGNS[sign]}, with {lord} {where}."


def _verdict(
    support: dict | None, strength: dict | None, occupants,
    lord: str, lord_standing: str,
) -> tuple[str, tuple[str, ...]]:
    """Whether this part of life is set up to work, and what says so.

    Four independent readings — the points the chart gives this house, where its
    strength ranks against the other eleven, how the grahas standing in it are doing,
    and how its ruler is doing. They are counted rather than blended, so the answer says
    which of them disagreed instead of hiding it in an average.

    The ruler counts because most houses are empty: leaving it out returned "nothing
    stands out either way" for a house whose lord was struggling, which is the one thing
    that could be said about it.
    """
    good = 0
    bad = 0
    because: list[str] = []

    if support:
        # The number alone is not a reading — 33 of 56 sat beside "third weakest" and
        # looked like a contradiction rather than the two measures disagreeing.
        if support["reading"] == "strong":
            good += 1
            because.append(f"the chart supports it well, {support['points']} of 56 points")
        elif support["reading"] == "weak":
            bad += 1
            because.append(f"the chart barely supports it, {support['points']} of 56 points")

    if strength:
        if strength["rank"] <= 4:
            good += 1
            because.append(strength["reading"])
        elif strength["rank"] >= 9:
            bad += 1
            because.append(strength["reading"])

    for occupant in occupants:
        if occupant.standing == "well placed":
            good += 1
            because.append(f"{occupant.body} stands in it well placed")
        elif occupant.standing == "poorly placed":
            bad += 1
            because.append(f"{occupant.body} stands in it poorly placed")

    if lord_standing == "well placed":
        good += 1
        because.append(f"its ruler {lord} is well placed")
    elif lord_standing == "poorly placed":
        bad += 1
        because.append(f"its ruler {lord} is poorly placed")
    else:
        # Counts for neither side, but is still the most that can be said about an
        # empty house whose measures are all middling — and it is the reason a remedy
        # is being offered further down, which would otherwise look unprompted.
        because.append(f"its ruler {lord} is under some pressure")

    if good and not bad:
        return "working", tuple(because)
    if bad and not good:
        return "needs work", tuple(because)
    if good and bad:
        return "mixed", tuple(because)
    # Neither side scored. "Mixed" would claim a disagreement that never happened —
    # nothing here is strong enough to count either way, which is its own answer.
    return "quiet", tuple(because) or ("nothing stands out either way",)


def payload(reading: HouseReading) -> dict:
    """Serialisable form, in the shape the interface reads."""
    return {
        "house": reading.house,
        "varga": reading.varga,
        "sign": reading.sign,
        "sign_name": reading.sign_name,
        "means": plainly(HOUSE_MEANINGS[reading.house]),
        "headline": reading.headline,
        "represents": reading.represents,
        "sign_says": reading.sign_says,
        "lord": reading.lord,
        "occupants": [
            {
                "body": o.body, "sign": o.sign, "degree": o.degree,
                "house": o.house,
                "dignity": o.dignity, "plain": o.plain,
                "retrograde": o.retrograde, "combust": o.combust,
                "rules": list(o.rules), "reaches": list(o.reaches),
                "standing": o.standing, "reasons": list(o.reasons),
                "nakshatra": o.nakshatra, "strength": o.strength,
                "avastha": o.avastha,
                "vargottama": o.vargottama, "varga_class": o.varga_class,
                "rasi_house": o.rasi_house,
                "classical": [c for c in o.classical if c],
            }
            for o in reading.occupants
        ],
        "aspected_by": list(reading.aspected_by),
        "support": reading.support,
        "strength": reading.strength,
        "read_for": reading.read_for,
        "verdict": reading.verdict,
        "because": list(reading.verdict_because),
        "remedies": list(reading.remedies),
        "note": None if reading.varga == "D1" else (
            f"Signs and houses here are the {reading.varga} chart's. Dignity, strength "
            "and the star a planet falls in are the birth chart's, which is where the "
            "texts define them."
        ),
    }


def _dignity_in(facts: ChartFacts, body: str, sign: int) -> str:
    """A graha's dignity in a divisional sign.

    Own sign and moolatrikona are read from the divisional sign itself; friendship is
    the compound relation, since the temporal half of it is a fact about the birth
    chart and does not move with the division. The same reading `saptavargaja_bala`
    uses, so the two cannot disagree.
    """
    from astro.core.strength import MOOLATRIKONA

    if body in MOOLATRIKONA and MOOLATRIKONA[body][0] == sign:
        return "moolatrikona"
    lord = sign_lord(sign)
    if lord == body:
        return "own"
    distance = (
        1 if lord == body
        else (facts.chart.positions[lord].sign - facts.chart.positions[body].sign) % 12 + 1
    )
    return compound_relation(
        natural_relation(body, lord), temporal_relation(distance)
    )


def _varga_aspects(facts: ChartFacts, table, house: int) -> tuple[str, ...]:
    """Who looks at this house inside the division.

    The same aspect rules, applied to the division's own signs. A divisional chart with
    no aspects at all was reporting less than it knows: the seventh is aspected in every
    chart there is.
    """
    from astro.core.strength import SPECIAL_ASPECTS

    looking = []
    for body, sign in table.signs.items():
        from_house = (sign - table.lagna_sign) % 12 + 1
        distance = (house - from_house) % 12 + 1
        if distance == 7 or distance in SPECIAL_ASPECTS.get(body, ()):
            looking.append(body)
    return tuple(looking)


def _read_for(varga: str) -> dict | None:
    """What this division is read for, in the chapter's own words (ch. 7 v. 1-8).

    Only for the divisions. The verse's entry for the birth chart is "the physique from
    Lagn", which is about the ascendant, and printing it above the seventh house said
    the birth chart is read for the body — which is the opposite of true.
    """
    if varga == "D1":
        return None
    subject = VARGA_PURPOSE.get(int(varga[1:]))
    if subject is None:
        return None
    passage = texts.varga_purposes()
    return {
        "subject": subject,
        "sentence": f"Of the sixteen divisions, this one is read for {subject}.",
        **(_cite(passage) or {}),
    }
