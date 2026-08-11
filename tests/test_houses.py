"""Tests for the corpus index and the house reading built on it.

The reading is assembled from pointers into the library, so the thing that can go wrong
is not the prose — there is none — but the pointers. A citation that resolves to the
wrong verse is worse than no citation: it reads as authority and says something else. So
most of these check that a derived pointer lands on a passage that actually talks about
the thing it was asked for.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from astro.core.ephemeris import NAKSHATRAS, SIGNS
from astro.core.panchanga import day_span
from astro.core.shadbala import bhava_bala, shadbala
from astro.corpus import index as texts
from astro.interpret.houses import house_reading, payload
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
CHART = NATAL.chart
SPAN = day_span(CHART.jd_ut, CHART.latitude, CHART.longitude)
BALAS = shadbala(CHART, SPAN)
BHAVA = bhava_bala(CHART, BALAS, SPAN)


def reading(house: int, varga: str = "D1") -> dict:
    return payload(
        house_reading(CHART, NATAL.facts, house, balas=BALAS, bhava=BHAVA, varga=varga)
    )


# --- the index --------------------------------------------------------------


def test_every_bhava_has_its_own_verse_of_significations():
    """BPHS ch. 11 gives one verse per bhava, and each names that bhava."""
    for house in range(1, 13):
        hit = texts.significations(house)
        assert hit is not None, house
        assert hit.chapter == 11 and hit.verses == str(house + 1)
        assert any(name in hit.body for name in texts.bhava_names(house)), (
            house, hit.body[:80]
        )


def test_the_lord_in_house_grid_lands_on_the_verse_it_claims():
    """ch. 24 is a 12x12 grid in reading order, so the verse is arithmetic.

    Arithmetic that is off by twelve would still return a real verse about a real
    placement — just the wrong one — which is why each cell is checked for both bhava
    names rather than for merely existing.
    """
    found = 0
    for lord_of in range(1, 13):
        for sits_in in range(1, 13):
            hit = texts.lord_in_house(lord_of, sits_in)
            if hit is None:
                continue  # a few cells are missing from this printing
            found += 1
            for role, which in (("owner", lord_of), ("guest", sits_in)):
                assert any(name in hit.body for name in texts.bhava_names(which)), (
                    role, lord_of, sits_in, hit.citation, hit.body[:90]
                )
    assert found >= 135, f"only {found} of 144 cells resolved"


def test_a_missing_cell_comes_back_empty_rather_than_as_its_neighbour():
    """Verse 12 is absent from this printing. Returning verse 11 or 13 instead would be
    a confident citation of a different placement."""
    assert texts.lord_in_house(1, 12) is None


def test_every_sign_gets_a_passage_that_describes_it():
    for sign in range(12):
        excerpt = texts.sign_excerpt(sign)
        assert excerpt is not None, SIGNS[sign]
        text, hit = excerpt
        assert hit.chapter == 4
        assert len(text) > 120, (SIGNS[sign], text)
        # A description, not the list of all twelve names in v. 3.
        assert text.count("Rāśi") + text.count("Rashi") < 6, SIGNS[sign]


def test_the_sign_excerpt_is_cut_to_the_sign_asked_for():
    """The ingestion merged verses, so one passage carries four signs. Handing over the
    whole block would answer a question about Virgo with a paragraph about Sagittarius."""
    virgo, _ = texts.sign_excerpt(5)
    libra, _ = texts.sign_excerpt(6)
    assert virgo != libra
    assert "Tula" not in virgo
    assert libra.startswith("Tula")


def test_virgo_is_the_one_sign_described_without_being_named():
    """Which is why it is pointed at by hand; this guards the pointer."""
    assert 5 in texts.SIGN_VERSE_OVERRIDES
    virgo, hit = texts.sign_excerpt(5)
    assert "Kanya" not in virgo
    assert "Virgin" in virgo, virgo


def test_every_graha_has_a_mantra_on_the_page_prescribed_for_it():
    for body, page in texts.REMEDY_PAGES.items():
        mantra = texts.mantra(body)
        assert mantra, body
        assert mantra.startswith("Om"), (body, mantra)
        assert texts.practice(body).page == page


def test_every_nakshatra_has_a_description_of_its_character():
    """From the one work written about them. A general search found Charak's table of
    muhurta combinations for two of them — correctly cited, describing nothing."""
    for name in NAKSHATRAS:
        hit = texts.nakshatra_note(name)
        assert hit is not None, name
        assert hit.work == texts.NAKSHATRA_WORK, (name, hit.work)


def test_the_bhava_chapters_line_up_with_their_houses():
    for house in range(1, 13):
        chapter = texts.bhava_chapter(house)
        assert chapter, house
        assert all(hit.chapter == 11 + house for hit in chapter)


# --- the reading ------------------------------------------------------------


def test_every_house_composes_with_its_citations_intact():
    for house in range(1, 13):
        data = reading(house)
        assert data["represents"]["citation"].startswith("Brihat Parashara")
        assert data["sign_says"]["text"]
        assert data["lord"]["name"]
        assert data["verdict"] in ("working", "mixed", "needs work", "quiet")
        assert data["because"]


def test_the_headline_names_the_subject_the_sign_and_where_the_ruler_went():
    data = reading(10)
    assert "work and standing" in data["headline"]
    assert data["sign_name"] in data["headline"]
    assert data["lord"]["name"] in data["headline"]


def test_the_verdict_says_which_measures_it_rests_on():
    """Counted, not blended, so a reader can see when they disagreed."""
    for house in range(1, 13):
        data = reading(house)
        if data["verdict"] == "mixed":
            assert len(data["because"]) >= 2, (house, data["because"])


def test_an_empty_house_still_says_something_about_its_ruler():
    """Most houses are empty. Leaving the ruler out of the verdict returned "nothing
    stands out either way" for a house whose lord was the whole story."""
    empty = [h for h in range(1, 13) if not reading(h)["occupants"]]
    assert empty
    for house in empty:
        because = " ".join(reading(house)["because"])
        assert "ruler" in because, (house, because)


