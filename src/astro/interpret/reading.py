"""Generating and storing a written reading.

The dashboard used to hold its depth behind a question box: every deterministic endpoint
answered in under a second, but anything written took forty seconds because it was
produced on demand. So the substance was only ever a question away, never simply there.

This writes the reading once, in the background, and stores it. Reading is then instant
and asking becomes a follow-up rather than the only way in.

Each section is generated on its own, so a failure is local. A section that comes back
without having consulted a single fact, or that trails off telling the reader to call a
tool, is stored as failed — and the interface falls back to the deterministic text,
which is always correct if drier. A half-grounded paragraph presented as a reading is
worse than a plain one.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime

import httpx

from astro.interpret.factcheck import check as factcheck
from astro.interpret.glossary import bare_terms, explain
from astro.interpret.life_stages import life_stages
from astro.interpret.qa import (
    DEFAULT_HOST,
    DEFAULT_MODEL,
    REQUEST_TIMEOUT,
    Answer,
    ModelUnavailable,
    ollama_tools,
    _check_model,
)
from astro.interpret.sections import COMMON, SECTIONS, Section
from astro.interpret.tools import ChartTools, dispatch
from astro.service import NatalChart, now_jd

MAX_TOOL_ROUNDS = 4  # facts are pre-loaded, so a section rarely needs more than one

STATUS_OK = "ok"
STATUS_FAILED = "failed"


@dataclass(frozen=True)
class SectionResult:
    key: str
    title: str
    body: str
    status: str
    model: str
    tool_calls: int
    warning: str = ""

    @property
    def ok(self) -> bool:
        return self.status == STATUS_OK


def _tools_for(natal: NatalChart) -> ChartTools:
    start = now_jd()
    return ChartTools(
        facts=natal.facts,
        dashas=natal.dashas,
        stages=life_stages(natal.facts, natal.dashas, start, start + 3650.0),
        profile_name=natal.profile.name,
    )


def generate_section(
    natal: NatalChart,
    section: Section,
    *,
    model: str | None = None,
    host: str | None = None,
    correction: str = "",
) -> SectionResult:
    """Write one section. Facts are supplied up front; tools remain available."""
    model = model or DEFAULT_MODEL
    host = host or DEFAULT_HOST
    tools = _tools_for(natal)
    facts = section.facts(natal)

    messages = [
        {"role": "system", "content": COMMON},
        {
            "role": "user",
            "content": (
                f"{section.instruction}\n\n"
                f"These are the computed facts for {natal.profile.name}'s chart. "
                "Everything you write must rest on them, or on a tool call if you need "
                "something they do not cover.\n\n"
                f"{json.dumps(facts, indent=1, default=str)}"
                + (
                    "\n\nYour previous attempt stated something the chart contradicts:\n"
                    f"{correction}\n"
                    "Write it again, correcting that. Check every planet's sign and "
                    "house against the facts above before writing it down."
                    if correction
                    else ""
                )
            ),
        },
    ]

    calls = 0
    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        for _ in range(MAX_TOOL_ROUNDS):
            try:
                response = client.post(
                    f"{host}/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "tools": ollama_tools(),
                        "stream": False,
                        "options": {"temperature": 0.3},
                    },
                )
                response.raise_for_status()
            except httpx.HTTPError as error:
                raise ModelUnavailable(f"Ollama request failed: {error}") from error

            message = response.json().get("message", {})
            messages.append(message)
            requests = message.get("tool_calls") or []

            if not requests:
                body = (message.get("content") or "").strip()
                return _judge(section, body, model, calls, natal)

            for request in requests:
                function = request.get("function", {})
                name = function.get("name", "")
                arguments = function.get("arguments") or {}
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                try:
                    output = dispatch(tools, name, arguments)
                except Exception as problem:
                    output = f"error: {problem}"
                calls += 1
                messages.append(
                    {
                        "role": "tool",
                        "tool_name": name,
                        "content": json.dumps(output, default=str)[:4000],
                    }
                )

    return SectionResult(
        key=section.key, title=section.title, body="", status=STATUS_FAILED,
        model=model, tool_calls=calls,
        warning="The model kept calling tools without settling on an answer.",
    )


def _judge(
    section: Section, body: str, model: str, calls: int, natal: NatalChart
) -> SectionResult:
    """Accept or reject a written section.

    Facts are pre-loaded, so an absence of tool calls is expected and is not itself a
    failure — unlike question answering, where it means free recall. What is checked is
    that the section says something, finishes, states nothing false about where the
    planets are, and keeps the vocabulary rule.
    """
    answer = Answer(text=body, model=model, tool_calls=[{"n": calls}] if calls else [])

    if len(body) < 120:
        return SectionResult(
            section.key, section.title, body, STATUS_FAILED, model, calls,
            "The model returned almost nothing.",
        )
    if not answer.complete:
        return SectionResult(
            section.key, section.title, body, STATUS_FAILED, model, calls,
            "The model stopped short of an answer.",
        )

    # Instruction is not grounding. A fluent, confident, false placement is the exact
    # failure this whole design exists to prevent, so it is checked rather than trusted.
    false_claims = factcheck(body, natal.facts)
    if false_claims:
        return SectionResult(
            section.key, section.title, body, STATUS_FAILED, model, calls,
            "Contradicts the chart: " + "; ".join(str(claim) for claim in false_claims[:3]),
        )

    # Apply the vocabulary rule rather than hoping it was followed. What is stored is
    # what the reader sees, so it has to obey the rule the interface promises.
    body = explain(body)
    warning = ""
    remaining = bare_terms(body)
    if remaining:  # should not happen; recorded if it does
        warning = f"Unexplained terms: {', '.join(sorted(set(remaining))[:5])}"

    return SectionResult(
        section.key, section.title, body, STATUS_OK, model, calls, warning
    )


# --- storage -----------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    profile_id   INTEGER NOT NULL,
    section      TEXT    NOT NULL,
    title        TEXT    NOT NULL DEFAULT '',
    body         TEXT    NOT NULL DEFAULT '',
    status       TEXT    NOT NULL DEFAULT 'ok',
    warning      TEXT    NOT NULL DEFAULT '',
    model        TEXT    NOT NULL DEFAULT '',
    generated_at TEXT    NOT NULL,
    PRIMARY KEY (profile_id, section)
);
"""


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA)


