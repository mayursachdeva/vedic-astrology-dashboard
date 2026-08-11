"""End-to-end tests for the store, service composition and HTTP layer."""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from astro import store
from astro.api.main import app, set_db_path
from astro.service import build_natal_chart, chart_payload, jd_to_iso
from astro.store import Profile

DELHI = {"latitude": 28.6139, "longitude": 77.2090}

SAMPLE = {
    "name": "Test Native",
    "birth_local": "1990-01-01T12:00:00",
    "place": "New Delhi",
    "relation": "self",
    **DELHI,
}


@pytest.fixture()
def client(tmp_path):
    set_db_path(tmp_path / "test.db")
    return TestClient(app)


@pytest.fixture()
def connection(tmp_path):
    return store.connect(tmp_path / "store.db")


# --- store ------------------------------------------------------------------


def test_profile_roundtrips_through_sqlite(connection):
    saved = store.create_profile(
        connection,
        Profile(name="A", birth_local=datetime(1990, 1, 1, 12, 0), **DELHI),
    )
    assert saved.id is not None

    loaded = store.get_profile(connection, saved.id)
    assert loaded.name == "A"
    assert loaded.birth_local == datetime(1990, 1, 1, 12, 0)
    assert loaded.ayanamsa == "lahiri"
    assert loaded.use_true_lmt is False


def test_profiles_can_be_listed_updated_and_deleted(connection):
    first = store.create_profile(
        connection, Profile(name="A", birth_local=datetime(1990, 1, 1), **DELHI)
    )
    store.create_profile(
        connection, Profile(name="B", birth_local=datetime(1991, 2, 3), **DELHI)
    )
    assert [p.name for p in store.list_profiles(connection)] == ["A", "B"]

    from dataclasses import replace

    updated = store.update_profile(connection, replace(first, name="A renamed"))
    assert updated.name == "A renamed"

    store.delete_profile(connection, first.id)
    assert [p.name for p in store.list_profiles(connection)] == ["B"]

    with pytest.raises(KeyError):
        store.get_profile(connection, first.id)
    with pytest.raises(KeyError):
        store.delete_profile(connection, first.id)


def test_invalid_profiles_are_rejected_at_construction():
    with pytest.raises(ValueError):
        Profile(name="  ", birth_local=datetime(1990, 1, 1), **DELHI)
    with pytest.raises(ValueError):
        Profile(name="A", birth_local=datetime(1990, 1, 1), latitude=91.0, longitude=0.0)
    with pytest.raises(ValueError):
        Profile(
            name="A",
            birth_local=datetime(1990, 1, 1),
            time_confidence="pretty sure",
            **DELHI,
        )


# --- service composition ----------------------------------------------------


def test_natal_chart_wires_timezone_ephemeris_and_dasha_together():
    profile = Profile(name="A", birth_local=datetime(1990, 1, 1, 12, 0), **DELHI)
    natal = build_natal_chart(profile)

    assert natal.moment.timezone_name == "Asia/Kolkata"
    assert natal.moment.utc_datetime == datetime(1990, 1, 1, 6, 30)
    assert natal.chart.positions["Moon"].nakshatra_name == "Dhanishta"
    assert natal.dashas[0].lord == "Mars"  # Dhanishta is ruled by Mars


def test_profile_settings_are_honoured_end_to_end():
    lahiri = build_natal_chart(
        Profile(name="A", birth_local=datetime(1990, 1, 1, 12, 0), **DELHI)
    )
    raman = build_natal_chart(
        Profile(
            name="A", birth_local=datetime(1990, 1, 1, 12, 0), ayanamsa="raman", **DELHI
        )
    )
    assert lahiri.chart.ayanamsa == "lahiri"
    assert raman.chart.ayanamsa == "raman"
    assert lahiri.chart.positions["Sun"].longitude != raman.chart.positions["Sun"].longitude


def test_chart_payload_is_complete_and_self_describing():
    natal = build_natal_chart(
        Profile(name="A", birth_local=datetime(1990, 1, 1, 12, 0), **DELHI)
    )
    payload = chart_payload(natal, at_jd=natal.moment.jd_ut)

    assert payload["birth"]["offset"] == "UTC+05:30"
    assert payload["settings"]["ayanamsa"] == "lahiri"
    assert payload["lagna"]["sign_name"] == "Pisces"
    assert len(payload["positions"]) == 9
    assert payload["positions"]["Ketu"]["retrograde"] is True
    assert set(payload["vargas"]) == {"D1", "D9", "D10"}
    assert payload["vargas"]["D9"]["name"] == "Navamsa"
    assert len(payload["dasha"]["mahadashas"]) == 9
    # At the moment of birth the chain is the balance-holding lord at every level.
    assert payload["dasha"]["current"][0]["lord"] == "Mars"
    assert payload["dasha"]["balance_at_birth"]["lord"] == "Mars"