def test_every_house_has_something_to_do_about_it():
    """Gating guidance on trouble left nine houses of twelve showing nothing at all —
    no conduct, no mantra — which is not the same as there being nothing to say."""
    for house in range(1, 13):
        entries = reading(house)["remedies"]
        assert entries, house
        for entry in entries:
            assert entry["mantra"].startswith("Om")
            assert entry["practice"]["citation"]


def test_guidance_covers_the_planets_the_house_involves_and_no_others():
    for house in range(1, 13):
        data = reading(house)
        involved = {o["body"] for o in data["occupants"]} | {data["lord"]["name"]}
        assert {entry["body"] for entry in data["remedies"]} == involved, house


def test_what_is_struggling_is_marked_and_comes_first():
    """The gate now decides emphasis rather than whether anything is shown."""
    for house in range(1, 13):
        data = reading(house)
        struggling = {
            o["body"] for o in data["occupants"] if o["standing"] != "well placed"
        }
        if data["lord"]["standing"] != "well placed":
            struggling.add(data["lord"]["name"])
        flagged = {e["body"] for e in data["remedies"] if e["indicated"]}
        assert flagged == struggling, house
        marks = [entry["indicated"] for entry in data["remedies"]]
        assert marks == sorted(marks, reverse=True), house


def test_most_houses_carry_conduct_a_reader_can_act_on():
    """The Lal Kitab grid, not a rite: things to do and not do."""
    with_conduct = sum(
        1 for house in range(1, 13)
        for entry in reading(house)["remedies"] if entry["conduct"]
    )
    total = sum(len(reading(house)["remedies"]) for house in range(1, 13))
    assert with_conduct >= total - 3, f"only {with_conduct} of {total} carry conduct"


def test_each_occupant_carries_its_star_and_what_the_texts_say_of_it():
    housed = [h for h in range(1, 13) if reading(h)["occupants"]]
    assert housed
    for house in housed:
        for occupant in reading(house)["occupants"]:
            assert occupant["nakshatra"]["name"] in NAKSHATRAS
            assert 1 <= occupant["nakshatra"]["pada"] <= 4
            assert occupant["nakshatra"]["says"]["citation"]
            for verse in occupant["classical"]:
                assert verse["citation"].startswith("Brihat Parashara")


def test_the_classical_verses_come_from_this_houses_own_chapter():
    for house in range(1, 13):
        for occupant in reading(house)["occupants"]:
            for verse in occupant["classical"]:
                assert verse["chapter"] == 11 + house, (house, verse["citation"])


def test_the_ninth_part_chart_reads_its_own_signs_but_says_so():
    """Its dignity and strength stay the birth chart's, because that is where they are
    defined; a reader who is not told that would take them for the varga's."""
    birth, ninth = reading(1, "D1"), reading(1, "D9")
    assert ninth["note"] and "D9" in ninth["note"]
    assert birth["note"] is None
    # The same twelve subjects, read in a different set of signs.
    assert birth["means"] == ninth["means"]
    assert any(reading(h, "D9")["sign"] != reading(h, "D1")["sign"] for h in range(1, 13))


