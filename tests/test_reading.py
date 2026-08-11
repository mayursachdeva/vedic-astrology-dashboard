"""Tests for the precomputed written reading.

The reading is the part of the dashboard a reader actually reads, and it is written by
an 8B model. Everything here exists because instructing that model is not the same as
constraining it: the two gates below both caught real failures in generated prose.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from astro.core.ephemeris import SIGNS
from astro.interpret.factcheck import check
from astro.interpret.glossary import GLOSSARY, bare_terms, explain, render
from astro.interpret.reading import (
    STATUS_FAILED,
    STATUS_OK,
    SectionResult,
    load_reading,
    progress,
    save_section,
)
from astro.interpret.sections import BY_KEY, SECTIONS
from astro.service import build_natal_chart
from astro.store import Profile, connect
from fastapi.testclient import TestClient

from astro.api.main import app, set_db_path

PROFILE = Profile(
    name="Synthetic", birth_local=datetime(1990, 1, 1, 12, 0),
    latitude=28.6139, longitude=77.2090, place="New Delhi",
)
NATAL = build_natal_chart(PROFILE)


# --- the vocabulary rule -----------------------------------------------------


def test_every_term_has_a_plain_phrase_and_a_definition():
    for term, entry in GLOSSARY.items():
        assert entry.plain and entry.plain.lower() != term
        assert entry.definition.endswith(".")


def test_render_puts_the_plain_phrase_first():
    assert render("mahadasha") == "major life chapter (mahadasha)"
    assert render("combust") == "hidden by the Sun (combust)"


def test_a_bare_term_is_caught_and_an_explained_one_is_not():
    assert bare_terms("The mahadasha runs until 2043.") == ["mahadasha"]
    assert bare_terms("a major life chapter (mahadasha) runs until 2043") == []


def test_a_proper_name_is_not_mistaken_for_a_bare_term():
    """"Gaja Kesari Yoga" is a name. Flagging it would force the interface to write
    "Gaja Kesari combination (Yoga)", which is nonsense."""
    assert bare_terms("Gaja Kesari Yoga is present in this chart.") == []
    assert bare_terms("The yoga is present.") == ["yoga"]


def test_explaining_rewrites_the_first_use_only():
    """The rule is explain on first use, not gloss every time."""
    text = "Saturn is combust. Being combust, it struggles."
    out = explain(text)
    assert out.count("hidden by the Sun") == 1
    assert bare_terms(out) == []


def test_explaining_is_idempotent():
    once = explain("Saturn is combust and retrograde.")
    assert explain(once) == once


# --- the placement checker ---------------------------------------------------


def test_a_false_placement_is_caught():
    """The exact sentence an 8B model produced: it read a house's sign and attached it
    to that house's ruler, writing "Mars in Aries" about a Mars standing in Scorpio."""
    wrong = check("Mars in Aries offers energy, and the Sun in Leo balances it.", NATAL.facts)
    said = {claim.said for claim in wrong}
    assert "Mars in Aries" in said
    assert "Sun in Leo" in said


def test_true_placements_pass():
    mars = SIGNS[NATAL.facts.sign_of("Mars")]
    house = NATAL.facts.house_of("Mars")
    assert check(f"Mars stands in {mars}.", NATAL.facts) == []
    assert check(f"Mars is in the {house}th house.", NATAL.facts) == []


def test_a_false_house_claim_is_caught():
    wrong = NATAL.facts.house_of("Saturn") % 12 + 1
    ordinals = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth",
                7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth", 11: "eleventh",
                12: "twelfth"}
    claims = check(f"Saturn sits in the {ordinals[wrong]} house.", NATAL.facts)
    assert claims and "Saturn" in claims[0].said


def test_the_checker_ignores_interpretation():
    """It verifies where planets are, which has a truth value. It must not try to judge
    what a placement means, which does not."""
    assert check("Saturn brings patience and slow, hard-won authority.", NATAL.facts) == []


# --- sections ----------------------------------------------------------------


def test_there_is_a_section_for_every_life_area_plus_the_frame():
    from astro.interpret.life_stages import DOMAINS

    keys = {section.key for section in SECTIONS}
    assert {domain.lower() for domain in DOMAINS} <= keys
    assert {"overview", "timeline", "remedies"} <= keys


def test_every_section_can_build_its_facts_without_a_model():
    for section in SECTIONS:
        facts = section.facts(NATAL)
        assert isinstance(facts, dict) and facts


def test_fact_keys_say_whose_sign_they_mean():
    """A key called "sign" beside a nested ruler is what produced "Mars in Aries"."""
    facts = BY_KEY["career"].facts(NATAL)
    house = facts["houses"][0]
    assert "this_house_occupies_the_sign" in house
    assert "this_planet_stands_in_sign" in house["this_house_is_ruled_by"]
    assert "sign" not in house


# --- storage -----------------------------------------------------------------


@pytest.fixture()
def connection(tmp_path):
    return connect(tmp_path / "readings.db")


