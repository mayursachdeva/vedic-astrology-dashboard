# Session log — 10/11 August 2026

Where the project got to, what was decided and why, and what to pick up next.

State at the end: **625 tests pass**. All ten views render clean at 1250px and 760px with
no console errors. All twelve houses open by real pointer click in the overview chart and
in both D1 and D9.

---

## What was built

### Streaming answers

`qa.ask_stream()` replaced the blocking tool loop; `ask()` is now a thin consumer of it,
so there is one code path. New SSE endpoint `POST /api/profiles/{id}/ask/stream`.

The lookups stream as well as the tokens, because the lookups are most of the wait. What
the reader sees is "Reading the house of work and standing and its ruler", not a tool
name or a julian day.

### Shadbala — BPHS ch. 27

`core/shadbala.py`. All six sources in virupas against each graha's own minimum: Sthana
(five parts), Dig, Kala (eight parts, including Ahargana-derived year and month lords and
the Chaldean hora), Chesta, Naisargika, Drik (over the ch. 26 drishti values), plus the
yuddha adjustment. Also `bhava_bala()` for the twelve houses (v. 26-31).

Cross-checked line by line against Charak pp. 177-187, who sets out the same system
independently. **Four disagreements, all recorded in `KNOWN_VARIANTS` and each guarded by
a test** — see `docs/references.md` for the detail. Three were errors on this side:

- the eight motions were mapped so a graha at its usual pace scored 7.5 and a crawling
  one 30, which inverts the measure
- Jupiter's drishti curve was wrong in four segments, and every planet's aspect past 180°
  returned zero
- the year-lord divisor

### House readings

The largest piece. `corpus/index.py` derives pointers into the library rather than
paraphrasing it; `interpret/houses.py` composes them with the arithmetic.

Clicking any house — in the overview chart, or in D1 or D9 — opens: what the house is
read for (ch. 11), its sign (ch. 4, sliced to the sign asked for), its ruler and the verse
for that exact placement (ch. 24, a 12×12 grid where the verse is arithmetic), each
occupant with dignity, shadbala, nakshatra, avasthas and the classical verses naming it,
the house's ashtakavarga and bhava bala, and what the texts prescribe.

**Nothing in this module is written by it.** Every claim is a passage returned whole with
its chapter and verse, openable in place. The module contributes arithmetic and joining
sentences. That is the reason a house reading cannot say something the library does not.

### Three layers from works nothing was reading

- **Avasthas** (ch. 45 + the *Avasthas of the Planets* monograph) — baladi, jagradadi and
  deeptadi. Answers what dignity and shadbala do not: how much of what a planet promises
  actually arrives.
- **Chara karakas** (ch. 32) — ranks the grahas by degree travelled and assigns eight
  roles. Rahu counted backwards from 30.
- **Dasha effect verses** (ch. 52-60) — 80 of 81 pairs resolve, so the running period
  carries what BPHS says about that exact pair.

### Conduct, mantras and guidance

Bansal pp. 224-229 carry a full Lal Kitab planet-by-house table of conduct — the only
material in the library that answers "what should I change" with something actionable.
**89 of 108 cells parse**; the gaps are the book's own.

Guidance is now shown for **every** planet a house involves, not only the struggling ones.
The earlier gate left nine houses of twelve showing nothing at all; it now decides
emphasis, marking what to attend to first.

### The interface

Rebuilt around structure. Design tokens where colour answers exactly one question
(helping or costing), and three primitives in `components/Panel.jsx`: `Panel` in three
tiers, `Meter` diverging from a centre, `Verdict` as a coloured chip.

Home, Area, Timeline and Technical were restructured into zones with rails; `Band` is
shared between the overview and the timeline.

Then the house reading was made a **five-step reader** — what it is, who runs it, who is
in it, how it is doing, what to do — with each step unlocking as the one before is read.
Measured: **9,348px → 1,070px**, 646 words on screen → about 175.

The gate is not decoration. "What to do" means nothing before "how is it doing", and
handing over remedies first is what made it read like a shop.

### Ask became a conversation

It answered one question and stopped, so when the model ended by offering to look at
something else there was no way to say yes. Turns now stay on screen and each question
carries the exchange. Two gates were softened for follow-ups: the "not to be trusted"
warning, and the nudge that pushes the model to use its tools.

---

## Bugs found, and how

Worth keeping because the *method* mattered more than the fix.

