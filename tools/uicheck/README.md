# Browser checks

The Python suite covers the computation and the payloads. It cannot see whether a thing
on the screen can actually be clicked, and that gap has cost real bugs twice — a planet
glyph silently swallowing every house click, and a citation block quietly showing the
whole page instead of its own sentence. These scripts close it.

They drive headless Chrome over the DevTools protocol. They are not part of `pytest`:
they need Chrome and both servers running, so they are run by hand when the interface
changes.

## Running

Both servers first:

```
uv run uvicorn astro.api.main:app --host 127.0.0.1 --port 8000
cd web && npx vite --port 5173
```

Then any of:

| script | what it answers |
| --- | --- |
| `check.py` | Does every view render, at 1250px and 760px, with no console errors and no horizontal overflow? |
| `houseclicks.py` | Does a **real pointer click** open all twelve houses, in the overview chart and in both D1 and D9? |
| `steptest.py` | Does the house reader step forward, does the lock hold when you try to skip, does going back re-lock, does Done close it? |
| `threadtest.py` | Do two turns of Ask stay on screen, and does the follow-up carry the exchange with it? |
| `measure.py` | How tall is the page and how many words are on it, per step? |
| `shot.py <out.png> [view]` | Screenshot a named view. |
| `shot3.py <out.png> [view] [js] [wait]` | Screenshot, running some JS first, clipped to `window.__CLIP`. |

`threadtest.py` and `houseclicks.py` take minutes — the first waits on the local model.

## The one rule worth keeping

**Click with `Input.dispatchMouseEvent`, never with `element.dispatchEvent`.**

A synthetic event dispatched straight onto an element bypasses hit-testing entirely. It
proves the handler is wired and proves nothing about whether a mouse can reach it. That
is exactly how the planet-glyph bug shipped: the handler worked, the screenshot looked
right, and no user could click a house that had a planet in it.

`CHROME` at the top of each script is a hard-coded path to a Puppeteer-installed build;
change it if yours lives elsewhere.