def test_payload_carries_yogas_with_citations_and_evidence():
    natal = build_natal_chart(
        Profile(name="A", birth_local=datetime(1990, 1, 1, 12, 0), **DELHI)
    )
    payload = chart_payload(natal, at_jd=natal.moment.jd_ut)

    assert isinstance(payload["yogas"], list)
    for yoga in payload["yogas"]:
        assert yoga["citation"], f"{yoga['id']} has no citation"
        assert yoga["plain"], f"{yoga['id']} has no plain-language wording"
        assert yoga["evidence"], f"{yoga['id']} fired without evidence"
        assert yoga["polarity"] in ("benefic", "malefic", "neutral")


def test_unlocated_citations_are_flagged_in_the_payload():
    """A rule whose verse was never found must never read as though it had been."""
    natal = build_natal_chart(
        Profile(name="A", birth_local=datetime(1990, 1, 1, 12, 0), **DELHI)
    )
    payload = chart_payload(natal, at_jd=natal.moment.jd_ut)
    for yoga in payload["yogas"]:
        if yoga["citation_located"]:
            assert ("ch." in yoga["citation"] and "v." in yoga["citation"]) or (
                "p." in yoga["citation"]
            )
        else:
            assert "no source located" in yoga["citation"]


def test_payload_carries_ashtakavarga_totalling_337():
    natal = build_natal_chart(
        Profile(name="A", birth_local=datetime(1990, 1, 1, 12, 0), **DELHI)
    )
    varga = chart_payload(natal, at_jd=natal.moment.jd_ut)["ashtakavarga"]

    assert len(varga["houses"]) == 12
    assert varga["sav_total"] == 337
    assert sum(house["sav"] for house in varga["houses"]) == 337
    assert varga["houses"][0]["house"] == 1
    for house in varga["houses"]:
        assert house["reading"] in ("strong", "average", "weak")
        assert sum(house["bav"].values()) == house["sav"]


def test_payload_carries_planetary_conditions():
    natal = build_natal_chart(
        Profile(name="A", birth_local=datetime(1990, 1, 1, 12, 0), **DELHI)
    )
    conditions = chart_payload(natal, at_jd=natal.moment.jd_ut)["conditions"]

    assert len(conditions) == 9
    assert conditions["Sun"]["dignity"]
    assert isinstance(conditions["Jupiter"]["owns_houses"], list)
    assert isinstance(conditions["Mars"]["aspects_houses"], list)


def test_jd_to_iso_roundtrips_a_known_instant():
    from astro.core.ephemeris import julian_day

    assert jd_to_iso(julian_day(1990, 1, 1, 6.5)) == "1990-01-01T06:30:00"


# --- HTTP -------------------------------------------------------------------