def test_the_ninth_part_chart_leaves_out_what_does_not_apply_to_it():
    """Ashtakavarga and bhava bala are defined on the birth chart. Computing them from a
    varga would produce a number with nothing behind it."""
    ninth = reading(7, "D9")
    assert ninth["support"] is None
    assert ninth["strength"] is None
    assert reading(7, "D1")["support"] is not None


def test_a_house_reading_never_reaches_the_reader_as_a_table_key():
    for varga in ("D1", "D9"):
        for house in range(1, 13):
            data = reading(house, varga)
            shown = [data["headline"], data["means"], *data["because"]]
            for occupant in data["occupants"]:
                shown += [occupant["plain"], *occupant["reasons"]]
            shown.append(data["lord"]["plain"])
            for line in shown:
                assert "_" not in line, line


# --- bhava bala -------------------------------------------------------------


def test_bhava_bala_covers_the_twelve_and_sums_its_parts():
    assert set(BHAVA) == set(range(1, 13))
    for house, bala in BHAVA.items():
        parts = bala.dig + bala.drik + bala.lord_bala + bala.guests + bala.rising
        assert bala.total == pytest.approx(parts)
        assert bala.rupas == pytest.approx(bala.total / 60.0)


def test_a_house_holding_jupiter_gains_a_rupa_and_one_holding_saturn_loses_one():
    """BPHS ch. 27 v. 30, and the one part of bhava bala that is a flat number."""
    for body, expected in (("Jupiter", 60.0), ("Mercury", 60.0), ("Saturn", -60.0)):
        house = NATAL.facts.house_of(body)
        assert BHAVA[house].guests <= expected if expected < 0 else BHAVA[house].guests >= expected


