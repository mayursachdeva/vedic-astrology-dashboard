"""Tests for the rule engine and the BPHS yoga rules.

Every rule ships with two charts: one that must fire it and one that must not. The
second half matters more — a rule that fires on everything is worse than no rule, since
it makes a report look substantive while saying nothing.
"""

from __future__ import annotations

import pytest

from astro.core.facts import build_facts
from astro.interpret.remedies import remedy_rules
from astro.rules.engine import (
    Citation,
    apply_rules,
    evaluate,
    known_predicates,
    load_rules,
    parse_rule,
)
from conftest import synthetic_chart

ARIES, TAURUS, GEMINI, CANCER, LEO, VIRGO = 0, 1, 2, 3, 4, 5
LIBRA, SCORPIO, SAGITTARIUS, CAPRICORN, AQUARIUS, PISCES = 6, 7, 8, 9, 10, 11

RULES = load_rules()
BY_ID = {rule.id: rule for rule in RULES}


def at(sign: int, degree: float = 10.0) -> float:
    return sign * 30.0 + degree


def spread(**overrides: float):
    """Every graha in a different sign, Aries rising.

    A deliberately quiet chart: no conjunctions, no exchanges, nothing in a kendra with
    anything else. Used as the negative case wherever a rule needs "and not otherwise".
    """
    placements = {
        "Sun": at(ARIES), "Moon": at(TAURUS), "Mars": at(GEMINI),
        "Mercury": at(CANCER), "Jupiter": at(LEO), "Venus": at(VIRGO),
        "Saturn": at(LIBRA), "Rahu": at(SAGITTARIUS),
    }
    placements.update(overrides)
    return synthetic_chart(at(ARIES, 0.0), **placements)


def fires(rule_id: str, chart) -> bool:
    return evaluate(BY_ID[rule_id].condition, build_facts(chart))