def test_health_lists_the_supported_vargas(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["vargas"]["D9"] == "Navamsa"


def test_profile_crud_over_http(client):
    created = client.post("/api/profiles", json=SAMPLE)
    assert created.status_code == 201
    profile_id = created.json()["id"]

    assert len(client.get("/api/profiles").json()) == 1

    updated = client.put(
        f"/api/profiles/{profile_id}", json={**SAMPLE, "name": "Renamed"}
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed"

    assert client.delete(f"/api/profiles/{profile_id}").status_code == 204
    assert client.get("/api/profiles").json() == []


def test_missing_profile_gives_404_not_500(client):
    assert client.get("/api/profiles/999/chart").status_code == 404
    assert client.put("/api/profiles/999", json=SAMPLE).status_code == 404
    assert client.delete("/api/profiles/999").status_code == 404


def test_chart_endpoint_returns_the_dashboard_payload(client):
    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    payload = client.get(f"/api/profiles/{profile_id}/chart").json()

    assert payload["profile"]["name"] == "Test Native"
    assert payload["lagna"]["sign_name"] == "Pisces"
    assert payload["positions"]["Sun"]["sign_name"] == "Sagittarius"
    assert payload["dasha"]["current"], "there should always be an active dasha today"


def test_chart_endpoint_accepts_a_varga_selection(client):
    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    payload = client.get(f"/api/profiles/{profile_id}/chart?vargas=1,30,60").json()
    assert set(payload["vargas"]) == {"D1", "D30", "D60"}


def test_unsupported_varga_is_rejected_with_a_useful_message(client):
    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    response = client.get(f"/api/profiles/{profile_id}/chart?vargas=1,5")
    assert response.status_code == 422
    assert "shodasavarga" in response.json()["detail"]


def test_invalid_coordinates_are_rejected(client):
    response = client.post("/api/profiles", json={**SAMPLE, "latitude": 120.0})
    assert response.status_code == 422


def test_dasha_endpoint_returns_a_nested_tree(client):
    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    tree = client.get(f"/api/profiles/{profile_id}/dashas?depth=3").json()

    assert len(tree) == 9
    assert len(tree[0]["children"]) == 9
    assert len(tree[0]["children"][0]["children"]) == 9
    assert tree[0]["level_name"] == "mahadasha"
    assert tree[0]["children"][0]["level_name"] == "antardasha"


def test_dasha_depth_is_bounded(client):
    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    assert client.get(f"/api/profiles/{profile_id}/dashas?depth=9").status_code == 422


def test_timezone_lookup_endpoint(client):
    assert client.get("/api/timezone?latitude=28.61&longitude=77.20").json() == {
        "timezone": "Asia/Kolkata"
    }


def test_birth_time_warnings_reach_the_payload(client):
    """A 1943 Indian birth ran on wartime daylight saving; the dashboard must be told."""
    profile_id = client.post(
        "/api/profiles", json={**SAMPLE, "birth_local": "1943-06-15T12:00:00"}
    ).json()["id"]
    payload = client.get(f"/api/profiles/{profile_id}/chart").json()

    assert payload["birth"]["offset"] == "UTC+06:30"
    assert any("Daylight saving" in warning for warning in payload["birth"]["warnings"])


# --- transits ---------------------------------------------------------------


def test_transit_endpoint_reports_both_doctrines_and_dated_windows(client):
    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    payload = client.get(f"/api/profiles/{profile_id}/transits?months=36").json()

    assert len(payload["gochara"]) == 9
    for body, standing in payload["gochara"].items():
        assert 1 <= standing["house_from_moon"] <= 12
        assert standing["doctrines_agree"] == (
            standing["supported"] == standing["traditionally_good"]
        )

    assert payload["windows"], "three years should contain retrogrades at least"
    for window in payload["windows"]:
        assert window["start"] < window["end"]
        assert window["kind"] in ("retrograde", "combust", "sade_sati", "sign_transit")


def test_transit_confluence_shows_its_working(client):
    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    confluence = client.get(f"/api/profiles/{profile_id}/transits").json()["confluence"]

    assert confluence["reading"] in ("supported", "obstructed", "mixed")
    assert confluence["components"]
    assert "heuristic" in confluence["basis"]


def test_transit_horizon_is_bounded(client):
    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    assert client.get(f"/api/profiles/{profile_id}/transits?months=999").status_code == 422


# --- life stages, remedies, report and Q&A ----------------------------------


def test_life_stages_endpoint_returns_a_dated_timeline(client):
    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    payload = client.get(f"/api/profiles/{profile_id}/life-stages?years=8").json()

    assert payload["stages"]
    assert sum(1 for stage in payload["stages"] if stage["current"]) == 1
    for stage in payload["stages"]:
        assert stage["start"] < stage["end"]
        assert stage["headline"].endswith(".")
        assert stage["opened_by"]
        for domain in stage["domains"]:
            assert domain["score"] == sum(d["weight"] for d in domain["drivers"])


def test_life_stage_domains_cite_the_houses_they_rest_on(client):
    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    domains = client.get(f"/api/profiles/{profile_id}/life-stages").json()["domains"]
    assert set(domains) == {
        "Career", "Relationships", "Health", "Finance", "Family", "Learning",
    }
    for definition in domains.values():
        assert definition["houses"]
        assert "ch. 11" in definition["citation"]


def test_remedies_endpoint_groups_by_source_and_carries_a_disclaimer(client):
    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    payload = client.get(f"/api/profiles/{profile_id}/remedies").json()
    assert payload["count"] == sum(len(g) for g in payload["by_source"].values())
    assert "not medical, financial or legal advice" in payload["disclaimer"]


def test_report_endpoint_returns_markdown(client):
    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    response = client.get(f"/api/profiles/{profile_id}/report?years=5")
    assert response.status_code == 200
    assert response.text.startswith("# Vedic astrology reading")
    assert "## Remedies" in response.text


def test_asking_when_ollama_is_unreachable_says_exactly_what_is_wrong(client, monkeypatch):
    """The dashboard must be able to tell the user what to start, and make clear that
    nothing else is affected."""
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")  # nothing listens here
    import astro.interpret.qa as qa

    monkeypatch.setattr(qa, "DEFAULT_HOST", "http://127.0.0.1:9")

    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    response = client.post(
        f"/api/profiles/{profile_id}/ask", json={"question": "What about my career?"}
    )
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "ollama serve" in detail
    assert "works without it" in detail


# --- synastry ---------------------------------------------------------------


def test_synastry_endpoint_scores_two_profiles(client):
    first = client.post("/api/profiles", json=SAMPLE).json()["id"]
    second = client.post(
        "/api/profiles",
        json={**SAMPLE, "name": "Partner", "birth_local": "1992-06-15T09:30:00"},
    ).json()["id"]

    payload = client.get(f"/api/synastry?first={first}&second={second}").json()

    assert payload["maximum"] == 36
    assert payload["total"] == sum(kuta["points"] for kuta in payload["kutas"])
    assert payload["verdict"] in ("strong", "workable", "weak")
    assert len(payload["kutas"]) == 8
    for kuta in payload["kutas"]:
        assert 0 <= kuta["points"] <= kuta["maximum"]
        assert kuta["reason"]
        if kuta["precision"] == "simplified":
            assert kuta["caveat"]


def test_synastry_says_the_kuta_system_is_not_in_the_ingested_text(client):
    first = client.post("/api/profiles", json=SAMPLE).json()["id"]
    second = client.post(
        "/api/profiles", json={**SAMPLE, "name": "Partner"}
    ).json()["id"]
    payload = client.get(f"/api/synastry?first={first}&second={second}").json()

    assert "not in the ingested" in payload["note"]
    for reading in payload["seventh_house"].values():
        assert "ch. 18" in reading["citation"]


def test_comparing_someone_with_themselves_is_rejected(client):
    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    response = client.get(f"/api/synastry?first={profile_id}&second={profile_id}")
    assert response.status_code == 422


# --- panchanga --------------------------------------------------------------


def test_panchanga_endpoint_covers_birth_and_today(client):
    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    payload = client.get(f"/api/profiles/{profile_id}/panchanga").json()

    assert set(payload) == {"birth", "today"}
    for moment in payload.values():
        assert moment["paksha"] in ("Shukla", "Krishna")
        assert 1 <= moment["tithi"]["index"] <= 30
        assert 1 <= moment["karana"]["index"] <= 60
        assert 1 <= moment["yoga"]["index"] <= 27
        assert moment["vara"]["name"]
        for limb in ("tithi", "karana", "yoga", "nakshatra"):
            assert moment[limb]["ends"] > moment["at"]


def test_panchanga_flags_carry_their_citation(client):
    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    payload = client.get(f"/api/profiles/{profile_id}/panchanga").json()
    for moment in payload.values():
        for flag in moment["flags"]:
            assert "ch. 85" in flag or "ch. 92" in flag


def test_a_house_reading_answers_without_a_model_in_the_path(client):
    """Clicking a house has to answer at once, so nothing here may be generated."""
    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    for varga in ("D1", "D9"):
        for house in (1, 6, 12):
            data = client.get(
                f"/api/profiles/{profile_id}/houses/{house}?varga={varga}"
            ).json()
            assert data["house"] == house and data["varga"] == varga
            assert data["represents"]["citation"]
            assert data["sign_says"]["text"]
            assert data["lord"]["name"]
            assert data["because"]


def test_a_house_reading_refuses_a_division_it_is_not_defined_for(client):
    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    assert client.get(f"/api/profiles/{profile_id}/houses/13").status_code == 422
    assert client.get(
        f"/api/profiles/{profile_id}/houses/1?varga=D10"
    ).status_code == 422


def test_shadbala_reaches_the_dashboard_with_its_parts_intact(client):
    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    data = client.get(f"/api/profiles/{profile_id}/chart").json()["shadbala"]

    assert data["hour_based_parts"] is True
    assert data["strongest"] in data["grahas"]
    assert len(data["grahas"]) == 7
    for body, bala in data["grahas"].items():
        assert bala["total"] == pytest.approx(
            sum(bala["sources"].values()) + bala["yuddha"], abs=0.05
        )
        assert bala["strong"] == (bala["total"] >= bala["required"])
        assert bala["rupas"] == pytest.approx(bala["total"] / 60.0, abs=0.02)


def test_the_qa_tools_report_strength_alongside_dignity(client):
    """A graha can be uncomfortable and still able to deliver, or the reverse.

    Answering "is my Saturn strong?" from dignity alone gets it wrong about as often as
    right, so the tool the model calls carries both.
    """
    from astro.interpret.life_stages import life_stages
    from astro.interpret.tools import ChartTools
    from astro.service import now_jd

    natal = build_natal_chart(
        Profile(name="A", birth_local=datetime(1990, 1, 1, 12, 0), **DELHI)
    )
    start = now_jd()
    tools = ChartTools(
        facts=natal.facts, dashas=natal.dashas,
        stages=life_stages(natal.facts, natal.dashas, start, start + 3650.0),
        profile_name="A",
    )
    saturn = tools.get_planet("Saturn")
    assert saturn["dignity"] == "enemy"
    assert saturn["strength"]["verdict"] == "strong enough"
    assert tools.get_planet("Rahu")["strength"] is None


def test_ashtakavarga_payload_carries_the_reductions_with_their_citation(client):
    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    varga = client.get(f"/api/profiles/{profile_id}/chart").json()["ashtakavarga"]

    reductions = varga["reductions"]
    assert "ch. 67" in reductions["citation"]
    assert len(reductions["by_planet"]) == 7
    for body, values in reductions["by_planet"].items():
        assert values["reduced_total"] == sum(values["reduced"])
        assert values["reduced_total"] <= varga["totals"][body]
        assert values["sodhya_pinda"] == values["rasi_pinda"] + values["graha_pinda"]


# --- place lookup -----------------------------------------------------------


def test_place_search_returns_usable_coordinates(client):
    payload = client.get("/api/places?q=New Delhi").json()
    assert payload["results"]
    best = payload["results"][0]
    assert {"name", "label", "latitude", "longitude", "timezone"} <= set(best)
    assert 28.0 < best["latitude"] < 29.0
    assert 76.5 < best["longitude"] < 78.0
    assert best["timezone"] == "Asia/Kolkata"


def test_a_profile_can_be_created_from_a_searched_place(client):
    """The whole point: nobody types coordinates."""
    place = client.get("/api/places?q=Porbandar").json()["results"][0]
    created = client.post(
        "/api/profiles",
        json={
            "name": "From search",
            "birth_local": "1950-05-05T09:15:00",
            "place": place["label"],
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "timezone_name": place["timezone"],
        },
    )
    assert created.status_code == 201

    chart = client.get(f"/api/profiles/{created.json()['id']}/chart").json()
    assert chart["birth"]["timezone"] == "Asia/Kolkata"
    assert chart["lagna"]["sign_name"]


def test_place_search_limit_is_bounded(client):
    assert client.get("/api/places?q=Delhi&limit=100").status_code == 422


# --- the corpus, reachable from the interface -------------------------------


def test_corpus_works_lists_every_ingested_text(client):
    works = client.get("/api/corpus/works").json()
    assert len(works) >= 20
    names = {work["work"] for work in works}
    assert "Brihat Parashara Hora Shastra" in names
    assert any("Raman" in name for name in names)
    for work in works:
        assert work["passages"] > 0
        assert isinstance(work["versified"], bool)


def test_corpus_search_returns_passages_with_citations(client):
    payload = client.get("/api/corpus/search?q=Vasumathi").json()
    assert payload["results"]
    for hit in payload["results"]:
        assert hit["citation"]
        assert hit["text"].strip()


def test_a_citation_can_be_opened_to_the_passage_it_names(client):
    """The point of citing. A reference nobody can check is decoration."""
    payload = client.get(
        "/api/corpus/passage?work=Brihat Parashara Hora Shastra&chapter=66&verse=56-58"
    ).json()
    from astro.corpus.search import _fold

    assert payload["citation"] == "Brihat Parashara Hora Shastra, ch. 66, v. 56-58"
    # The text spells it "Śukr"; compare folded, the same way search does.
    text = _fold(payload["passages"][0]["text"])
    assert "sukr" in text and "ashtakavarg" in text


def test_a_page_citation_can_be_opened_too(client):
    payload = client.get(
        "/api/corpus/passage?work=Elements of Vedic Astrology (K. S. Charak)&page=376"
    ).json()
    assert payload["passages"]
    assert "p. 376" in payload["citation"]


def test_an_unknown_citation_gives_404_not_an_empty_page(client):
    response = client.get("/api/corpus/passage?work=Nonexistent Work&page=1")
    assert response.status_code == 404


def test_every_located_rule_citation_resolves_to_a_real_passage(client):
    """The strongest form of the promise: not just that a rule names a source, but that
    the source can be opened and read. A citation that resolves to nothing is worse
    than none, because it looks checked."""
    from astro.rules.engine import load_rules

    for rule in load_rules():
        if not rule.citation.located:
            continue
        params = {"work": rule.citation.text}
        if rule.citation.chapter:
            params["chapter"] = rule.citation.chapter
        if rule.citation.verse:
            params["verse"] = rule.citation.verse
        if rule.citation.page:
            params["page"] = rule.citation.page
        response = client.get("/api/corpus/passage", params=params)
        assert response.status_code == 200, f"{rule.id} cites {rule.citation}, which does not resolve"


def test_findings_carry_a_structured_reference_the_interface_can_resolve(client):
    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    payload = client.get(f"/api/profiles/{profile_id}/chart").json()
    for yoga in payload["yogas"]:
        assert "citation_ref" in yoga
        if yoga["citation_located"]:
            assert yoga["citation_ref"]["work"]


# --- the precomputed reading -------------------------------------------------


def test_reading_endpoint_lists_every_section_even_before_generation(client):
    """Home must render from stored data with no model call in the path, so the shape
    of the reading is known before a word of it exists."""
    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    payload = client.get(f"/api/profiles/{profile_id}/reading").json()

    keys = [section["key"] for section in payload["sections"]]
    assert "overview" in keys and "career" in keys and "remedies" in keys
    assert all(section["status"] == "missing" for section in payload["sections"])
    assert payload["progress"]["written"] == 0
    assert payload["progress"]["complete"] is False


def test_reading_generation_is_refused_clearly_when_the_model_is_down(client, monkeypatch):
    import astro.interpret.qa as qa

    # Patched on the module, which only works because the host is read at call time
    # rather than bound as a default argument — it was, and this test reached the real
    # Ollama and started an eleven-minute generation inside the suite.
    monkeypatch.setattr(qa, "DEFAULT_HOST", "http://127.0.0.1:9")
    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    response = client.post(f"/api/profiles/{profile_id}/reading")
    assert response.status_code == 503
    assert "ollama serve" in response.json()["detail"]


def test_asking_for_an_unknown_section_is_rejected(client, monkeypatch):
    monkeypatch.setattr(
        "astro.interpret.qa.available_models", lambda *a, **k: ["qwen3:8b"]
    )
    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    response = client.post(f"/api/profiles/{profile_id}/reading?sections=nonsense")
    assert response.status_code == 422


def test_a_stored_reading_is_returned_with_its_status(client):
    from astro import store as store_module
    from astro.api import main as api
    from astro.interpret.reading import STATUS_OK, SectionResult, save_section

    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    with store_module.connect(api._db_path) as connection:
        save_section(connection, profile_id, SectionResult(
            "overview", "The shape of this chart", "A written overview.", STATUS_OK,
            "qwen3:8b", 0))

    payload = client.get(f"/api/profiles/{profile_id}/reading").json()
    overview = next(s for s in payload["sections"] if s["key"] == "overview")
    assert overview["body"] == "A written overview."
    assert overview["status"] == "ok"
    assert payload["progress"]["written"] == 1


def test_generation_never_starts_during_the_test_suite(client, monkeypatch):
    """TestClient runs background tasks synchronously, so a POST that got through
    would sit here writing a real reading for eleven minutes. It did once."""
    started = []
    from astro.api import main as api

    monkeypatch.setattr(api, "_run_generation", lambda *a: started.append(a))
    monkeypatch.setattr(
        "astro.interpret.qa.available_models", lambda *a, **k: ["qwen3:8b"]
    )
    profile_id = client.post("/api/profiles", json=SAMPLE).json()["id"]
    response = client.post(f"/api/profiles/{profile_id}/reading?sections=overview")

    assert response.status_code == 202
    assert response.json()["started"] is True
    assert started, "the background task should have been scheduled"
