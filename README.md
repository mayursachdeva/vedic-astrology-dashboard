# Vedic astrology dashboard

A local-only Vedic astrology dashboard for a family. Birth data never leaves the
machine: there is no auth because there is no network exposure, and the only feature
that makes an outbound call is chart question answering, which is opt-in.

## What is not in this repository

Three things are deliberately absent, and the app will not do much until two of them are
put back:

| missing | why | how to restore |
| --- | --- | --- |
| `data/astro.db` | real names, birth times to the minute and coordinates | created empty on first run; add people through the dashboard |
| `knowledge-layer/`, `corpus_md/` | eighteen copyrighted books and the text extracted from them | supply your own copies, then `scripts/convert_pdf.sh` and the corpus backfill |
| `data/places.db` | 58 MB of GeoNames | `uv run python scripts/fetch_places.py` |

Without the corpus the computation all works — charts, dashas, shadbala, ashtakavarga,
yogas — but every citation resolves to nothing and the house readings come back empty.

## Running it

```bash
uv sync --extra dev                                   # Python 3.12, pinned
uv run uvicorn astro.api.main:app --port 8000         # API
cd web && npm install && npm run dev                  # dashboard on :5173
```

Then open <http://localhost:5173>.

```bash
uv run pytest                                         # the whole suite
```

## What it does

- **Charts** — sidereal positions, all sixteen divisional charts, whole-sign houses,
  configurable ayanamsa and node convention.
- **Timing** — Vimshottari dasha to pratyantardasha, transits by two doctrines, sade
  sati, retrograde and combustion windows.
- **Findings** — 32 classical yogas and a set of remedies, each a rule with a source.
- **Life stages** — the main view: a dated series of chapters scored across career,
  relationships, health, finance, family and learning.
- **Report** — the whole reading as markdown, at `/api/profiles/{id}/report`.
- **Compatibility** — the eight-factor thirty-six point comparison between any two
  saved people, plus the seventh-house reading the ingested text actually prescribes.
- **Panchanga** — the five limbs of the day at birth and today, with the readings BPHS
  attaches to particular tithis and karanas.

## The two rules this project is built on

**Nothing is asserted without its basis.** Every yoga, remedy and score carries the
placements that produced it and the text it comes from. Where a rule's chapter and
verse were located in an ingested text, they are given. Where they were not, the output
says *"no verse located in the ingested texts"* rather than implying a source was
checked. Scores are always the sum of the drivers printed beside them.

**Plain language first, rigour underneath.** Findings read as ordinary sentences, with
the technical basis collapsed below them. The reader should not need to know what a
pratyantardasha is to learn what is happening in their life.

## The library

`knowledge-layer/` holds the source PDFs; `corpus_md/` holds the ingested result —
**10,345 cited passages across 22 works**, including Brihat Parashara Hora Shastra,
Raman's *Manual of Hindu Astrology* (1935), Charak's *Elements of Vedic Astrology*,
Bansal's *Encyclopedia of Astrological Remedies*, *Jaimini Sutras*, *Muhurta Jyotisha*,
*Lal Kitab*, *Jyotisha Siddhanta Sara* and two works on the nodes.

Two of them are scans with no text layer. `scripts/ocr_pdf.py` reads them with
Tesseract into `data/ocr/`, which `ingest.py` prefers over `pdftotext` when present —
Raman's 172-page *Manual* took 32 seconds.

Of the 32 yoga rules, 25 cite a located source and 7 do not. Every unlocated rule
carries a note saying what was searched for and what was found, so the gap is visible
rather than silent, and nobody repeats the hunt.

Citations are not decoration: the dashboard resolves every one of them against the
corpus, so a reader can open the passage behind a finding and read the words. A test
asserts that each located citation resolves to a real passage — a reference that points
nowhere is worse than none, because it looks checked.

## Adding a text

```bash
uv run python -m astro.corpus.ingest path/to/book.pdf --work "Phaladeepika"
```

About a second per book. Versified works like BPHS keep their chapter and verse
numbering; everything else falls back to page-level passages cited as "Work, p. 42",
which is the only honest locator when a book numbers nothing. Markdown splits on its
own headings.

To OCR a scan:

```bash
brew install tesseract
uv run python scripts/ocr_pdf.py "knowledge-layer/A Manual of Hindu Astrology.pdf"
```

No image preprocessing and no `pytesseract`. The usual recipe says grayscale, boost
contrast, denoise, sharpen — but these are clean bitonal page images that plain OCR
already reads without error, and pushing contrast on a one-bit image can only destroy
strokes. That was measured on a sample page before deciding. `pytesseract` and
`pdf2image` are thin wrappers over the two binaries the script already calls.

Three extraction details that matter more than they look. `pdftotext -layout` preserves
the indentation verse parsing depends on, but on a two-column book it stitches the left
and right columns into single lines and produces fluent nonsense — four books in this
library are two-column, so the column layout is detected and plain reading order used
instead. The verse parser only keeps text following a chapter heading it recognises, so
on a book whose headings it half-reads it returns a tidy handful of passages and drops
the rest — Raman's Manual gave 80 passages from 160,000 characters until a coverage
check was added, and now yields the whole book at page level. And if a PDF is a scan
with no OCR sidecar, `ingest.py` says so rather than yielding an empty corpus.