def test_the_first_bhava_is_measured_from_the_ascendant_itself():
    """The bhava runs from the lagna's own degree, so the first one's directional
    strength is the same measurement the ascendant would get."""
    from astro.core.shadbala import _arc

    angles = {
        "ascendant": CHART.ascendant,
        "descendant": (CHART.ascendant + 180.0) % 360.0,
        "midheaven": CHART.midheaven,
        "nadir": (CHART.midheaven + 180.0) % 360.0,
    }
    from astro.core.shadbala import _bhava_angle

    sign = int(CHART.ascendant // 30) % 12
    weak = angles[_bhava_angle(sign, CHART.ascendant % 30.0)]
    assert BHAVA[1].dig == pytest.approx(_arc(CHART.ascendant - weak) / 3.0)


# --- the Lal Kitab conduct table --------------------------------------------


def test_the_conduct_grid_parses_most_of_its_cells():
    """Bansal pp. 224-229. The gaps are the book's own — it says outright that some
    placements have no measure prescribed."""
    table = texts.conduct_table()
    assert len(table) >= 85, f"only {len(table)} of 108 cells parsed"
    for body in ("Jupiter", "Saturn", "Rahu"):
        houses = sorted(house for (who, house) in table if who == body)
        assert houses == list(range(1, 13)), (body, houses)


def test_the_moon_block_is_found_despite_having_no_heading():
    """Its heading is missing from the scan; the block is identified by the house
    numbers restarting inside what looks like the Sun's span."""
    table = texts.conduct_table()
    moon = sorted(house for (who, house) in table if who == "Moon")
    assert len(moon) >= 6, moon
    assert "Respect the mother" in table[("Moon", 7)]


def test_conduct_cells_hold_their_own_text_and_not_the_next_one():
    table = texts.conduct_table()
    assert table[("Jupiter", 1)].startswith("Stay away from shameless girl")
    assert table[("Sun", 1)].startswith("Native should bore a hand pump")
    # A cell that swallowed the next graha's heading would carry it in the text.
    for text in table.values():
        assert not texts._CONDUCT_HEAD.search(text)


def test_every_graha_has_a_deity_a_colour_and_something_to_give_away():
    expected = {
        "Sun": "Vishnu", "Moon": "Shiva", "Mars": "Hanuman", "Mercury": "Durga",
        "Jupiter": "Bramha", "Venus": "Laxmi", "Saturn": "Bhairava",
        "Rahu": "Saraswati", "Ketu": "Ganesh",
    }
    for body, deity in expected.items():
        found = texts.planet_profile(body)
        assert found, body
        text, hit = found
        assert deity in text, (body, text)
        assert hit.page == 219
        # Ketu is last in the table and used to run into the next numbered section.
        assert "WARINING" not in text and "WARNING" not in text


def test_the_guidance_shows_the_cell_and_not_the_whole_page():
    """`_cite` carries a "text" of its own — the entire page it came from. Spreading it
    after the cell's own text replaced every conduct block with all of Bansal p. 225,
    and the table-level tests could not see it because the table was fine."""
    for house in range(1, 13):
        for entry in reading(house)["remedies"]:
            for block in (entry["conduct"], entry["profile"]):
                if not block:
                    continue
                assert len(block["text"]) < 1500, (house, entry["body"], len(block["text"]))
                assert not texts._CONDUCT_HEAD.search(block["text"]), entry["body"]
    # Every conduct block on the page must be the table's cell verbatim.
    table = texts.conduct_table()
    checked = 0
    for house in range(1, 13):
        data = reading(house)
        for entry in data["remedies"]:
            if not entry["conduct"]:
                continue
            # The lord is advised for the house it actually stands in, not the one it
            # rules, so look the cell up by where the graha is.
            where = next(
                (o["house"] for o in data["occupants"] if o["body"] == entry["body"]),
                data["lord"]["sits_in_house"],
            )
            assert entry["conduct"]["text"] == table[(entry["body"], where)], (
                house, entry["body"]
            )
            checked += 1
    assert checked >= 12, checked


# --- the ninth-part chart ---------------------------------------------------


def test_a_division_reads_dignity_from_its_own_signs():
    """Reporting the birth chart's dignity beside a divisional sign described a
    different planet — "neutral" next to a navamsa the graha is exalted in."""
    # Collected across the whole chart, because a graha sits in different houses in
    # the two and a per-house comparison never lines the same body up.
    def dignities(varga: str) -> dict[str, str]:
        return {
            o["body"]: o["dignity"]
            for house in range(1, 13)
            for o in reading(house, varga)["occupants"]
        }

    birth, ninth = dignities("D1"), dignities("D9")
    assert set(birth) == set(ninth)
    differs = [body for body in birth if birth[body] != ninth[body]]
    assert differs, "no graha's dignity changed between the charts, which cannot be"


def test_the_lord_is_described_from_one_chart_at_a_time():
    """Its house was the division's and its sign the birth chart's, so a single
    sentence pointed at two different places."""
    from astro.core.varga import varga_chart

    table = varga_chart(CHART, 9)
    for house in range(1, 13):
        lord = reading(house, "D9")["lord"]
        assert lord["sits_in_sign"] == table.sign_name(lord["name"]), house
        assert lord["sits_in_house"] == table.house_of(lord["name"]), house


def test_a_division_says_what_it_is_read_for_and_the_birth_chart_does_not():
    """ch. 7 v. 1-8 gives "spouse from Navāńś". Its entry for the birth chart is "the
    physique from Lagn", which is about the ascendant; printing that over the seventh
    house claimed the birth chart is read for the body."""
    ninth = reading(7, "D9")["read_for"]
    assert ninth["subject"] == "the spouse"
    assert ninth["citation"].startswith("Brihat Parashara")
    assert reading(7, "D1")["read_for"] is None


def test_the_division_carries_its_own_aspects():
    """A divisional chart reporting no aspects at all knows less than it does — the
    seventh is aspected in every chart there is."""
    links = sum(len(reading(h, "D9")["aspected_by"]) for h in range(1, 13))
    assert links > 0


def test_the_navamsa_class_of_every_occupant_is_named():
    """ch. 6 v. 12: each ninth of a sign is divine, human or devilish."""
    seen = set()
    for house in range(1, 13):
        for occupant in reading(house, "D9")["occupants"]:
            assert occupant["varga_class"]["name"] in ("Deva", "Manushya", "Rakshasa")
            seen.add(occupant["varga_class"]["name"])
        for occupant in reading(house, "D1")["occupants"]:
            assert occupant["varga_class"] is None
    assert len(seen) >= 2


def test_conduct_follows_the_graha_to_where_it_really_stands():
    """Lal Kitab is about the birth chart. Keying its measures to a divisional house
    would prescribe for a house the native does not have."""
    table = texts.conduct_table()
    for house in range(1, 13):
        data = reading(house, "D9")
        for entry in data["remedies"]:
            if not entry["conduct"]:
                continue
            where = next(
                (o["rasi_house"] for o in data["occupants"] if o["body"] == entry["body"]),
                NATAL.facts.house_of(entry["body"]),
            )
            assert entry["conduct"]["text"] == table[(entry["body"], where)], (
                house, entry["body"]
            )


def test_vargottama_is_reported_where_it_holds():
    from astro.core.strength import SEVEN

    expected = {body for body in SEVEN if NATAL.facts.is_vargottama(body)}
    seen = {
        o["body"] for h in range(1, 13)
        for o in reading(h, "D9")["occupants"] if o["vargottama"]
    }
    assert seen == expected & seen
