# Decisions

Every decision in this project that a reasonable person could have made differently, with
the reason and what would overturn it. Grouped by kind, not by date.

This exists because the code is full of choices that look arbitrary until you know what
was tried. Most of them were made after something went wrong; the ones with a bug attached
are marked **·cost**.

The scholarly divergences are also held in `KNOWN_VARIANTS` dicts next to the code that
implements them, and each is guarded by a test. This file is the index; those are the
authority.

---

## 1. Constraints

### 1.1 Birth data never leaves the machine
The corpus is ingested locally, the place gazetteer is offline, and the question-answering
model runs under Ollama.

**Why:** this holds the user's own and family members' birth data.

**Cost, accepted:** a local 8B model needs grounding gates, a factchecker and a nudge that
a hosted frontier model would not. Answers are seconds rather than instant.

**What would change it:** nothing, for the default path. If a hosted model is ever wanted
the shape is an explicit opt-in per question with the privacy cost stated at the point of
use — never a default.

### 1.2 No new dependency for what a few lines can do
No charting library, no router, no markdown library, no ORM. The SVG kundli, `useState`
routing, a 20-line markdown renderer and hand-written SQL are the pattern.

**What would change it:** a genuine need the stdlib and existing dependencies cannot meet.

---

## 2. How sources are treated

### 2.1 Primary text beats secondary implementation ·cost
A second implementation tells you **where** to look, not **who is right**. Only the cited
text settles it.

**Why:** VedAstro reads Venus's ashtakavarga row from Mars as `(3,5,6,9,11,12)` where this
reads `(3,4,6,9,11,12)`. Taken alone their version looks like a correction, and it was
briefly applied as one. BPHS ch. 66 v. 56-58 gives the table house by house and yields
`3,4,6`; seven of the eight rows in that verse already matched this code exactly. The
change was reverted.

**How it is applied:** divergences are recorded in `KNOWN_VARIANTS` and a test asserts the
difference stays confined to the documented cells, rather than asserting equality.

### 2.2 Derive pointers; never copy content
`corpus/index.py` computes which passage applies rather than paraphrasing it into a table.
BPHS ch. 11 is one verse per bhava; ch. 12-23 one chapter each; ch. 24 is a 12×12 grid
where the verse is `(lord−1)×12 + house`.

**Why:** a copied summary drifts from its source and nobody notices. A derived pointer
cannot.

**Where the scan defeats it,** the exception is written down and tested rather than
smoothed over:

| exception | why |
| --- | --- |
| Virgo pointed at by hand (ch. 4 v. 13-14) | the translation describes it without ever naming it — "a Virgin", not Kanya |
| The nakshatra book's own spellings written out (MRGA, KRTTIKA, SATABISHA) | guessing by prefix found 25 of 27 and attached the other two to a page of muhurta tables that describes nothing |
| Bansal's conduct table parsed with the Moon's block found by house numbers restarting | its heading is missing from the scan entirely, and Saturn's leading "7." came out as "?" |

### 2.3 A missing citation beats a confident wrong one
Cells absent from the printing return `None`.

**Why:** a citation that resolves to the wrong verse reads as authority and says something
else. BPHS ch. 24 v. 12 (lagna lord in the 12th) and the Mercury/Ketu dasha cell are both
absent; returning a neighbouring verse would have been a confident claim about a different
placement.

### 2.4 Passages are sliced, not returned whole ·cost
Where the ingestion merged verses, the excerpt is cut to the part asked for.

**Why:** ch. 4 v. 13-14 carries Virgo, Libra, Scorpio and Sagittarius in one passage —
answering "what is my ninth house's sign like" with a paragraph about four signs is barely
an answer. Worse, ch. 24 and ch. 52-60 glue the *tail* of one verse group onto the next, so
Saturn/Jupiter resolved to a passage that opens with Rahu's sub-period. The citation was
right and the paragraph was about a different planet.

### 2.5 Rules are data, predicates are code
A yoga is YAML — a condition tree of named predicates plus its citation. No `eval`.

### 2.6 Every rule declares whether it was found
`located` means the passage was read and states the rule. `unlocated` means it is in common
use but nothing ingested says it, and the reader is told.

**Still unlocated, with the near misses recorded so the hunt is not repeated:**

- `bphs.saraswati` — the name appears once, in Muhurta Jyotisha p. 72, about when to begin
  studying a science. That is the electional use, not the natal combination.
