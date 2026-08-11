"""Pointers into the ingested texts, worked out rather than written down.

The house reading needs to say what a house means, what its sign is like, what happens
when its lord sits where it does, and what the texts prescribe for each planet. All of
that is in the library already; the problem is finding the right passage for a given
cell without paraphrasing it into a table that would then drift from the source.

So this module derives the pointers. Three of the four are arithmetic, because the
chapters are regular:

    BPHS ch. 11    one verse per bhava, v. 2 to v. 13
    BPHS ch. 12-23 one chapter per bhava, in order
    BPHS ch. 24    a 12x12 grid: the lord of bhava L in bhava H is verse (L-1)*12 + H

The fourth, the sign descriptions in ch. 4, is not regular — its verses are grouped
unevenly and one sign shares a passage with the next — so those are found by looking
for the Sanskrit name rather than by counting.

Nothing here paraphrases. Every function returns the passage itself, so what the reader
sees is the text, with its chapter and verse attached.
"""

from __future__ import annotations

import re
from functools import lru_cache

from astro.corpus.search import Hit, load_passages, lookup, search

BPHS = "Brihat Parashara Hora Shastra"
REMEDIES = "Encyclopedia of Astrological Remedies (Arun Kumar Bansal)"
NAKSHATRA_WORK = "28 Nakshatras: The Real Secrets of Vedic Astrology"

# The names the translation uses for the twelve bhavas, in order.
BHAVA_NAMES = (
    "Tanu", "Dhan", "Sahaj", "Bandhu", "Putr", "Ari",
    "Yuvati", "Randhr", "Dharm", "Karm", "Labh", "Vyaya",
)

# The first bhava alone goes by more than one name. ch. 24 calls it Lagn throughout,
# ch. 11 calls it "the ascending Rāśi", and only the rest of the library calls it Tanu.
BHAVA_ALIASES = {1: ("Tanu", "Lagn", "ascending")}


def bhava_names(house: int) -> tuple[str, ...]:
    """Every name this translation uses for one bhava."""
    return BHAVA_ALIASES.get(house, (BHAVA_NAMES[house - 1],))

# The names it uses for the twelve rasis, in order from Aries.
SANSKRIT_SIGNS = (
    "Mesh", "Vrishabh", "Mithun", "Kark", "Simh", "Kanya",
    "Tula", "Vrischik", "Dhanu", "Makar", "Kumbh", "Meen",
)

# What a passage that describes a rasi says, as opposed to one that merely names it.
DESCRIBES = re.compile(
    r"complexion|lorded by|Its ruler is|Its Lord is|described|resorts to", re.IGNORECASE
)

# Virgo is the one sign this translation describes without naming: the passage opens
# "This Rāśi is a hill-resorter", carrying on from the numbering of the verse before,
# and calls it "a Virgin" rather than Kanya. Pointed at by hand because there is no word
# to search for; a test asserts the passage it lands on does describe Virgo.
SIGN_VERSE_OVERRIDES = {5: "13-14"}

# Bansal gives each graha a page of its own: what its yantra is for, what to recite and
# how often, and what to do daily. The page is the locator because the book numbers
# nothing else. A test asserts each one carries that graha's mantra, which is what makes
# these safe to hard-code — get one wrong and the test says so.
REMEDY_PAGES = {
    "Sun": 90, "Moon": 91, "Mars": 92, "Mercury": 93, "Jupiter": 94,
    "Venus": 95, "Saturn": 96, "Rahu": 97, "Ketu": 98,
}

# The beej mantra shape: "Om <three seed syllables> Sah <deity> Namah". Read out of the
# page rather than copied here, so the two cannot drift apart. The space after "Om" is
# optional because the scan of Bansal p. 91 ran the two together — "OmShraang" — and a
# required space silently lost the Moon's mantra.
MANTRA = re.compile(r"Om\s*\S+\s+\S+\s+\S+\s+Sah\s+\S+\s+Namah")

