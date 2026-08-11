"""The read-only chart tools a question-answering model may call.

The model is never handed the whole chart as a blob. It asks for what it needs — one
house, one graha, the dasha at a date — and each answer comes back as computed facts
with the placements attached. That keeps the context small, makes the reasoning
traceable, and means the model cannot assert a position that was never computed.

Every function here is pure and side-effect free, so the tool surface is fully testable
without a model in the loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Any, Callable

from astro.core.dasha import DashaPeriod, chain_at
from astro.core.ephemeris import SIGNS, Chart
from astro.core.facts import ChartFacts
from astro.core.transit import contacts, gochara
from astro.corpus.search import search as search_corpus
from astro.interpret.life_stages import DOMAINS, LifeStage, current_stage


@dataclass(frozen=True)
class ChartTools:
    """A bundle of read-only lookups bound to one native's chart."""

    facts: ChartFacts
    dashas: tuple[DashaPeriod, ...]
    stages: list[LifeStage]
    profile_name: str

    @property
    def chart(self) -> Chart:
        return self.facts.chart

    @cached_property
    def shadbala(self) -> dict:
        """The six-fold strengths, computed once per chart rather than per lookup.

        A question can call get_planet nine times; shadbala touches seven vargas and
        every pairwise aspect, so recomputing it each time would be the slowest thing
        in the loop for no gain.
        """
        from astro.core.panchanga import day_span
        from astro.core.shadbala import shadbala as compute

        chart = self.chart
        return compute(chart, day_span(chart.jd_ut, chart.latitude, chart.longitude))

    # --- placements ---------------------------------------------------------

    def get_house(self, house: int) -> dict:
        """What a house holds, who rules it, and how well supported it is."""
        if not isinstance(house, int) or isinstance(house, bool) or not 1 <= house <= 12:
            raise ValueError(f"house must be a whole number 1-12, got {house!r}")
        lord = self.facts.lord_of(house)
        # The lord's facts are nested under "lord" rather than sitting as siblings of
        # the house's own. Naming them apart was not enough: a model still merged
        # "house_aspected_by" into the lord's aspects and reported Mercury as aspected
        # by Saturn and Rahu, which reach the 7th house but not Mercury three signs
        # away. Nesting makes the ownership structural instead of a matter of reading
        # the key carefully.
        return {
            "house": house,
            "sign": SIGNS[self.facts.sign_of_house(house)],
            "occupants": list(self.facts.occupants(house)),
            "house_aspected_by": list(self.facts.bodies_aspecting(house)),
            "lord": {
                "name": lord,
                # The lord's own sign, not the house's. Without it a model infers the
                # lord sits in the house it rules and says so — "Mercury in Virgo, its
                # own sign" when Mercury is actually in Capricorn.
                "sign": SIGNS[self.facts.sign_of(lord)],
                "placed_in_house": self.facts.lord_placed_in(house),
                "dignity": self.facts.dignity(lord),
                "aspected_by": [
                    body
                    for body in self.facts.condition
                    if body != lord and self.facts.aspects_body(body, lord)
                ],
            },
            "ashtakavarga_points": self.facts.sav_of_house(house),
            "domains": [
                domain
                for domain, definition in DOMAINS.items()
                if house in definition["houses"]
            ],
        }

    def get_planet(self, body: str) -> dict:
        """One graha's placement and condition."""
        if body not in self.facts.condition:
            # Name the valid options: a model that guessed "10th house" here can
            # recover from this, where a bare rejection just makes it give up.
            raise ValueError(
                f"unknown graha {body!r}. Valid names are "
                f"{', '.join(self.facts.condition)}. To find the planet ruling a house, "
                "call get_house first and use the 'lord' it returns."
            )
        condition = self.facts.condition[body]
        return {
            "planet": body,
            "sign": SIGNS[condition.sign],
            "house": condition.house,
            "degree_in_sign": round(
                self.chart.positions[body].degree_in_sign, 4
            ),
            "nakshatra": self.chart.positions[body].nakshatra_name,
            "pada": self.chart.positions[body].pada,
            "dignity": condition.dignity,
            "retrograde": condition.retrograde,
            "combust": condition.combust,
            "benefic": condition.is_benefic,
            "rules_houses": list(condition.owns_houses),
            "aspects_houses": list(condition.aspects_houses),
            "vargottama": self.facts.is_vargottama(body),
            # Dignity says how comfortable the graha is; shadbala says how much it can
            # actually do. They disagree often enough that answering "is my Saturn
            # strong?" from dignity alone is wrong about as often as it is right.
            "strength": self._strength(body),
        }

    def _strength(self, body: str) -> dict | None:
        """Shadbala for one graha, as a fraction of what it needs.

        None for the nodes, which the chapter assigns no strength — better than a zero
        the model would read as "very weak".
        """
        balas = self.shadbala
        if balas is None or body not in balas:
            return None
        bala = balas[body]
        return {
            "shadbala_rupas": round(bala.rupas, 2),
            "needed_rupas": round(bala.required / 60.0, 2),
            "share_of_what_it_needs": round(bala.ratio, 2),
            "verdict": "strong enough" if bala.strong else "short of its minimum",
        }

    # --- time ---------------------------------------------------------------

    def get_dasha_at(self, jd: float) -> dict:
        """The nested dasha periods running at a moment."""
        from astro.service import jd_to_iso

        chain = chain_at(self.dashas, jd)
        return {
            "date": jd_to_iso(jd),
            "periods": [
                {
                    "level": period.level_name,
                    "lord": period.lord,
                    "start": jd_to_iso(period.start_jd),
                    "end": jd_to_iso(period.end_jd),
                }
                for period in chain
            ],
        }

    def get_life_stage(self, jd: float) -> dict | None:
        """The life chapter covering a moment, with its scores and their drivers."""
        from astro.service import jd_to_iso

        stage = current_stage(self.stages, jd)
        if stage is None:
            return None
        return {
            "start": jd_to_iso(stage.start_jd),
            "end": jd_to_iso(stage.end_jd),
            "headline": stage.headline(),
            "mahadasha": stage.mahadasha,
            "antardasha": stage.antardasha,
            "opened_by": list(stage.opened_by),
            "domains": [
                {
                    "domain": reading.domain,
                    "score": reading.score,
                    "verdict": reading.verdict,
                    "drivers": [driver.text for driver in reading.drivers],
                }
                for reading in stage.domains
            ],
        }

    def get_transits_at(self, jd: float) -> dict:
        """Transit standing and contacts with the natal chart at a moment."""
        standings = gochara(self.chart, self.facts.ashtakavarga, jd)
        return {
            "gochara": {
                body: {
                    "sign": standing.sign_name,
                    "house_from_moon": standing.house_from_moon,
                    "bindus": standing.bindus,
                    "supported": standing.supported,
                    "traditionally_good": standing.traditionally_good,
                }
                for body, standing in standings.items()
            },
            "contacts": [
                {
                    "transiting": contact.transiting,
                    "natal_point": contact.natal_point,
                    "kind": contact.kind,
                }
                for contact in contacts(self.chart, jd)
            ],
        }

    # --- findings and sources -----------------------------------------------

    def get_yogas(self) -> list[dict]:
        from astro.service import rules

        from astro.rules.engine import apply_rules

        return [
            {
                "name": finding.rule.name,
                "plain": " ".join(finding.rule.plain.split()),
                "citation": finding.citation,
                "citation_located": finding.rule.citation.located,
                "evidence": list(finding.evidence),
            }
            for finding in apply_rules(rules(), self.facts)
        ]

    def search_scripture(self, term: str, limit: int = 5) -> list[dict]:
        """Passages from the ingested texts containing a term."""
        return [
            {
                "citation": hit.citation,
                "chapter_title": hit.chapter_title,
                "heading": hit.heading,
                "text": hit.body,
            }
            for hit in search_corpus(term, limit=limit)
        ]