# Each entry: rule id, a chart that must fire it, a chart that must not.
CASES = [
    (
        "bphs.ruchaka",
        synthetic_chart(at(ARIES), Mars=at(CAPRICORN, 28.0)),  # exalted, 10th house
        synthetic_chart(at(TAURUS), Mars=at(CAPRICORN, 28.0)),  # exalted but 9th house
    ),
    (
        "bphs.bhadra",
        synthetic_chart(at(GEMINI), Mercury=at(VIRGO, 15.0)),  # exalted, 4th house
        synthetic_chart(at(ARIES), Mercury=at(VIRGO, 15.0)),  # exalted but 6th house
    ),
    (
        "bphs.hamsa",
        synthetic_chart(at(CANCER), Jupiter=at(CANCER, 5.0)),  # exalted, 1st house
        synthetic_chart(at(LEO), Jupiter=at(CANCER, 5.0)),  # exalted but 12th house
    ),
    (
        "bphs.malavya",
        synthetic_chart(at(PISCES), Venus=at(PISCES, 27.0)),
        synthetic_chart(at(ARIES), Venus=at(PISCES, 27.0)),
    ),
    (
        "bphs.sasa",
        synthetic_chart(at(LIBRA), Saturn=at(LIBRA, 20.0)),
        synthetic_chart(at(SCORPIO), Saturn=at(LIBRA, 20.0)),
    ),
    (
        "bphs.gajakesari",
        # 4th from the Moon, in its own sign, with Venus aspecting from the 7th.
        synthetic_chart(
            at(ARIES), Moon=at(ARIES), Jupiter=at(CANCER), Venus=at(CAPRICORN),
            Sun=at(LEO), Mars=at(GEMINI), Mercury=at(VIRGO), Saturn=at(SCORPIO),
            Rahu=at(SAGITTARIUS),
        ),
        # Same kendra placement, but no benefic conjunct or aspecting Jupiter, so the
        # verse's second condition fails.
        synthetic_chart(
            at(ARIES), Moon=at(ARIES), Jupiter=at(CANCER), Venus=at(TAURUS),
            Sun=at(LEO), Mars=at(GEMINI), Mercury=at(VIRGO), Saturn=at(SCORPIO),
            Rahu=at(SAGITTARIUS),
        ),
    ),
    (
        "bphs.sunapha",
        synthetic_chart(at(ARIES), Moon=at(ARIES), Venus=at(TAURUS)),
        synthetic_chart(at(ARIES), Moon=at(ARIES)),  # everything else piled on the Moon
    ),
    (
        "bphs.anapha",
        synthetic_chart(at(ARIES), Moon=at(TAURUS), Venus=at(ARIES)),
        synthetic_chart(at(ARIES), Moon=at(ARIES)),
    ),
    (
        "bphs.durudhara",
        synthetic_chart(at(ARIES), Moon=at(TAURUS), Venus=at(ARIES), Mars=at(GEMINI)),
        synthetic_chart(at(ARIES), Moon=at(TAURUS), Venus=at(ARIES)),  # only the 12th
    ),
    (
        "bphs.kemadruma",
        # Moon alone in Cancer; every other graha is four signs away in Aries, so
        # nothing occupies the 12th, the 1st or the 2nd from it.
        # Moon alone in Leo: its 12th, 1st and 2nd are empty, and no graha but the Sun
        # occupies a kendra from the Aries lagna.
        synthetic_chart(
            at(ARIES),
            Moon=at(LEO), Sun=at(ARIES), Mars=at(TAURUS), Mercury=at(GEMINI),
            Jupiter=at(SCORPIO), Venus=at(SAGITTARIUS), Saturn=at(AQUARIUS),
            Rahu=at(PISCES),
        ),
        # The same chart with Venus moved to Libra, a kendra from the lagna. The verse
        # exempts this outright, however isolated the Moon is.
        synthetic_chart(
            at(ARIES),
            Moon=at(LEO), Sun=at(ARIES), Mars=at(TAURUS), Mercury=at(GEMINI),
            Jupiter=at(SCORPIO), Venus=at(LIBRA), Saturn=at(AQUARIUS),
            Rahu=at(PISCES),
        ),
    ),
    (
        "bphs.adhi",
        synthetic_chart(at(ARIES), Moon=at(ARIES), Jupiter=at(VIRGO), Venus=at(LIBRA)),
        spread(),
    ),
    (
        "bphs.chandra_mangala",
        synthetic_chart(at(ARIES), Moon=at(CANCER, 5.0), Mars=at(CANCER, 25.0)),
        spread(),
    ),
    (
        "bphs.sakata",
        # Deliberately a case where the old reversed reading and the corrected one
        # disagree. Gemini rising, Moon in Taurus, Jupiter in Aries: Jupiter is the
        # 12th from the Moon, so Charak's rule fires — but the Moon is only the 2nd
        # from Jupiter, so the reading this rule used to encode would not.
        synthetic_chart(at(GEMINI), Moon=at(TAURUS), Jupiter=at(ARIES)),
        # Same relation to the Moon, but Aries rising puts Jupiter in the 1st, a
        # kendra, which the text excludes.
        synthetic_chart(at(ARIES), Moon=at(TAURUS), Jupiter=at(ARIES)),
    ),
    (
        "bphs.vasumathi",
        # Siddhanta Sara: every benefic in an upachaya. Aries rising, so the 3rd, 6th,
        # 10th and 11th are Gemini, Virgo, Capricorn and Aquarius. Jupiter, Venus and a
        # bright Mercury are all placed there; the Moon is dark, so it is not a benefic
        # and is free to sit elsewhere.
        synthetic_chart(
            at(ARIES), Jupiter=at(GEMINI), Venus=at(VIRGO), Mercury=at(CAPRICORN),
            Sun=at(TAURUS), Moon=at(TAURUS, 20.0), Mars=at(LEO), Saturn=at(SCORPIO),
            Rahu=at(PISCES),
        ),
        # Venus moved out to the 5th. The upachayas still hold nothing but benefics, so
        # the weaker reading this rule used to encode would still fire.
        synthetic_chart(
            at(ARIES), Jupiter=at(GEMINI), Venus=at(LEO), Mercury=at(CAPRICORN),
            Sun=at(TAURUS), Moon=at(TAURUS, 20.0), Mars=at(SCORPIO), Saturn=at(PISCES),
            Rahu=at(TAURUS, 5.0),
        ),
    ),
    (
        "bphs.budha_aditya",
        synthetic_chart(at(ARIES), Sun=at(LEO, 0.0), Mercury=at(LEO, 20.0)),
        synthetic_chart(at(ARIES), Sun=at(LEO, 0.0), Mercury=at(LEO, 5.0)),  # combust
    ),
    (
        "bphs.amala",
        synthetic_chart(at(ARIES), Jupiter=at(CAPRICORN)),
        # A malefic beside it, so the 10th is no longer exclusively benefic — and the
        # Moon route must fail too, so the Moon is parked where its own 10th is empty.
        synthetic_chart(
            at(ARIES), Jupiter=at(CAPRICORN), Saturn=at(CAPRICORN), Moon=at(CAPRICORN),
            Sun=at(ARIES), Mars=at(ARIES), Mercury=at(ARIES), Venus=at(ARIES),
            Rahu=at(TAURUS),
        ),
    ),
    (
        "bphs.saraswati",
        synthetic_chart(
            at(SAGITTARIUS),
            Jupiter=at(SAGITTARIUS),  # own sign, 1st house
            Venus=at(PISCES, 27.0),  # 4th house
            Mercury=at(VIRGO, 15.0),  # 10th house
        ),
        synthetic_chart(
            at(SAGITTARIUS),
            Jupiter=at(SAGITTARIUS),
            Venus=at(PISCES, 27.0),
            Mercury=at(SCORPIO),  # 12th house
        ),
    ),
    (
        "bphs.raja_kendra_trikona",
        # Aries rising: Moon rules the 4th, the Sun the 5th. Together in Gemini.
        synthetic_chart(at(ARIES), Moon=at(GEMINI, 5.0), Sun=at(GEMINI, 25.0)),
        # No kendra lord and trikona lord conjunct, exchanging, sitting in the other's
        # house, or in mutual aspect. Harder to build than it looks, which is the point:
        # the verse's four relations make this yoga common, and spread() qualifies under
        # it even though it was a valid negative for the conjunction-only version.
        synthetic_chart(
            at(ARIES), Sun=at(TAURUS), Moon=at(GEMINI), Mars=at(VIRGO),
            Mercury=at(ARIES), Jupiter=at(SCORPIO), Venus=at(PISCES),
            Saturn=at(AQUARIUS), Rahu=at(CANCER),
        ),
    ),
    (
        "bphs.yogakaraka_kendra_trikona",
        # Taurus rising makes Saturn the yogakaraka; Capricorn is its own 9th house.
        synthetic_chart(at(TAURUS), Saturn=at(CAPRICORN)),
        synthetic_chart(at(ARIES), Saturn=at(CAPRICORN)),  # no yogakaraka for Aries
    ),
    (
        "bphs.dhana_2_11",
        # Aries rising: Venus rules the 2nd, Saturn the 11th.
        synthetic_chart(at(ARIES), Venus=at(LEO, 5.0), Saturn=at(LEO, 25.0)),
        spread(),
    ),
    (
        "bphs.dhana_parivartana",
        synthetic_chart(at(ARIES), Venus=at(AQUARIUS), Saturn=at(TAURUS)),
        synthetic_chart(at(ARIES), Venus=at(AQUARIUS), Saturn=at(GEMINI)),  # half only
    ),
    (
        "bphs.lakshmi",
        # Aries rising: Jupiter rules the 9th. It must sit in a kendra in its own or
        # exalted sign, with Mars, the lagna lord, strong as well.
        synthetic_chart(at(ARIES), Jupiter=at(CANCER, 5.0), Mars=at(ARIES, 5.0)),
        # Jupiter still dignified, but in the 9th — a trikona, not a kendra.
        synthetic_chart(at(ARIES), Jupiter=at(SAGITTARIUS), Mars=at(ARIES, 5.0)),
    ),
    (
        "bphs.harsha",
        synthetic_chart(at(ARIES), Mercury=at(VIRGO)),  # 6th lord in the 6th
        spread(),
    ),
    (
        "bphs.sarala",
        synthetic_chart(at(ARIES), Mars=at(SCORPIO)),  # 8th lord in the 8th
        spread(),
    ),
    (
        "bphs.vimala",
        synthetic_chart(at(ARIES), Jupiter=at(PISCES)),  # 12th lord in the 12th
        spread(),
    ),
    (
        "bphs.kuja_dosha",
        synthetic_chart(at(ARIES), Mars=at(ARIES)),
        spread(),  # Mars in the 3rd
    ),
    (
        "bphs.grahana_sun",
        synthetic_chart(at(ARIES), Sun=at(TAURUS, 5.0), Rahu=at(TAURUS, 25.0)),
        spread(),
    ),
    (
        "bphs.grahana_moon",
        synthetic_chart(at(ARIES), Moon=at(TAURUS, 5.0), Rahu=at(TAURUS, 25.0)),
        spread(),
    ),
    (
        "bphs.guru_chandala",
        synthetic_chart(at(ARIES), Jupiter=at(TAURUS, 5.0), Rahu=at(TAURUS, 25.0)),
        spread(),
    ),
    (
        "bphs.kala_sarpa",
        synthetic_chart(
            at(ARIES),
            Rahu=at(ARIES),
            Sun=at(TAURUS), Moon=at(TAURUS), Mars=at(GEMINI), Mercury=at(GEMINI),
            Jupiter=at(CANCER), Venus=at(LEO), Saturn=at(VIRGO),
        ),
        synthetic_chart(
            at(ARIES),
            Rahu=at(ARIES),
            Sun=at(TAURUS), Moon=at(TAURUS), Mars=at(GEMINI), Mercury=at(GEMINI),
            Jupiter=at(CANCER), Venus=at(LEO), Saturn=at(SCORPIO),  # one outside
        ),
    ),
    (
        "bphs.daridra",
        synthetic_chart(at(ARIES), Saturn=at(VIRGO)),  # 11th lord in the 6th
        spread(),
    ),
    (
        "bphs.neecha_bhanga",
        # Sun fallen in Libra, its dispositor Venus in the 4th. Every other graha is
        # placed explicitly so no second debilitation can fire the rule instead.
        synthetic_chart(
            at(ARIES),
            Sun=at(LIBRA, 10.0), Venus=at(CANCER), Moon=at(TAURUS), Mars=at(GEMINI),
            Mercury=at(LEO), Jupiter=at(VIRGO), Saturn=at(SCORPIO), Rahu=at(SAGITTARIUS),
        ),
        # Same fallen Sun, but Venus sits in the 3rd, which cancels nothing.
        synthetic_chart(
            at(ARIES),
            Sun=at(LIBRA, 10.0), Venus=at(GEMINI), Moon=at(TAURUS), Mars=at(GEMINI),
            Mercury=at(CANCER), Jupiter=at(LEO), Saturn=at(VIRGO), Rahu=at(SAGITTARIUS),
        ),
    ),
]


