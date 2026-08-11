"""Keyword search over ingested passages.

Deliberately not embeddings. Finding the verse that defines a named yoga is a
lookup for a rare word — "Kemadruma", "Ruchaka" — and exact matching beats semantic
similarity for that, with no index to build and no model to load. Embeddings earn their
place later, for the interpretation layer, where the query is a question rather than a
name.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

CORPUS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "corpus_md"


@dataclass(frozen=True)
class Hit:
    work: str
    chapter: int
    chapter_title: str
    verses: str
    heading: str
    body: str
    page: int
    score: int

    @property
    def versified(self) -> bool:
        return bool(self.verses)

    @property
    def citation(self) -> str:
        """Chapter and verse for versified texts, page for everything else.

        This used to hard-code the verse form, so every passage from a book that
        numbers nothing was cited as "ch. 0, v. " — a reference that looks precise and
        points nowhere. Most of the library is unversified, so that was most of it.
        """
        if self.versified:
            return f"{self.work}, ch. {self.chapter}, v. {self.verses}"
        return f"{self.work}, p. {self.page}"

    def excerpt(self, term: str, width: int = 240) -> str:
        position = _fold(self.body).find(_fold(term))
        if position < 0:
            return self.body[:width]
        start = max(0, position - width // 3)
        return ("..." if start else "") + self.body[start : start + width] + "..."


def _fold(text: str) -> str:
    """Lowercase and strip diacritics.

    These translations render Sanskrit inconsistently — Sukr and Śukr, Rasi and Rāśi —
    so a search for a plain-ASCII spelling has to match the accented form.
    """
    stripped = unicodedata.normalize("NFKD", text)
    return "".join(c for c in stripped if not unicodedata.combining(c)).lower()


def load_passages(corpus_dir: Path | str = CORPUS_DIR) -> list[dict]:
    passages: list[dict] = []
    for file in sorted(Path(corpus_dir).glob("*.jsonl")):
        for line in file.read_text().splitlines():
            if line.strip():
                passages.append(json.loads(line))
    return passages


def search(
    term: str,
    passages: list[dict] | None = None,
    *,
    chapters: set[int] | None = None,
    limit: int = 10,
) -> list[Hit]:
    """Passages containing `term`, most occurrences first."""
    passages = load_passages() if passages is None else passages
    needle = _fold(term)
    pattern = re.compile(re.escape(needle))

    hits: list[Hit] = []
    for passage in passages:
        if chapters and passage["chapter"] not in chapters:
            continue
        haystack = _fold(f"{passage['heading']} {passage['body']}")
        count = len(pattern.findall(haystack))
        if count:
            hits.append(
                Hit(
                    work=passage["work"],
                    chapter=passage["chapter"],
                    chapter_title=passage["chapter_title"],
                    verses=passage["verses"],
                    heading=passage["heading"],
                    body=passage["body"],
                    page=passage["page"],
                    score=count,
                )
            )
    hits.sort(key=lambda hit: (-hit.score, hit.chapter))
    return hits[:limit]


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="search the ingested corpus")
    parser.add_argument("term")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--full", action="store_true", help="print whole passages")
    arguments = parser.parse_args()

    passages = load_passages()
    for hit in search(arguments.term, passages, limit=arguments.limit):
        print(f"[{hit.citation}] {hit.chapter_title} — {hit.heading or '(no heading)'}")
        print("   ", hit.body if arguments.full else hit.excerpt(arguments.term))
        print()


if __name__ == "__main__":
    main()


def works(passages: list[dict] | None = None) -> list[dict]:
    """Every ingested work, with how much of it there is."""
    passages = load_passages() if passages is None else passages
    counts: dict[str, dict] = {}
    for record in passages:
        entry = counts.setdefault(
            record["work"], {"work": record["work"], "passages": 0, "versified": False}
        )
        entry["passages"] += 1
        if record["verses"]:
            entry["versified"] = True
    return sorted(counts.values(), key=lambda entry: -entry["passages"])


def lookup(
    work: str,
    chapter: str = "",
    verse: str = "",
    page: str = "",
    passages: list[dict] | None = None,
) -> list[Hit]:
    """Resolve a citation back to the passage it names.

    This is what makes a citation checkable rather than decorative: the reader sees the
    reference on a finding and can open the actual words behind it.
    """
    passages = load_passages() if passages is None else passages
    found = []
    for record in passages:
        if record["work"] != work:
            continue
        if verse and str(record["verses"]) != str(verse):
            continue
        if chapter and str(record["chapter"]) != str(chapter):
            continue
        if page and str(record["page"]) != str(page):
            continue
        found.append(
            Hit(
                work=record["work"], chapter=record["chapter"],
                chapter_title=record["chapter_title"], verses=record["verses"],
                heading=record["heading"], body=record["body"], page=record["page"],
                score=1,
            )
        )
    return found