- `bphs.daridra` — BPHS ch. 42 is the poverty chapter and every yoga in it turns on the
  lagna lord, never the 11th. Pathak p. 112 comes closest but only for the 8th house and
  only alongside the 8th lord. **Open question:** narrow the rule to Pathak's, or leave the
  wider common form unlocated.
- `remedy.debilitated_lagna_lord`, `remedy.mars_in_marriage_houses` — the affliction is in
  the library; the prescribed measures are not.

**Partial attribution is stated, not hidden.** `remedy.saturn_pressure` and
`remedy.sun_afflicted_by_node` cite measures prescribed for a graha in general, not for the
placements the rule fires on, and say so in their notes.

---

## 3. Astrological readings where the texts disagree

Each of these is in `KNOWN_VARIANTS` with fuller reasoning and a test.

### Ashtakavarga (`core/ashtakavarga.py`)
- **`vedastro`** — Venus's row from Mars. See 2.1.
- **`bphs_english_edition`** — six further cells where this English edition disagrees with
  the tables in common use.

### Shadbala (`core/shadbala.py`)
Cross-checked line by line against Charak pp. 177-187. They agree on the exaltation arc,
the seven vargas, odd and even signs, the kendra split, the decanates, the four directions,
day and night strength, the thirds of the day, the natural table, and the division of the
aspect total by four. Where they part:

- **`varsha_bala_divisor`** — this printing says divide the Ahargana by 60; Charak names
  "the year of 360 days". **360 used**, because the verse's own next step (advance the
  weekday by three per year) is arithmetic that only works for 360.
- **`chesta_motion_names`** ·cost — both give the same eight values; this translation
  attaches 7.5 to *Sama* (a graha at its usual pace) and 30 to *Manda* (a slow one).
  Charak's ordering runs the right way. **Charak's names used** — this code originally had
  the inverted version.
- **`drishti_from_the_ladder_not_the_arithmetic`** ·cost — ch. 26 states the values twice
  and contradicts itself. **The ladder used**, as a table, matching Charak exactly. The
  arithmetic reading had Jupiter wrong in four segments and returned zero for every aspect
  past 180°.
- **`paksha_bala_of_the_moon`** — Charak doubles the Moon's; BPHS does not mention it.
  **BPHS followed**, leaving her up to 60 virupas below a Charak-following implementation.
  A genuine disagreement between authors, not a bad printing.
- **`chesta_bala_method`** — BPHS gives two methods. **The eight-fold motion table used**,
  because the chesta-kendra method needs mean longitudes the ephemeris layer does not
  expose, and using it would mean inventing them.
- **`chesta_motion_thresholds`** — the eight motions are named but their boundaries are
  not. The bands are this implementation's choice, stated as such.
- **`suns_doubled_ayana_in_chesta`** — v. 18 says the Sun's Chesta "corresponds to his Ayan
  Bal" without saying which figure. **The doubled one used**, which is why the Sun is the
  one graha whose Chesta can pass 60.

**Bhava Bala departure:** the verse measures from a bhava's cusp and this project uses
whole-sign houses, which have none. Bhavas run from the lagna's own degree.

### Avasthas (`core/avastha.py`)
- **`deeptadi_precedence`** — the nine states are listed without saying which wins when two
  apply. Combustion over malefic company over the dignity ladder. **This implementation's
  choice; the verse does not say.**
- **`dipt_and_moolatrikona`** — BPHS gives Dipt to exaltation alone, Charak to exaltation
  *or* moolatrikona. **BPHS followed.**
- **`baladi_by_drekkana`** — some reckon it from the drekkana. **The six-degree reading
  used**, per ch. 45 v. 3.
- **Two sets not implemented:** Lajjitadi is stated too loosely, and Sayanadi needs a
  formula whose scan is unreadable. Guessing at either would produce a confident state with
  nothing behind it.

### Chara karakas (`core/karaka.py`)
- **`seven_or_eight`** — v. 1-2 says seven, then reports that some include Rahu. **Eight
  used**, because v. 3-8 gives Rahu its own rule and v. 13-17 names eight roles, which
  seven cannot fill.
- **`matru_and_putra`** — kept separate, as the verse's own list does.

### Elsewhere
- **Kala Sarpa** — the source defines the hemming by degree; this implements it by sign.
  Stated in the rule's note.
- **Sakata** ·cost — Charak has Jupiter in the 6/8/12 **from the Moon**, not the Moon from
  Jupiter, and excludes kendras. Both were wrong here, and the first fix wrote the note
  while the condition went unchanged.
