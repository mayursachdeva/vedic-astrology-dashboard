"""Tests for offline place lookup.

The point of this feature is that nobody types coordinates, so what matters is that a
typed name resolves to the right point on the earth and that it does so fast enough to
run on every keystroke.
"""

from __future__ import annotations

import time

import pytest

from astro.core.places import Place, build_database, coverage, fold, search


def test_folding_ignores_what_transliterations_disagree_about():
    assert fold("Bengalūru") == fold("Bengaluru")
    assert fold("  New   Delhi ") == "new delhi"
    assert fold("Thiruvananthapuram!") == "thiruvananthapuram"


def test_a_label_hides_a_bare_numeric_admin_code():
    """GeoNames admin1 is "16" for Maharashtra, which tells a reader nothing."""
    numeric = Place("Nashik", "India", "16", 20.0, 73.8, "Asia/Kolkata", 1_000_000)
    named = Place("Nashik", "India", "Maharashtra", 20.0, 73.8, "Asia/Kolkata", 1_000_000)
    assert numeric.label == "Nashik, India"
    assert named.label == "Nashik, Maharashtra, India"


def test_a_one_letter_query_returns_nothing():
    """Typeahead fires on every keystroke; one letter would match half the world."""
    assert search("D") == []
    assert search("") == []


def test_a_major_city_resolves_to_the_right_coordinates():
    results = search("New Delhi", limit=3)
    assert results
    best = results[0]
    assert "Delhi" in best.name
    assert best.latitude == pytest.approx(28.6, abs=0.3)
    assert best.longitude == pytest.approx(77.2, abs=0.3)
    assert best.timezone == "Asia/Kolkata"


def test_the_biggest_place_of_a_shared_name_comes_first():
    """Several places are called Delhi; the one with eleven million people is meant."""
    results = search("Delhi", limit=5)
    assert results[0].population > 1_000_000
    assert results[0].population == max(place.population for place in results)


def test_a_state_narrows_an_ambiguous_name():
    narrowed = search("Nashik, Maharashtra", limit=3)
    assert narrowed
    assert narrowed[0].name == "Nashik"
    assert all("India" in place.country for place in narrowed)


def test_an_unmatched_context_still_returns_the_town():
    """A misspelled state should not hide the place."""
    assert search("Porbandar, Gujrat", limit=3)


def test_results_are_deduplicated_across_the_two_tiers():
    results = search("Porbandar", limit=8)
    keys = [(place.name, round(place.latitude, 2)) for place in results]
    assert len(keys) == len(set(keys))


def test_search_is_fast_enough_to_run_on_every_keystroke():
    """Holding the full dump as objects cost a second and a half per search, which is
    why it is an indexed file rather than a list."""
    search("Delhi")  # warm the connection
    start = time.time()
    for query in ("Del", "Delh", "Delhi", "Mumb", "Chenn"):
        search(query, limit=8)
    average = (time.time() - start) / 5
    assert average < 0.4, f"{average * 1000:.0f}ms per search is too slow for typeahead"


def test_coverage_reports_both_tiers():
    summary = coverage()
    assert summary["bundled"] > 30_000
    assert summary["total"] == summary["bundled"] + summary["indexed"]


def test_building_an_index_from_a_dump(tmp_path):
    """One malformed row must not take the file down with it."""
    dumps = tmp_path / "dumps"
    dumps.mkdir()
    good = "\t".join(
        ["1", "Testville", "Testville", "", "12.5", "77.5", "P", "PPL", "IN", "",
         "16", "", "", "", "5000", "", "", "Asia/Kolkata"]
    )
    river = good.replace("\tPPL\t", "\tSTM\t")  # a stream, not a place
    broken = "\t".join(["2", "Broken", "", "", "not-a-number", "x", "P", "PPL", "IN"])
    (dumps / "IN.txt").write_text("\n".join([good, river, broken]))

    database = tmp_path / "places.db"
    written = build_database(dumps, database, admin_names={"IN.16": "Maharashtra"})
    assert written == 1

    found = search("Testville", database=database)
    assert found[0].admin == "Maharashtra"
    assert found[0].timezone == "Asia/Kolkata"
