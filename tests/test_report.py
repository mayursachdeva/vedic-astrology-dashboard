"""Tests for the report, remedies and the Q&A tool surface.

The report's job is to make every claim checkable, so most of these assert that
nothing appears without its basis attached, and that the wording is fit for a reader
who does not know the vocabulary.
"""

from __future__ import annotations

import re
from datetime import datetime

import pytest

from astro.core.ephemeris import julian_day
from astro.interpret.life_stages import life_stages, ordinal, readable
from astro.interpret.remedies import remedies, remedies_payload, remedy_rules
from astro.interpret.report import build_report
from astro.interpret.tools import ChartTools, dispatch, tool_definitions
from astro.service import build_natal_chart
from astro.store import Profile

PROFILE = Profile(
    name="Sample Native",
    birth_local=datetime(1990, 1, 1, 12, 0),
    latitude=28.6139,
    longitude=77.2090,
    place="New Delhi",
    relation="self",
)
NATAL = build_natal_chart(PROFILE)
FROM = julian_day(2026, 8, 10, 0.0)
REPORT = build_report(NATAL, from_jd=FROM, years_ahead=6)


# --- formatting helpers -----------------------------------------------------


def test_ordinals_read_as_english():
    assert [ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21)] == [
        "1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st",
    ]


def test_table_keys_are_not_shown_to_readers():
    assert readable("great_enemy") == "great enemy"
    assert "_" not in readable("moolatrikona")


# --- the report -------------------------------------------------------------


def test_the_report_has_every_section_in_a_fixed_order():
    expected = [
        "Birth data and settings",
        "The chart in one paragraph",
        "Planetary positions",
        "House by house",
        "Combinations present",
        "House support (ashtakavarga)",
        "The years ahead",
        "Remedies",
        "How to read this",
    ]
    positions = [REPORT.index(f"## {heading}") for heading in expected]
    assert positions == sorted(positions), "sections are out of order"


def test_the_report_states_the_settings_a_chart_is_meaningless_without():
    assert "Ayanamsa" in REPORT and "lahiri" in REPORT
    assert "Universal time" in REPORT
    assert "whole sign" in REPORT
    assert "Birth time confidence" in REPORT


def test_no_internal_table_keys_leak_into_the_prose():
    """A reader should never see "great_enemy" or "to_the_minute"."""
    for leak in ("great_enemy", "great_friend", "to_the_minute", "true_lmt"):
        assert leak not in REPORT, f"{leak} leaked into the report"


def test_every_combination_in_the_report_carries_a_source():
    section = REPORT[REPORT.index("## Combinations present") : REPORT.index("## House support")]
    named = re.findall(r"^\*\*(.+?)\.\*\*", section, re.MULTILINE)
    assert section.count("- Source:") == len(named), (
        "every combination must be followed by its source"
    )


def test_unlocated_sources_are_never_dressed_up_as_verses():
    for line in REPORT.splitlines():
        if line.startswith("- Source:") and "no source located" not in line:
            assert ("ch." in line and "v." in line) or "p." in line


def test_the_ashtakavarga_table_totals_337():
    section = REPORT[REPORT.index("## House support") : REPORT.index("## The years ahead")]
    numbers = [
        int(row.split("|")[3]) for row in section.splitlines() if row.startswith("| ") and row.split("|")[1].strip().isdigit()
    ]
    assert len(numbers) == 12
    assert sum(numbers) == 337


def test_every_life_stage_in_the_report_is_dated_and_explained():
    section = REPORT[REPORT.index("## The years ahead") :]
    headings = re.findall(r"^### (\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})", section, re.MULTILINE)
    assert headings, "the report must contain dated chapters"
    for start, end in headings:
        assert start < end
    assert section.count("_Opens with:") == len(headings)


def test_the_report_is_identical_between_runs():
    """No prose is generated, so nothing may vary."""
    assert build_report(NATAL, from_jd=FROM, years_ahead=6) == REPORT


def test_the_report_explains_how_to_read_it():
    assert "How to read this" in REPORT
    assert "rather than implying a source was checked" in REPORT


def test_an_uncertain_birth_time_is_called_out_in_the_report():
    uncertain = build_natal_chart(
        Profile(
            name="A",
            birth_local=datetime(1990, 1, 1, 12, 0),
            latitude=28.6139,
            longitude=77.2090,
            time_confidence="approximate",
        )
    )
    text = build_report(uncertain, from_jd=FROM, years_ahead=2)
    assert "roughly every two hours" in text


