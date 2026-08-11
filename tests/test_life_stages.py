"""Tests for the life-stages view.

The dates must be exactly the computed dasha and transit dates — the prose may vary,
the boundaries may not. The scores must always be reconstructible from their drivers,
because a number nobody can check is worse than no number.
"""

from __future__ import annotations

import pytest

from astro.core.dasha import chain_at, vimshottari
from astro.core.ephemeris import compute_chart, julian_day
from astro.core.facts import build_facts
from astro.interpret.life_stages import (
    DOMAINS,
    LifeStage,
    current_stage,
    life_stages,
)

NATAL = compute_chart(julian_day(1990, 1, 1, 6.5), 28.6139, 77.2090)
FACTS = build_facts(NATAL)
DASHAS = vimshottari(NATAL.positions["Moon"].longitude, NATAL.jd_ut, depth=2)

FROM = julian_day(2024, 1, 1, 0.0)
TO = julian_day(2034, 1, 1, 0.0)
STAGES = life_stages(FACTS, DASHAS, FROM, TO)


# --- the domain map ---------------------------------------------------------


def test_every_domain_names_its_houses_and_cites_them():
    assert set(DOMAINS) == {
        "Career", "Relationships", "Health", "Finance", "Family", "Learning",
    }
    for domain, definition in DOMAINS.items():
        assert definition["houses"], domain
        assert all(1 <= house <= 12 for house in definition["houses"])
        assert "Brihat Parashara Hora Shastra, ch. 11" in definition["citation"]
        assert definition["why"]


# --- chapter boundaries -----------------------------------------------------


def test_stages_tile_the_span_without_gaps_or_overlaps():
    assert STAGES
    assert STAGES[0].start_jd == FROM
    assert STAGES[-1].end_jd == TO
    for earlier, later in zip(STAGES, STAGES[1:]):
        assert earlier.end_jd == later.start_jd


def test_every_boundary_is_a_real_dasha_or_transit_date():
    """A chapter may only begin where something actually changes."""
    from astro.core.transit import sign_transits

    allowed = {FROM}
    for maha in DASHAS:
        allowed.add(maha.start_jd)
        for antar in maha.children:
            allowed.add(antar.start_jd)
    for body in ("Saturn", "Jupiter", "Rahu"):
        for window in sign_transits(NATAL, body, FROM, TO):
            allowed.add(window.start_jd)

    for stage in STAGES:
        assert any(abs(stage.start_jd - moment) < 1e-6 for moment in allowed), (
            f"stage starting at {stage.start_jd} matches no computed event"
        )


def test_every_stage_says_what_opened_it():
    for stage in STAGES:
        assert stage.opened_by
        assert all(label.strip() for label in stage.opened_by)


def test_short_stages_are_folded_away():
    """A six-week life stage is noise, not a chapter."""
    for stage in STAGES[:-1]:
        assert stage.end_jd - stage.start_jd >= 120.0


def test_a_span_that_ends_before_it_starts_is_rejected():
    with pytest.raises(ValueError):
        life_stages(FACTS, DASHAS, TO, FROM)


def test_the_ruling_lords_match_the_dasha_running_at_the_time():
    for stage in STAGES:
        middle = (stage.start_jd + stage.end_jd) / 2.0
        chain = chain_at(DASHAS, middle)
        assert stage.mahadasha == chain[0].lord
        if stage.antardasha is not None:
            assert stage.antardasha == chain[1].lord


# --- scoring ----------------------------------------------------------------


def test_every_stage_scores_every_domain():
    for stage in STAGES:
        assert {reading.domain for reading in stage.domains} == set(DOMAINS)


def test_scores_are_exactly_the_sum_of_their_drivers():
    """The whole point of returning drivers is that they add up to the number shown."""
    for stage in STAGES:
        for reading in stage.domains:
            assert reading.score == sum(driver.weight for driver in reading.drivers)


def test_every_driver_explains_itself():
    for stage in STAGES:
        for reading in stage.domains:
            for driver in reading.drivers:
                assert driver.text.strip()
                assert driver.weight != 0


def test_the_verdict_follows_the_score():
    for stage in STAGES:
        for reading in stage.domains:
            if reading.score >= 2:
                assert reading.verdict == "supported"
            elif reading.score <= -2:
                assert reading.verdict == "under strain"
            else:
                assert reading.verdict == "mixed"


def test_the_leading_domain_is_the_loudest_in_either_direction():
    for stage in STAGES:
        leading = stage.leading
        assert all(
            abs(reading.score) <= abs(leading.score) for reading in stage.domains
        )


# --- plain language ---------------------------------------------------------


def test_the_headline_names_the_ruling_lords_and_reads_as_a_sentence():
    for stage in STAGES:
        headline = stage.headline()
        assert headline.endswith(".")
        assert stage.mahadasha in headline
        assert len(headline.split()) <= 20  # a headline, not a paragraph