# --- the engine itself ------------------------------------------------------


def test_rules_load_with_citations():
    assert len(RULES) >= 30
    for rule in RULES:
        assert rule.citation.text
        assert rule.plain.strip()
        assert rule.summary.strip()
        assert rule.polarity in ("benefic", "malefic", "neutral")


def test_unlocated_citations_say_so_rather_than_looking_confirmed():
    unlocated = Citation(text="Classical Vedic astrology")
    assert not unlocated.located
    assert "no source located" in str(unlocated)

    located = Citation(text="BPHS", chapter="7", verse="12", status="located")
    assert located.located
    assert str(located) == "BPHS, ch. 7, v. 12"


def test_a_located_citation_without_chapter_and_verse_is_rejected():
    """The whole point of the status is that "located" means someone looked."""
    with pytest.raises(ValueError, match="chapter and verse, or a page"):
        Citation(text="BPHS", status="located")
    # A page alone is enough for the unversified half of the library.
    assert Citation(text="Lal Kitab", page="42", status="located").located
    with pytest.raises(ValueError):
        Citation(text="BPHS", status="probably")


def test_rules_found_in_the_corpus_carry_a_real_locator():
    """Versified works give a chapter and verse; the rest of the library numbers
    nothing, so a page is the locator. Either is fine — an empty one is not."""
    located = [rule for rule in RULES if rule.citation.located]
    assert len(located) >= 24
    for rule in located:
        has_verse = bool(rule.citation.chapter and rule.citation.verse)
        has_page = bool(rule.citation.page)
        assert has_verse or has_page, rule.id
        assert "no source located" not in str(rule.citation)