@pytest.fixture()
def client_and_profile(tmp_path):
    set_db_path(tmp_path / "views.db")
    client = TestClient(app)
    created = client.post("/api/profiles", json={
        "name": "Synthetic", "birth_local": "1990-01-01T12:00:00",
        "latitude": 28.6139, "longitude": 77.2090, "place": "New Delhi",
    })
    return client, created.json()["id"]


def test_sections_are_stored_and_read_back(connection):
    save_section(connection, 1, SectionResult(
        "overview", "The shape of this chart", "Some prose.", STATUS_OK, "test", 0))
    stored = load_reading(connection, 1)
    assert stored["overview"]["body"] == "Some prose."
    assert stored["overview"]["status"] == STATUS_OK


def test_regenerating_a_section_replaces_it(connection):
    for body in ("first", "second"):
        save_section(connection, 1, SectionResult(
            "overview", "t", body, STATUS_OK, "test", 0))
    stored = load_reading(connection, 1)
    assert stored["overview"]["body"] == "second"
    assert len(stored) == 1


def test_progress_reports_what_is_left(connection):
    assert progress(connection, 1)["written"] == 0
    save_section(connection, 1, SectionResult("overview", "t", "x", STATUS_OK, "m", 0))
    save_section(connection, 1, SectionResult("career", "t", "", STATUS_FAILED, "m", 0))
    state = progress(connection, 1)
    assert state["written"] == 1 and state["failed"] == 1
    assert "health" in state["pending"]
    assert not state["complete"]


def test_a_false_dignity_claim_is_caught():
    """The placement can be right and the claim about it still wrong. An 8B model wrote
    "Saturn's placement in Sagittarius — its own sign": Saturn is in Sagittarius, but
    that is Jupiter's sign. Checking position alone let it through."""
    claims = check("Saturn's placement in Sagittarius, its own sign, helps.", NATAL.facts)
    assert claims
    assert "own sign" in claims[0].said
    assert "does not rule" in claims[0].actually


def test_a_true_own_sign_claim_passes():
    from astro.core.strength import sign_lord

    own = next(
        body for body in NATAL.facts.condition
        if NATAL.facts.dignity(body) in ("own", "moolatrikona")
    )
    assert check(f"{own} stands in its own sign.", NATAL.facts) == []


def test_house_numbers_are_given_their_meaning():
    """"The 10th house" says nothing to a reader who does not know the system."""
    out = explain("The 10th house is strong and the 2nd house supports it.")
    assert "house of work and standing" in out
    assert "house of money and family" in out
    assert "(the 10th)" in out  # the number is kept for anyone checking


def test_a_house_is_explained_once_not_every_time():
    out = explain("The 10th house matters. The 10th house again. And the 10th house.")
    assert out.count("house of work and standing") == 1


# --- the vocabulary rule, enforced across what a reader actually sees ---------


def _reading_view_strings(client, profile_id) -> list[tuple[str, str]]:
    """Every string the reading views render, with where it came from."""
    found: list[tuple[str, str]] = []

    chart = client.get(f"/api/profiles/{profile_id}/chart").json()
    for yoga in chart["yogas"]:
        found.append((f"yoga {yoga['id']} plain", yoga["plain"]))

    stages = client.get(f"/api/profiles/{profile_id}/life-stages?years=6").json()
    for stage in stages["stages"]:
        found.append(("stage headline", stage["headline"]))
        for domain in stage["domains"]:
            for driver in domain["drivers"]:
                found.append((f"{domain['domain']} driver", driver["text"]))

    remedies = client.get(f"/api/profiles/{profile_id}/remedies").json()
    for group in remedies["by_source"].values():
        for remedy in group:
            found.append((f"remedy {remedy['id']} plain", remedy["plain"]))

    return found


def test_no_bare_jargon_reaches_the_reading_views(client_and_profile):
    """The dashboard's promise is that a reader needs no prior knowledge. It was not
    being kept: the default view carried fourteen Sanskrit terms and house numbers with
    no meaning attached. This fails if any of them come back."""
    client, profile_id = client_and_profile

    offenders = []
    for where, text in _reading_view_strings(client, profile_id):
        bare = bare_terms(text)
        if bare:
            offenders.append(f"{where}: {text!r} contains {bare}")
    assert not offenders, "\n".join(offenders[:8])


def test_no_bare_house_numbers_reach_the_reading_views(client_and_profile):
    """"the 10th" is jargon too — it means nothing without the system."""
    import re

    client, profile_id = client_and_profile
    pattern = re.compile(r"\bthe (1st|2nd|3rd|[4-9]th|1[012]th)\b", re.IGNORECASE)

    offenders = [
        f"{where}: {text!r}"
        for where, text in _reading_view_strings(client, profile_id)
        if pattern.search(text)
    ]
    assert not offenders, "\n".join(offenders[:8])


def test_the_technical_view_may_still_use_the_terms(client_and_profile):
    """The rule applies to the reading, not to the chart itself. Someone who opens the
    technical view is asking for the vocabulary."""
    client, profile_id = client_and_profile
    chart = client.get(f"/api/profiles/{profile_id}/chart").json()
    assert chart["positions"]["Sun"]["nakshatra_name"]
    assert any(yoga["summary"] for yoga in chart["yogas"])