# The nakshatra book uses its own transliteration throughout, and it is not ours: MRGA
# for Mrigashira, KRTTIKA for Krittika, SATABISHA for Shatabhisha. Written out because
# guessing at them by prefix found 25 of 27 and quietly attached the other two to a page
# of muhurta tables that describes nothing.
NAKSHATRA_SPELLINGS = {
    "Ashwini": "ASWINI", "Bharani": "BHARANI", "Krittika": "KRTTIKA",
    "Rohini": "ROHINI", "Mrigashira": "MRGA", "Ardra": "ARDRA",
    "Punarvasu": "PUNARVASU", "Pushya": "PUSHYA", "Ashlesha": "ASHLESHA",
    "Magha": "MAGHA", "Purva Phalguni": "PURVAPHALGUNI",
    "Uttara Phalguni": "UTTARAPHALGUNI", "Hasta": "HASTA", "Chitra": "CHITRA",
    "Swati": "SWATI", "Vishakha": "VISAKHA", "Anuradha": "ANURADHA",
    "Jyeshtha": "JYESTHA", "Mula": "MULA", "Purva Ashadha": "PURVAASHADA",
    "Uttara Ashadha": "UTTARAASADHA", "Shravana": "SHRAVAN",
    "Dhanishta": "DHANISTHA", "Shatabhisha": "SATABISHA",
    "Purva Bhadrapada": "PURVABHADRAPADA", "Uttara Bhadrapada": "UTTARABHADRAPADA",
    "Revati": "REVATI",
}


@lru_cache(maxsize=1)
def _passages() -> tuple[dict, ...]:
    return tuple(load_passages())


def _one(work: str, **where) -> Hit | None:
    found = lookup(work, passages=list(_passages()), **where)
    return found[0] if found else None


def significations(house: int) -> Hit | None:
    """What BPHS says is read from this bhava (ch. 11, one verse each)."""
    return _one(BPHS, chapter="11", verse=str(house + 1))


def bhava_chapter(house: int) -> list[Hit]:
    """The whole chapter on this bhava's effects — ch. 12 for the 1st, and so on."""
    return lookup(BPHS, chapter=str(11 + house), passages=list(_passages()))


def lord_in_house(lord_of: int, sits_in: int) -> Hit | None:
    """BPHS ch. 24 on the lord of one bhava standing in another.

    The chapter is a 12x12 grid in reading order, so the verse is arithmetic. A few
    cells are missing from this printing — verse 12, the lagna lord in the 12th, among
    them — and those come back as None rather than as the neighbouring verse, which
    would be a confident citation of the wrong sentence.
    """
    return _one(BPHS, chapter="24", verse=str((lord_of - 1) * 12 + sits_in))


def sign_description(sign: int) -> Hit | None:
    """BPHS ch. 4 on one rasi.

    Found by name, not by counting: the verses are grouped unevenly and several signs
    share a passage with the one described after them.

    Two filters, both earned. Verse 3 names every rasi and describes none of them —
    "The 12 Rāśis of the zodiac in order are Mesh, Vrishabh, ..." — and matching on the
    name alone returned that list for eleven of the twelve. Verse 1-2 mentions Mesh in
    passing, so a description marker is required as well.
    """
    name = SANSKRIT_SIGNS[sign % 12]
    override = SIGN_VERSE_OVERRIDES.get(sign % 12)
    if override:
        return _one(BPHS, chapter="4", verse=override)

    for passage in lookup(BPHS, chapter="4", passages=list(_passages())):
        named = sum(
            1 for other in SANSKRIT_SIGNS if re.search(rf"\b{other}\b", passage.body)
        )
        if named > 6 or not DESCRIBES.search(passage.body):
            continue
        if re.search(rf"\b{name}\b", passage.body):
            return passage
    return None