def test_every_located_citation_resolves_to_a_real_passage():
    """"Located" has to mean the passage is there, not that someone believed it was.

    Nothing checked this before, and the gap showed: bphs.dhana_2_11 sat unlocated with
    a note saying Charak p. 355 did not state the rule, while the full page states it
    plainly — the earlier pass had judged from a search excerpt. A test cannot read a
    page for you, but it can insist the reference points somewhere.
    """
    from astro.corpus.search import load_passages, lookup

    passages = load_passages()
    for rule in RULES + remedy_rules():
        citation = rule.citation
        if not citation.located:
            continue
        found = lookup(
            citation.text,
            chapter=citation.chapter,
            verse=citation.verse,
            page=citation.page,
            passages=passages,
        )
        assert found, f"{rule.id} cites {citation}, which resolves to nothing"


def test_the_corrected_sakata_disagrees_with_the_reading_it_replaced():
    """Guards the actual correction, not just the citation. The note on this rule claims
    the relation was reversed and the kendra exclusion added; an earlier pass wrote that
    note while the condition went unchanged, and fixtures that happened to pass under
    both readings hid it."""
    chart = synthetic_chart(at(GEMINI), Moon=at(TAURUS), Jupiter=at(ARIES))
    facts = build_facts(chart)

    assert facts.distance("Jupiter", "Moon") == 12  # Charak's relation holds
    assert facts.distance("Moon", "Jupiter") == 2  # the old one does not
    assert fires("bphs.sakata", chart)

    condition = BY_ID["bphs.sakata"].condition
    assert condition["all"][0]["distance"]["body"] == "Jupiter"
    assert condition["all"][0]["distance"]["from"] == "Moon"