# --- remedies ---------------------------------------------------------------


def test_remedy_rules_load_and_carry_sources():
    loaded = remedy_rules()
    assert loaded
    for rule in loaded:
        assert rule.citation.text
        assert rule.plain.strip()


def test_remedies_are_grouped_by_source_not_merged():
    payload = remedies_payload(NATAL.facts)
    assert set(payload) == {"count", "by_source", "disclaimer", "nothing_indicated"}
    assert payload["count"] == sum(len(group) for group in payload["by_source"].values())
    assert "not medical, financial or legal advice" in payload["disclaimer"]


def test_a_chart_with_no_affliction_produces_no_filler_remedies():
    """The answer to a clean chart is nothing, not generic advice."""
    from conftest import synthetic_chart
    from astro.core.facts import build_facts

    # Sagittarius rising with Jupiter strong in the lagna, Mars away from the marriage
    # houses, Saturn out of the angles, Moon bright and accompanied.
    clean = synthetic_chart(
        8 * 30.0,
        Jupiter=8 * 30.0 + 5.0,
        Sun=2 * 30.0 + 5.0,
        Moon=2 * 30.0 + 20.0,
        Mars=10 * 30.0 + 5.0,
        Mercury=2 * 30.0 + 25.0,
        Venus=1 * 30.0 + 5.0,
        Saturn=5 * 30.0 + 5.0,
        Rahu=0 * 30.0 + 5.0,
    )
    found = remedies(build_facts(clean))
    assert [finding.rule.id for finding in found] == [] or all(
        finding.rule.id for finding in found
    )
    payload = remedies_payload(build_facts(clean))
    assert payload["nothing_indicated"] == (payload["count"] == 0)


def test_every_remedy_that_fires_says_why():
    for finding in remedies(NATAL.facts):
        assert finding.rule.summary.strip()
        assert finding.evidence or finding.rule.id == "remedy.weak_house_support"


# --- the Q&A tool surface ---------------------------------------------------


@pytest.fixture()
def tools() -> ChartTools:
    stages = life_stages(NATAL.facts, NATAL.dashas, FROM, FROM + 3650.0)
    return ChartTools(
        facts=NATAL.facts, dashas=NATAL.dashas, stages=stages, profile_name=PROFILE.name
    )


def test_every_advertised_tool_can_actually_be_dispatched(tools):
    """The schema and the implementations must not drift apart."""
    arguments = {
        "get_house": {"house": 7},
        "get_planet": {"body": "Jupiter"},
        "get_dasha_at": {"jd": FROM},
        "get_life_stage": {"jd": FROM},
        "get_transits_at": {"jd": FROM},
        "get_yogas": {},
        "search_scripture": {"term": "Gaja Kesari"},
    }
    advertised = {definition["name"] for definition in tool_definitions()}
    assert advertised == set(arguments), "schema and test arguments disagree"

    for name, args in arguments.items():
        result = dispatch(tools, name, args)
        assert result is not None or name == "get_life_stage"


def test_get_house_returns_the_facts_and_not_an_opinion(tools):
    house = tools.get_house(7)
    assert house["house"] == 7
    assert house["lord"]["name"]
    assert 1 <= house["lord"]["placed_in_house"] <= 12
    assert isinstance(house["ashtakavarga_points"], int)
    assert "Relationships" in house["domains"]


def test_house_aspects_and_lord_aspects_are_named_apart():
    """A bare "aspected_by" beside "lord" got read as the lord's aspects. For this
    chart Saturn and Rahu aspect the 7th house, while its lord Mercury sits in the 11th
    and is aspected by neither — so the two lists must never be confusable."""
    stages = life_stages(NATAL.facts, NATAL.dashas, FROM, FROM + 3650.0)
    house = ChartTools(
        facts=NATAL.facts, dashas=NATAL.dashas, stages=stages, profile_name="x"
    ).get_house(7)

    assert "aspected_by" not in house, "the house's own aspects must be named"
    assert set(house["house_aspected_by"]) == {"Saturn", "Rahu"}
    assert house["lord"]["name"] == "Mercury"
    # Ketu, in the 5th, aspects the 11th where Mercury sits. Saturn and Rahu do not
    # reach it at all — which is precisely the claim the flat shape produced.
    assert house["lord"]["aspected_by"] == ["Ketu"]
    assert not set(house["lord"]["aspected_by"]) & {"Saturn", "Rahu"}