def test_the_headline_direction_matches_the_leading_score():
    """The wording leads with the meaning now — "Good for family — a stretch under
    Saturn" rather than "A Saturn period that favours family", which put two planet
    names in front of a reader before telling them anything."""
    for stage in STAGES:
        leading = stage.leading
        headline = stage.headline()
        if leading.score > 0:
            assert headline.startswith(f"Good for {leading.domain.lower()}")
        elif leading.score < 0:
            assert headline.startswith(f"Pressure on {leading.domain.lower()}")
        else:
            assert "no one area" in headline


def test_the_headline_says_what_it_means_before_naming_a_planet():
    for stage in STAGES:
        headline = stage.headline()
        planet_at = min(
            (headline.find(lord) for lord in stage.ruling if lord in headline),
            default=len(headline),
        )
        # str.find returns -1 when absent, so the missing markers have to be dropped
        # before taking the minimum rather than after.
        positions = [
            headline.find(marker)
            for marker in ("Good for", "Pressure on", "steady stretch")
            if marker in headline
        ]
        assert positions, f"headline states no meaning: {headline}"
        assert min(positions) < planet_at, f"planet named before the meaning: {headline}"


def test_headlines_are_assembled_not_generated():
    """Same inputs, same words. Nothing here may vary between runs."""
    again = life_stages(FACTS, DASHAS, FROM, TO)
    assert [stage.headline() for stage in again] == [
        stage.headline() for stage in STAGES
    ]


# --- lookup -----------------------------------------------------------------


def test_current_stage_finds_the_chapter_containing_a_moment():
    middle = (FROM + TO) / 2.0
    stage = current_stage(STAGES, middle)
    assert isinstance(stage, LifeStage)
    assert stage.start_jd <= middle < stage.end_jd


def test_current_stage_is_none_outside_the_span():
    assert current_stage(STAGES, FROM - 100.0) is None
    assert current_stage(STAGES, TO + 100.0) is None


def test_stage_years_are_consistent_with_the_dates():
    for stage in STAGES:
        assert stage.years == pytest.approx(
            (stage.end_jd - stage.start_jd) / 365.25
        )


# --- folding away chapters that are not chapters -----------------------------


def test_consecutive_identical_chapters_are_merged():
    """Boundaries are drawn at slow-planet ingresses, but the scoring never reads those
    transits — so an ingress could split a chapter without changing any score, and the
    reader saw the same paragraph twice with different dates. Nearly half the timeline
    was duplicates before this was folded."""
    def signature(stage):
        return (
            stage.mahadasha,
            stage.antardasha,
            tuple((reading.domain, reading.score) for reading in stage.domains),
        )

    for earlier, later in zip(STAGES, STAGES[1:]):
        assert signature(earlier) != signature(later), (
            f"identical chapters left unmerged at {earlier.start_jd}"
        )


def test_merging_keeps_the_events_that_opened_each_part():
    """A merged chapter must still show every transition inside it, or the ingress
    information is simply lost."""
    long_stages = [stage for stage in STAGES if len(stage.opened_by) > 1]
    assert long_stages, "some chapters should have absorbed a later boundary"
    for stage in long_stages:
        assert all(label.strip() for label in stage.opened_by)


def test_merging_leaves_the_timeline_still_tiling_the_span():
    assert STAGES[0].start_jd == FROM
    assert STAGES[-1].end_jd == TO
    for earlier, later in zip(STAGES, STAGES[1:]):
        assert earlier.end_jd == later.start_jd


def test_dignity_reads_as_english_not_as_a_table_key():
    """"Saturn rules the house of work and standing and is own" is a key read aloud."""
    from astro.interpret.life_stages import DIGNITY_PHRASES, dignity_phrase

    for dignity, phrase in DIGNITY_PHRASES.items():
        assert "_" not in phrase
        assert not phrase.startswith("is " + dignity)
    assert dignity_phrase("own") == "rules the sign it stands in"
    assert dignity_phrase("great_enemy") == "stands in a hostile sign"

    for stage in STAGES:
        for reading in stage.domains:
            for driver in reading.drivers:
                assert " is own" not in driver.text
                assert "_" not in driver.text


def test_the_distinguishing_driver_actually_differs_between_chapters():
    """Printed down a column, the first driver repeated identically eight times: it is
    usually the support figure, which does not change. The line has to say what is
    different about this chapter, or the column is noise."""
    lines = [stage.distinguishing("Career") for stage in STAGES]
    assert all(line for line in lines)
    # Consecutive chapters must not simply repeat the same sentence.
    repeats = sum(1 for a, b in zip(lines, lines[1:]) if a == b)
    assert repeats <= len(lines) // 2, lines