def sign_excerpt(sign: int) -> tuple[str, Hit] | None:
    """Just the part of the passage that describes this rasi, with its citation.

    The ingestion merged several of ch. 4's verses, so one passage can carry four signs
    — Virgo, Libra, Scorpio and Sagittarius all live in v. 13-14. Handing a reader the
    whole block to answer "what is my ninth house's sign like" is barely an answer, so
    it is cut at the next sign named after this one.
    """
    passage = sign_description(sign)
    if passage is None:
        return None
    name = SANSKRIT_SIGNS[sign % 12]
    body = " ".join(passage.body.split())

    marks = sorted(
        (match.start(), other)
        for other in SANSKRIT_SIGNS
        for match in re.finditer(rf"\b{other}\b", body)
    )
    # Where this sign's own description begins. Virgo is never named, and begins the
    # block it shares, so it starts at nothing.
    start = next((at for at, other in marks if other == name), 0)
    end = next((at for at, other in marks if at > start and other != name), len(body))
    return body[start:end].strip(" .;"), passage


def verses_naming(house: int, body: str) -> list[Hit]:
    """Verses in this bhava's own chapter that name a given graha.

    BPHS has no planet-by-house table — ch. 24 is lords, not occupants — but the
    per-bhava chapters are full of conditions, and a good number name a graha outright.
    Those are the classical statements that bear on a planet standing here, and they are
    returned as found rather than summarised.
    """
    alias = SANSKRIT_GRAHAS.get(body)
    if alias is None:
        return []
    pattern = re.compile(rf"\b({re.escape(body)}|{re.escape(alias)})\b", re.IGNORECASE)
    return [
        passage for passage in bhava_chapter(house) if pattern.search(passage.body)
    ]


# The translation uses the Sanskrit names throughout, so an English search for "Jupiter"
# finds nothing in BPHS.
SANSKRIT_GRAHAS = {
    "Sun": "Sūrya", "Moon": "Candr", "Mars": "Mangal", "Mercury": "Budh",
    "Jupiter": "Guru", "Venus": "Śukr", "Saturn": "Śani",
    "Rahu": "Rahu", "Ketu": "Ketu",
}


# ch. 52-60, one chapter per mahadasha lord, in Vimshottari order from the Sun. Read off
# the chapters rather than assumed: each one's verses say "in the Dasha of <lord>"
# throughout, and a test checks that every chapter here says its own lord's name.
DASHA_CHAPTERS = {
    "Sun": 52, "Moon": 53, "Mars": 54, "Rahu": 55, "Jupiter": 56,
    "Saturn": 57, "Mercury": 58, "Ketu": 59, "Venus": 60,
}


def _antar_marker(graha: str | None = None) -> re.Pattern:
    """Where a sub-period's discussion begins."""
    names = (
        f"{re.escape(SANSKRIT_GRAHAS[graha])}|{re.escape(graha)}" if graha
        else "|".join(
            re.escape(name) for pair in SANSKRIT_GRAHAS.items() for name in pair
        )
    )
    return re.compile(rf"Antar\s+Dasha\s+of\s+({names})\b", re.IGNORECASE)


def antardasha_effect(mahadasha: str, antardasha: str) -> tuple[str, Hit] | None:
    """What BPHS says of one sub-period inside one major period.

    The most personal thing the library has to say about a moment: not what a graha does
    in general, but what this graha does inside this other graha's years.

    Sliced, not just matched. The ingestion glued the tail of one verse group onto the
    next, so a passage can open with Rahu's sub-period and carry Jupiter's header at the
    end of it. Returning that whole passage cited the right verse and showed the wrong
    planet's paragraph, which is worse than showing nothing.
    """
    chapter = DASHA_CHAPTERS.get(mahadasha)
    if chapter is None or antardasha not in SANSKRIT_GRAHAS:
        return None

    passages = lookup(BPHS, chapter=str(chapter), passages=list(_passages()))
    wanted, any_graha = _antar_marker(antardasha), _antar_marker()
    for passage in passages:
        body = " ".join(passage.body.split())
        found = wanted.search(body)
        if not found:
            continue
        after = any_graha.search(body, found.end())
        return body[found.start() : after.start() if after else len(body)].strip(), passage

    # A lord's own sub-period is written possessively — "in her Antar Dasha", "in his
    # own Dasha" — rather than "the Antar Dasha of Candr", so the name search misses it.
    # Vimshottari opens every major period with the lord's own sub-period and the
    # chapters follow that order, so it is the one the chapter starts with.
    if mahadasha == antardasha and passages:
        body = " ".join(passages[0].body.split())
        after = any_graha.search(body)
        return body[: after.start() if after else len(body)].strip(), passages[0]
    return None


