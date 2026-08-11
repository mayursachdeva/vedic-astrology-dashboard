"""FastAPI app.

Thin by design: parse, call `service`, return JSON. No astrology logic lives here.
Binds to localhost only — this app holds family birth data and is not meant to be
reachable from the network.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import threading

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from astro import store
from astro.corpus.search import lookup as lookup_passage
from astro.corpus.search import search as search_corpus
from astro.corpus.search import works as corpus_works
from astro.core.places import coverage as place_coverage
from astro.core.places import search as search_places
from astro.core.timeloc import find_timezone
from astro.core.varga import SHODASAVARGA, VARGA_NAMES
from astro.service import (
    build_natal_chart,
    chart_payload,
    dasha_tree_payload,
    life_stages_payload,
    panchanga_payload,
    remedies_for,
    synastry_payload,
    transit_payload,
)
from astro.store import Profile

app = FastAPI(title="Vedic Astrology Dashboard", version="0.1.0")

# The Vite dev server runs on another port; both are local.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_db_path: Path | str = store.DEFAULT_DB_PATH


def set_db_path(path: Path | str) -> None:
    """Point the app at a different database. Used by tests."""
    global _db_path
    _db_path = path


def _connection():
    return store.connect(_db_path)


class ProfileIn(BaseModel):
    name: str
    birth_local: datetime
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    relation: str = ""
    place: str = ""
    timezone_name: str | None = None
    use_true_lmt: bool = False
    time_confidence: str = "to_the_minute"
    ayanamsa: str = "lahiri"
    node_type: str = "mean"
    house_system: str = "whole_sign"
    notes: str = ""

    def to_profile(self, profile_id: int | None = None) -> Profile:
        return Profile(
            id=profile_id,
            name=self.name,
            birth_local=self.birth_local.replace(tzinfo=None),
            latitude=self.latitude,
            longitude=self.longitude,
            relation=self.relation,
            place=self.place,
            timezone_name=self.timezone_name,
            use_true_lmt=self.use_true_lmt,
            time_confidence=self.time_confidence,
            ayanamsa=self.ayanamsa,
            node_type=self.node_type,
            house_system=self.house_system,
            notes=self.notes,
        )


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "vargas": {f"D{d}": VARGA_NAMES[d] for d in SHODASAVARGA}}


@app.get("/api/timezone")
def timezone_for(latitude: float, longitude: float) -> dict:
    try:
        return {"timezone": find_timezone(latitude, longitude)}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/places")
def get_places(q: str, limit: int = 8) -> dict:
    """Search birth places by name, entirely offline.

    Nothing about the query leaves this machine — see astro/core/places.py for why that
    matters more here than it looks.
    """
    if not 1 <= limit <= 25:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 25")
    return {
        "query": q,
        "results": [place.as_dict() for place in search_places(q, limit=limit)],
        "coverage": place_coverage(),
    }


@app.get("/api/profiles")
def get_profiles() -> list[dict]:
    with _connection() as connection:
        return [profile.as_dict() for profile in store.list_profiles(connection)]


@app.post("/api/profiles", status_code=201)
def post_profile(payload: ProfileIn) -> dict:
    try:
        profile = payload.to_profile()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    with _connection() as connection:
        return store.create_profile(connection, profile).as_dict()


@app.put("/api/profiles/{profile_id}")
def put_profile(profile_id: int, payload: ProfileIn) -> dict:
    try:
        profile = payload.to_profile(profile_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    with _connection() as connection:
        try:
            store.get_profile(connection, profile_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return store.update_profile(connection, profile).as_dict()


@app.delete("/api/profiles/{profile_id}", status_code=204)
def remove_profile(profile_id: int) -> None:
    with _connection() as connection:
        try:
            store.delete_profile(connection, profile_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error


def _load(profile_id: int):
    with _connection() as connection:
        try:
            return store.get_profile(connection, profile_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/profiles/{profile_id}/chart")
def get_chart(profile_id: int, vargas: str = "1,9,10") -> dict:
    profile = _load(profile_id)
    try:
        divisors = tuple(int(part) for part in vargas.split(",") if part.strip())
    except ValueError as error:
        raise HTTPException(
            status_code=422, detail=f"vargas must be comma-separated integers: {error}"
        ) from error

    unknown = [d for d in divisors if d not in SHODASAVARGA]
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"not part of the shodasavarga: {unknown}; valid: {list(SHODASAVARGA)}",
        )

    try:
        natal = build_natal_chart(profile)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return chart_payload(natal, vargas=divisors)


@app.get("/api/profiles/{profile_id}/dashas")
def get_dashas(profile_id: int, depth: int = 3) -> list[dict]:
    if not 1 <= depth <= 4:
        raise HTTPException(status_code=422, detail="depth must be between 1 and 4")
    natal = build_natal_chart(_load(profile_id), dasha_depth=depth)
    return dasha_tree_payload(natal)


@app.get("/api/profiles/{profile_id}/transits")
def get_transits(profile_id: int, months: int = 24) -> dict:
    if not 1 <= months <= 240:
        raise HTTPException(status_code=422, detail="months must be between 1 and 240")
    natal = build_natal_chart(_load(profile_id))
    return transit_payload(natal, months_ahead=months)


@app.get("/api/profiles/{profile_id}/life-stages")
def get_life_stages(profile_id: int, years: int = 12) -> dict:
    if not 1 <= years <= 120:
        raise HTTPException(status_code=422, detail="years must be between 1 and 120")
    natal = build_natal_chart(_load(profile_id))
    return life_stages_payload(natal, years_ahead=years)


@app.get("/api/profiles/{profile_id}/remedies")
def get_remedies(profile_id: int) -> dict:
    return remedies_for(build_natal_chart(_load(profile_id)))


@app.get("/api/profiles/{profile_id}/report", response_class=PlainTextResponse)
def get_report(profile_id: int, years: int = 10) -> str:
    """The full written reading, as markdown."""
    if not 1 <= years <= 120:
        raise HTTPException(status_code=422, detail="years must be between 1 and 120")
    from astro.interpret.report import build_report

    return build_report(build_natal_chart(_load(profile_id)), years_ahead=years)


class Turn(BaseModel):
    question: str
    answer: str


class QuestionIn(BaseModel):
    question: str
    # The exchange so far, so a follow-up knows what it is following up on.
    history: list[Turn] = Field(default_factory=list)


@app.post("/api/profiles/{profile_id}/ask")
def ask_question(profile_id: int, payload: QuestionIn) -> dict:
    """Answer a question about one native's chart, using a local model via Ollama.

    Returns 503 with a precise message when Ollama is not running or the model is not
    installed, so the dashboard can say what to do rather than showing a generic error.
    """
    from astro.interpret.life_stages import life_stages
    from astro.interpret.qa import ModelUnavailable, ask
    from astro.interpret.tools import ChartTools
    from astro.service import now_jd

    natal = build_natal_chart(_load(profile_id))
    start = now_jd()
    tools = ChartTools(
        facts=natal.facts,
        dashas=natal.dashas,
        stages=life_stages(natal.facts, natal.dashas, start, start + 3650.0),
        profile_name=natal.profile.name,
    )
    try:
        answer = ask(
            tools,
            payload.question,
            history=[(turn.question, turn.answer) for turn in payload.history],
        )
    except ModelUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {
        "answer": answer.text,
        "model": answer.model,
        "grounded": answer.grounded,
        "complete": answer.complete,
        "warning": answer.warning,
        "rounds": answer.rounds,
        "tool_calls": answer.tool_calls,
    }


@app.get("/api/profiles/{profile_id}/houses/{house}")
def get_house(profile_id: int, house: int, varga: str = "D1") -> dict:
    """Everything one house has to say, with every claim's chapter and verse attached.

    Deterministic and fast — no model is involved, so clicking a house answers at once
    rather than after a minute of generation.
    """
    from astro.core.panchanga import day_span
    from astro.core.shadbala import bhava_bala, shadbala
    from astro.interpret.houses import house_reading, payload as house_payload

    if not 1 <= house <= 12:
        raise HTTPException(status_code=422, detail="house must be 1 to 12")
    if varga not in ("D1", "D9"):
        raise HTTPException(
            status_code=422,
            detail="varga must be D1 or D9; the other divisions have no house reading",
        )

    natal = build_natal_chart(_load(profile_id))
    chart = natal.chart
    span = day_span(chart.jd_ut, chart.latitude, chart.longitude)
    balas = shadbala(chart, span)
    return house_payload(
        house_reading(
            chart, natal.facts, house,
            balas=balas, bhava=bhava_bala(chart, balas, span), varga=varga,
        )
    )


@app.post("/api/profiles/{profile_id}/ask/stream")
def ask_question_streaming(profile_id: int, payload: QuestionIn):
    """The same answer, sent as it is produced.

    Forty seconds of silence and forty seconds of visible work are different
    experiences, and most of those seconds are lookups rather than writing, so the
    lookups are reported too.
    """
    import json as _json

    from astro.interpret.life_stages import life_stages
    from astro.interpret.qa import DEFAULT_MODEL, ModelUnavailable, _check_model, ask_stream
    from astro.interpret.tools import ChartTools
    from astro.service import now_jd

    # Checked before the response starts, so a missing model is a 503 the dashboard can
    # act on rather than an error event arriving inside a successful stream.
    try:
        _check_model(DEFAULT_MODEL)
    except ModelUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    natal = build_natal_chart(_load(profile_id))
    start = now_jd()
    tools = ChartTools(
        facts=natal.facts,
        dashas=natal.dashas,
        stages=life_stages(natal.facts, natal.dashas, start, start + 3650.0),
        profile_name=natal.profile.name,
    )

    def events():
        try:
            history = [(turn.question, turn.answer) for turn in payload.history]
            for event in ask_stream(tools, payload.question, history=history):
                if event["type"] == "answer":
                    answer = event["answer"]
                    event = {
                        "type": "answer",
                        "answer": answer.text,
                        "model": answer.model,
                        "grounded": answer.grounded,
                        "complete": answer.complete,
                        "warning": answer.warning,
                        "rounds": answer.rounds,
                        "tool_calls": answer.tool_calls,
                    }
                yield f"data: {_json.dumps(event)}\n\n"
        except ModelUnavailable as error:
            # The status line is already 200 by the time this can happen, so the
            # failure has to travel as an event rather than as an HTTP error.
            yield f"data: {_json.dumps({'type': 'error', 'message': str(error)})}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/synastry")
def get_synastry(first: int, second: int) -> dict:
    """Compatibility between two saved profiles."""
    if first == second:
        raise HTTPException(
            status_code=422, detail="pick two different people to compare"
        )
    return synastry_payload(
        build_natal_chart(_load(first)), build_natal_chart(_load(second))
    )


@app.get("/api/profiles/{profile_id}/panchanga")
def get_panchanga(profile_id: int) -> dict:
    """The five limbs at birth and today, computed locally."""
    return panchanga_payload(build_natal_chart(_load(profile_id)))


@app.get("/api/corpus/works")
def get_corpus_works() -> list[dict]:
    """Every ingested text and how much of it there is."""
    return corpus_works()


@app.get("/api/corpus/search")
def get_corpus_search(q: str, limit: int = 10) -> dict:
    """Search the ingested texts. Keyword, diacritic-insensitive, entirely local."""
    if not 1 <= limit <= 50:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 50")
    hits = search_corpus(q, limit=limit)
    return {
        "query": q,
        "results": [
            {
                "citation": hit.citation,
                "work": hit.work,
                "chapter_title": hit.chapter_title,
                "heading": hit.heading,
                "excerpt": hit.excerpt(q),
                "text": hit.body,
            }
            for hit in hits
        ],
    }


@app.get("/api/corpus/passage")
def get_corpus_passage(
    work: str, chapter: str = "", verse: str = "", page: str = ""
) -> dict:
    """The passage a citation names, so a reader can check the claim against the text."""
    hits = lookup_passage(work, chapter=chapter, verse=verse, page=page)
    if not hits:
        raise HTTPException(
            status_code=404,
            detail=f"no passage found for {work} ch.{chapter or '-'} v.{verse or '-'} p.{page or '-'}",
        )
    return {
        "citation": hits[0].citation,
        "work": hits[0].work,
        "chapter_title": hits[0].chapter_title,
        "passages": [
            {"heading": hit.heading, "text": hit.body, "page": hit.page} for hit in hits
        ],
    }


# One generation per profile at a time. A reading takes minutes, and two runs racing
# each other would interleave writes to the same rows.
_generating: set[int] = set()
_generation_lock = threading.Lock()


def _run_generation(profile_id: int, only: tuple[str, ...] | None) -> None:
    from astro.interpret.reading import generate_reading
    from astro.interpret.qa import ModelUnavailable

    try:
        profile = _load(profile_id)
        natal = build_natal_chart(profile)
        with _connection() as connection:
            generate_reading(connection, natal, profile_id, only=only)
    except (ModelUnavailable, Exception):
        pass  # the failure is visible in the per-section status; nothing to raise to
    finally:
        with _generation_lock:
            _generating.discard(profile_id)


@app.get("/api/profiles/{profile_id}/reading")
def get_reading(profile_id: int) -> dict:
    """The written reading, as far as it has been generated.

    Never blocks on the model. Sections appear as they are written; whatever is missing
    is covered by the computed detail the interface shows anyway.
    """
    from astro.interpret.reading import load_reading, progress
    from astro.interpret.sections import SECTIONS

    _load(profile_id)
    with _connection() as connection:
        stored = load_reading(connection, profile_id)
        state = progress(connection, profile_id)

    return {
        "sections": [
            {
                "key": section.key,
                "title": section.title,
                "question": section.question,
                **(
                    stored.get(section.key)
                    or {"body": "", "status": "missing", "warning": "", "model": "",
                        "generated_at": None}
                ),
            }
            for section in SECTIONS
        ],
        "progress": {**state, "running": profile_id in _generating},
    }


@app.post("/api/profiles/{profile_id}/reading", status_code=202)
def post_reading(
    profile_id: int, tasks: BackgroundTasks, sections: str = ""
) -> dict:
    """Start writing the reading in the background."""
    from astro.interpret.qa import available_models, ModelUnavailable
    from astro.interpret.sections import BY_KEY

    _load(profile_id)
    try:
        available_models()
    except ModelUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    only = tuple(key for key in sections.split(",") if key.strip()) or None
    if only:
        unknown = [key for key in only if key not in BY_KEY]
        if unknown:
            raise HTTPException(status_code=422, detail=f"unknown sections: {unknown}")

    with _generation_lock:
        if profile_id in _generating:
            return {"started": False, "reason": "already writing"}
        _generating.add(profile_id)

    tasks.add_task(_run_generation, profile_id, only)
    return {"started": True, "sections": list(only) if only else "all"}


@app.get("/api/glossary")
def get_glossary() -> dict:
    """Plain phrasing and definitions, so the interface and the reading agree.

    The frontend used to carry its own hand-written copy of this, which could drift
    from the one the generated prose is held to.
    """
    from astro.interpret.glossary import GLOSSARY, HOUSE_MEANINGS
    from astro.interpret.life_stages import DIGNITY_PHRASES

    return {
        "terms": {
            term: {"plain": entry.plain, "definition": entry.definition}
            for term, entry in GLOSSARY.items()
        },
        "houses": HOUSE_MEANINGS,
        "dignities": DIGNITY_PHRASES,
    }