def save_section(
    connection: sqlite3.Connection, profile_id: int, result: SectionResult
) -> None:
    ensure_schema(connection)
    connection.execute(
        "INSERT OR REPLACE INTO readings (profile_id, section, title, body, status,"
        " warning, model, generated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            profile_id, result.key, result.title, result.body, result.status,
            result.warning, result.model, datetime.now().isoformat(),
        ),
    )
    connection.commit()


def load_reading(connection: sqlite3.Connection, profile_id: int) -> dict[str, dict]:
    ensure_schema(connection)
    rows = connection.execute(
        "SELECT * FROM readings WHERE profile_id = ?", (profile_id,)
    ).fetchall()
    return {
        row["section"]: {
            "section": row["section"],
            "title": row["title"],
            "body": row["body"],
            "status": row["status"],
            "warning": row["warning"],
            "model": row["model"],
            "generated_at": row["generated_at"],
        }
        for row in rows
    }


def progress(connection: sqlite3.Connection, profile_id: int) -> dict:
    stored = load_reading(connection, profile_id)
    done = [key for key, value in stored.items() if value["status"] == STATUS_OK]
    failed = [key for key, value in stored.items() if value["status"] != STATUS_OK]
    return {
        "total": len(SECTIONS),
        "written": len(done),
        "failed": len(failed),
        "pending": [s.key for s in SECTIONS if s.key not in stored],
        "complete": len(stored) == len(SECTIONS),
    }


def generate_reading(
    connection: sqlite3.Connection,
    natal: NatalChart,
    profile_id: int,
    *,
    model: str | None = None,
    host: str | None = None,
    only: tuple[str, ...] | None = None,
    on_section=None,
) -> list[SectionResult]:
    """Write every section and store each as it lands.

    Storing per section rather than at the end means an interrupted run keeps what it
    finished, and the interface can show real progress instead of a spinner.
    """
    model = model or DEFAULT_MODEL
    host = host or DEFAULT_HOST
    _check_model(model, host)
    results = []
    for section in SECTIONS:
        if only and section.key not in only:
            continue
        try:
            result = generate_section(natal, section, model=model, host=host)
            # One corrective retry. A model told precisely what it got wrong usually
            # fixes it, and three sections in nine failed the placement check on the
            # first pass — too many to simply discard.
            if not result.ok and result.warning.startswith("Contradicts the chart"):
                result = generate_section(
                    natal, section, model=model, host=host,
                    correction=result.warning.removeprefix("Contradicts the chart: "),
                )
        except ModelUnavailable:
            raise
        except Exception as error:  # one bad section must not lose the rest
            result = SectionResult(
                section.key, section.title, "", STATUS_FAILED, model, 0, str(error)[:200]
            )
        save_section(connection, profile_id, result)
        results.append(result)
        if on_section:
            on_section(result)
    return results
