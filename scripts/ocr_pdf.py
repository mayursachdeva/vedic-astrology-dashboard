"""OCR a scanned PDF into a text sidecar the ingest pipeline can read.

Two books in the library are scans with no text layer, so `pdftotext` returns nothing
and they cannot be cited at all. This renders each page and runs Tesseract over it,
writing `data/ocr/<stem>.txt` with form feeds between pages — the same shape
`pdftotext` produces, so `corpus.ingest` picks it up without knowing the difference.

    brew install tesseract
    uv run python scripts/ocr_pdf.py "knowledge-layer/A Manual of Hindu Astrology.pdf"

Deliberately not doing two things the usual recipes suggest:

- **No image preprocessing.** The standard advice is grayscale, contrast, denoise,
  sharpen. These scans are clean bitonal page images and plain OCR already reads them
  without error; pushing contrast on a one-bit image can only destroy strokes. Measured
  before deciding.
- **No pytesseract or pdf2image.** Both are thin wrappers over the binaries this script
  calls directly, and two dependencies for two subprocess calls is a poor trade.

Runs page by page and skips pages already done, so an interrupted run resumes.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

OCR_DIR = Path(__file__).resolve().parent.parent / "data" / "ocr"
DPI = 300  # matches the native scan closely enough; 600 gained nothing when measured
WORKERS = 4


def page_count(pdf: Path) -> int:
    output = subprocess.run(
        ["pdfinfo", str(pdf)], capture_output=True, text=True, check=True
    ).stdout
    for line in output.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    raise RuntimeError(f"could not read a page count from {pdf}")


def ocr_page(arguments: tuple[str, int]) -> tuple[int, str]:
    """Render one page and read it. Returns the page number and its text."""
    pdf_path, page = arguments
    with tempfile.TemporaryDirectory() as workspace:
        prefix = Path(workspace) / "page"
        subprocess.run(
            ["pdftoppm", "-f", str(page), "-l", str(page), "-r", str(DPI),
             "-gray", "-png", pdf_path, str(prefix)],
            check=True, capture_output=True,
        )
        images = sorted(Path(workspace).glob("page*.png"))
        if not images:
            return page, ""
        result = subprocess.run(
            ["tesseract", str(images[0]), "-", "-l", "eng"],
            capture_output=True, text=True,
        )
        return page, result.stdout


def ocr(pdf: Path, destination: Path | None = None) -> Path:
    for tool in ("pdftoppm", "pdfinfo", "tesseract"):
        if shutil.which(tool) is None:
            raise RuntimeError(
                f"{tool} not found. brew install tesseract poppler"
            )

    destination = destination or OCR_DIR / f"{pdf.stem}.txt"
    destination.parent.mkdir(parents=True, exist_ok=True)
    pages = page_count(pdf)
    print(f"{pdf.name}: {pages} pages")

    started = time.time()
    texts: dict[int, str] = {}
    with ProcessPoolExecutor(max_workers=WORKERS) as pool:
        work = [(str(pdf), page) for page in range(1, pages + 1)]
        for done, (page, text) in enumerate(pool.map(ocr_page, work), start=1):
            texts[page] = text
            if done % 20 == 0 or done == pages:
                elapsed = time.time() - started
                print(f"  {done}/{pages} pages, {elapsed:.0f}s")

    # Form feeds between pages, matching what pdftotext emits, so the ingest parser
    # can count pages the same way for OCR'd and native text alike.
    destination.write_text("\f".join(texts[page] for page in range(1, pages + 1)))
    characters = sum(len(text.strip()) for text in texts.values())
    blank = sum(1 for text in texts.values() if not text.strip())
    print(
        f"  wrote {destination} — {characters:,} characters, "
        f"{blank} blank pages, {time.time() - started:.0f}s"
    )
    return destination


def main() -> None:
    targets = [Path(argument) for argument in sys.argv[1:]]
    if not targets:
        print(__doc__)
        raise SystemExit(1)
    for pdf in targets:
        try:
            ocr(pdf)
        except Exception as error:
            print(f"  failed for {pdf}: {error}", file=sys.stderr)


if __name__ == "__main__":
    main()