Once a text is in, `astro.corpus.search` can locate the rules currently marked
unlocated, and their citations can be upgraded.

## Where the maths is deliberately incomplete

Two of the eight compatibility factors are simplified, and say so in their output
rather than presenting an approximation as exact:

- **Yoni** grades fourteen animals on a five-point scale. Only the values sources agree
  on are encoded — 4 for the same animal, 0 for the seven opposed pairs, 2 otherwise.
  The intermediate 1 and 3 are omitted rather than guessed.
- **Vashya** has half-point gradations between some classes; only whole values are here.

The ashtakavarga reductions (BPHS ch. 67-69) *are* now implemented — trikona and
ekadhipatya sodhana and the rasi, graha and sodhya pindas — and exposed under
`ashtakavarga.reductions`. They are kept separate from the raw counts, because a
sodhya pinda is used for longevity work rather than for reading a house's support, and
mixing them would invite comparing unlike numbers.

Ch. 69 v. 1-4 states its multipliers twice, in prose and in a table, and the two
disagree on six values. The table is used because it matches every other authority; the
prose reading is recorded in `MULTIPLIER_VARIANTS` so nobody quietly "corrects" the code
back to it.

Shadbala is not implemented at all. No rule needs a numeric six-fold strength yet, and
a half-version would be worse than its absence.

## No third-party services

The plan originally called for provider adapters wrapping external astrology APIs. Most
of that was argued away rather than built:

- Hosted calculation APIs send birth data to someone else, which the local-only
  constraint rules out for real profiles.
- Panchang is arithmetic on the Sun and Moon longitudes already computed here, so
  `core/panchanga.py` does it locally rather than fetching it.
- Geocoding and timezone lookup are handled offline by `timezonefinder`.

No `providers/` abstraction has been written, because there is nothing to put behind
it. If you later want a specific service, it is a small addition at that point — an
interface with no implementations would be worse than none.

## Question answering

`POST /api/profiles/{id}/ask` runs against **Ollama on this machine**, so birth data
never leaves it — the same promise as the rest of the project, including when someone
asks a question.

```bash
ollama serve                      # if it is not already running
ollama pull llama3.2:3b           # or any tool-calling model
ASTRO_QA_MODEL=qwen3:8b uv run uvicorn astro.api.main:app --port 8000
```

`OLLAMA_HOST` and `ASTRO_QA_MODEL` both override the defaults
(`http://localhost:11434`, `llama3.2:3b`). If Ollama is down or the model is missing,
the endpoint returns 503 naming the exact problem and everything else keeps working.

The model gets no chart data up front. It must call the read-only tools in
`astro/interpret/tools.py` for every fact, so it cannot assert a position that was never
computed. Two gates guard the result: `grounded` is false when no tool was called at
all, and `complete` is false when the model printed a tool call as prose or turned round
and asked the reader for chart facts. Both read like answers and contain nothing.

**On model size.** The default is `qwen3:8b`. It answers a direct question correctly and
completely — "what does my 7th house say" returns the right sign, lord, the lord's own
sign and house, and correctly attributes the aspects to the house rather than to its
ruler. It chains two lookups (house then its lord) correctly some runs and, on others,
writes out the steps it intends to take without taking them. That second case is caught
and reported rather than shown as an answer.

`llama3.2:3b` also works for direct questions but is unreliable at chaining and at
argument types. Anything smaller is not worth trying.

Running against a model surfaced three defects in the tool surface that no unit test
would have found, all now fixed and covered:

- Arguments arrived as strings (`{"house": "7"}`), so the boundary coerces to the type
  the schema declares.
- `get_house` returned a flat `aspected_by` beside `lord` and `lord_dignity`, and the
  model reported the house's aspects as the lord's — claiming Mercury was aspected by
  Saturn and Rahu when they reach the 7th house and Mercury sits three signs away.
  Renaming the key did not stop it; nesting the lord's facts under `lord` did.
- `get_house` gave the lord's dignity but not its sign, so the model inferred the lord
  sat in the house it rules. It now returns the sign.

## Layout

```
src/astro/
  core/        pure computation — ephemeris, timeloc, dasha, varga, strength,
               ashtakavarga, transit, facts
  rules/       the rule engine plus yoga and remedy data
  corpus/      PDF ingestion and search over the texts
  interpret/   life stages, report, remedies, Q&A tools
  api/         FastAPI, thin
web/           React dashboard
docs/          references.md — the external projects assessed, and why
```

`core/` is network-free and has no knowledge of storage, which is what makes the
golden-chart tests possible. `ephemeris.py` is the only module that imports swisseph.

## Verification

Positions are checked against published values — Lahiri ayanamsa at J2000 to the
arcsecond, Mesha Sankranti 2026 to within two minutes of the published panchang — and
cross-checked against VedAstro, an independent implementation. The ashtakavarga tables
are checked against BPHS ch. 66 verse by verse; where authorities disagree, the
divergence is recorded in `KNOWN_VARIANTS` rather than silently resolved. See
`docs/references.md`.