- **Vasumathi** ·cost — "all benefics in upachaya", not "only benefics in upachaya". The
  converse holds far more often.
- **Bhakoot** ·cost — the afflicted pairs are {6,8} and {5,9}, not {6,9} and {5,10}.

---

## 4. Computation

### 4.1 `swe.get_ayanamsa_ex_ut`, not `get_ayanamsa_ut` ·cost
The plain call omits the precession correction and reads ~14″ high, silently contradicting
the longitudes it sits beside.

### 4.2 One module touches swisseph
`core/ephemeris.py`. Everything else is arithmetic over a computed `Chart`.

**Consequence:** declination for Ayana Bala is derived from the sidereal longitude and the
chart's own ayanamsa rather than fetched — three lines, and it keeps the boundary.

### 4.3 The weekday is counted at the birthplace ·cost
Julian days are counted in UT. Delhi's 05:24 sunrise is 23:54 UT the day before, so a
weekday read straight off the julian day put every Indian sunrise on the previous day —
Friday 15 June 1990 reported as Thursday. Fixed at the shared root, `panchanga.weekday_index`.

### 4.4 Dig Bala is measured from the angles, not the cusps
Under whole-sign houses a "cusp" is a sign boundary; reading Dig Bala off one would make
the same birth yield different strengths for no astronomical reason.

### 4.5 Whole-sign houses, Lahiri, mean nodes — stated, never assumed
Every chart carries the settings used to build it. A set of longitudes without its ayanamsa
is meaningless.

---

## 5. The model

### 5.1 It is given no chart data; it must call tools
**Why:** it cannot state a position that was never computed. This matters more with a local
8B than it would with a frontier model.

### 5.2 Grounding by instruction is not grounding ·cost
Told to use only the supplied facts, the model wrote "Mars in Aries (its own sign)" about a
Mars in Scorpio — it had read the *house's* sign and attached it to the house's ruler.
Fluent, confident, false. `interpret/factcheck.py` now verifies placement claims against
the chart deterministically; a section that fails is stored as failed.

### 5.3 Enforce, do not instruct
The same lesson generalised. The factchecker, the vocabulary rule, the citation-resolution
test and the passage-size gates all exist because telling the model — or a future
maintainer — proved insufficient.

### 5.4 The model is pushed once, not argued with ·cost
qwen3 sometimes answers "the chart isn't available in the tools provided" having called
nothing. One nudge, then its answer is accepted with the warning shown.

### 5.5 Thinking off by default ·cost
Measured on an M5: the same question with the same tools took 26.4s with thinking and 1.5s
without, producing an identical tool call — 1,511 characters of reasoning for a
196-character answer. `_Visible` was already discarding all of it before it reached the
screen. `ASTRO_QA_THINK=1` restores it.

**The lesson:** the filter hid the symptom. The question was why the model was doing it at
all.

### 5.6 Conversations carry questions and answers, not tool traffic
**Why:** the traffic would dwarf the context, and the model is meant to look a fact up
again rather than trust its own earlier summary of it.

### 5.7 Follow-ups are judged differently
A first answer with no lookups is free recall. A follow-up resting on what was already
fetched is not, so the "should not be trusted" wording is wrong for it, and the tool-use
nudge does not fire.

---

## 6. Interface

### 6.1 Plain first, term in brackets
"A nineteen-year chapter ruled by Saturn (mahadasha)". Enforced by a test that walks the
rendered strings of every view and fails on bare jargon outside the technical view.

**Why:** glossing on hover is invisible when scanning and absent on touch.

### 6.2 Colour answers exactly one question
Is this helping or costing? `--good`, `--bad`, `--flat`, defined once and used nowhere
else.

### 6.3 Scores are shown, not written ·cost
A diverging meter from a centre. A column of "+2 / 0 / −3" must be read row by row; a
column of meters has a shape.

**Two corrections:** the track is `--line`, not a wash, because a wash was invisible on the
panel and a small score looked like a stray dot. And a *reason* weighted +1 is unambiguously
helping, even though a *domain* at +1 is genuinely mixed — separate `tone` and `signTone`.

### 6.4 Width is time
The chapter band. A list makes a two-month stretch and a six-year one look the same size,
and "what changes next" is a question about how soon.

### 6.5 The house reading is stepped, and steps unlock ·cost
Five steps: what it is, who runs it, who is in it, how it is doing, what to do. One step
ahead of the furthest reached stays open.

