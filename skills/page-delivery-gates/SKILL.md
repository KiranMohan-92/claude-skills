---
name: page-delivery-gates
description: Final gates for a web page before hand-off (landing pages, explainers, review pages, dashboards, three.js or WebGL scenes, published artifacts). Use before saying a page is done, before deploying, publishing or sending its link, and after any change to its layout, animation or scene. Loads the page at desktop and phone width three ways (normal, reduced motion, WebGL refused) and fails on console or uncaught errors, failed requests, sideways overflow at any scroll stop, a canvas that never shows a picture, motion that ignores reduced motion, text that disappears when motion or WebGL is off, and CDN scripts without an exact version. Then writes contact sheets for a visual review. Not for choosing a design, and not for pages you are only reading.
license: MIT
compatibility: Python 3.10+ with the playwright and pillow packages (uv run installs them from the script's header) and Playwright's Chromium (python -m playwright install chromium), or an installed Chrome via --channel chrome.
metadata:
  version: 0.11.1
---

# Page delivery gates

Across four months of page work (a portfolio site, 3D review pages, a home-control UI) the same hand-off checks were written by hand in session after session: a sideways-overflow probe 144 times in 14 sessions, a reduced-motion check 81 times in 16, a no-WebGL check 56 times in 8. Written by hand, they failed in both directions.

**Defects they missed**
- A phone-width page was 394 px wide in a 390 px view, but only while stamps animated in halfway down. The check at the top of the page saw nothing.
- A scene kept moving with reduced motion on.
- A 3D page was handed over with its reduced-motion and no-WebGL views never rendered, on the argument that "the text is plain HTML, so it should show".

**Defects they invented**
- A pixel probe screenshotted the canvas element, read black in headless Chromium, and failed a working scene.
- A screenshot showed a page-coloured square punched through the scene. It was the headless browser's software compositing, not the page.
- A screenshot caught the loader, and the review graded a loading screen.

So: gate what a viewer gets (the composited page, at phone width, with motion off, with WebGL off), and treat a view nobody rendered as a view that failed.

## 1. Technical gate on the page as served
```bash
uv run scripts/gate_page.py <page.html | https://url> [--out DIR] [--viewport WxH ...] [--settle-ms 2000] [--ignore TEXT ...] [--channel chrome]
```
(`scripts/` is in this skill's folder. Without uv: `pip install playwright pillow`, `python -m playwright install chromium`, then `python scripts/gate_page.py …`.)

It loads the page at 1440×900 and 390×844, three times each, and scrolls through every load in steps of less than one screen, asking the page for its height again at every step so that sections which load as you arrive are scrolled too. At what looks like the bottom it waits a second for such a load to land; a page that grows after that fails as ungated. It prints one line per load, then each failure, then `PASS` or `FAIL`, and exits 0 (PASS), 1 (FAIL) or 2 (usage, no browser to run in, or the page could not be loaded or checked). A page of ten screens takes about a minute, and the time grows with the page's length. A page still going after 200 stops (about 160 screens) fails as ungated; it is never cut short and passed. An exit of 2 means the page is ungated: say so, don't report it as passed.

A local file that is only a page body (no doctype, written for a host that wraps it) is served inside a minimal UTF-8 document, and the output says so. Served bare, the browser guesses the encoding and lays the page out in quirks mode, which is a page no viewer gets.

| Load | Fails when | Why it is checked this way |
|---|---|---|
| all | the page is wider than the view at any scroll stop | Sampled three times per stop, because an element can widen the page only while it animates in. Measured against `clientWidth`, which leaves the scrollbar out. The failure names the widest element. |
| normal, reduced motion | a console error, an uncaught error, an HTTP status of 400 or more, or a failed request | A missing asset and a script that died both leave a page that "looks fine" on the author's machine. |
| normal, reduced motion | any canvas covering 15 % or more of the view shows no picture at any of five positions | Judged from a screenshot of the composited page with everything hidden except that one canvas, so a drawn chart can't vouch for a dead scene. Reading pixels back from a WebGL canvas returns an empty buffer in headless Chromium. Flat at only some positions is printed as a note, since a scene may fade out on purpose. |
| reduced motion | more than 0.2 % of the view changes in 0.6 s while nobody scrolls | Two stills, compared. A fade started by the scroll gets one more second before the verdict. |
| reduced motion, no WebGL | a text block that was visible in the normal load is not visible here | "Visible" means in the view, not `display: none`, not hidden, not at opacity 0, and not cut away by a wrapper that clips its overflow (a reveal left at `max-height: 0`). Digits are masked, so a counter caught mid-animation matches its final value. A missing block gets a second, centred look before it counts. |
| no WebGL | an uncaught error, a canvas handed to a worker, or a worker drawing with WebGL | WebGL contexts are refused on page canvases and on `OffscreenCanvas`. Libraries log an error when that happens, so console errors don't count in this load; a script that dies does. Nothing can be refused inside a worker, so a canvas passed to one, or a worker caught drawing, fails the load as unverified. |
| first normal load | a script comes from an npm CDN without an exact `x.y.z` version | A page that loads `latest` or a range can change, or break, after it was reviewed, with no edit by anyone. In a combined URL every package needs its own version. |

- **Text that is meant to be absent** with motion or WebGL off (a "Scroll to begin" hint, a "Replay" button): pass `--ignore "Replay"`. Don't use it to silence real copy.
- **A page that needs longer to settle** (a loader, a slow scene): raise `--settle-ms`.
- **If the gate's own browser can't give the page WebGL**, the normal load fails as unverified instead of passing a scene nobody saw. Rerun with `--channel chrome`.
- **After deploying or publishing**, run it once more on the public URL when there is one. The local file is not the published page: paths, headers and caching differ.
- **If the page changed after the gate ran**, the gate has not run.

## 2. Build the page so the gates pass
Each rule is the cheap way to satisfy a check above.
- **Put all the copy in HTML and treat the scene as a layer behind it.** Then the reduced-motion and no-WebGL views need no second copy of the content: hide the canvas and the page still reads. Text drawn only inside the canvas is gone in both views.
- **Reveals fail open.** Content is visible by default, or made visible in a `prefers-reduced-motion` rule, and the script only adds the animation. A reveal that starts at opacity 0 and waits for a script leaves blank panels whenever that script doesn't run.
- **Write final values in the HTML** and animate up to them. A counter that starts at 0 in the markup shows 0 when the script fails.
- **Guard the context.** Create the renderer inside a check or a `try`; on failure remove the canvas and let the rest of the script run. An unguarded `getContext` result kills everything after it, including the code that reveals the copy.
- **With reduced motion on, stop the ambient loop** and render one still frame per scroll position. The gate checks only that the page holds still while nobody scrolls; whether scrolling may still move the camera is a design decision.
- **Clip decoration on its own wrapper.** `overflow-x: hidden` on `body` alone does not contain a too-wide child: the page still measures wider and still scrolls sideways. `overflow: clip` on the element's container does.
- **Pin every CDN script to an exact version.**

## 3. Visual review: read the sheets
The gate writes one contact sheet per load to `--out` (`sheet-<WxH>-<load>.png`, five scroll positions each). Read at least both normal sheets and the phone reduced-motion and no-WebGL sheets, and write one line per item:
- **Loaded:** no shot shows a loader or a half-finished transition. If one does, raise `--settle-ms` and rerun; don't review a loading screen.
- **Scene against copy:** no 3D object sits on top of a headline or body text, at phone width especially. Narrow views move the scene under the text.
- **Text:** legible over the scene at every stop, nothing cut off at an edge, no line running out of a label drawn on a canvas.
- **Exposure:** the background is the colour intended, not lifted to grey, and glow doesn't wash out the frame. In a linear-light pipeline, colours written as display values come out lighter, and a bloom threshold below the background level makes the background itself bloom.
- **Fallbacks:** the reduced-motion and no-WebGL sheets look deliberate, not like a broken page with a hole where the scene was.

The gate shows that the page works. Only the sheets show whether it looks right, and neither shows whether it is what was asked for.

## 4. Hand-off
The final message gives: where the page is, the gate result per load, which sheets were read and what they showed, and what was not verified (the published URL, a real phone, a second GPU vendor).

## Gotchas
- A scripted `scrollTo` barely moves a page that sets `scroll-behavior: smooth`. The gate scrolls with `behavior: 'instant'`; do the same in any probe of your own.
- Playwright's default headless shell composites in software, and a screenshot can then show a page-coloured hole in a canvas under an animated element. The gate launches full Chromium for that reason, and runs the software renderer as the GPU when the machine has none. A hand-written `chromium.launch()` probe gets the shell.
- The `browser:` line names the GPU the scene ran on. A shader can produce NaN (a black frame) on one vendor and not on another, so a pass on one says nothing about the other.
- A still taken right after jumping to a scroll position shows a scroll-eased camera in mid-flight from wherever it was. The gate cuts its sheets from stills taken on the way down, one short step at a time. A probe of your own that jumps straight to a position should wait for the scene to arrive.
- A browser tab that is hidden or in the background throttles animation to a few frames a second, and a screenshot taken there catches mid-transition states. Take evidence with the gate, not from a background tab.
- Text that a script cycles through (a typewriter line) is compared as it happened to be shown. If the fallback shows only the first phrase, the others are reported missing. That is a real difference; either show them all or pass `--ignore`.
- Comparing what is visible across loads only works if every part of the page was on screen in each. A probe that samples a long page at a fixed number of positions reports text as missing that it never scrolled to.
- The gate scrolls the window. A page that scrolls inside an element (a full-height container with its own scrollbar) is checked only where it loads, so its lower sections are not gated.
- A local file is served over http from its own folder, because `file://` blocks module imports and fetch. A page that reaches into a parent folder (`../shared.js`) won't load that way: serve it yourself and pass the URL.
- A gate inside a filtered pipeline (`gate_page.py … | tail -3 && deploy`) tests `tail`'s exit status, not the gate's. Run the gate on its own and test its exit code.
