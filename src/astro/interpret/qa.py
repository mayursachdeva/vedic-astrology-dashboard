"""Chart question answering, through a local model.

Ollama, not a hosted API. That keeps the whole project's promise intact: with this
running against a local model, no birth data leaves the machine at any point, including
when someone asks a question about it.

The model is given no chart data up front. It must call the read-only tools in
`interpret.tools` for every fact it uses, so it cannot state a position that was never
computed. That constraint matters more with a small local model than it would with a
large hosted one — it is what stops a 3B model from confidently inventing placements.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field

import httpx

from astro.interpret.tools import ChartTools, dispatch, tool_definitions

DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("ASTRO_QA_MODEL", "qwen3:8b")
MAX_TOOL_ROUNDS = 10
REQUEST_TIMEOUT = 180.0

# qwen3 reasons aloud before every reply, and the loop asks it for three to five replies
# per question. Measured on an M5: the same question with the same tools took 26.4s with
# thinking and 1.5s without, producing an identical tool call — 1,511 characters of
# reasoning to reach a 196-character answer. `_Visible` was already throwing all of that
# away before it reached the screen, so it was pure cost.
#
# Set ASTRO_QA_THINK=1 to put it back. Nothing here needs a model that deliberates: the
# facts come from tools and the answer is a plain-English rendering of them.
THINK = os.environ.get("ASTRO_QA_THINK", "").strip() not in ("", "0", "false", "no")

SYSTEM_PROMPT = """\
You are helping someone understand their own Vedic astrology chart. They are not an \
astrologer and should not need to become one.

Rules you must follow:

1. Never state a planetary position, house, dignity, dasha or transit from your own \
knowledge. Every fact must come from a tool call. If a tool has not told you \
something, you do not know it. Call the tools before answering.
2. Answer in plain English first. Say what it means for the person's life before you \
name a single planet or house.
3. Then list the specific placements your answer rests on, so they can check it.
4. When you refer to a classical text, use search_scripture and give the chapter and \
verse it returned. Never invent a reference.
5. Where the chart is ambiguous, say so plainly instead of sounding certain.
6. Astrology is not medicine, law or financial advice. Do not predict death, diagnose \
illness, or tell someone to make a medical or legal decision.
7. If the question cannot be answered from this chart, say so.

How the tools fit together:

- To find which planet rules a house, call get_house(house). Its "lord" field is that
  planet's name. Then call get_planet with that name to see how it is placed.
- get_planet takes a planet name only — Sun, Moon, Mars, Mercury, Jupiter, Venus,
  Saturn, Rahu, Ketu. It does not take a house.
- Never ask the person for chart facts. They do not know them; that is what the tools
  are for. Keep calling tools until you have what you need.
"""


class ModelUnavailable(RuntimeError):
    """Raised when the local model cannot be reached or is not installed."""


# Signs that a model stopped short: it printed the tool call it meant to make, told the
# reader to call one, or asked them for chart facts they do not have. All three read
# like answers and contain nothing.
#
# Note what is deliberately NOT here: a bare mention of a tool name. The prompt asks the
# model to show which lookup each fact came from, so "(from get_planet("Jupiter"))" is
# the desired behaviour, and an earlier version of this gate rejected good answers for
# doing exactly what it was told.
_UNFINISHED = (
    re.compile(r'\{\s*"name"\s*:'),
    re.compile(r"\bcall\s+(the\s+tools?|`?(get_\w+|search_scripture))", re.I),
    re.compile(r"\b(let me try again|can you (please )?tell me|please tell me which"
               r"|i need to know which)", re.I),
)


@dataclass
class Answer:
    text: str
    model: str
    tool_calls: list[dict] = field(default_factory=list)
    rounds: int = 0
    # Whether earlier turns of this conversation already looked things up. A follow-up
    # that adds no lookups of its own is resting on those, which is different from a
    # first answer produced out of thin air.
    follow_up: bool = False

    @property
    def grounded(self) -> bool:
        """Whether the answer rests on any computed fact.

        An answer produced without a single tool call is free recall, which is exactly
        what this module exists to prevent. The caller should treat False as a warning
        to show the reader, not as a failure to hide.
        """
        return bool(self.tool_calls)

    @property
    def complete(self) -> bool:
        """Whether the model actually finished.

        A weak model will sometimes print the tool call it meant to make, or turn round
        and ask the reader what their 10th lord is. Both read like answers and are
        worthless, so they are detected and reported rather than displayed as findings.
        """
        return not any(pattern.search(self.text) for pattern in _UNFINISHED)

    @property
    def warning(self) -> str:
        if not self.grounded:
            if self.follow_up:
                return (
                    "This reply looked nothing further up — it rests on what was "
                    "fetched earlier in this conversation."
                )
            return (
                "This answer was produced without looking anything up in the chart, so "
                "it should not be trusted."
            )
        if not self.complete:
            return (
                "The model did not finish working through the chart. Try asking about "
                "one thing at a time, or use a larger model via ASTRO_QA_MODEL."
            )
        return ""


def ollama_tools() -> list[dict]:
    """The same tool surface, in the schema Ollama expects.

    Converted rather than duplicated, so the definitions cannot drift apart.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": definition["name"],
                "description": definition["description"],
                "parameters": definition.get("input_schema", {"type": "object", "properties": {}}),
            },
        }
        for definition in tool_definitions()
    ]


