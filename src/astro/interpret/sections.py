"""What a reading is made of, and the facts each part is written from.

A reading is nine sections: an overview, one for each life area, the years ahead, and
remedies. Each is generated separately, which keeps a failure local — a section that
comes back ungrounded is dropped and the deterministic text shows in its place, rather
than poisoning the whole reading.

The important decision here is that **facts are handed to the model up front** rather
than left for it to fetch. Asked cold, an eight-billion-parameter model spends four or
five tool round trips assembling what this module can assemble in microseconds, and each
round trip is thirty seconds and another chance to misattribute. Pre-loading turns a
section into one call. The tools stay available for anything further it wants.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from astro.core.ephemeris import SIGNS
from astro.interpret.glossary import vocabulary_instructions
from astro.interpret.life_stages import DOMAINS, life_stages
from astro.service import NatalChart, jd_to_iso, now_jd

# How far ahead the timeline sections look.
HORIZON_YEARS = 10


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    question: str  # what this section answers, in the reader's words
    facts: Callable[[NatalChart], dict]
    instruction: str


def _condition(natal: NatalChart, body: str) -> dict:
    """One planet's standing, with keys that cannot be misread.

    "sign" and "house" are ambiguous next to a house's own sign: a model reads the
    house's sign and attributes it to the ruler, and writes "Mars in Aries" about a Mars
    that is in Scorpio. The keys say whose sign it is.
    """
    condition = natal.facts.condition[body]
    return {
        "planet": body,
        "this_planet_stands_in_sign": SIGNS[condition.sign],
        "this_planet_stands_in_house": condition.house,
        "condition": condition.dignity,
        "combust": condition.combust,
        "retrograde": condition.retrograde and body not in ("Rahu", "Ketu"),
        "rules_houses": list(condition.owns_houses),
    }


def _overview_facts(natal: NatalChart) -> dict:
    facts = natal.facts
    chart = natal.chart
    reference = now_jd()
    from astro.core.dasha import chain_at

    chain = chain_at(natal.dashas, reference)
    return {
        "name": natal.profile.name,
        "rising_sign": SIGNS[chart.lagna_sign],
        "moon_sign": chart.positions["Moon"].sign_name,
        "moon_nakshatra": chart.positions["Moon"].nakshatra_name,
        "chart_ruler": _condition(natal, facts.lagna_lord),
        "most_helpful_planet": list(facts.yogakarakas),
        "strongest_planets": [
            _condition(natal, body)
            for body in facts.condition
            if facts.condition[body].is_strong
        ],
        "weakest_planets": [
            _condition(natal, body)
            for body in facts.condition
            if facts.condition[body].is_weak
        ],
        "current_period": [
            {"level": period.level_name, "planet": period.lord,
             "until": jd_to_iso(period.end_jd)[:10]}
            for period in chain
        ],
        "combinations_present": [
            {"name": rule["name"], "meaning": rule["plain"], "source": rule["citation"]}
            for rule in _yogas(natal)
        ],
    }


def _yogas(natal: NatalChart) -> list[dict]:
    from astro.service import yoga_payload

    return yoga_payload(natal)


def _domain_facts(domain: str) -> Callable[[NatalChart], dict]:
    def build(natal: NatalChart) -> dict:
        facts = natal.facts
        houses = DOMAINS[domain]["houses"]
        start = now_jd()
        stages = life_stages(facts, natal.dashas, start, start + HORIZON_YEARS * 365.25)

        return {
            "life_area": domain,
            "why_these_houses": DOMAINS[domain]["why"],
            "houses": [
                {
                    "house_number": house,
                    "this_house_occupies_the_sign": SIGNS[facts.sign_of_house(house)],
                    "planets_standing_in_this_house": list(facts.occupants(house)),
                    "this_house_is_ruled_by": _condition(natal, facts.lord_of(house)),
                    "support_points_out_of_56": facts.sav_of_house(house),
                    "planets_aspecting_this_house": list(facts.bodies_aspecting(house)),
                }
                for house in houses
            ],
            "chapters_ahead": [
                {
                    "from": jd_to_iso(stage.start_jd)[:10],
                    "to": jd_to_iso(stage.end_jd)[:10],
                    "ruling_planets": list(stage.ruling),
                    "score_for_this_area": next(
                        reading.score for reading in stage.domains
                        if reading.domain == domain
                    ),
                    "reasons": [
                        driver.text for reading in stage.domains
                        if reading.domain == domain for driver in reading.drivers
                    ],
                }
                for stage in stages[:6]
            ],
            "relevant_combinations": [
                rule for rule in _yogas(natal) if domain in rule["domains"]
            ],
        }

    return build


def _timeline_facts(natal: NatalChart) -> dict:
    start = now_jd()
    stages = life_stages(natal.facts, natal.dashas, start, start + HORIZON_YEARS * 365.25)
    return {
        "chapters": [
            {
                "from": jd_to_iso(stage.start_jd)[:10],
                "to": jd_to_iso(stage.end_jd)[:10],
                "years": round(stage.years, 1),
                "ruling_planets": list(stage.ruling),
                "opens_with": list(stage.opened_by),
                "areas": {
                    reading.domain: {
                        "score": reading.score,
                        "reasons": [driver.text for driver in reading.drivers],
                    }
                    for reading in stage.domains
                },
            }
            for stage in stages
        ]
    }


def _remedy_facts(natal: NatalChart) -> dict:
    from astro.interpret.remedies import remedies_payload

    payload = remedies_payload(natal.facts)
    return {
        "remedies": payload["by_source"],
        "nothing_indicated": payload["nothing_indicated"],
        "disclaimer": payload["disclaimer"],
    }


COMMON = (
    "You are writing part of a reading of one person's birth chart, for that person.\n\n"
    + vocabulary_instructions()
    + "\n\nRules:\n"
    "1. Everything you say must rest on the facts given below or on a tool call. Never "
    "state a position, house or period from your own knowledge.\n"
    "2. Write in plain, direct sentences. No lists of adjectives, no horoscope filler, "
    "no flattery.\n"
    "3. Say what it means for the person's life before naming any planet.\n"
    "4. Where the facts are mixed or point both ways, say so. Do not resolve a "
    "tension that is really there.\n"
    "5. A house's sign and the sign its ruling planet stands in are different things, "
    "and the ruler is usually somewhere else entirely. Read the key names carefully "
    "before saying any planet is in any sign.\n"
    "6. Never predict death, diagnose illness, or advise on medical, legal or "
    "financial decisions.\n"
    "7. No headings, no bullet lists. Flowing paragraphs.\n"
)

SECTIONS: tuple[Section, ...] = (
    Section(
        key="overview",
        title="The shape of this chart",
        question="What kind of chart is this, in five sentences?",
        facts=_overview_facts,
        instruction=(
            "Write five or six sentences describing this chart as a whole: the "
            "temperament it suggests, what it is built to do well, and where it is "
            "under strain. Mention the period running now and when it ends. Do not list "
            "placements — characterise the person."
        ),
    ),
    *(
        Section(
            key=domain.lower(),
            title=domain,
            question=f"What does this chart say about {domain.lower()}?",
            facts=_domain_facts(domain),
            instruction=(
                f"Write two or three paragraphs about {domain.lower()}. Cover what this "
                "area is like for them, what supports it, what strains it, and when the "
                "next real change falls, with the date. Use the chapters given to say "
                "what is coming rather than speaking only in generalities. If the "
                "supports and strains are evenly matched, say that plainly."
            ),
        )
        for domain in DOMAINS
    ),
    Section(
        key="timeline",
        title="The years ahead",
        question="What is coming, and when?",
        facts=_timeline_facts,
        instruction=(
            "Write a short narrative of the next ten years, chapter by chapter, in "
            "order. For each, give the dates, what changes at the start of it, and the "
            "one or two areas of life it speaks to most. Keep each chapter to two or "
            "three sentences."
        ),
    ),
    Section(
        key="remedies",
        title="What the texts suggest",
        question="Is there anything to be done?",
        facts=_remedy_facts,
        instruction=(
            "Describe the remedies indicated, what each is for, and where it comes "
            "from. Be plain that these are traditional observances recorded in the "
            "classical literature and not medical, financial or legal advice. If "
            "nothing is indicated, say so in one sentence and stop."
        ),
    ),
)

BY_KEY = {section.key: section for section in SECTIONS}
