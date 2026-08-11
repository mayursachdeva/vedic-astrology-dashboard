"""Plain English for every term the interface can emit.

The dashboard's stated principle is that a reader should not need to become an
astrologer. It was not being kept: the default view carried about fourteen Sanskrit
terms, glossed only on hover — invisible when scanning and absent on a touch screen.

The rule here is one line: **plain phrase first, term in brackets, definition on
demand.** "A nineteen-year chapter ruled by Saturn (mahadasha)" teaches the word while
remaining readable to someone who has never seen it. Hiding the vocabulary entirely
would make the reading unverifiable against the texts; leading with it makes the reading
unusable. This is the middle.

Every entry is used in two places — the rendered interface, and the instructions given
to the model writing a reading, so generated prose obeys the same rule as authored text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Entry:
    term: str
    plain: str  # the phrase that replaces it in ordinary prose
    definition: str  # one sentence, shown on demand


def _entries() -> dict[str, Entry]:
    raw: list[tuple[str, str, str]] = [
        # --- time ---
        ("mahadasha", "major life chapter",
         "A long stretch of life, six to twenty years, coloured by one planet."),
        ("antardasha", "sub-period",
         "A shorter span inside a major chapter, ruled by a second planet, which shades "
         "it without replacing it."),
        ("pratyantardasha", "shorter sub-period",
         "A subdivision inside a sub-period — the finest level of timing shown here."),
        ("dasha", "planetary period",
         "A span of life assigned to one planet. The whole sequence is fixed at birth "
         "by the Moon's position."),
        ("vimshottari", "the 120-year cycle",
         "The standard scheme of planetary periods, running 120 years in total."),
        ("gochara", "current planetary positions",
         "Where the planets are now, as against where they were at birth."),
        ("sade sati", "Saturn's seven-year passage",
         "The roughly seven and a half years during which Saturn crosses the sign "
         "before, the sign of, and the sign after the Moon."),
        ("tithi", "lunar day",
         "One of thirty divisions of the month, measured by how far the Moon has pulled "
         "ahead of the Sun."),
        ("paksha", "fortnight",
         "The waxing or waning half of the lunar month."),
        ("karana", "half a lunar day",
         "Half of a tithi; there are sixty in a lunar month."),
        ("panchanga", "the five marks of the day",
         "The lunar day, weekday, lunar mansion and two subdivisions that together "
         "describe a day."),
        # --- places in the chart ---
        ("lagna", "rising sign",
         "The sign climbing over the horizon at birth. Every house is counted from it."),
        ("ascendant", "rising sign",
         "The sign climbing over the horizon at birth."),
        ("bhava", "house",
         "One of twelve divisions of the chart, each covering a part of life."),
        ("rasi", "sign",
         "One of the twelve signs of the zodiac."),
        ("kendra", "corner house",
         "The 1st, 4th, 7th and 10th — the four pillars of a chart."),
        ("trikona", "house of fortune",
         "The 1st, 5th and 9th, traditionally the most favourable."),
        ("dusthana", "house of difficulty",
         "The 6th, 8th and 12th, which carry illness, upheaval and loss."),
        ("upachaya", "house of growth",
         "The 3rd, 6th, 10th and 11th, which improve with effort and time."),
        ("nakshatra", "lunar mansion",
         "One of twenty-seven segments of sky the Moon passes through; the Moon's one "
         "at birth sets the whole timing sequence."),
        ("pada", "quarter of a lunar mansion",
         "A quarter of a nakshatra, about three and a third degrees."),
        # --- divisional charts ---
        ("varga", "divisional chart",
         "A second chart made by slicing each sign into equal parts, read for one part "
         "of life."),
        ("navamsa", "the ninth-part chart",
         "A chart made by dividing each sign into nine, read for marriage and for a "
         "planet's underlying strength."),
        ("dasamsa", "the tenth-part chart",
         "A chart made by dividing each sign into ten, read for career and standing."),
        ("vargottama", "same sign in both charts",
         "A planet holding the same sign in the birth chart and the ninth-part chart, "
         "which is read as steadiness."),
        # --- condition ---
        ("graha", "planet",
         "One of the nine bodies used: the Sun and Moon, five planets, and the two "
         "lunar nodes."),
        ("exalted", "at its strongest",
         "A planet in the sign where it is traditionally held to act best."),
        ("debilitated", "at its weakest",
         "A planet in the sign opposite its exaltation, where it struggles to deliver."),
        ("moolatrikona", "in its favourite degrees",
         "A narrow band within a planet's own sign where it is especially strong."),
        ("combust", "hidden by the Sun",
         "A planet close enough to the Sun to be lost in its glare, which is read as "
         "weakened."),
        ("retrograde", "apparently moving backwards",
         "A planet that appears to move backwards against the stars, read as turning "
         "its effects inward or repeating them."),
        ("digbala", "in the quarter of the sky it is strongest in",
         "A planet in the direction the texts give it — Jupiter and Mercury rising, "
         "the Sun and Mars overhead — which is read as added strength."),
        ("yogakaraka", "the chart's most helpful planet",
         "A planet ruling both a pillar house and a house of fortune, so its periods "
         "tend to move life forward."),
        ("dispositor", "the ruler of the sign it sits in",
         "The planet that owns the sign another planet occupies."),
        ("drishti", "aspect",
         "The influence a planet throws onto other houses from where it stands."),
        # --- findings ---
        ("yoga", "combination",
         "A named configuration of planets that the classical texts attach a meaning "
         "to."),
        ("dosha", "affliction",
         "A configuration the texts read as a difficulty."),
        ("ashtakavarga", "the points system",
         "A scheme scoring every sign out of the whole chart; the twelve always total "
         "337."),
        ("sarvashtakavarga", "the combined points",
         "The total of all the planets' points for a sign."),
        ("bindu", "point",
         "A single favourable mark in the points system."),
        ("upaya", "remedy",
         "A traditional observance prescribed against an affliction."),
    ]
    return {term: Entry(term, plain, definition) for term, plain, definition in raw}


GLOSSARY = _entries()

# House numbers read as jargon to anyone who does not already know the system —
# "the 10th house" says nothing on its own. These are the plain meanings, drawn from
# the same verses as the life-area map (BPHS ch. 11 v. 2-13).
HOUSE_MEANINGS = {
    1: "body and self", 2: "money and family", 3: "siblings and courage",
    4: "home and mother", 5: "children and learning", 6: "illness and rivals",
    7: "partnership", 8: "upheaval and longevity", 9: "fortune and belief",
    10: "work and standing", 11: "income and gains", 12: "loss and letting go",
}

_HOUSE_PATTERN = re.compile(
    r"\bthe\s+(1st|2nd|3rd|4th|5th|6th|7th|8th|9th|10th|11th|12th|first|second|third|"
    r"fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth)(?:\s+house)?\b",
    re.IGNORECASE,
)
_ORDINAL_TO_NUMBER = {
    "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5, "6th": 6, "7th": 7, "8th": 8,
    "9th": 9, "10th": 10, "11th": 11, "12th": 12, "first": 1, "second": 2, "third": 3,
    "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9,
    "tenth": 10, "eleventh": 11, "twelfth": 12,
}


def explain_houses(text: str) -> str:
    """Give each house its meaning the first time it is named.

    "The 10th house" tells a reader nothing. "The house of work and standing (the 10th)"
    tells them what is being discussed while keeping the number for anyone checking.
    """
    named: set[int] = set()

    def replace(match: re.Match) -> str:
        number = _ORDINAL_TO_NUMBER[match.group(1).lower()]
        if number in named:
            return match.group(0)
        named.add(number)
        return f"the house of {HOUSE_MEANINGS[number]} (the {match.group(1)})"

    return _HOUSE_PATTERN.sub(replace, text)

# Longest first, so "sarvashtakavarga" is matched before "ashtakavarga".
_PATTERN = re.compile(
    r"\b(" + "|".join(sorted((re.escape(t) for t in GLOSSARY), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def plain(term: str) -> str:
    """The ordinary-English phrase for a term, or the term if it has none."""
    entry = GLOSSARY.get(term.lower())
    return entry.plain if entry else term


def define(term: str) -> str:
    entry = GLOSSARY.get(term.lower())
    return entry.definition if entry else ""


def render(term: str) -> str:
    """Plain phrase first, term in brackets — the house style, in one place."""
    entry = GLOSSARY.get(term.lower())
    return f"{entry.plain} ({entry.term})" if entry else term


def bare_terms(text: str) -> list[str]:
    """Terms appearing without their plain phrase alongside.

    Used by the test that keeps unexplained vocabulary out of the reading views. A term
    counts as explained when its plain phrase appears within the preceding stretch of
    text, which is what "plain first, term in brackets" produces.
    """
    offenders = []
    lowered = text.lower()
    explained: set[str] = set()
    for match in _PATTERN.finditer(text):
        term = match.group(1).lower()
        entry = GLOSSARY[term]
        # Once a term has been introduced, later bare uses are correct style — the
        # rule is "explain on first use", not "gloss every time".
        if term in explained:
            continue
        window = lowered[max(0, match.start() - 90) : match.start()]
        if entry.plain.lower() in window:
            explained.add(term)
            continue
        # "Gaja Kesari Yoga" is a name, not a bare technical term. Part of a proper
        # name means both this word and the one before it are capitalised — and the
        # word before is not simply an article opening a sentence, or "The mahadasha"
        # would slip through as though it were a name.
        preceding = text[: match.start()].rstrip().split(" ")[-1] if match.start() else ""
        opener = preceding.strip(".,;:!?").lower() in {
            "the", "a", "an", "this", "that", "his", "her", "their", "your", "its",
        }
        if (
            match.group(1)[:1].isupper()
            and preceding[:1].isupper()
            and preceding.isalpha()
            and not opener
        ):
            continue
        offenders.append(match.group(1))
        explained.add(term)
    return offenders


def explain(text: str) -> str:
    """Rewrite the first bare use of each term into plain-phrase-then-term form.

    The model is told the rule and given every word it applies to, and still leaves
    "combust" and "retrograde" bare in most sections. Instructing is not enforcing —
    the same lesson the placement checker taught. This applies the rule to the text
    afterwards, so what is stored always reads the way the interface promises.

    Only the first bare occurrence is expanded: repeating the gloss every time would be
    worse than leaving it out.
    """
    expanded: set[str] = set()

    def replace(match: re.Match) -> str:
        word = match.group(1)
        term = word.lower()
        entry = GLOSSARY[term]
        if term in expanded:
            return word
        start = match.start()
        window = text[max(0, start - 90) : start].lower()
        if entry.plain.lower() in window:
            return word
        preceding = text[:start].rstrip().split(" ")[-1] if start else ""
        opener = preceding.strip(".,;:!?").lower() in {
            "the", "a", "an", "this", "that", "his", "her", "their", "your", "its",
        }
        if word[:1].isupper() and preceding[:1].isupper() and preceding.isalpha() and not opener:
            return word  # part of a proper name
        expanded.add(term)
        return f"{entry.plain} ({word})"

    return explain_houses(_PATTERN.sub(replace, text))


def plainly(text: str) -> str:
    """Plain phrase only, no bracketed term — for short interface fragments.

    Prose gets "hidden by the Sun (combust)", which teaches the word. A one-line driver
    like "Saturn rules the 11th but is combust" is not prose: bracketing every term in
    a list of six fragments produces noise, and the number carries no meaning for a
    reader who does not already know the system. Here the plain phrase simply replaces
    the term, and the technical view keeps the numbers for anyone checking.
    """
    def house(match: re.Match) -> str:
        number = _ORDINAL_TO_NUMBER[match.group(1).lower()]
        return f"the house of {HOUSE_MEANINGS[number]}"

    def term(match: re.Match) -> str:
        word = match.group(1)
        preceding = text[: match.start()].rstrip().split(" ")[-1] if match.start() else ""
        opener = preceding.strip(".,;:!?").lower() in {
            "the", "a", "an", "this", "that", "his", "her", "their", "your", "its",
        }
        if word[:1].isupper() and preceding[:1].isupper() and preceding.isalpha() and not opener:
            return word  # part of a proper name
        return GLOSSARY[word.lower()].plain

    return _PATTERN.sub(term, _HOUSE_PATTERN.sub(house, text))


def vocabulary_instructions() -> str:
    """The vocabulary rule, phrased for the model that writes a reading.

    Generated prose has to obey exactly the same rule as authored text, or half the
    interface teaches the words and the other half assumes them.
    """
    examples = "\n".join(
        f"  - instead of \"{entry.term}\", write \"{entry.plain} ({entry.term})\""
        for entry in list(GLOSSARY.values())[:6]
    )
    # The full list, not a sample. Naming six and hoping the rest follow left
    # "combust", "retrograde" and "antardasha" bare in most generated sections.
    every = ", ".join(sorted(entry.term for entry in GLOSSARY.values()))
    return (
        "Write for someone who knows no astrology. Never use a technical term on its "
        "own. Give the ordinary-English phrase first and put the term in brackets "
        "after it, once, the first time it appears. For example:\n"
        f"{examples}\n"
        "After the first mention, keep using the ordinary phrase.\n"
        f"This rule applies to every one of these words: {every}."
    )