def test_the_corrected_vasumathi_disagrees_with_the_reading_it_replaced():
    """Siddhanta Sara asks that every benefic be gathered in the upachayas. The rule
    previously asked only that whatever stood there be benefic, which is the converse
    and holds far more often."""
    from astro.rules.engine import evaluate

    chart = synthetic_chart(
        at(ARIES), Jupiter=at(GEMINI), Venus=at(LEO), Mercury=at(CAPRICORN),
        Sun=at(TAURUS), Moon=at(TAURUS, 20.0), Mars=at(SCORPIO), Saturn=at(PISCES),
        Rahu=at(TAURUS, 5.0),
    )
    facts = build_facts(chart)
    assert evaluate({"only_benefics_in": {"house": "upachaya"}}, facts), (
        "the old reading fires here"
    )
    assert not fires("bphs.vasumathi", chart), "the corrected one must not"


def test_every_unlocated_rule_records_what_was_searched():
    """So the next person does not repeat the hunt, and so a reader can see the gap is
    known rather than overlooked."""
    for rule in RULES:
        if not rule.citation.located:
            assert rule.note.strip(), f"{rule.id} is unlocated and says nothing about it"


def test_a_rule_without_a_source_is_rejected():
    with pytest.raises(ValueError, match="must cite"):
        parse_rule(
            {
                "id": "x", "name": "X", "summary": "s", "plain": "p",
                "source": {}, "when": {"in_house": {"body": "Sun", "house": 1}},
            }
        )


def test_a_rule_with_an_unknown_predicate_is_rejected_at_load_time():
    with pytest.raises(ValueError, match="unknown predicate"):
        parse_rule(
            {
                "id": "x", "name": "X", "summary": "s", "plain": "p",
                "source": {"text": "BPHS"}, "when": {"invented_predicate": {}},
            }
        )


def test_a_rule_missing_required_fields_is_rejected():
    with pytest.raises(ValueError, match="missing"):
        parse_rule({"id": "x", "name": "X"})


def test_combinators_work():
    chart = synthetic_chart(at(ARIES), Sun=at(ARIES), Moon=at(TAURUS))
    facts = build_facts(chart)
    sun_in_first = {"in_house": {"body": "Sun", "house": 1}}
    moon_in_first = {"in_house": {"body": "Moon", "house": 1}}

    assert evaluate({"all": [sun_in_first]}, facts)
    assert not evaluate({"all": [sun_in_first, moon_in_first]}, facts)
    assert evaluate({"any": [sun_in_first, moon_in_first]}, facts)
    assert evaluate({"not": moon_in_first}, facts)


