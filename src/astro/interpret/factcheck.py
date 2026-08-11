"""Verify placement claims in generated prose against the computed chart.

Grounding by instruction is not grounding. Told to use only the supplied facts, an
eight-billion-parameter model still wrote "Mars in Aries (its own sign)" about a Mars
standing in Scorpio — it had read the *house's* sign and attached it to the house's
ruler. The sentence was fluent, confident and false, and no prompt rule reliably stops
it.

So the claims are checked. This scans a section for statements of the form "Mars in
Aries" or "the Sun in the tenth house" and tests each against the chart. Anything false
fails the section, and the reader sees the deterministic text instead.

It is deliberately narrow. It checks the class of claim that is both easy to state
wrongly and cheap to verify exactly — where a planet is. It does not attempt to judge
interpretation, which is not the kind of thing that has a truth value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from astro.core.ephemeris import SIGNS
from astro.core.facts import ChartFacts
from astro.core.strength import GRAHAS

ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
    "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12,
    "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5, "6th": 6, "7th": 7, "8th": 8,
    "9th": 9, "10th": 10, "11th": 11, "12th": 12,
}

_PLANETS = "|".join(GRAHAS)
_SIGNS = "|".join(SIGNS)
_ORDINALS = "|".join(ORDINALS)

# "Mars in Scorpio", "Mars is in Scorpio", "Mars, placed in Scorpio"
SIGN_CLAIM = re.compile(
    rf"\b({_PLANETS})\b[^.,;]{{0,40}}?\b(?:is\s+|sits\s+|stands\s+|placed\s+|located\s+)?"
    rf"in\s+(?:the\s+sign\s+of\s+)?({_SIGNS})\b",
    re.IGNORECASE,
)

# "Saturn in the tenth house", "Saturn in the 10th"
HOUSE_CLAIM = re.compile(
    rf"\b({_PLANETS})\b[^.,;]{{0,40}}?\b(?:is\s+|sits\s+|stands\s+|placed\s+|located\s+)?"
    rf"in\s+the\s+({_ORDINALS})(?:\s+house)?\b",
    re.IGNORECASE,
)


# "Saturn ... its own sign" for a Saturn standing in Sagittarius, which is Jupiter's.
# The placement was right and the claim about it was wrong, so checking position alone
# let it through.
OWN_SIGN_CLAIM = re.compile(
    rf"\b({_PLANETS})\b[^.;]{{0,80}}?\bits own (?:sign|house)\b", re.IGNORECASE
)
DIGNITY_CLAIM = re.compile(
    rf"\b({_PLANETS})\b[^.;]{{0,60}}?\b(exalted|debilitated)\b", re.IGNORECASE
)
OWN_DIGNITIES = {"own", "moolatrikona"}


@dataclass(frozen=True)
class FalseClaim:
    claim: str
    said: str
    actually: str

    def __str__(self) -> str:
        return f"{self.claim!r} — said {self.said}, actually {self.actually}"


def check(text: str, facts: ChartFacts) -> list[FalseClaim]:
    """Every placement claim in the text that the chart contradicts."""
    wrong: list[FalseClaim] = []

    for match in SIGN_CLAIM.finditer(text):
        planet = match.group(1).capitalize()
        claimed = match.group(2).capitalize()
        if planet not in facts.condition:
            continue
        actual = SIGNS[facts.sign_of(planet)]
        if claimed.lower() != actual.lower():
            wrong.append(
                FalseClaim(match.group(0).strip(), f"{planet} in {claimed}",
                           f"{planet} is in {actual}")
            )

    for match in HOUSE_CLAIM.finditer(text):
        planet = match.group(1).capitalize()
        claimed = ORDINALS[match.group(2).lower()]
        if planet not in facts.condition:
            continue
        actual = facts.house_of(planet)
        if claimed != actual:
            wrong.append(
                FalseClaim(match.group(0).strip(), f"{planet} in house {claimed}",
                           f"{planet} is in house {actual}")
            )

    for match in OWN_SIGN_CLAIM.finditer(text):
        planet = match.group(1).capitalize()
        if planet not in facts.condition:
            continue
        dignity = facts.dignity(planet)
        if dignity not in OWN_DIGNITIES:
            wrong.append(
                FalseClaim(
                    match.group(0).strip(),
                    f"{planet} in its own sign",
                    f"{planet} is in {SIGNS[facts.sign_of(planet)]}, which it does not "
                    f"rule; it is {dignity.replace('_', ' ')} there",
                )
            )

    for match in DIGNITY_CLAIM.finditer(text):
        planet = match.group(1).capitalize()
        claimed = match.group(2).lower()
        if planet not in facts.condition:
            continue
        actual = facts.dignity(planet)
        if actual != claimed:
            wrong.append(
                FalseClaim(match.group(0).strip(), f"{planet} {claimed}",
                           f"{planet} is {actual.replace('_', ' ')}")
            )

    # The same false claim repeated should be reported once.
    seen: set[str] = set()
    unique = []
    for item in wrong:
        if item.said in seen:
            continue
        seen.add(item.said)
        unique.append(item)
    return unique