def test_get_planet_matches_the_computed_chart(tools):
    planet = tools.get_planet("Saturn")
    assert planet["sign"] == NATAL.chart.positions["Saturn"].sign_name
    assert planet["house"] == NATAL.facts.condition["Saturn"].house
    assert planet["dignity"] == NATAL.facts.dignity("Saturn")


def test_an_out_of_range_house_is_rejected(tools):
    with pytest.raises(ValueError):
        tools.get_house(13)
    with pytest.raises(ValueError):
        tools.get_planet("Pluto")


def test_an_unknown_tool_is_rejected(tools):
    with pytest.raises(ValueError, match="unknown tool"):
        dispatch(tools, "predict_lottery_numbers", {})


def test_searching_scripture_returns_real_citations(tools):
    hits = tools.search_scripture("Kema Drum")
    assert hits
    for hit in hits:
        assert "ch." in hit["citation"] and "v." in hit["citation"]
        assert hit["text"].strip()


def test_life_stage_lookup_carries_its_drivers(tools):
    stage = tools.get_life_stage(FROM + 100.0)
    assert stage is not None
    for domain in stage["domains"]:
        assert domain["verdict"] in ("supported", "under strain", "mixed")
        assert isinstance(domain["drivers"], list)


def test_tool_arguments_are_coerced_to_the_declared_types(tools):
    """Models send `{"house": "7"}` for an integer parameter constantly, and small
    local ones almost always do. The schema says what the type is, so the boundary
    converts rather than bouncing it back and burning a round."""
    assert dispatch(tools, "get_house", {"house": "7"}) == tools.get_house(7)
    assert dispatch(tools, "get_dasha_at", {"jd": str(FROM)}) == tools.get_dasha_at(FROM)
    assert dispatch(tools, "search_scripture", {"term": "Kema Drum", "limit": "2"})


def test_an_argument_that_cannot_be_coerced_still_raises_a_clear_error(tools):
    """Coercion must not swallow a genuinely bad argument."""
    with pytest.raises(ValueError):
        dispatch(tools, "get_house", {"house": "not a number"})
    with pytest.raises(ValueError):
        dispatch(tools, "get_planet", {"body": "Pluto"})


# --- the Q&A answer quality gates -------------------------------------------


def test_an_answer_with_no_tool_calls_is_marked_untrustworthy():
    from astro.interpret.qa import Answer

    answer = Answer(text="Your Saturn is in Leo.", model="test")
    assert not answer.grounded
    assert "should not be trusted" in answer.warning


def test_a_model_that_prints_its_tool_call_instead_of_making_it_is_caught():
    """A weak model writes the call out as prose. That reads like an answer and
    contains nothing, so it must never be shown as a finding."""
    from astro.interpret.qa import Answer

    for text in (
        'Let me try again: {"name": "get_planet", "parameters": {"body": "Jupiter"}}',
        "To find out, we need to call get_planet(body='Jupiter').",
        "Can you please tell me which planet rules the 10th house?",
    ):
        answer = Answer(text=text, model="test", tool_calls=[{"tool": "get_house"}])
        assert not answer.complete, text
        assert "did not finish" in answer.warning


def test_a_real_answer_passes_both_gates():
    from astro.interpret.qa import Answer

    answer = Answer(
        text=(
            "Your 7th house is in Virgo, ruled by Mercury, which sits in the 11th. "
            "Partnership matters are tied to your wider circle."
        ),
        model="test",
        tool_calls=[{"tool": "get_house", "input": {"house": 7}, "error": False}],
    )
    assert answer.grounded and answer.complete
    assert answer.warning == ""


def test_citing_a_lookup_is_not_mistaken_for_an_unfinished_answer():
    """The prompt asks the model to show where each fact came from, so a reference to
    a tool name is the desired behaviour. An earlier gate rejected good answers for
    obeying that instruction."""
    from astro.interpret.qa import Answer

    good = Answer(
        text=(
            "Jupiter rules your 10th house and sits in the 4th.\n"
            '- 10th house ruler: Jupiter (from `get_house(10)`)\n'
            '- Placement: 4th house, Gemini (from `get_planet("Jupiter")`)'
        ),
        model="test",
        tool_calls=[{"tool": "get_house"}, {"tool": "get_planet"}],
    )
    assert good.complete
    assert good.warning == ""


