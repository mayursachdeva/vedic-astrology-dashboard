"""Life stages — the dashboard's main view.

Turns the dasha sequence and the slow-planet transits into a dated series of chapters,
each scored across the domains a person actually thinks in: career, relationships,
health, finance, family, learning.

Nothing here is generated prose. Every chapter's boundaries come from computed dasha
and transit dates, and every score is a sum of named drivers that are returned
alongside it. A reader who disagrees with a score can see exactly which placements
produced it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from astro.core.ashtakavarga import SAV_STRONG, SAV_WEAK
from astro.core.dasha import DashaPeriod
from astro.core.facts import ChartFacts
from astro.core.transit import gochara, sign_transits
from astro.interpret.glossary import HOUSE_MEANINGS, plain as plain_term

# Which houses speak to which part of life, from BPHS ch. 11 v. 2-13, where Parashara
# lists each bhava's indications in turn. The mapping is a reading of those verses, not
# a quotation: "profession, honour, authority" (v. 11, the 10th) is plainly career, and
# "wife, trade" (v. 8, the 7th) is plainly partnership. The verse for each house is kept
# alongside so a reader can check the leap.
DOMAINS: dict[str, dict] = {
    "Career": {
        "houses": (10, 6, 2),
        "why": "profession, honour and authority (10th); service and rivals (6th); livelihood (2nd)",
        "citation": "Brihat Parashara Hora Shastra, ch. 11, v. 11, 7, 3",
    },
    "Relationships": {
        "houses": (7, 5, 11),
        "why": "spouse and partnership (7th); affection and children (5th); gains and circles (11th)",
        "citation": "Brihat Parashara Hora Shastra, ch. 11, v. 8, 6, 12",
    },
    "Health": {
        "houses": (1, 6, 8),
        "why": "body and vigour (1st); illness (6th); longevity (8th)",
        "citation": "Brihat Parashara Hora Shastra, ch. 11, v. 2, 7, 9",
    },
    "Finance": {
        "houses": (2, 11, 9),
        "why": "wealth and possessions (2nd); income (11th); fortune (9th)",
        "citation": "Brihat Parashara Hora Shastra, ch. 11, v. 3, 12, 10",
    },
    "Family": {
        "houses": (4, 2, 3),
        "why": "mother, home and land (4th); family (2nd); siblings (3rd)",
        "citation": "Brihat Parashara Hora Shastra, ch. 11, v. 5, 3, 4",
    },
    "Learning": {
        "houses": (5, 9, 4),
        "why": "learning and knowledge (5th); religion and higher study (9th); schooling (4th)",
        "citation": "Brihat Parashara Hora Shastra, ch. 11, v. 6, 10, 5",
    },
}

# Slow movers whose sign changes are worth marking as the start of a new chapter. The
# fast planets change too often to bound anything a person would call a life stage.
CHAPTER_MARKING_BODIES = ("Saturn", "Jupiter", "Rahu")

STRONG_DIGNITIES = ("exalted", "moolatrikona", "own", "great_friend")
WEAK_DIGNITIES = ("debilitated", "great_enemy", "enemy")


def ordinal(number: int) -> str:
    """1st, 2nd, 3rd... Houses read as ordinals in every text, so they should here."""
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


# "is own" and "is great_enemy" are table keys read aloud. These are the phrasings that
# complete the sentence "Saturn rules the house of work and standing and ___".
DIGNITY_PHRASES = {
    "exalted": "is at its strongest there",
    "moolatrikona": "sits in its favourite degrees",
    "own": "rules the sign it stands in",
    "great_friend": "stands in a firmly friendly sign",
    "friend": "stands in a friendly sign",
    "neutral": "stands in a neutral sign",
    "enemy": "stands in an unfriendly sign",
    "great_enemy": "stands in a hostile sign",
    "debilitated": "is at its weakest there",
}


def dignity_phrase(dignity: str) -> str:
    return DIGNITY_PHRASES.get(dignity, readable(dignity))


def houses_named(numbers: list[int]) -> str:
    """"the house of work and standing", or two of them joined readably."""
    names = [f"the house of {HOUSE_MEANINGS[number]}" for number in numbers]
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def readable(dignity: str) -> str:
    """"great_enemy" is a table key, not something to show a reader."""
    return dignity.replace("_", " ")


@dataclass(frozen=True)
class Driver:
    """One reason a domain scored the way it did."""

    text: str
    weight: int


@dataclass(frozen=True)
class DomainReading:
    domain: str
    score: int
    drivers: tuple[Driver, ...]

    @property
    def verdict(self) -> str:
        if self.score >= 2:
            return "supported"
        if self.score <= -2:
            return "under strain"
        return "mixed"


@dataclass(frozen=True)
class LifeStage:
    """One dated chapter."""

    start_jd: float
    end_jd: float
    mahadasha: str
    antardasha: str | None
    opened_by: tuple[str, ...]
    transits: tuple[str, ...]
    domains: tuple[DomainReading, ...]

    @property
    def years(self) -> float:
        return (self.end_jd - self.start_jd) / 365.25

    @property
    def ruling(self) -> tuple[str, ...]:
        """The ruling lords, deduplicated — a graha's own sub-period inside its
        mahadasha is common, and "Saturn and Saturn" is not a sentence."""
        return tuple(
            dict.fromkeys(
                lord for lord in (self.mahadasha, self.antardasha) if lord is not None
            )
        )

    def distinguishing(self, domain: str) -> str:
        """The driver that says what is different about this chapter for an area.

        The first driver is often the ashtakavarga support figure, which does not change
        between chapters — printed down a column it repeated identically eight times and
        told the reader nothing. A driver naming one of this chapter's ruling planets
        does change, so it is preferred.
        """
        reading = next(r for r in self.domains if r.domain == domain)
        if not reading.drivers:
            return ""

        # What actually differs between consecutive chapters is the sub-period lord and
        # where the planets have moved to. The major lord holds for years, so preferring
        # any ruling planet still printed the same Saturn line down the whole column.
        def first(match) -> str | None:
            return next((d.text for d in reading.drivers if match(d.text)), None)

        return (
            (self.antardasha and self.antardasha != self.mahadasha
             and first(lambda text: text.startswith(self.antardasha)))
            or first(lambda text: "in transit right now" in text)
            or reading.drivers[0].text
        )

    @property
    def leading(self) -> DomainReading:
        """The domain this stage speaks to most loudly, in either direction."""
        return max(self.domains, key=lambda reading: (abs(reading.score), reading.domain))

    def headline(self) -> str:
        """A plain sentence, leading with what it means.

        It used to open "A Saturn and Mercury period that…", which puts two planet
        names in front of a reader before telling them anything. The meaning comes
        first now and the ruling planets follow as context.
        """
        lords = " and ".join(self.ruling)
        leading = self.leading
        if leading.score == 0:
            return f"A steady stretch, under {lords}, with no one area standing out."
        if leading.score > 0:
            return f"Good for {leading.domain.lower()} — a stretch under {lords}."
        return f"Pressure on {leading.domain.lower()} — a stretch under {lords}."


def _score_domain(facts: ChartFacts, domain: str, lords: tuple[str, ...], standings) -> DomainReading:
    """Score one domain for one set of ruling lords.

    Three things count, and each is recorded as a driver: whether a ruling lord governs
    or occupies one of the domain's houses and how well placed it is, how much support
    those houses have in the ashtakavarga, and how the ruling lords are running in
    transit right now.
    """
    houses = DOMAINS[domain]["houses"]
    drivers: list[Driver] = []
    score = 0

    for lord in lords:
        condition = facts.condition[lord]
        owned = set(condition.owns_houses) & set(houses)
        occupies = condition.house in houses

        if not owned and not occupies:
            continue

        # Built with the houses' meanings rather than their numbers. "Saturn rules the
        # 11th" tells a reader nothing; the number belongs in the technical view, where
        # it is kept.
        connection = (
            f"rules {houses_named(sorted(owned))}"
            if owned
            else f"sits in {houses_named([condition.house])}"
        )
        if condition.dignity in STRONG_DIGNITIES:
            weight = 2
            note = f"{lord} {connection} and {dignity_phrase(condition.dignity)}"
        elif condition.dignity in WEAK_DIGNITIES or condition.combust:
            weight = -2
            state = (
                f"is {plain_term('combust')}"
                if condition.combust
                else dignity_phrase(condition.dignity)
            )
            note = f"{lord} {connection} but {state}"
        else:
            weight = 1
            note = f"{lord} {connection}"

        if facts.in_dusthana(lord):
            weight -= 1
            note += f", standing in {houses_named([condition.house])}"

        score += weight
        drivers.append(Driver(text=note, weight=weight))

    primary = houses[0]
    support = facts.sav_of_house(primary)
    if support >= SAV_STRONG:
        score += 1
        drivers.append(
            Driver(
                f"{houses_named([primary]).capitalize()} has strong support "
                f"({support} of 56 points)",
                1,
            )
        )
    elif support <= SAV_WEAK:
        score -= 1
        drivers.append(
            Driver(
                f"{houses_named([primary]).capitalize()} has little support "
                f"({support} of 56 points)",
                -1,
            )
        )

    for lord in lords:
        standing = standings.get(lord)
        if standing is None or lord in ("Rahu", "Ketu"):
            continue
        if standing.supported:
            score += 1
            drivers.append(Driver(f"{lord} is well placed in transit right now", 1))
        else:
            score -= 1
            drivers.append(Driver(f"{lord} is poorly placed in transit right now", -1))

    return DomainReading(domain=domain, score=score, drivers=tuple(drivers))


def _boundaries(
    facts: ChartFacts,
    dashas: tuple[DashaPeriod, ...],
    from_jd: float,
    to_jd: float,
) -> list[tuple[float, list[str]]]:
    """Every moment in the span where a chapter could begin, and what opens it."""
    events: dict[float, list[str]] = {}

    def add(jd: float, label: str) -> None:
        if from_jd < jd < to_jd:
            events.setdefault(jd, []).append(label)

    for maha in dashas:
        add(maha.start_jd, f"{maha.lord} mahadasha begins")
        for antar in maha.children:
            add(antar.start_jd, f"{maha.lord}/{antar.lord} sub-period begins")

    for body in CHAPTER_MARKING_BODIES:
        for window in sign_transits(facts.chart, body, from_jd, to_jd)[1:]:
            add(window.start_jd, f"{window.label.replace(' in ', ' enters ')}")

    return sorted(events.items())


def life_stages(
    facts: ChartFacts,
    dashas: tuple[DashaPeriod, ...],
    from_jd: float,
    to_jd: float,
) -> list[LifeStage]:
    """The dated chapters between two moments.

    Boundaries come from dasha changes and from the slow planets changing sign; both
    are computed, never estimated. A chapter shorter than a season is folded into the
    one before it, since a six-week "life stage" is noise rather than a chapter.
    """
    if to_jd <= from_jd:
        raise ValueError("the span must end after it starts")

    edges = [(from_jd, ["the period shown begins"])] + _boundaries(
        facts, dashas, from_jd, to_jd
    )

    # Fold away anything too short to be a chapter, keeping its label on the one before.
    minimum_days = 120.0
    merged: list[tuple[float, list[str]]] = []
    for jd, labels in edges:
        if merged and jd - merged[-1][0] < minimum_days:
            merged[-1][1].extend(labels)
            continue
        merged.append((jd, list(labels)))

    built: list[LifeStage] = []
    for index, (start, labels) in enumerate(merged):
        end = merged[index + 1][0] if index + 1 < len(merged) else to_jd
        if end - start < 1.0:
            continue

        middle = (start + end) / 2.0
        chain = _chain_at(dashas, middle)
        if not chain:
            continue

        lords = tuple(dict.fromkeys(period.lord for period in chain[:2]))
        standings = gochara(facts.chart, facts.ashtakavarga, middle)

        built.append(
            LifeStage(
                start_jd=start,
                end_jd=end,
                mahadasha=chain[0].lord,
                antardasha=chain[1].lord if len(chain) > 1 else None,
                opened_by=tuple(labels),
                transits=tuple(
                    f"{body} in {standings[body].sign_name}"
                    for body in CHAPTER_MARKING_BODIES
                ),
                domains=tuple(
                    _score_domain(facts, domain, lords, standings) for domain in DOMAINS
                ),
            )
        )
    return _fold_identical(built)


def _fold_identical(stages: list[LifeStage]) -> list[LifeStage]:
    """Merge consecutive chapters that say exactly the same thing.

    Boundaries are drawn at slow-planet sign changes as well as dasha changes, but the
    scoring reads only the dasha lords' condition and transit standing. A Jupiter
    ingress can therefore split a chapter in two without changing a single score, and
    the reader is shown the same paragraph twice with different dates — which was
    happening to nearly half the timeline.

    A chapter is a change. If nothing measurable changed, it is the same chapter, so the
    two are joined and both sets of opening events are kept.
    """
    if not stages:
        return stages

    def signature(stage: LifeStage):
        return (
            stage.mahadasha,
            stage.antardasha,
            tuple((reading.domain, reading.score) for reading in stage.domains),
        )

    folded = [stages[0]]
    for stage in stages[1:]:
        previous = folded[-1]
        if signature(stage) == signature(previous):
            folded[-1] = replace(
                previous,
                end_jd=stage.end_jd,
                opened_by=previous.opened_by + stage.opened_by,
                transits=stage.transits,
            )
        else:
            folded.append(stage)
    return folded


def _chain_at(dashas: tuple[DashaPeriod, ...], jd: float) -> tuple[DashaPeriod, ...]:
    from astro.core.dasha import chain_at

    return chain_at(dashas, jd)


def current_stage(stages: list[LifeStage], jd: float) -> LifeStage | None:
    for stage in stages:
        if stage.start_jd <= jd < stage.end_jd:
            return stage
    return None
