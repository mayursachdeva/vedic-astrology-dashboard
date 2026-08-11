"""Turn a scripture PDF into cited passages.

These texts are already structured: chapters are headed "Ch. 12. Effects of Tanu
Bhava", and each passage opens with its verse number or range — "42-53. Varg
Classification." That structure is the citation, so the parser's job is to preserve it
rather than to produce prose.

Most of the library has a real text layer, which `pdftotext -layout` reads in about a
second per book. Only fall back to OCR (see scripts/convert_pdf.sh) for scans.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

# "Ch. 6. The Sixteen Divisions of a Rasi", and "CHAPTER I." for books that number
# their chapters in Roman — Raman's Manual does, and would otherwise fall back to
# page-level citation despite being properly structured.
CHAPTER_RE = re.compile(r"^\s*Ch(?:apter|\.)\s*(\d+)\s*[.:]\s*(.+?)\s*$", re.I)
ROMAN_CHAPTER_RE = re.compile(r"^\s*CHAPTER\s+([IVXLC]+)\s*[.:]?\s*(.*)$")
ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def from_roman(numeral: str) -> int:
    total = 0
    for index, character in enumerate(numeral):
        value = ROMAN_VALUES[character]
        following = ROMAN_VALUES.get(numeral[index + 1]) if index + 1 < len(numeral) else None
        total += -value if following and following > value else value
    return total


OCR_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "ocr"

# "2-4. Names of the 16 Vargas. Lord Brahma has described..."
# The leading number or range is the verse reference; an optional short bold-style
# heading follows before the body proper.
VERSE_RE = re.compile(r"^\s*(\d+)(?:\s*[-–]\s*(\d+))?\s*[.)]\s+(\S.*)$")

# A passage's optional heading: a short capitalised phrase ending in a full stop.
HEADING_RE = re.compile(r"^([A-Z][^.]{2,60}?\.)\s+(.*)$")

# How far a verse number may jump before the parser treats it as a list item rather
# than a new passage. Verse numbers climb steadily; embedded lists restart low.
MAX_VERSE_GAP = 30


@dataclass(frozen=True)
class Passage:
    """One cited unit of a text.

    Two shapes, because the library is not uniform. BPHS and its kin number every
    passage, so the citation is a chapter and verse. Most modern books do not, and for
    those the page is the only honest locator — better than inventing a verse number or
    refusing to ingest the book at all.
    """

    work: str
    chapter: int
    chapter_title: str
    verses: str  # "42" or "42-53"; empty when the work is not versified
    heading: str
    body: str
    page: int

    @property
    def versified(self) -> bool:
        return bool(self.verses)

    @property
    def citation(self) -> str:
        if self.versified:
            return f"{self.work}, ch. {self.chapter}, v. {self.verses}"
        return f"{self.work}, p. {self.page}"

    @property
    def anchor(self) -> str:
        return f"ch{self.chapter}.v{self.verses}" if self.versified else f"p{self.page}"


# A -layout line with a wide gap between two runs of text is two columns printed side
# by side. Above this share of lines, the page is multi-column.
COLUMN_GAP = re.compile(r"\S {4,}\S")
COLUMN_SHARE = 0.25


def _run_pdftotext(pdf_path: Path, *flags: str) -> str:
    return subprocess.run(
        ["pdftotext", *flags, str(pdf_path), "-"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def looks_multi_column(text: str) -> bool:
    """Whether -layout output is two columns interleaved line by line.

    It matters a great deal. On a two-column book -layout stitches the left and right
    columns into single lines, so sentences from unrelated paragraphs are spliced
    together and every passage built from them is nonsense — while still looking like
    prose. Plain pdftotext reads such pages in proper reading order instead.
    """
    lines = [line for line in text.splitlines() if len(line.strip()) > 40]
    if len(lines) < 20:
        return False
    gapped = sum(1 for line in lines if COLUMN_GAP.search(line))
    return gapped / len(lines) > COLUMN_SHARE


def extract_pages(pdf_path: Path | str) -> list[str]:
    """Page text from a PDF's embedded text layer.

    Uses -layout, which keeps the indentation that verse numbering depends on, unless
    the document turns out to be multi-column — in which case that flag actively
    destroys the text and plain reading order is used instead.

    Raises if the PDF has no usable text layer, rather than returning empty strings that
    would quietly produce an empty corpus.
    """
    if shutil.which("pdftotext") is None:
        raise RuntimeError("pdftotext not found; install poppler (brew install poppler)")

    pdf_path = Path(pdf_path)

    # A scan has no text layer, so scripts/ocr_pdf.py writes one alongside. Prefer it:
    # it is the only text these books have.
    sidecar = OCR_DIR / f"{pdf_path.stem}.txt"
    if sidecar.exists():
        pages = sidecar.read_text(encoding="utf-8", errors="replace").split("\f")
        return [page for page in pages] or [""]

    text = _run_pdftotext(pdf_path, "-layout")
    if looks_multi_column(text):
        text = _run_pdftotext(pdf_path)

    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()

    characters = sum(len(page.strip()) for page in pages)
    if characters < 200 * len(pages):
        raise RuntimeError(
            f"{pdf_path} yielded only {characters} characters over {len(pages)} pages — "
            "it is probably a scan. Use scripts/convert_pdf.sh to OCR it instead."
        )
    return pages


def _flush(buffer: list[str]) -> str:
    """Join the wrapped lines of a passage back into a paragraph."""
    return re.sub(r"\s+", " ", " ".join(buffer)).strip()


def parse_passages(pages: list[str], work: str) -> list[Passage]:
    """Split a document into chapter- and verse-numbered passages."""
    passages: list[Passage] = []

    chapter = 0
    chapter_title = ""
    verses = ""
    start_page = 1
    last_verse = 0
    buffer: list[str] = []

    def close() -> None:
        nonlocal buffer
        if verses and buffer:
            body = _flush(buffer)
            heading = ""
            match = HEADING_RE.match(body)
            if match and len(match.group(1)) < 60:
                heading, body = match.group(1).rstrip("."), match.group(2)
            passages.append(
                Passage(
                    work=work,
                    chapter=chapter,
                    chapter_title=chapter_title,
                    verses=verses,
                    heading=heading,
                    body=body,
                    page=start_page,
                )
            )
        buffer = []

    for page_number, page in enumerate(pages, start=1):
        for line in page.splitlines():
            chapter_match = CHAPTER_RE.match(line)
            roman_match = None if chapter_match else ROMAN_CHAPTER_RE.match(line)
            if chapter_match or roman_match:
                close()
                if chapter_match:
                    chapter = int(chapter_match.group(1))
                    chapter_title = chapter_match.group(2)
                else:
                    chapter = from_roman(roman_match.group(1))
                    chapter_title = roman_match.group(2).strip()
                verses, last_verse = "", 0
                continue

            verse_match = VERSE_RE.match(line)
            if verse_match and chapter:
                first = int(verse_match.group(1))
                last = int(verse_match.group(2) or first)
                # Numbered lists inside a passage restart low; a real verse number
                # always moves forward, and never by a huge jump.
                if last_verse < first <= last_verse + MAX_VERSE_GAP:
                    close()
                    verses = f"{first}-{last}" if last != first else str(first)
                    last_verse = last
                    start_page = page_number
                    buffer = [verse_match.group(3)]
                    continue

            if verses and line.strip():
                buffer.append(line.strip())

    close()
    return passages


# Blocks are merged up to roughly this length rather than dropped. An earlier version
# discarded anything shorter, which silently binned the most citable content there is:
# "Vasumathi Yoga is caused when all the benefics are in upachaya houses, namely the
# 3rd, 6th, 10th and 11th" is 105 characters, and it vanished from the corpus entirely.
# Nothing is thrown away now except unmistakable page furniture.
MIN_PASSAGE_CHARACTERS = 120

# Shorter than this, with no sentence in it, is a running header or a page number.
NOISE_CHARACTERS = 25


def parse_pages(pages: list[str], work: str) -> list[Passage]:
    """Fall back to page-level passages for books that number nothing.

    Paragraphs are joined per page and split on blank lines, so a search hit lands on a
    block of prose with a page number rather than on a whole chapter.
    """
    passages: list[Passage] = []
    for page_number, page in enumerate(pages, start=1):
        blocks = [_flush(block.splitlines()) for block in re.split(r"\n\s*\n", page)]
        blocks = [block for block in blocks if len(block) >= NOISE_CHARACTERS]

        # Merge forwards until each chunk is substantial, rather than discarding the
        # short ones. A short block is usually a complete thought — a definition, a
        # rule — and it is exactly what a citation wants to point at.
        merged: list[str] = []
        for block in blocks:
            if merged and len(merged[-1]) < MIN_PASSAGE_CHARACTERS:
                merged[-1] = f"{merged[-1]} {block}"
            else:
                merged.append(block)

        for body in merged:
            heading = ""
            match = HEADING_RE.match(body)
            if match and len(match.group(1)) < 60:
                heading, body = match.group(1).rstrip("."), match.group(2)
            passages.append(
                Passage(
                    work=work,
                    chapter=0,
                    chapter_title="",
                    verses="",
                    heading=heading,
                    body=body,
                    page=page_number,
                )
            )
    return passages


def parse_markdown(text: str, work: str) -> list[Passage]:
    """Markdown split on its own headings, which are the only structure it has."""
    passages: list[Passage] = []
    heading = ""
    buffer: list[str] = []
    section = 0

    def close() -> None:
        nonlocal buffer
        body = _flush(buffer)
        if len(body) >= MIN_PASSAGE_CHARACTERS:
            passages.append(
                Passage(
                    work=work,
                    chapter=0,
                    chapter_title="",
                    verses="",
                    heading=heading,
                    body=body,
                    page=section,
                )
            )
        buffer = []

    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if match:
            close()
            section += 1
            heading = match.group(2).strip()
        elif line.strip():
            buffer.append(line.strip())
        else:
            close()
    close()
    return passages


def to_markdown(passages: list[Passage], work: str) -> str:
    """A readable markdown rendering, one section per chapter."""
    lines = [f"# {work}", ""]
    current = None
    for passage in passages:
        if passage.versified:
            if passage.chapter != current:
                current = passage.chapter
                lines += ["", f"## Chapter {passage.chapter}. {passage.chapter_title}", ""]
            title = f" {passage.heading}" if passage.heading else ""
            lines += [f"**{passage.verses}.**{title} {passage.body}", ""]
        else:
            if passage.page != current:
                current = passage.page
                lines += ["", f"## p. {passage.page}", ""]
            if passage.heading:
                lines += [f"**{passage.heading}.** {passage.body}", ""]
            else:
                lines += [passage.body, ""]
    return "\n".join(lines)


def to_jsonl(passages: list[Passage]) -> str:
    """One JSON object per passage, ready for chunking and embedding."""
    return "\n".join(
        json.dumps({**asdict(passage), "citation": passage.citation}, ensure_ascii=False)
        for passage in passages
    )


# Below this many verse-numbered passages, the "verses" the parser found are almost
# certainly numbered lists in prose rather than a versified text.
VERSIFIED_THRESHOLD = 40

# The verse parser only keeps text that follows a recognised chapter heading and a
# verse number, so on a book whose headings it half-recognises it can return a tidy
# handful of passages while silently discarding most of the work. If it captured less
# than this share of the document, the structure was not really found and page-level
# passages are used instead — worse citations, but the whole book.
MIN_CAPTURE_SHARE = 0.5

# A verse passage runs to a few hundred characters, occasionally a couple of thousand.
# When the parser recognises a verse number and then fails to find the next one, it
# swallows everything in between: Jyotisha Siddhanta Sara produced a single "ch. 5,
# v. 27" holding 80,000 characters — a third of the book behind one reference that
# looks precise. If the largest passage is past this, the numbering was not really
# followed and page citations are the honest fallback. BPHS, which parses properly,
# tops out at 7,100.
MAX_VERSE_CHARACTERS = 12_000


def ingest(source: Path | str, output_dir: Path | str, work: str | None = None) -> list[Passage]:
    """Convert one PDF or markdown file and write both renderings next to each other.

    Versified texts keep their chapter and verse numbering. Anything else falls back to
    page-level passages, so the book is still searchable and still cites something real.
    """
    source = Path(source)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    name = work or source.stem

    if source.suffix.lower() == ".md":
        passages = parse_markdown(source.read_text(encoding="utf-8", errors="replace"), name)
    else:
        pages = extract_pages(source)
        passages = parse_passages(pages, name)
        available = sum(len(re.sub(r"\s+", " ", page).strip()) for page in pages)
        captured = sum(len(passage.body) for passage in passages)
        largest = max((len(passage.body) for passage in passages), default=0)
        if (
            len(passages) < VERSIFIED_THRESHOLD
            or not available
            or captured / available < MIN_CAPTURE_SHARE
            or largest > MAX_VERSE_CHARACTERS
        ):
            passages = parse_pages(pages, name)

    (output / f"{source.stem}.md").write_text(to_markdown(passages, name))
    (output / f"{source.stem}.jsonl").write_text(to_jsonl(passages))
    return passages


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("corpus_md"))
    parser.add_argument("--work", help="title to cite this text as")
    arguments = parser.parse_args()

    passages = ingest(arguments.pdf, arguments.output_dir, arguments.work)
    chapters = {passage.chapter for passage in passages}
    print(
        f"{len(passages)} passages across {len(chapters)} chapters "
        f"-> {arguments.output_dir}/{arguments.pdf.stem}.md"
    )


if __name__ == "__main__":
    main()