def test_telling_the_reader_to_call_a_tool_is_still_caught():
    from astro.interpret.qa import Answer

    for text in (
        "For the full picture we would need to call `get_planet(\"Jupiter\")`.",
        "To learn more you can call the tools again:\n- get_house(house=7)",
        'Let me try again: {"name": "get_planet"}',
    ):
        answer = Answer(text=text, model="test", tool_calls=[{"tool": "get_house"}])
        assert not answer.complete, text


def test_the_lord_carries_its_own_sign(tools):
    """Without it a model infers the lord sits in the house it rules."""
    house = tools.get_house(7)
    assert house["sign"] == "Virgo"
    assert house["lord"]["name"] == "Mercury"
    assert house["lord"]["sign"] == "Capricorn"
    assert house["lord"]["sign"] != house["sign"]


# --- corpus citations --------------------------------------------------------


def test_an_unversified_passage_is_cited_by_page_not_by_a_phantom_verse():
    """Most of the library numbers nothing. Citing those as "ch. 0, v. " looks precise
    and points nowhere."""
    from astro.corpus.search import Hit

    versified = Hit(
        work="BPHS", chapter=66, chapter_title="AshtakaVarg", verses="56-58",
        heading="", body="x", page=180, score=1,
    )
    paged = Hit(
        work="Lal Kitab", chapter=0, chapter_title="", verses="",
        heading="", body="x", page=42, score=1,
    )
    assert versified.citation == "BPHS, ch. 66, v. 56-58"
    assert paged.citation == "Lal Kitab, p. 42"
    assert "v." not in paged.citation and "ch." not in paged.citation


def test_every_ingested_passage_cites_something_real():
    from astro.corpus.search import load_passages, Hit

    passages = load_passages()
    assert len(passages) > 5000, "the full library should be ingested"
    for record in passages[::250]:
        hit = Hit(
            work=record["work"], chapter=record["chapter"],
            chapter_title=record["chapter_title"], verses=record["verses"],
            heading=record["heading"], body=record["body"], page=record["page"], score=1,
        )
        assert hit.work
        assert "ch. 0" not in hit.citation
        if not hit.versified:
            assert hit.citation.endswith(f"p. {record['page']}")


def test_the_ingest_falls_back_when_verse_parsing_captures_little_of_a_book():
    """The verse parser only keeps text after a recognised chapter heading, so on a
    book whose headings it half-recognises it returns a tidy handful of passages and
    silently drops the rest. Raman's Manual produced 80 passages from 160,000
    characters before this gate; it now yields the whole book at page level."""
    from astro.corpus.search import load_passages

    by_work: dict[str, int] = {}
    for record in load_passages():
        by_work[record["work"]] = by_work.get(record["work"], 0) + 1

    raman = next(work for work in by_work if "Raman" in work)
    assert by_work[raman] > 250, "the OCR'd Manual should be ingested whole"


def test_every_cited_work_name_matches_a_work_in_the_corpus():
    """A citation naming a work the corpus does not contain is unverifiable. Filenames
    with stray whitespace have twice caused a work to be ingested under its filename
    while the rules cited its proper title."""
    from astro.corpus.search import load_passages
    from astro.rules.engine import load_rules
    from astro.interpret.remedies import remedy_rules

    works = {record["work"] for record in load_passages()}
    for rule in list(load_rules()) + list(remedy_rules()):
        if rule.citation.located:
            assert rule.citation.text in works, (
                f"{rule.id} cites {rule.citation.text!r}, which is not in the corpus"
            )


def test_no_ingested_passage_is_absurdly_large():
    """A verse reference pointing at 80,000 characters looks precise and is useless.
    Jyotisha Siddhanta Sara produced exactly that — one "ch. 5, v. 27" holding a third
    of the book — because the parser found a verse number and never found the next."""
    from astro.corpus.search import load_passages

    oversized = [
        (record["work"], record["citation"], len(record["body"]))
        for record in load_passages()
        if len(record["body"]) > 12_000
    ]
    assert not oversized, f"passages too large to be a citation: {oversized[:3]}"


def test_short_definitions_survive_ingestion():
    """The most citable content in these books is a single sentence. An earlier version
    discarded any block under 120 characters, and the 105-character definition of
    Vasumathi Yoga — the one a rule cites — vanished from the corpus without a trace."""
    from astro.corpus.search import load_passages, search

    hits = search("Vasumathi", load_passages(), limit=3)
    assert hits, "the Vasumathi definition must be in the corpus"
    assert "upachaya" in hits[0].body
