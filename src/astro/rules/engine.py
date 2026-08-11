"""The yoga rule engine.

A rule is data: a condition tree of named predicates, plus the citation it came from.
Predicates are ordinary Python functions registered by name, so adding a rule that
needs a new test means adding one function here rather than extending a parser. There
is no expression language and no `eval` — a rule file cannot execute anything.

Every rule must carry a source citation. A rule without one is rejected at load time,
because an uncited yoga is exactly the thing this project exists to avoid.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml

from astro.core.facts import GRAHAS, ChartFacts
from astro.core.strength import DUSTHANAS, KENDRAS, TRIKONAS, UPACHAYAS

RULES_DIR = Path(__file__).resolve().parent / "yogas"

HOUSE_GROUPS = {
    "kendra": KENDRAS,
    "trikona": TRIKONAS,
    "dusthana": DUSTHANAS,
    "upachaya": UPACHAYAS,
}

Predicate = Callable[[ChartFacts, dict], bool]
_PREDICATES: dict[str, Predicate] = {}


def predicate(name: str) -> Callable[[Predicate], Predicate]:
    def register(function: Predicate) -> Predicate:
        _PREDICATES[name] = function
        return function

    return register


def _houses(value: Any) -> tuple[int, ...]:
    """Accept a house number, a list of them, or a named group like "kendra"."""
    if isinstance(value, str):
        if value not in HOUSE_GROUPS:
            raise ValueError(f"unknown house group {value!r}; expected {sorted(HOUSE_GROUPS)}")
        return HOUSE_GROUPS[value]
    if isinstance(value, int):
        return (value,)
    return tuple(int(item) for item in value)


def _bodies(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    return tuple(value)


# --- predicates -------------------------------------------------------------


@predicate("in_house")
def _in_house(facts: ChartFacts, args: dict) -> bool:
    return facts.house_of(args["body"]) in _houses(args["house"])


@predicate("in_sign")
def _in_sign(facts: ChartFacts, args: dict) -> bool:
    signs = args["sign"]
    signs = (signs,) if isinstance(signs, int) else tuple(signs)
    return facts.sign_of(args["body"]) in signs


@predicate("lagna_is")
def _lagna_is(facts: ChartFacts, args: dict) -> bool:
    signs = args["sign"]
    signs = (signs,) if isinstance(signs, int) else tuple(signs)
    return facts.lagna_sign in signs


@predicate("conjunct")
def _conjunct(facts: ChartFacts, args: dict) -> bool:
    bodies = _bodies(args["bodies"])
    first = facts.sign_of(bodies[0])
    return all(facts.sign_of(body) == first for body in bodies[1:])


@predicate("aspects_body")
def _aspects_body(facts: ChartFacts, args: dict) -> bool:
    return facts.aspects_body(args["body"], args["target"])


@predicate("aspects_house")
def _aspects_house(facts: ChartFacts, args: dict) -> bool:
    return any(facts.aspects_house(args["body"], house) for house in _houses(args["house"]))


@predicate("dignity")
def _dignity(facts: ChartFacts, args: dict) -> bool:
    return facts.dignity(args["body"]) in _bodies(args["is"])


@predicate("retrograde")
def _retrograde(facts: ChartFacts, args: dict) -> bool:
    return facts.condition[args["body"]].retrograde is bool(args.get("value", True))


@predicate("combust")
def _combust(facts: ChartFacts, args: dict) -> bool:
    return facts.condition[args["body"]].combust is bool(args.get("value", True))


@predicate("benefic")
def _benefic(facts: ChartFacts, args: dict) -> bool:
    return facts.is_benefic(args["body"]) is bool(args.get("value", True))


@predicate("vargottama")
def _vargottama(facts: ChartFacts, args: dict) -> bool:
    return facts.is_vargottama(args["body"]) is bool(args.get("value", True))


@predicate("distance")
def _distance(facts: ChartFacts, args: dict) -> bool:
    """House distance from one graha to another, counted inclusively."""
    return facts.distance(args["body"], args["from"]) in _houses(args["is"])


@predicate("lord_of_in_house")
def _lord_of_in_house(facts: ChartFacts, args: dict) -> bool:
    return facts.lord_placed_in(args["house_lord"]) in _houses(args["house"])


@predicate("lords_conjunct")
def _lords_conjunct(facts: ChartFacts, args: dict) -> bool:
    houses = _houses(args["houses"])
    lords = [facts.lord_of(house) for house in houses]
    if len(set(lords)) == 1:
        # One graha ruling both houses cannot form a conjunction with itself.
        return False
    first = facts.sign_of(lords[0])
    return all(facts.sign_of(lord) == first for lord in lords[1:])


@predicate("lord_of_aspects_house")
def _lord_of_aspects_house(facts: ChartFacts, args: dict) -> bool:
    lord = facts.lord_of(args["house_lord"])
    return any(facts.aspects_house(lord, house) for house in _houses(args["house"]))


@predicate("is_yogakaraka")
def _is_yogakaraka(facts: ChartFacts, args: dict) -> bool:
    return args["body"] in facts.yogakarakas


@predicate("house_empty")
def _house_empty(facts: ChartFacts, args: dict) -> bool:
    houses = _houses(args["house"])
    empty = all(facts.is_empty(house) for house in houses)
    return empty is bool(args.get("value", True))


@predicate("count_in_house")
def _count_in_house(facts: ChartFacts, args: dict) -> bool:
    total = sum(len(facts.occupants(house)) for house in _houses(args["house"]))
    return total >= int(args.get("at_least", 1)) and total <= int(args.get("at_most", 99))


@predicate("only_benefics_in")
def _only_benefics_in(facts: ChartFacts, args: dict) -> bool:
    occupants = [
        body for house in _houses(args["house"]) for body in facts.occupants(house)
    ]
    return bool(occupants) and all(facts.is_benefic(body) for body in occupants)


@predicate("only_malefics_in")
def _only_malefics_in(facts: ChartFacts, args: dict) -> bool:
    occupants = [
        body for house in _houses(args["house"]) for body in facts.occupants(house)
    ]
    return bool(occupants) and not any(facts.is_benefic(body) for body in occupants)


@predicate("body_in_house_group")
def _body_in_house_group(facts: ChartFacts, args: dict) -> bool:
    """Any of the named grahas occupying any of the named houses."""
    houses = _houses(args["house"])
    return any(facts.house_of(body) in houses for body in _bodies(args["body"]))


@predicate("all_bodies_in")
def _all_bodies_in(facts: ChartFacts, args: dict) -> bool:
    """Every graha in a group occupies one of the named houses.

    Note the direction. This is "all the benefics are in the upachayas", which is not
    the same claim as only_benefics_in's "everything in the upachayas is a benefic" —
    the second holds whenever a lone benefic sits there and the rest are elsewhere.
    """
    houses = _houses(args["house"])
    bodies = _group(facts, args["body"]) if "body" in args else GRAHAS
    return bool(bodies) and all(facts.house_of(body) in houses for body in bodies)


def _group(facts: ChartFacts, value: Any) -> tuple[str, ...]:
    """Resolve a named group of grahas, or take an explicit list."""
    if isinstance(value, list):
        return tuple(value)
    groups = {
        "all": GRAHAS,
        "seven": tuple(body for body in GRAHAS if body not in ("Rahu", "Ketu")),
        "benefics": tuple(body for body in GRAHAS if facts.is_benefic(body)),
        "malefics": tuple(body for body in GRAHAS if not facts.is_benefic(body)),
        # The classical lunar yogas count every graha except the Sun and the nodes,
        # since the Sun is always near the Moon at some point in the month and the
        # nodes are shadows rather than bodies.
        "except_sun_and_nodes": ("Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"),
    }
    if value not in groups:
        raise ValueError(f"unknown body group {value!r}; expected {sorted(groups)}")
    return groups[value]


@predicate("bodies_at_distance")
def _bodies_at_distance(facts: ChartFacts, args: dict) -> bool:
    """How many of a group of grahas sit at a given house distance from another graha.

    This is the shape of most lunar yogas: "a planet other than the Sun in the second
    from the Moon" is one graha at distance 2 from the Moon.
    """
    origin = args["from"]
    candidates = [body for body in _group(facts, args.get("body", "all")) if body != origin]
    wanted = _houses(args["is"])
    count = sum(1 for body in candidates if facts.distance(body, origin) in wanted)
    return int(args.get("at_least", 1)) <= count <= int(args.get("at_most", 99))


@predicate("associated_with")
def _associated_with(facts: ChartFacts, args: dict) -> bool:
    """Conjunct with, or receiving an aspect from, any graha in a group.

    BPHS's "yuti with, or receiving a Drishti from" is one idea, and several yogas turn
    on it, so it is one predicate rather than an `any` of two.
    """
    body = args["body"]
    others = [other for other in _group(facts, args.get("with", "benefics")) if other != body]
    return any(
        facts.conjunct(body, other) or facts.aspects_body(other, body) for other in others
    )


@predicate("lord_dignity")
def _lord_dignity(facts: ChartFacts, args: dict) -> bool:
    return facts.dignity(facts.lord_of(args["house_lord"])) in _bodies(args["is"])


@predicate("lords_related")
def _lords_related(facts: ChartFacts, args: dict) -> bool:
    """Any of the four relations BPHS ch. 34 v. 11-12 accepts between two house lords:
    an exchange of signs, a conjunction, either sitting in the other's house, or a full
    mutual aspect. Encoding only the conjunction, as a first pass did, misses most of
    the cases the text allows.
    """
    first, second = _houses(args["houses"])
    lord_first, lord_second = facts.lord_of(first), facts.lord_of(second)
    if lord_first == lord_second:
        return False  # one graha ruling both is the yogakaraka case, treated separately

    exchange = (
        facts.sign_of(lord_first) == facts.sign_of_house(second)
        and facts.sign_of(lord_second) == facts.sign_of_house(first)
    )
    conjunct = facts.sign_of(lord_first) == facts.sign_of(lord_second)
    in_others_house = (
        facts.house_of(lord_first) == second or facts.house_of(lord_second) == first
    )
    mutual_aspect = facts.aspects_body(lord_first, lord_second) and facts.aspects_body(
        lord_second, lord_first
    )
    return exchange or conjunct or in_others_house or mutual_aspect


@predicate("lord_owns_dusthana")
def _lord_owns_dusthana(facts: ChartFacts, args: dict) -> bool:
    """Whether a house's lord also rules the 6th, 8th or 12th.

    BPHS ch. 34 v. 15 withholds the raja yoga when it does.
    """
    owned = set(facts.houses_owned_by(facts.lord_of(args["house_lord"])))
    return bool(owned & set(DUSTHANAS))


@predicate("parivartana")
def _parivartana(facts: ChartFacts, args: dict) -> bool:
    """An exchange of signs: each house's lord sits in the other's sign."""
    first, second = _houses(args["houses"])
    lord_first = facts.lord_of(first)
    lord_second = facts.lord_of(second)
    if lord_first == lord_second:
        return False
    return (
        facts.sign_of(lord_first) == facts.sign_of_house(second)
        and facts.sign_of(lord_second) == facts.sign_of_house(first)
    )


@predicate("dispositor_in_house")
def _dispositor_in_house(facts: ChartFacts, args: dict) -> bool:
    """Where the lord of the sign a graha occupies is placed."""
    from astro.core.strength import sign_lord

    dispositor = sign_lord(facts.sign_of(args["body"]))
    if dispositor == args["body"]:
        return False
    return facts.house_of(dispositor) in _houses(args["house"])


@predicate("all_between_nodes")
def _all_between_nodes(facts: ChartFacts, args: dict) -> bool:
    """Every physical graha hemmed inside the Rahu-Ketu axis, in either direction.

    Measured by sign rather than degree, which is the common reading and avoids
    declaring the yoga broken by a fraction of a degree.
    """
    rahu = facts.sign_of("Rahu")
    seven = tuple(body for body in GRAHAS if body not in ("Rahu", "Ketu"))
    forward = all(0 < (facts.sign_of(body) - rahu) % 12 < 6 for body in seven)
    backward = all(6 < (facts.sign_of(body) - rahu) % 12 < 12 for body in seven)
    return forward or backward


@predicate("moon_waxing")
def _moon_waxing(facts: ChartFacts, args: dict) -> bool:
    return facts.moon_waxing is bool(args.get("value", True))


@predicate("sav_at_least")
def _sav_at_least(facts: ChartFacts, args: dict) -> bool:
    return all(
        facts.sav_of_house(house) >= int(args["count"]) for house in _houses(args["house"])
    )


@predicate("sav_at_most")
def _sav_at_most(facts: ChartFacts, args: dict) -> bool:
    return all(
        facts.sav_of_house(house) <= int(args["count"]) for house in _houses(args["house"])
    )


@predicate("bav_at_least")
def _bav_at_least(facts: ChartFacts, args: dict) -> bool:
    return facts.bav_of(args["body"], int(args["house"])) >= int(args["count"])


# --- rule definition --------------------------------------------------------


CITATION_STATUS = ("located", "unlocated")


@dataclass(frozen=True)
class Citation:
    """Where a rule comes from, and how well that is established.

    "located" means the chapter and verse were found in an ingested text under
    `corpus_md/` and the rule's condition was read against the actual wording.

    "unlocated" means the rule is in common use but no ingested text has been found
    that states it. That is not a claim it is wrong — most of these come from works not
    yet in the corpus — but it must never be displayed as though a source had been
    checked. Inventing a chapter and verse would defeat the whole design.
    """

    text: str
    chapter: str = ""
    verse: str = ""
    page: str = ""
    status: str = "unlocated"

    def __post_init__(self) -> None:
        if self.status not in CITATION_STATUS:
            raise ValueError(f"status must be one of {CITATION_STATUS}, got {self.status!r}")
        # Versified works cite chapter and verse; the rest of the library numbers
        # nothing, so a page is the only honest locator. One or the other is required —
        # "located" has to mean somebody actually found the passage.
        if self.status == "located" and not (self.chapter and self.verse) and not self.page:
            raise ValueError(
                "a located citation needs either a chapter and verse, or a page"
            )

    @property
    def located(self) -> bool:
        return self.status == "located"

    def __str__(self) -> str:
        if not self.located:
            return f"{self.text} — no source located in the ingested texts"
        if self.chapter and self.verse:
            return f"{self.text}, ch. {self.chapter}, v. {self.verse}"
        return f"{self.text}, p. {self.page}"


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    summary: str  # technical statement of the condition
    plain: str  # what it means, in ordinary words
    citation: Citation
    condition: dict
    domains: tuple[str, ...] = ()
    polarity: str = "benefic"  # benefic, malefic or neutral
    # Where the encoded condition departs from, or interprets, the wording of the
    # source. Shown to the reader alongside the citation.
    note: str = ""


@dataclass(frozen=True)
class Finding:
    rule: Rule
    matched: bool
    evidence: tuple[str, ...]

    @property
    def citation(self) -> str:
        return str(self.rule.citation)


def evaluate(condition: dict, facts: ChartFacts) -> bool:
    """Evaluate one node of a condition tree."""
    if not isinstance(condition, dict) or len(condition) != 1:
        raise ValueError(
            f"a condition node must be a single-key mapping, got {condition!r}"
        )
    (key, value), = condition.items()

    if key == "all":
        return all(evaluate(child, facts) for child in value)
    if key == "any":
        return any(evaluate(child, facts) for child in value)
    if key == "not":
        return not evaluate(value, facts)

    if key not in _PREDICATES:
        raise ValueError(f"unknown predicate {key!r}; known: {sorted(_PREDICATES)}")
    return _PREDICATES[key](facts, value or {})


def _evidence_for(rule: Rule, facts: ChartFacts) -> tuple[str, ...]:
    """Plain descriptions of the grahas a rule mentions, so a reader can check it."""
    mentioned: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("body", "target", "from") and isinstance(value, str):
                    mentioned.append(value)
                elif key in ("body", "bodies") and isinstance(value, list):
                    mentioned.extend(item for item in value if isinstance(item, str))
                elif key in ("house_lord", "houses"):
                    for house in _houses(value):
                        mentioned.append(facts.lord_of(house))
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(rule.condition)
    seen: list[str] = []
    for body in mentioned:
        if body in GRAHAS and body not in seen:
            seen.append(body)
    return tuple(facts.describe(body) for body in seen)


def apply_rules(rules: list[Rule], facts: ChartFacts) -> list[Finding]:
    """Every rule that fires, with the evidence that made it fire."""
    findings = []
    for rule in rules:
        if evaluate(rule.condition, facts):
            findings.append(
                Finding(rule=rule, matched=True, evidence=_evidence_for(rule, facts))
            )
    return findings


# --- loading ----------------------------------------------------------------


def parse_rule(raw: dict) -> Rule:
    missing = {"id", "name", "summary", "plain", "source", "when"} - set(raw)
    if missing:
        raise ValueError(f"rule {raw.get('id', '<unnamed>')} is missing {sorted(missing)}")

    source = raw["source"]
    if not source.get("text"):
        raise ValueError(f"rule {raw['id']} has no source text — every rule must cite one")

    rule = Rule(
        id=raw["id"],
        name=raw["name"],
        summary=raw["summary"],
        plain=raw["plain"],
        citation=Citation(
            text=source["text"],
            chapter=str(source.get("chapter", "")),
            verse=str(source.get("verse", "")),
            page=str(source.get("page", "")),
            status=source.get("status", "unlocated"),
        ),
        note=raw.get("note", ""),
        condition=raw["when"],
        domains=tuple(raw.get("domains", ())),
        polarity=raw.get("polarity", "benefic"),
    )
    _validate_condition(rule.condition, rule.id)
    return rule


def _validate_condition(condition: Any, rule_id: str) -> None:
    """Reject unknown predicates at load time rather than when a chart happens to hit
    that branch."""
    if not isinstance(condition, dict) or len(condition) != 1:
        raise ValueError(f"rule {rule_id}: condition node must be a single-key mapping")
    (key, value), = condition.items()
    if key in ("all", "any"):
        for child in value:
            _validate_condition(child, rule_id)
    elif key == "not":
        _validate_condition(value, rule_id)
    elif key not in _PREDICATES:
        raise ValueError(
            f"rule {rule_id}: unknown predicate {key!r}; known: {sorted(_PREDICATES)}"
        )


def load_rules(directory: Path | str = RULES_DIR) -> list[Rule]:
    """Load every rule file in a directory, failing loudly on a duplicate id."""
    path = Path(directory)
    rules: list[Rule] = []
    seen: set[str] = set()
    for file in sorted(path.glob("*.yaml")):
        documents = yaml.safe_load(file.read_text()) or []
        for raw in documents:
            rule = parse_rule(raw)
            if rule.id in seen:
                raise ValueError(f"duplicate rule id {rule.id!r} in {file.name}")
            seen.add(rule.id)
            rules.append(rule)
    return rules


def known_predicates() -> tuple[str, ...]:
    return tuple(sorted(_PREDICATES))