def test_a_malformed_condition_node_is_rejected():
    facts = build_facts(spread())
    with pytest.raises(ValueError, match="single-key"):
        evaluate({"in_house": {}, "in_sign": {}}, facts)


def test_house_groups_resolve():
    facts = build_facts(synthetic_chart(at(ARIES), Jupiter=at(CANCER)))
    assert evaluate({"in_house": {"body": "Jupiter", "house": "kendra"}}, facts)
    assert not evaluate({"in_house": {"body": "Jupiter", "house": "dusthana"}}, facts)


def test_an_unknown_house_group_is_rejected():
    facts = build_facts(spread())
    with pytest.raises(ValueError, match="unknown house group"):
        evaluate({"in_house": {"body": "Sun", "house": "nonsense"}}, facts)


def test_predicates_are_all_reachable_from_the_rule_files():
    """Every predicate should earn its place; an unused one is dead weight."""
    used = set()

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("all", "any", "not"):
                    walk(value)
                else:
                    used.add(key)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for rule in RULES:
        walk(rule.condition)

    unused = set(known_predicates()) - used
    # A handful are kept for the transit and remedy rules still to come; name them so
    # this test fails when the list grows rather than silently accumulating.
    allowed_unused = {
        "aspects_body", "aspects_house", "all_bodies_in", "bav_at_least",
        "benefic", "count_in_house", "house_empty", "in_sign", "lagna_is",
        "lord_of_aspects_house", "moon_waxing", "only_malefics_in", "retrograde",
        "sav_at_least", "sav_at_most", "vargottama",
    }
    assert unused <= allowed_unused, f"unused predicates not accounted for: {unused - allowed_unused}"


# --- every rule fires when it should, and stays quiet when it should not -----


@pytest.mark.parametrize("rule_id,positive,_negative", CASES, ids=[case[0] for case in CASES])
def test_rule_fires_on_its_positive_chart(rule_id, positive, _negative):
    assert fires(rule_id, positive), f"{rule_id} did not fire on its positive fixture"


@pytest.mark.parametrize("rule_id,_positive,negative", CASES, ids=[case[0] for case in CASES])
def test_rule_stays_quiet_on_its_negative_chart(rule_id, _positive, negative):
    assert not fires(rule_id, negative), f"{rule_id} fired on its negative fixture"


def test_every_loaded_rule_has_a_fixture_pair():
    """New rules must arrive with their tests, not after them."""
    covered = {case[0] for case in CASES}
    assert covered == set(BY_ID), f"rules without fixtures: {set(BY_ID) - covered}"


# --- applying the whole set --------------------------------------------------


def test_apply_rules_returns_findings_with_evidence_and_citations():
    chart = synthetic_chart(at(CANCER), Jupiter=at(CANCER, 5.0))
    findings = apply_rules(RULES, build_facts(chart))

    assert findings, "an exalted Jupiter in the lagna should fire something"
    by_id = {finding.rule.id: finding for finding in findings}
    assert "bphs.hamsa" in by_id

    hamsa = by_id["bphs.hamsa"]
    assert any("Jupiter" in line for line in hamsa.evidence)
    assert "Brihat Parashara Hora Shastra" in hamsa.citation


def test_a_quiet_chart_produces_few_findings_rather_than_a_wall_of_them():
    """The point of the negative fixtures, restated on a whole chart: rules must be
    selective or a report becomes noise."""
    findings = apply_rules(RULES, build_facts(spread()))
    assert len(findings) <= 6, [finding.rule.id for finding in findings]


def test_findings_run_against_a_real_computed_chart():
    from astro.core.ephemeris import compute_chart, julian_day

    chart = compute_chart(julian_day(1990, 1, 1, 6.5), 28.6139, 77.2090)
    findings = apply_rules(RULES, build_facts(chart))
    for finding in findings:
        assert finding.evidence
        assert finding.rule.plain
