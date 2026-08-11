# External projects and data sources

Assessment of the seven repositories supplied, and what each is used for here.

Local-only is a hard constraint on this project: family birth data must not leave the
machine. Anything below that involves a hosted service is therefore usable for
verification against synthetic charts, or after self-hosting, but not for real profiles.

## Adopted

### VedAstro — https://github.com/VedAstro/VedAstro
MIT, C#/.NET, actively maintained, by far the most substantial of the seven.

Used as the **independent verification oracle**. It found a disagreement no internal
test could: Venus's ashtakavarga row from Mars reads `(3, 4, 6, 9, 11, 12)` here and
`(3, 5, 6, 9, 11, 12)` there. Row lengths are equal, so the 337-point checksum and every
other internal test passes either way while one bindu sits in a different house.

Taken in isolation the VedAstro reading looks like a correction, and it was briefly
applied here as one. Reading the primary text settled it the other way: BPHS ch. 66
v. 56-58 gives Venus's table house by house, and transposing it yields `3, 4, 6`. Seven
of the eight rows in that verse match this code exactly, and the row totals 52 as it
must. The change was reverted and the divergence recorded in `KNOWN_VARIANTS`, with
`tests/test_crosscheck.py` asserting the difference stays confined to those two signs
rather than asserting equality.

The lesson worth keeping: a second implementation tells you *where* to look, not *who is
right*. Only the cited text settles that.

Verified to agree on: all nine sidereal longitudes (under one arcsecond), the ascendant
(within ten arcseconds), navamsa, the Vimshottari chain three levels deep at birth, and
the whole ashtakavarga apart from the single documented cell above. Reference values are
frozen as literals in `tests/test_crosscheck.py`, so the suite stays offline and
deterministic.

Two traps worth recording:
- The `vedastro` PyPI package is **a REST client, not a local library**. Every call
  posts to vedastro.org. Do not point it at a family member's birth data. They publish
  a Docker image (`vedastro/api`) if the reference set ever needs regenerating from
  real charts.
- Their per-planet BAV rows are indexed by **sign** (Aries first) while their
  Sarvashtakavarga row is indexed by **house** (lagna first). Reading one as the other
  silently rotates every value. `test_the_two_indexings_are_consistent` guards this.

Also worth using later:
- `Library/Logic/Calculate` — the calculation logic, MIT, so it can be ported directly.
- [15,000 famous people birth dataset](https://huggingface.co/datasets/vedastro-org/15000-Famous-People-Birth-Date-Location)
  (`PersonList-15k.csv`) — real birth data covering extreme latitudes, pre-standard-time
  dates and DST transitions. Useful for widening the golden fixtures well past the one
  synthetic chart in use now.

## Cross-checking within the library

The same lesson applies inside the corpus, where it is cheaper: BPHS is the primary text,
but this translation is not a clean one, and a second author stating the same system is
what shows where.

Shadbala (BPHS ch. 27, with the drishti values of ch. 26) was checked line by line
against Charak, *Elements of Vedic Astrology*, pp. 177-187, who sets out the same six
sources independently. They agree on the exaltation arc, the seven vargas, odd and even
signs, the kendra split, the decanates, the four directions, day and night strength, the
thirds of the day, the natural table and the division of the aspect total by four. Four
places they do not, all recorded in `shadbala.KNOWN_VARIANTS` and each guarded by a test:

- **The year lord's divisor.** This BPHS printing says to divide the Ahargana by 60;
  Charak (p. 183) names "the year of 360 days". 360 is used, because the verse's own next
  step — advance the weekday by three per year — is arithmetic that only works for 360.
- **The eight motions.** Both give the same eight values. This translation attaches 7.5
  to *Sama*, a graha at about its usual pace, and 30 to *Manda*, a slow one; Charak
  (p. 184) has Mandatara 7.5, Manda 15, Madhya 30, which runs the right way round.
  Charak's names are followed.
- **The drishti values.** ch. 26 states them twice and contradicts itself: the ladder in
  v. 2-5 against the arithmetic in v. 6-12, which is discontinuous for Jupiter at the
  fifth aspect and would put 30 rather than a full 60 on the seventh. Charak (p. 186)
  tabulates every thirty degrees and matches the ladder exactly, so the ladder is
  implemented as a table and the arithmetic treated as corrupt.
- **The Moon's paksha bala.** Charak (p. 182) doubles it; BPHS does not mention doubling.
  BPHS is followed, which leaves the Moon up to 60 virupas below what a Charak-following
  implementation reports. This one is a genuine divergence between authors rather than a
  bad printing, so it is recorded rather than resolved.

## Reference only

### daiv-ai — https://github.com/master12coder/daiv-ai
AGPL-3.0, Python. The closest sibling to this project: Swiss Ephemeris plus AI
interpretation. Worth reading for how it structures interpretation. AGPL is viral, so
read for approach, do not copy code.

### stellium — https://github.com/katelouie/stellium
AGPL-3.0, Python, Swiss Ephemeris. Western-leaning but strong on chart visualisation and
reporting. Same AGPL caution.

### The-Seer — https://github.com/mrslbt/The-Seer
No licence file, which means no reuse rights at all. Readable as an example of Swiss
Ephemeris via WASM in the browser; nothing can be taken from it.

## Not adopted

### panchanga_api — https://github.com/degen0root/panchanga_api
An MCP server for panchang. Licence is unrecognised, the project is small, and it gates
tiers behind USDC and Telegram Stars payments. Panchang is also cheap to compute
locally: tithi, nakshatra, yoga and karana are all simple functions of the Sun-Moon
longitudes already available from `core/ephemeris.py`. Computing it here is less work
than integrating a paid dependency.

### astroway-mcp — https://github.com/astroway/astroway-mcp
MIT, an MCP client for a hosted calculation API covering natal charts, synastry,
transits and dashas. Sound project, but it sends birth data to a third party, which the
local-only constraint rules out for real profiles. Could serve as a second verification
source against synthetic charts if VedAstro alone ever proves insufficient.

### open-astro-org-web-service — https://github.com/ftadvisory/open-astro-org-web-service
GPL-3.0, last touched January 2024. Generates chart images server-side. The SVG kundli
in `web/src/Kundli.jsx` already covers this, and GPL would infect the project.

## PDF ingestion

Marker (the OCR pipeline in `~/Documents/marker-ocr`) was the first approach and was
abandoned. It stalls indefinitely on this book: it loads its models, then sits at 0% CPU
and never finishes. `--disable_multiprocessing` let a five-page probe complete in 115
seconds but did not fix the full run. Chunking by page range worked but would have taken
roughly 40 minutes because every chunk reloads the models.

None of that was necessary. The PDF has an intact text layer, so `pdftotext -layout`
reads it in well under a second, and the text preserves exactly the structure needed for
citation: chapter headings (`Ch. 66. AshtakaVarg`) and verse numbers at the start of each
passage (`56-58. ...`). `src/astro/corpus/ingest.py` parses that into 1871 cited passages
across 97 chapters in 0.27 seconds.

`scripts/convert_pdf.sh` is kept only as the OCR fallback for scanned texts with no text
layer. Check for a text layer first — `ingest.py` raises with a clear message if a PDF
is a scan.