| bug | how it surfaced |
| --- | --- |
| Planet glyph swallowed every house click (14px transparent stroke on top of the cell, calling `stopPropagation`) | **The user.** My check dispatched an event onto the element, bypassing hit-testing. See `tools/uicheck/README.md`. |
| `panchanga.vara` computed the weekday from a UT julian day, so Delhi's 05:24 sunrise landed on the previous day — Friday 15 June 1990 read as Thursday | Writing Vara Bala; no existing test pinned a weekday |
| `_cite()` returns a `text` of its own — the whole page — and spreading it after the cell's text replaced every conduct block with all of Bansal p. 225 | **Reading a screenshot.** The table-level tests were fine; the defect was in the payload assembly between them and the screen. |
| Merged verses: ch. 24 and ch. 52-60 passages carry the *next* graha's header at their end, so a correct citation showed the wrong planet's paragraph | Printing what the citations actually resolved to |
| D9 described the lord's house from one chart and its sign from the other; dignity was the birth chart's beside a divisional sign | Adding depth to D9 |
| A failed Ask question vanished — the box clears on send | Ollama wedging mid-test |
| qwen3 spent 1,511 characters of reasoning per reply, on every round, which `_Visible` then discarded | Measuring after the user said the local model had hit its limit |

---

## Decisions worth not relitigating

Summarised here; the full log with reasoning and what would overturn each one is in
[`decisions.md`](decisions.md).

- **Primary text beats secondary implementation.** A second source tells you *where* to
  look, not *who is right*. Divergences are recorded in `KNOWN_VARIANTS`, not resolved
  silently.
- **Enforce rather than instruct.** The factchecker, the vocabulary rule, the
  citation-resolution test and the passage-size gates all exist because telling the model
  or a future maintainer proved insufficient.
- **Derive pointers, do not copy content.** `corpus/index.py` computes which verse
  applies, so the library and the code cannot drift apart. Where the scan defeats it —
  Virgo is never named, the Moon's conduct heading is missing — the exception is written
  down and tested.
- **A missing citation beats a confident wrong one.** ch. 24 v. 12 and the Mercury/Ketu
  dasha cell return nothing rather than a neighbour.
- **Local only.** Birth data does not leave the machine. This is why the corpus, the
  gazetteer and the model are all local, and it is the constraint any model decision has
  to answer to.

---

## Pick up here

### 1. The model — decided in principle, not yet done

Ollama was **not** the limit. qwen3:8b was running with thinking on: 21.6s versus 1.7s
for an identical tool call. Now off by default (`ASTRO_QA_THINK=1` restores it), first
token at ~2.4s.

Recommended next, in order:

1. **Move up to a 14B.** `ollama pull qwen2.5:14b-instruct`, then
   `ASTRO_QA_MODEL=qwen2.5:14b-instruct`. About 9 GB; the machine has 24 GB and is using
   5.2. Biggest quality gain available, one env var, no code change. **Not yet measured.**
2. **Rebuild Ask as retrieval-first.** Today the model must decide what to look up and
   hunt across 3-5 rounds, which is the part an 8B is worst at. The written reading
   already avoids this — `sections.py` hands over facts pre-assembled and takes one round.
   Ask should work the same way: route the question to the computed material, hand it over
   whole, let the model only phrase it. Cuts answers to a few seconds and removes the
   whole "looked up the wrong thing" class of failure.
3. **Do not move to a hosted model** for the default path. If ever wanted, the shape is an
   explicit opt-in per question with the privacy cost stated at the point of use.

### 2. Smaller open threads

- **Four citations still unlocated**: `bphs.saraswati`, `bphs.daridra`,
  `remedy.debilitated_lagna_lord`, `remedy.mars_in_marriage_houses`. Each carries a note
  naming the near misses so the hunt is not repeated. Daridra is the interesting one — the
  coded rule (11th lord in 6/8/12) is wider than anything the library states, so it is
  either narrowed to Pathak p. 112 or left as is.
- **Mercury/Ketu antardasha** lost its header in the scan — 80 of 81 pairs resolve.
- **19 of 108 conduct cells** absent, mostly the book's own gaps.
- **Lajjitadi and Sayanadi avasthas** not implemented: the first is stated loosely, the
  second needs a formula whose scan is unreadable.
- **Shadbala fixtures** could be widened using VedAstro's 15,000-birth dataset
  (`docs/references.md`).

### 3. Library still untapped

Jaimini Sutras (chara dasha, 692 passages), Muhurta Jyotisha (electional — "when to start
something", 611), Prediction through Yogini Dasha (322), Raman's *Manual* (551).

---

## Running it

```
uv run uvicorn astro.api.main:app --host 127.0.0.1 --port 8000
cd web && npx vite --port 5173
uv run pytest -q                     # 625 tests
```

Browser checks are in `tools/uicheck/` — they are not part of pytest because they need
Chrome and both servers. Run them whenever the interface changes.

**This project is not in git.** Everything above is the only record of why the code looks
the way it does.