def available_models(host: str | None = None) -> list[str]:
    host = host or DEFAULT_HOST
    try:
        response = httpx.get(f"{host}/api/tags", timeout=10.0)
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise ModelUnavailable(
            f"Could not reach Ollama at {host}. Start it with `ollama serve`, or set "
            "OLLAMA_HOST. Everything else in the dashboard works without it."
        ) from error
    return [model["name"] for model in response.json().get("models", [])]


def _check_model(model: str, host: str | None = None) -> None:
    host = host or DEFAULT_HOST
    installed = available_models(host)
    # Ollama reports names as "llama3.2:3b"; accept a bare name if only one tag matches.
    if model in installed:
        return
    matching = [name for name in installed if name.split(":")[0] == model]
    if matching:
        return
    raise ModelUnavailable(
        f"Model {model!r} is not installed in Ollama. Available: "
        f"{', '.join(installed) or 'none'}. Pull one with `ollama pull {model}`, or set "
        "ASTRO_QA_MODEL to one you have."
    )


class _Visible:
    """Strips the model's reasoning out of a stream of content fragments.

    qwen3 thinks aloud. Recent Ollama builds put that in a separate `thinking` field,
    but older ones leave `<think>…</think>` in the content, and the tags can be split
    across chunks. Nobody wants to watch a model talk itself into an answer, so this
    keeps a small tail buffer and releases only what is outside the tags.
    """

    def __init__(self) -> None:
        self.buffer = ""
        self.inside = False

    def feed(self, fragment: str) -> str:
        self.buffer += fragment
        out = ""
        while True:
            if self.inside:
                end = self.buffer.find("</think>")
                if end < 0:
                    self.buffer = self.buffer[-8:]
                    return out
                self.buffer = self.buffer[end + len("</think>") :]
                self.inside = False
                continue
            start = self.buffer.find("<think>")
            if start >= 0:
                out += self.buffer[:start]
                self.buffer = self.buffer[start + len("<think>") :]
                self.inside = True
                continue
            # Hold back anything that could be the start of a split "<think>".
            keep = 0
            for size in range(1, min(len(self.buffer), 7) + 1):
                if "<think>".startswith(self.buffer[-size:]):
                    keep = size
            out += self.buffer[: len(self.buffer) - keep]
            self.buffer = self.buffer[len(self.buffer) - keep :]
            return out