def varga_purposes() -> Hit | None:
    """ch. 7 v. 1-8, which says what each of the sixteen divisions is read for."""
    return _one(BPHS, chapter="7", verse="1-8")


def karakatwas() -> Hit | None:
    """The verse that assigns the chara karakas by degree (ch. 32 v. 13-17)."""
    return _one(BPHS, chapter="32", verse="13-17")


def avastha_rule(which: str) -> Hit | None:
    """The verse defining one set of states (ch. 45)."""
    return _one(BPHS, chapter="45", verse={
        "baladi": "3", "baladi_results": "4",
        "jagradadi": "5", "jagradadi_results": "6",
        "deeptadi": "8-10",
    }.get(which, ""))


# --- the Lal Kitab conduct table -------------------------------------------
#
# Bansal pp. 224-229, "Remedial measures for afflicted planets in different houses":
# a graha-by-house grid of things to do and not do. It is the only place in the library
# that answers "what should I actually change" with something a person can act on
# tomorrow — keep aniseed by your pillow, serve the elderly, do not sell gold — rather
# than with a rite.
#
# It is parsed rather than copied, so it stays tied to the page. Three things about the
# scan make that harder than it sounds and are handled below: the Moon's heading is
# missing entirely, Saturn's leading 7 came out as a question mark, and lowercase
# "3rd house" appears throughout the prose and must not be mistaken for a heading.
CONDUCT_PAGES = (220, 232)
CONDUCT_TITLE = "REMEDIAL MEASURES FOR AFFLICTED PLANETS"
_CONDUCT_HEAD = re.compile(
    r"[1-9?]\s*\.\s*(SUN|MOON|JUPITER|VENUS|MERCURY|MARS|SATURN|RAHU|KETU)\s*:"
)
# Uppercase HOUSE only. The same pattern case-insensitively matched every "in the 3rd
# house" in the prose and shredded the table into 32 pieces.
_CONDUCT_MARK = re.compile(
    r"(?<![\d])(\d{1,2})\s*[^A-Za-z0-9]{0,3}\s*[a-zA-Z]{0,3}\s*HO[US]{2}E\b\s*:?"
)
# The book's own order, which is not the usual one.
_CONDUCT_ORDER = ("Sun", "Moon", "Jupiter", "Venus", "Mercury", "Mars",
                  "Saturn", "Rahu", "Ketu")


@lru_cache(maxsize=1)
def _conduct_source() -> tuple[str, int]:
    """The remedy table as one run of text, and the page it starts on."""
    rows = sorted(
        (row for row in _passages()
         if row["work"] == REMEDIES
         and CONDUCT_PAGES[0] <= (row["page"] or 0) <= CONDUCT_PAGES[1]),
        key=lambda row: row["page"],
    )
    blob = " ".join(" ".join(row["body"].split()) for row in rows)
    at = blob.find(CONDUCT_TITLE)
    return (blob[at:] if at >= 0 else ""), 224


