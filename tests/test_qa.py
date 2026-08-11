"""Tests for the streaming question-answer loop.

No model runs here. Ollama is replaced by a script of chunks, which is the only way to
assert what the loop does with a partial response — that the reasoning never reaches the
reader, that a lookup is reported the moment it happens rather than at the end, and that
`ask()` still returns exactly what it returned before the loop learned to stream.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from astro.core.ephemeris import julian_day
from astro.interpret import qa
from astro.interpret.life_stages import life_stages
from astro.interpret.tools import ChartTools
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


@pytest.fixture()
def tools() -> ChartTools:
    stages = life_stages(NATAL.facts, NATAL.dashas, FROM, FROM + 3650.0)
    return ChartTools(
        facts=NATAL.facts, dashas=NATAL.dashas, stages=stages, profile_name=PROFILE.name
    )


# --- the thinking filter ----------------------------------------------------


def visible(*fragments: str) -> str:
    """What a reader would see, given the model's content arriving in these pieces."""
    filter_ = qa._Visible()
    return "".join(filter_.feed(fragment) for fragment in fragments)


def test_reasoning_is_not_shown_to_the_reader():
    assert visible("<think>hmm, Saturn</think>Your career is steady.") == (
        "Your career is steady."
    )


def test_reasoning_is_hidden_even_when_its_tags_arrive_split_across_chunks():
    """Tokens do not respect tag boundaries: "<th" and "ink>" arrive separately."""
    assert visible("<th", "ink>", "hmm", "</thi", "nk>", "Steady.") == "Steady."
    assert visible("Steady", ". <", "think>later thought</think>") == "Steady. "


def test_text_containing_no_reasoning_passes_through_whole():
    assert visible("Your ", "career ", "is steady.") == "Your career is steady."


# --- the loop ---------------------------------------------------------------


class _Response:
    def __init__(self, chunks: list[dict]) -> None:
        self.chunks = chunks

    def raise_for_status(self) -> None:
        pass

    def iter_lines(self):
        for chunk in self.chunks:
            yield json.dumps(chunk)
            yield ""  # Ollama's newline-delimited stream, blank lines and all.

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class _Ollama:
    """A scripted Ollama. Each round of the loop consumes one entry."""

    def __init__(self, rounds: list[list[dict]]) -> None:
        self.rounds = list(rounds)
        self.sent: list[dict] = []

    def __call__(self, *_, **__):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def stream(self, _method, _url, *, json: dict):
        self.sent.append(json)
        return _Response(self.rounds.pop(0))