**Why:** it had reached 9,348px and 646 words on screen. Now 1,070px and about 175.

**Why gated rather than merely paginated:** "what to do" means nothing before "how is it
doing", and handing over remedies first is what made it read like a shop.

### 6.6 Guidance is shown for every planet a house involves ·cost
Gating it on trouble left nine houses of twelve showing nothing at all — no conduct, no
mantra. The gate now decides emphasis, marking what to attend to first.

### 6.7 The whole cell opens the house; glyphs are labels ·cost
The planet card was removed rather than fought for the same pixels — everything it said is
in the house reading, with more behind it. See 7.1.

### 6.8 Conduct stays keyed to the birth chart
Lal Kitab's measures are about where a planet actually stands. Keying them to a navamsa
house would prescribe for a house the native does not have. The label says so.

### 6.9 Divisional charts leave out what does not apply to them
Ashtakavarga and bhava bala are defined on the birth chart. Computing them from a varga
would produce a number with nothing behind it. Dignity, however, **is** read from the
division's own signs — reporting the birth chart's dignity beside a divisional sign
described a different planet.

---

## 7. Verification

### 7.1 Click with the protocol, never with `dispatchEvent` ·cost
**The bug that set this rule:** a 14px transparent stroke on each planet glyph, added to
make planets tappable, sat on top of the house cell and called `stopPropagation`. Clicking
any house containing a planet selected the planet; the house never opened. My check
dispatched a synthetic event straight onto the element, which bypasses hit-testing
entirely. It proved the handler was wired and nothing about whether a mouse could reach it.
The user found it.

Harnesses in `tools/uicheck/`.

### 7.2 Read the screenshot ·cost
`_cite()` returns a `text` of its own — the whole page — and spreading it after the cell's
own text replaced every conduct block with all of Bansal p. 225. Every unit test passed;
the table was fine. The defect was in the payload assembly between the table and the
screen, and only looking at the render found it.

### 7.3 Assert the fix, not the note ·cost
An earlier Sakata correction wrote the note explaining the fix while the condition went
unchanged — the edit was in a script that died on a `SyntaxError` — and the fixtures passed
under both readings. Tests now assert the corrected behaviour disagrees with the reading it
replaced.

### 7.4 Every rule ships a chart that must fire it and one that must not
A rule that fires on everything is worse than no rule: it makes a report look substantive
while saying nothing.

### 7.5 Check that a test is not vacuous
`test_a_well_placed_house_is_not_handed_a_remedy` asserted the clean set is non-empty first,
"so this proves nothing" otherwise. Several tests carry that guard.

---

## 8. Ingestion

### 8.1 `pdftotext -layout`, not an OCR pipeline ·cost
Marker stalled repeatedly on a PDF that already had a text layer; `pdftotext` did it in
0.27s. OCR sidecars are used only where there is genuinely no text layer.

### 8.2 `-layout` is dropped for two-column pages ·cost
It interleaves the columns. Multi-column pages are detected and read in plain order.

### 8.3 Passages are gated on size, and short blocks merge rather than drop ·cost
Three separate failures: a verse parser that captured 80 passages from 160k characters of
Raman (capture-share gate), an 80,189-character "verse" in Siddhanta Sara (max-size gate),
and a 105-character definition of Vasumathi binned by a minimum-length rule (now merged
into its neighbour).

### 8.4 Page citations for unversified works ·cost
`search.py` hard-coded the verse form, so every passage from a book that numbers nothing
was cited as "ch. 0, v. " — a reference that looks precise and points nowhere. Most of the
library is unversified, so that was most of it.

### 8.5 Keyword search, not embeddings
Finding the verse that defines a named yoga is a lookup for a rare word — "Kemadruma",
"Ruchaka" — and exact matching beats semantic similarity for that, with no index to build
and no model to load.

---

## 9. Open

- **Model:** pull `qwen2.5:14b-instruct` and measure; then rebuild Ask as retrieval-first
  so the model phrases rather than hunts. See `docs/session-log.md`.
- **`bphs.daridra`:** narrow to Pathak's statement, or leave the wider form unlocated.
- **Shadbala fixtures** could be widened with VedAstro's 15,000-birth dataset.
- **Untapped library:** Jaimini Sutras (chara dasha), Muhurta Jyotisha (electional), Yogini
  Dasha, Raman's *Manual*.
- **The project is not in git.** This file and `session-log.md` are the only record of why
  the code looks the way it does.