@lru_cache(maxsize=1)
def conduct_table() -> dict[tuple[str, int], str]:
    """What to do and not do, for each graha in each house."""
    seg, _ = _conduct_source()
    if not seg:
        return {}

    heads = [(m.start(), m.group(1).capitalize(), m.end())
             for m in _CONDUCT_HEAD.finditer(seg)]
    marks = [(m.start(), int(m.group(1)), m.end())
             for m in _CONDUCT_MARK.finditer(seg) if 1 <= int(m.group(1)) <= 12]

    spans: list[tuple[str, list]] = []
    for index, (at, name, _) in enumerate(heads):
        stop = heads[index + 1][0] if index + 1 < len(heads) else len(seg)
        inner = [mark for mark in marks if at < mark[0] < stop]
        if name != "Sun":
            spans.append((name, inner))
            continue
        # The Moon has no heading of its own; its block runs from where the house
        # numbers restart to the end of what looks like the Sun's span.
        restart = next(
            (i for i in range(1, len(inner)) if inner[i][1] <= inner[i - 1][1]),
            len(inner),
        )
        spans.append(("Sun", inner[:restart]))
        spans.append(("Moon", inner[restart:]))

    table: dict[tuple[str, int], str] = {}
    for name, inner in spans:
        if name not in _CONDUCT_ORDER:
            continue
        # Keep only a rising run. A stray repeated "1st HOUSE" in the prose would
        # otherwise swallow everything after it into one cell.
        kept, highest = [], 0
        for mark in inner:
            if mark[1] > highest:
                kept.append(mark)
                highest = mark[1]
        for i, (_, house, end) in enumerate(kept):
            stop = kept[i + 1][0] if i + 1 < len(kept) else None
            text = seg[end : stop if stop is not None else end + 900].strip(" .:;")
            # Cut at the next graha's heading if this is the last cell of a block.
            following = _CONDUCT_HEAD.search(text)
            if following:
                text = text[: following.start()].strip(" .:;")
            if 15 < len(text) < 1400:
                table[(name, house)] = text
    return table


def conduct(body: str, house: int) -> tuple[str, Hit] | None:
    """Lal Kitab's measures for this graha standing in this house."""
    text = conduct_table().get((body, house))
    if not text:
        return None
    page = _one(REMEDIES, page="225")
    return (text, page) if page else None


# p. 219: the deity, colour and articles of donation for each graha, which is the
# plainest description of what a planet *is* that the library carries.
def planet_profile(body: str) -> tuple[str, Hit] | None:
    passage = _one(REMEDIES, page="219")
    if passage is None:
        return None
    text = " ".join(passage.body.split())
    order = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn",
             "Rahu", "Ketu")
    if body not in order:
        return None
    start = text.find(f"{body} ")
    if start < 0:
        return None
    nxt = order.index(body) + 1
    end = text.find(f"{order[nxt]} ", start + 1) if nxt < len(order) else len(text)
    row = text[start : end if end > start else len(text)]
    # Ketu is last in the table and runs straight on into the next numbered section.
    row = re.split(r"\s[A-Z]?\s?\d+\s*\.\s*[A-Z]{4,}", row)[0]
    # The row opens with the graha's own name, which the heading above it already says.
    row = re.sub(rf"^{re.escape(body)}\s+", "", row.strip())
    return row.strip(" .,;"), passage


def practice(body: str) -> Hit | None:
    """Bansal's page for one graha: what it is worshipped for, and with what."""
    page = REMEDY_PAGES.get(body)
    if page is None:
        return None
    for passage in lookup(REMEDIES, page=str(page), passages=list(_passages())):
        if MANTRA.search(passage.body):
            return passage
    return _one(REMEDIES, page=str(page))


def mantra(body: str) -> str | None:
    """The graha's beej mantra, read out of the page that prescribes it."""
    passage = practice(body)
    if passage is None:
        return None
    found = MANTRA.search(passage.body)
    return found.group(0) if found else None


def nakshatra_note(name: str) -> Hit | None:
    """A description of one nakshatra's character.

    Only the one work written about them is searched. Most of the library mentions the
    nakshatras to say when to begin a journey, and a general search returned Charak's
    table of muhurta combinations — a real passage, correctly cited, describing nothing
    about the person. Better to have nothing to show than a citation that looks like an
    answer.
    """
    spelling = NAKSHATRA_SPELLINGS.get(name)
    if spelling is None:
        return None
    within = [dict(row) for row in _passages() if row["work"] == NAKSHATRA_WORK]
    hits = [hit for hit in search(spelling, within, limit=10) if len(hit.body) > 200]
    return hits[0] if hits else None