def tool_definitions() -> list[dict]:
    """JSON-schema definitions for the tools.

    Written in the Anthropic tool shape; `qa.ollama_tools()` converts them to the
    OpenAI-style envelope Ollama expects rather than keeping a second copy. Kept next to
    the implementations so the two cannot drift apart; a test asserts that every
    advertised tool can actually be dispatched and vice versa.
    """
    return [
        {
            "name": "get_house",
            "description": (
                "What a house of the birth chart contains: its sign, occupants, ruling "
                "planet, where that ruler sits, what aspects it, and its ashtakavarga "
                "support."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "house": {"type": "integer", "minimum": 1, "maximum": 12}
                },
                "required": ["house"],
            },
        },
        {
            "name": "get_planet",
            "description": "One planet's sign, house, nakshatra, dignity and condition.",
            "input_schema": {
                "type": "object",
                "properties": {"body": {"type": "string"}},
                "required": ["body"],
            },
        },
        {
            "name": "get_dasha_at",
            "description": "The planetary periods running on a given date.",
            "input_schema": {
                "type": "object",
                "properties": {"jd": {"type": "number"}},
                "required": ["jd"],
            },
        },
        {
            "name": "get_life_stage",
            "description": (
                "The life chapter covering a date, with per-domain scores and the "
                "specific placements that produced each score."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"jd": {"type": "number"}},
                "required": ["jd"],
            },
        },
        {
            "name": "get_transits_at",
            "description": "Transit positions and their contacts with the natal chart.",
            "input_schema": {
                "type": "object",
                "properties": {"jd": {"type": "number"}},
                "required": ["jd"],
            },
        },
        {
            "name": "get_yogas",
            "description": "The classical combinations present in this chart, with citations.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "search_scripture",
            "description": (
                "Search the ingested classical texts for a term and return the matching "
                "passages with their chapter and verse."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "term": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                "required": ["term"],
            },
        },
    ]


def _coerce(name: str, arguments: dict) -> dict:
    """Cast arguments to the types the schema declares.

    Models routinely send `{"house": "7"}` for an integer parameter — small local ones
    almost always do. Rejecting that is pedantry: the schema says what the type is, so
    the boundary should convert rather than bounce it back and burn a round. Anything
    that will not convert is left alone, so the tool still raises a clear error.
    """
    schema = next(
        (
            definition.get("input_schema", {})
            for definition in tool_definitions()
            if definition["name"] == name
        ),
        {},
    )
    casts = {"integer": int, "number": float, "string": str, "boolean": bool}
    converted = dict(arguments)
    for key, spec in schema.get("properties", {}).items():
        if key not in converted:
            continue
        cast = casts.get(spec.get("type", ""))
        if cast is None or isinstance(converted[key], cast):
            continue
        try:
            converted[key] = cast(converted[key])
        except (TypeError, ValueError):
            pass  # leave it; the tool's own validation will report it properly
    return converted


def dispatch(tools: ChartTools, name: str, arguments: dict) -> Any:
    """Run one advertised tool by name."""
    handlers: dict[str, Callable[..., Any]] = {
        "get_house": tools.get_house,
        "get_planet": tools.get_planet,
        "get_dasha_at": tools.get_dasha_at,
        "get_life_stage": tools.get_life_stage,
        "get_transits_at": tools.get_transits_at,
        "get_yogas": tools.get_yogas,
        "search_scripture": tools.search_scripture,
    }
    if name not in handlers:
        raise ValueError(f"unknown tool {name!r}; known: {sorted(handlers)}")
    return handlers[name](**_coerce(name, arguments))