def ask_stream(
    tools: ChartTools,
    question: str,
    *,
    model: str | None = None,
    host: str | None = None,
    history: Sequence[tuple[str, str]] = (),
) -> Iterator[dict]:
    """Run the tool loop, reporting as it goes.

    Yields `{"type": "lookup", ...}` as each fact is fetched and `{"type": "token", ...}`
    as the answer is written, ending with one `{"type": "answer", "answer": Answer}`.

    Most of the wait is the lookups, not the writing, so a stream that only carried
    tokens would still be silent for most of it. Showing the lookups is what turns the
    wait into something a reader can follow.

    `history` is the exchange so far as (question, answer) pairs. Without it every
    question started a new conversation, so when an answer ended by offering to look at
    something else there was no way to say yes — the follow-up arrived with no idea what
    "yes" referred to. Only the questions and the finished answers are carried, not the
    tool traffic: it would dwarf the context, and the model is meant to look a fact up
    again rather than trust its own earlier summary of it.
    """
    model = model or DEFAULT_MODEL
    host = host or DEFAULT_HOST
    _check_model(model, host)

    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for asked, answered in history:
        messages.append({"role": "user", "content": asked})
        messages.append({"role": "assistant", "content": answered})
    messages.append({
        "role": "user",
        "content": (
            question if history
            else f"The chart belongs to {tools.profile_name}.\n\nQuestion: {question}"
        ),
    })
    calls: list[dict] = []
    nudged = False

    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        for round_number in range(1, MAX_TOOL_ROUNDS + 1):
            content = ""
            requests: list[dict] = []
            visible = _Visible()
            try:
                with client.stream(
                    "POST",
                    f"{host}/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "tools": ollama_tools(),
                        "think": THINK,
                        "stream": True,
                        # Low temperature: this is a reading of computed facts, not a
                        # creative writing task.
                        "options": {"temperature": 0.2},
                    },
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line.strip():
                            continue
                        message = json.loads(line).get("message", {})
                        requests.extend(message.get("tool_calls") or [])
                        fragment = message.get("content") or ""
                        if not fragment:
                            continue
                        content += fragment
                        shown = visible.feed(fragment)
                        if shown:
                            yield {"type": "token", "text": shown}
            except httpx.HTTPError as error:
                raise ModelUnavailable(f"Ollama request failed: {error}") from error

            assistant: dict = {"role": "assistant", "content": content}
            if requests:
                assistant["tool_calls"] = requests
            messages.append(assistant)

            if not requests and not calls and not nudged and not history:
                # Observed on qwen3:8b: it sometimes answers "the chart isn't available
                # in the tools provided" and asks for a birth date, having called
                # nothing. The tools were there; it did not try. One push is enough,
                # and it costs a round only in the case that was worthless anyway.
                nudged = True
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "You have the chart. Do not ask me for birth details — call "
                            "get_house, get_planet or get_life_stage and answer from "
                            "what they return."
                        ),
                    }
                )
                # Whatever it just wrote is being thrown away, so the reader should
                # stop seeing it.
                yield {"type": "restart"}
                continue

            if not requests:
                yield {
                    "type": "answer",
                    "answer": Answer(
                        text=_strip_thinking(content),
                        model=model,
                        tool_calls=calls,
                        rounds=round_number,
                        follow_up=bool(history),
                    ),
                }
                return

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
                    failed = False
                except Exception as problem:
                    # Handed back to the model rather than raised: a small model gets
                    # tool arguments wrong often, and it can usually correct itself.
                    output, failed = f"error: {problem}", True

                call = {"tool": name, "input": arguments, "error": failed}
                calls.append(call)
                yield {"type": "lookup", **call}
                messages.append(
                    {
                        "role": "tool",
                        "tool_name": name,
                        "content": json.dumps(output, default=str)[:4000],
                    }
                )

    yield {
        "type": "answer",
        "answer": Answer(
            text=(
                "I could not settle this within the number of lookups allowed. Try "
                "asking about one thing at a time."
            ),
            model=model,
            tool_calls=calls,
            rounds=MAX_TOOL_ROUNDS,
            follow_up=bool(history),
        ),
    }


_THINK_BLOCK = re.compile(r"<think>.*?(?:</think>|\Z)", re.S)


def _strip_thinking(text: str) -> str:
    return _THINK_BLOCK.sub("", text).strip()


def ask(
    tools: ChartTools,
    question: str,
    *,
    model: str | None = None,
    host: str | None = None,
    history: Sequence[tuple[str, str]] = (),
) -> Answer:
    """Answer one question about one native's chart, running the tool loop to the end."""
    answer = None
    for event in ask_stream(tools, question, model=model, host=host, history=history):
        if event["type"] == "answer":
            answer = event["answer"]
    assert answer is not None, "the stream always ends with an answer"
    return answer