def chunk(content: str = "", tool_calls: list[dict] | None = None) -> dict:
    message: dict = {"content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {"message": message}


CALL_TENTH = [{"function": {"name": "get_house", "arguments": {"house": 10}}}]


@pytest.fixture()
def scripted(monkeypatch):
    def install(rounds: list[list[dict]]) -> _Ollama:
        fake = _Ollama(rounds)
        monkeypatch.setattr(qa.httpx, "Client", fake)
        monkeypatch.setattr(qa, "_check_model", lambda *a, **k: None)
        return fake

    return install


def test_a_lookup_is_reported_before_the_answer_is_written(tools, scripted):
    """The point of streaming: the lookups are most of the wait, so they are shown."""
    scripted([
        [chunk("<think>need the tenth</think>"), chunk(tool_calls=CALL_TENTH)],
        [chunk("Steady "), chunk("work.")],
    ])
    events = list(qa.ask_stream(tools, "career?"))
    kinds = [event["type"] for event in events]

    assert kinds.index("lookup") < kinds.index("token")
    assert events[kinds.index("lookup")]["tool"] == "get_house"
    assert "".join(e["text"] for e in events if e["type"] == "token") == "Steady work."


def test_the_model_thinking_never_arrives_as_a_token(tools, scripted):
    scripted([
        [chunk(tool_calls=CALL_TENTH)],
        [chunk("<think>Saturn rules it</think>"), chunk("Steady work.")],
    ])
    tokens = "".join(
        event["text"] for event in qa.ask_stream(tools, "career?")
        if event["type"] == "token"
    )
    assert "Saturn rules it" not in tokens
    assert tokens == "Steady work."


def test_ask_returns_the_same_answer_the_stream_ends_with(tools, scripted):
    scripted([
        [chunk(tool_calls=CALL_TENTH)],
        [chunk("<think>hm</think>Steady work.")],
    ])
    answer = qa.ask(tools, "career?")
    assert answer.text == "Steady work."
    assert answer.rounds == 2
    assert [call["tool"] for call in answer.tool_calls] == ["get_house"]
    assert answer.grounded and answer.complete


def test_a_failing_lookup_is_handed_back_to_the_model_rather_than_raised(tools, scripted):
    """A small model gets arguments wrong constantly; it can usually correct itself."""
    fake = scripted([
        [chunk(tool_calls=[{"function": {"name": "get_house", "arguments": {"house": 99}}}])],
        [chunk(tool_calls=CALL_TENTH)],
        [chunk("Steady work.")],
    ])
    answer = qa.ask(tools, "career?")

    assert [call["error"] for call in answer.tool_calls] == [True, False]
    assert answer.text == "Steady work."
    # The error text reached the model, which is what lets it retry.
    tool_replies = [
        message for message in fake.sent[-1]["messages"] if message["role"] == "tool"
    ]
    assert "error:" in tool_replies[0]["content"]


def test_a_model_that_answers_without_looking_anything_up_is_pushed_once(tools, scripted):
    """qwen3:8b does this: "the chart isn't available", having called nothing."""
    fake = scripted([
        [chunk("I don't have your birth details.")],
        [chunk(tool_calls=CALL_TENTH)],
        [chunk("Steady work.")],
    ])
    events = list(qa.ask_stream(tools, "career?"))

    assert [event["type"] for event in events].count("restart") == 1
    assert events[-1]["answer"].text == "Steady work."
    assert events[-1]["answer"].grounded


def test_a_model_that_declines_twice_is_left_alone(tools, scripted):
    """The push is one round, not a loop that argues with it."""
    scripted([[chunk("I don't have your birth details.")] for _ in range(2)])
    answer = qa.ask(tools, "career?")
    assert answer.rounds == 2
    assert not answer.grounded
    assert "should not be trusted" in answer.warning


def test_a_model_that_never_stops_calling_tools_gives_up_and_says_so(tools, scripted):
    scripted([[chunk(tool_calls=CALL_TENTH)] for _ in range(qa.MAX_TOOL_ROUNDS)])
    answer = qa.ask(tools, "career?")
    assert answer.rounds == qa.MAX_TOOL_ROUNDS
    assert "one thing at a time" in answer.text


# --- following up -----------------------------------------------------------


def test_a_follow_up_carries_the_exchange_with_it(tools, scripted):
    """Every question used to start a new conversation, so an answer ending "shall I
    look at your seventh house?" could not be answered — "yes" arrived with nothing to
    attach to."""
    fake = scripted([[chunk(tool_calls=CALL_TENTH)], [chunk("Its ruler is strong.")]])
    answer = qa.ask(
        tools, "yes please",
        history=[("How is my marriage?", "The seventh is quiet. Shall I look at the ruler?")],
    )
    sent = fake.sent[-1]["messages"]
    roles = [message["role"] for message in sent]
    assert roles[:4] == ["system", "user", "assistant", "user"]
    assert sent[1]["content"] == "How is my marriage?"
    assert "Shall I look at the ruler?" in sent[2]["content"]
    assert sent[3]["content"] == "yes please"
    assert answer.text == "Its ruler is strong."


def test_the_first_question_still_names_whose_chart_it_is(tools, scripted):
    """And a follow-up does not repeat it, which would read as a new conversation."""
    # A lookup on the first turn, so the no-lookup nudge does not eat a scripted round.
    fake = scripted([
        [chunk(tool_calls=CALL_TENTH)], [chunk("Steady.")],
        [chunk("Money too.")],
    ])
    qa.ask(tools, "career?")
    assert tools.profile_name in fake.sent[0]["messages"][1]["content"]

    qa.ask(tools, "and money?", history=[("career?", "Steady.")])
    # The last thing *sent* is the loop's own running transcript, so look at the last
    # message the reader supplied rather than the last message of any kind.
    asked = [m for m in fake.sent[-1]["messages"] if m["role"] == "user"][-1]
    assert asked["content"] == "and money?"
    assert tools.profile_name not in asked["content"]


def test_a_follow_up_that_looks_nothing_up_is_not_called_untrustworthy(tools, scripted):
    """A first answer with no lookups is free recall. A follow-up resting on what was
    already fetched is a different thing, and the alarming wording was wrong for it."""
    scripted([[chunk("Yes — that is what I meant.")]])
    reply = qa.ask(tools, "so it is good?", history=[("career?", "Steady work.")])
    assert not reply.grounded
    assert reply.follow_up
    assert "should not be trusted" not in reply.warning
    assert "rests on what was fetched earlier" in reply.warning


def test_the_nudge_does_not_fire_on_a_follow_up(tools, scripted):
    """The push to use the tools exists for a first question answered out of thin air.
    On a follow-up, "yes, shall I go on?" is a perfectly good reply with no lookups."""
    fake = scripted([[chunk("Yes.")]])
    reply = qa.ask(tools, "really?", history=[("career?", "Steady.")])
    assert reply.text == "Yes."
    assert len(fake.rounds) == 0, "it asked again instead of accepting the reply"


def test_the_model_is_asked_not_to_deliberate(tools, scripted):
    """qwen3 reasons aloud before every reply, and the loop asks for three to five
    replies per question. Measured on an M5: 26.4s with thinking against 1.5s without,
    for an identical tool call. `_Visible` was already discarding all of it."""
    fake = scripted([[chunk("Steady.")], [chunk("Steady.")]])
    qa.ask(tools, "career?")
    assert fake.sent[0]["think"] is False


def test_deliberation_can_be_put_back_by_the_environment(tools, scripted, monkeypatch):
    monkeypatch.setattr(qa, "THINK", True)
    fake = scripted([[chunk(tool_calls=CALL_TENTH)], [chunk("Steady.")]])
    qa.ask(tools, "career?")
    assert fake.sent[0]["think"] is True
